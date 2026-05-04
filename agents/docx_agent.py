# agents/docx_agent.py
from langchain_core.messages import AIMessage
from core.state import ChatState

# Import the compiled docx graph
from workflows.docx_workflow import docx_workflow 

def docx_agent(state: ChatState):
    """
    Wrapper to execute the complex document generation workflow.
    """
    print("--- 📄 EXECUTING DOCX AGENT ---")
    
    # 1. Extract the user's request from the shared memory state
    user_prompt = state["messages"][-1].content
    
    try:
        # 2. Trigger the internal sub-graph
        result = docx_workflow.invoke({
            "topic": user_prompt,
            "saved_filepath": "",
            "needs_research": False, 
            "queries": [],
            "evidence": [],
            "plan": None,
            "sections": [],
            "merged_md": "",
            "final_text": ""
        })
        
        # 3. Format the response for the UI
        filepath = result.get("saved_filepath", "")
        preview = result.get("final_text", "Document generated successfully.")[:400]
        
        # Determine format text based on extension
        file_type = "Document"
        if filepath.endswith(".pdf"): file_type = "PDF Report"
        elif filepath.endswith(".txt"): file_type = "Text File"
        elif filepath.endswith(".docx"): file_type = "Word Document"

        reply = (
            f"✅ **{file_type} Generation Complete!**\n\n"
            "I have built your file based on the research and requirements. Here is a quick preview of the introduction:\n\n"
            f"> *{preview}...*\n\n"
            f"[DOWNLOAD_FILE:{filepath}]\n\n"
            "What would you like to work on next?"
        )
        
    except Exception as e:
        reply = f"❌ Sorry, there was an error generating the document: {str(e)}"

    # 4. Return the result to update the main database and set the active agent
    return {"messages": [AIMessage(content=reply)], "active_agent": "docx_agent"}