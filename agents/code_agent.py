
# agents/code_agent.py
from langchain_core.messages import AIMessage
from core.state import ChatState

# Import the compiled graph and the dynamic path function from the workflows folder
from workflows.code_workflow import code_workflow, set_dynamic_project_root

def run_code_agent(state: ChatState):
    """
    Wrapper function called by core/workflow.py.
    Extracts the prompt, sets the folder, runs the code_workflow, and returns UI text.
    """
    print("--- 💻 EXECUTING CODE AGENT ---")
    
    # 1. Get the user's prompt
    user_prompt = state["messages"][-1].content
    
    # 2. Set dynamic folder name based on prompt
    dynamic_folder_path = set_dynamic_project_root(user_prompt)
    folder_name = dynamic_folder_path.name
    
    print(f"Creating project in: {dynamic_folder_path}")
    
    # 3. Run your custom Software Factory Workflow
    try:
        # We invoke the imported sub-graph
        final_state = code_workflow.invoke({"user_prompt": user_prompt})
        
        # 4. Format a clean UI response
        reply = (
            f"✅ **Software Project Generated Successfully!**\n\n"
            f"I have architected and written the code for your request.\n\n"
            f"📂 **Project Folder Name:** `{folder_name}`\n"
            f"📍 **Saved Location:** `{dynamic_folder_path}`\n\n"
            "You can now navigate to this folder in your terminal to run the code."
        )
    except Exception as e:
        reply = f"❌ There was an error generating your code: {str(e)}"
    
    # 5. Return the LangGraph state update
    return {"messages": [AIMessage(content=reply)], "active_agent": "code_agent"}