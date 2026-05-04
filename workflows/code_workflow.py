import os
import re
import pathlib
import subprocess
from typing import Tuple, Annotated, TypedDict, Optional, Literal
from pydantic import BaseModel, Field, ConfigDict

from langchain_core.prompts import PromptTemplate
from langchain_core.messages import SystemMessage, HumanMessage, BaseMessage, AIMessage
from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import START, END, StateGraph
from langgraph.prebuilt import create_react_agent

from core.state import ChatState

# ==========================================
# 1. DYNAMIC FOLDER SETUP
# ==========================================
# Default fallback, but we will dynamically update this per-request
PROJECT_ROOT = pathlib.Path.cwd() / "generated_project"

def set_dynamic_project_root(prompt: str) -> pathlib.Path:
    """Creates a safe folder name from the prompt to isolate projects."""
    global PROJECT_ROOT
    # Clean the prompt to create a folder name (e.g., "create a calculator" -> "create_a_calculato")
    safe_name = re.sub(r'[^a-zA-Z0-9]', '_', prompt.strip().lower())[:20].strip('_')
    if not safe_name:
        safe_name = "default_project"
        
    PROJECT_ROOT = pathlib.Path.cwd() / "generated_projects" / safe_name
    PROJECT_ROOT.mkdir(parents=True, exist_ok=True)
    return PROJECT_ROOT

def safe_path_for_project(path: str) -> pathlib.Path:
    p = (PROJECT_ROOT / path).resolve()
    if PROJECT_ROOT.resolve() not in p.parents and PROJECT_ROOT.resolve() != p.parent and PROJECT_ROOT.resolve() != p:
        raise ValueError("Attempt to write outside project root")
    return p

# ==========================================
# 2. YOUR ORIGINAL TOOLS
# ==========================================
@tool
def write_file(path: str, content: str) -> str:
    """Writes content to a file at the specified path within the project root."""
    p = safe_path_for_project(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(content)
    return f"WROTE:{p}"

@tool
def read_file(path: str) -> str:
    """Reads content from a file at the specified path within the project root."""
    p = safe_path_for_project(path)
    if not p.exists():
        return ""
    with open(p, "r", encoding="utf-8") as f:
        return f.read()

@tool
def get_current_directory() -> str:
    """Returns the current working directory."""
    return str(PROJECT_ROOT)

@tool
def list_files(directory: str = ".") -> str:
    """Lists all files in the specified directory within the project root."""
    p = safe_path_for_project(directory)
    if not p.is_dir():
        return f"ERROR: {p} is not a directory"
    files = [str(f.relative_to(PROJECT_ROOT)) for f in p.glob("**/*") if f.is_file()]
    return "\n".join(files) if files else "No files found."

@tool
def run_cmd(cmd: str, cwd: str = None, timeout: int = 30) -> Tuple[int, str, str]:
    """Runs a shell command in the specified directory and returns the result."""
    cwd_dir = safe_path_for_project(cwd) if cwd else PROJECT_ROOT
    res = subprocess.run(cmd, shell=True, cwd=str(cwd_dir), capture_output=True, text=True, timeout=timeout)
    return res.returncode, res.stdout, res.stderr

# ==========================================
# 3. YOUR ORIGINAL PROMPTS & MODELS
# ==========================================

model = ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=os.getenv("GOOGLE_API_KEY_CODE_AGENT"))

def planner_prompt(user_prompt: str) -> str:
    return f"""You are the PLANNER agent. Convert the user prompt into a COMPLETE engineering project plan.
User request:
{user_prompt}"""

def architect_prompt(plan: str) -> str:
    return f"""You are the ARCHITECT agent. Given this project plan, break it down into explicit engineering tasks.
RULES:
- For each FILE in the plan, create one or more IMPLEMENTATION TASKS.
- In each task description:
    * Specify exactly what to implement.
    * Name the variables, functions, classes, and components to be defined.
    * Mention how this task depends on or will be used by previous tasks.
    * Include integration details: imports, expected function signatures, data flow.
- Order tasks so that dependencies are implemented first.
- Each step must be SELF-CONTAINED but also carry FORWARD the relevant context from earlier tasks.
Project Plan:
{plan}"""

def coder_system_prompt() -> str:
    return """You are the CODER agent.
You are implementing a specific engineering task.
You have access to tools to read and write files.
Always:
- Review all existing files to maintain compatibility.
- Implement the FULL file content, integrating with other modules.
- Maintain consistent naming of variables, functions, and imports.
- When a module is imported from another file, ensure it exists and is implemented as described."""

# ==========================================
# 4. YOUR ORIGINAL PYDANTIC MODELS
# ==========================================
class File(BaseModel):
    path: str = Field(description="The path to the file to be created or modified")
    purpose: str = Field(description="The purpose of the file")

class Plan(BaseModel):
    name: str = Field(description="The name of app to be built")
    description: str = Field(description="A oneline description of the app to be built")
    techstack: str = Field(description="The tech stack to be used for the app")
    features: list[str] = Field(description="A list of features that the app should have")
    files: list[File] = Field(description="A list of files to be created, each with a 'path' and 'purpose'")

class ImplementationTask(BaseModel):
    filepath: str = Field(description="The path to the file to be modified")
    task_description: str = Field(description="A detailed description of the task to be performed on the file")

class TaskPlan(BaseModel):
    implementation_steps: list[ImplementationTask] = Field(description="A list of steps to be taken to implement the task")
    model_config = ConfigDict(extra="allow")

class CoderState(BaseModel):
    task_plan: TaskPlan = Field(description="The plan for the task to be implemented")
    current_step_idx: int = Field(0, description="The index of the current step in the implementation steps")
    current_file_content: Optional[str] = Field(None, description="The content of the file currently being edited")
    status: Literal["Done", "Incompleted"]

class Datacontainer(TypedDict, total=False):
    user_prompt: str
    plan: Plan
    task_plan: TaskPlan
    code: str
    coderstate: CoderState

# ==========================================
# 5. YOUR ORIGINAL SUB-GRAPH NODES
# ==========================================
def planner(state: Datacontainer) -> Datacontainer:
    user_prompt = state["user_prompt"]
    plan_structure_output = model.with_structured_output(Plan)
    result = plan_structure_output.invoke(planner_prompt(user_prompt))
    return {"plan": result}

def artitect(state: Datacontainer) -> Datacontainer:
    plan: Plan = state["plan"]
    plan_text = plan.model_dump_json(indent=2)
    taskplan_structure_output = model.with_structured_output(TaskPlan)
    result = taskplan_structure_output.invoke(architect_prompt(plan_text))
    result.plan = plan
    if result is None:
        raise ValueError("Architect did not return a valid response")
    return {"task_plan": result}

def coder(state: Datacontainer) -> Datacontainer:
    coder_state: CoderState = state.get("coderstate")
    if coder_state is None:
        coder_state = CoderState(task_plan=state["task_plan"], current_step_idx=0, status="Incompleted")

    steps = coder_state.task_plan.implementation_steps
    if coder_state.current_step_idx >= len(steps):
        coder_state.status = "Done"
        return {"coderstate": coder_state}

    current_task = steps[coder_state.current_step_idx]
    system_prompt = coder_system_prompt()
    coder_tools = [read_file, write_file, list_files, get_current_directory]
    
    # Run the read tool directly
    existing_content = read_file.invoke({"path": current_task.filepath})
    
    user_prompt = (
        f"Task: {current_task.task_description}\n"
        f"File: {current_task.filepath}\n"
        f"Existing content:\n{existing_content}\n"
        "Use write_file(path, content) to save your changes."
    )
    
    agent = create_react_agent(model, coder_tools)
    agent.invoke({"messages": [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]})
    
    coder_state.current_step_idx += 1
    return {"coderstate": coder_state}

def route(state: Datacontainer) -> Literal["coder", END]:
    if state["coderstate"].status != "Done":
        return "coder"  
    else:
        return END

# Build the internal sub-graph
code_graph = StateGraph(Datacontainer)
code_graph.add_node("planner", planner)
code_graph.add_node("artitect", artitect)
code_graph.add_node("coder", coder)
code_graph.add_edge(START, "planner")
code_graph.add_edge("planner", "artitect")
code_graph.add_edge("artitect", "coder")
code_graph.add_conditional_edges("coder", route)
# code_graph.add_edge("coder", END)
code_workflow = code_graph.compile()
