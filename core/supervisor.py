# core/supervisor.py
from langchain_core.messages import SystemMessage
from core.state import ChatState, RouteAgent
from config import Config  # Assuming you put your LLM initializations in a config or model.py file

# You can import your model from wherever you initialize it globally
from core.llm_setup import gemini_model as model

def supervisor_node(state: ChatState):
    """The brain of the system that decides which agent should handle the request."""
    print("--- SUPERVISOR THINKING ---")
    
    if state.get("forced_agent"):
        print(f"🎯 MANUAL OVERRIDE DETECTED: Routing directly to {state['forced_agent']}")
        return {"next_node": state["forced_agent"], "active_agent": "supervisor"}
    
    messages = state["messages"]
    
    routing_system_prompt = """You are the Lead Orchestrator of a Multi-Agent AI System. 
    Analyze the user's latest request and route it to the correct specialized agent.
    
    AGENT DIRECTORY:
    - ppt_agent: Specifically for creating or formatting PowerPoint (.pptx) files.
    - docx_agent: Route here if the user asks to CREATE, WRITE, or GENERATE a document, comprehensive report, essay, or cheat sheet. CRITICAL: If the user requests an output file like PDF, DOCX, or TXT, it MUST go here.
    - multimodal_rag: For answering questions about uploaded TEXT documents (PDFs, TXT, DOCX) using vector search.
    - code_agent: For writing, debugging, or executing programming code.
    - research_agent: ONLY route here if the user wants deep-dive web analysis or data gathering to be read directly IN THE CHAT UI. Do NOT route here if they want to generate a downloadable file or document.
    - chatmodal: Route here for standard queries and ALL tool usage, including:
        * Fetching current stock prices or market data.
        * General conversation, greetings, and quick web facts.
        * Calculating math operations.
        * Sending an email or WhatsApp message.
        * Generating or creating new images from text prompts.
        * Analyzing uploaded images (OCR, visual context).
        
    CRITICAL RULE FOR REPORTS: If the user asks for a "comprehensive report" AND "output as PDF/DOCX", the file format takes priority. Route to docx_agent.
    
    Select the single most appropriate 'next_node'."""
    
    structured_router = model.with_structured_output(RouteAgent)
    route_messages = [SystemMessage(content=routing_system_prompt)] + messages[-3:] 
    
    try:
        decision = structured_router.invoke(route_messages)
        chosen_node = decision.next_node
    except Exception as e:
        print(f"Routing Exception: {e}")
        chosen_node = "chatmodal"  # Failsafe
        
    print(f"--- SUPERVISOR ROUTED TO: {chosen_node.upper()} ---")
    return {"next_node": chosen_node}

def route_from_supervisor(state: ChatState):
    """Reads the LLM's decision and physically routes the graph edge."""
    return state.get("next_node", "chatmodal")