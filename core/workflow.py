# core/workflow.py
import sqlite3
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.prebuilt import tools_condition

from core.state import ChatState
from core.supervisor import supervisor_node, route_from_supervisor

# Import your agent functions (you will split these into agents/ folder)
from agents.chat_agent import chatmodal
from agents.code_agent import run_code_agent
from agents.research_agent import run_research_agent
from agents.ppt_agent import ppt_agent
from agents.docx_agent import docx_agent
from agents.rag_agent import rag_agent
from tools.tool_manager import dynamic_tool_node, route_back_to_caller


# 1. Initialize Graph
graph = StateGraph(ChatState)

# 2. Add Nodes
graph.add_node("supervisor", supervisor_node)
graph.add_node("chatmodal", chatmodal)
graph.add_node("code_agent", run_code_agent)
graph.add_node("research_agent", run_research_agent)
graph.add_node("multimodal_rag", rag_agent)
graph.add_node("ppt_agent", ppt_agent)
graph.add_node("docx_agent", docx_agent)
graph.add_node("tools", dynamic_tool_node) 

# 3. Add Edges (The Flow)
graph.add_edge(START, "supervisor")

graph.add_conditional_edges(
    "supervisor", 
    route_from_supervisor,
    {
        "chatmodal": "chatmodal",
        "code_agent": "code_agent",
        "research_agent": "research_agent",
        "multimodal_rag": "multimodal_rag",
        "ppt_agent": "ppt_agent",       
        "docx_agent": "docx_agent"
    }
)

# 4. Terminal Endpoints (Agents that don't need the shared tools node)
graph.add_edge("multimodal_rag", END)
graph.add_edge("docx_agent", END)  
graph.add_edge("ppt_agent", END)  

# 5. Tool Check Conditions
graph.add_conditional_edges("chatmodal", tools_condition)
graph.add_conditional_edges("code_agent", tools_condition)
graph.add_conditional_edges("research_agent", tools_condition)

# 6. Return Routing (Tools back to the agent that called them)
graph.add_conditional_edges(
    "tools", 
    route_back_to_caller,
    {
        "chatmodal": "chatmodal",
        "code_agent": "code_agent",
        "research_agent": "research_agent",
    }
)

# 7. Compile with Database
conn = sqlite3.connect(database="database/chatbot.db", check_same_thread=False)
checkpointer = SqliteSaver(conn=conn)

workflow = graph.compile(checkpointer=checkpointer)