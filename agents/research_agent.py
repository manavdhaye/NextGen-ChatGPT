# agents/research_agent.py
from langchain_core.messages import AIMessage
from core.state import ChatState

# Import the compiled research graph
from workflows.research_workflow import research_workflow_app

def run_research_agent(state: ChatState):
    """
    Wrapper function called by core/workflow.py.
    Extracts the prompt, runs the deep research workflow, and returns the report.
    """
    print("--- 🔬 EXECUTING RESEARCH AGENT ---")
    
    # 1. Get the user's prompt
    user_prompt = state["messages"][-1].content
    
    # 2. Set up the initial state for the internal research graph
    initial_research_state = {
        "user_query": user_prompt, 
        "search_history": [], 
        "search_queries": [],
        "all_search_results": [], 
        "scraped_sources": [], 
        "relevant_context": "",
        "fact_checks": {}, 
        "is_sufficient": "", 
        "final_report": "", 
        "image_assets": [],
        "loop_count": 0
    }
    
    try:
        # 3. Invoke the internal sub-graph
        print(f"Starting deep research for: '{user_prompt}'")
        result = research_workflow_app.invoke(initial_research_state)
        
        # 4. Extract the final formatted markdown report
        report = result.get("final_report", "No report was generated.")
        images = result.get("image_assets", []) # <--- GET URLs
        
        reply = (
            "✅ **Deep Research Complete!**\n\n"
            "I have compiled a comprehensive report based on live web data across multiple sources.\n\n"
            f"{report}"
        )
        
        if images:
            for img_url in images:
            # We don't need a leading slash here because these are full web http:// URLs
                reply += f"\n\n![Research Image]({img_url})"

        # Wrap it with a nice confirmation message
        
    except Exception as e:
        reply = f"❌ There was an error conducting the research: {str(e)}"
        images = []
    
    # 5. Return the LangGraph state update to the master supervisor
    return {"messages": [AIMessage(content=reply)], "active_agent": "research_agent","research_images": images}