# tools/tool_manager.py
from langgraph.prebuilt import ToolNode
from core.state import ChatState

# Import your newly secured standard tools
from tools.all_tools import (
    calculator, 
    get_stock_price, 
    # email_tool, 
    draft_email_tool, 
    send_email_tool,
    whatsapp_tool, 
    create_image_tool,
    analyze_image_tool

)


# Assuming you initialize a secondary fast LLM for your RAG tool somewhere
from core.llm_setup import gemini_model

# Create the baseline tool list
base_tools = [calculator, get_stock_price,draft_email_tool, send_email_tool, whatsapp_tool, create_image_tool,analyze_image_tool]

def get_tools_for_thread(thread_id: str):
    """
    Dynamically fetches tools. Adds the RAG document_qa tool ONLY if 
    the user has a vector database for this specific thread.
    """
    tools = base_tools.copy()
    
    # try:
    #     vectorstore = load_vectorstore(thread_id)
    #     if vectorstore:
    #         llm = get_fast_llm() # Fetch your Llama-3 model instance
    #         rag_tool = DocumentQATool(vectorstore, llm)
    #         tools.append(rag_tool.as_tool())
    # except Exception as e:
    #     print(f"No vectorstore found for {thread_id} or error loading: {e}")
        
    return tools

def dynamic_tool_node(state: ChatState):
    """
    The actual Node executed by LangGraph. It checks the thread, 
    gets the right tools, and runs the requested tool.
    """
    thread_id = state.get("thread_id", "default")
    tools = get_tools_for_thread(thread_id)
    
    # Initialize LangGraph's prebuilt ToolNode
    tool_node = ToolNode(tools)
    
    # Execute the requested tool
    return tool_node.invoke(state)

def route_back_to_caller(state: ChatState):
    """
    Reads the state to figure out which Agent called the tool.
    This tells LangGraph where to route the workflow next.
    """
    return state.get("active_agent", "chatmodal")