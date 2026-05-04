# agents/ppt_agent.py
from langchain_core.messages import AIMessage
from core.state import ChatState

# Import the compiled PPT graph
from workflows.ppt_workflow import ppt_workflow 

def ppt_agent(state: ChatState):
    """
    Wrapper to execute the complex ppt generation workflow.
    """
    print("--- 📊 EXECUTING PPT AGENT ---")
    
    # 1. Extract the user's request from the shared memory state
    user_prompt = state["messages"][-1].content
    
    try:
        # 2. Trigger your internal LangGraph sub-graph
        result = ppt_workflow.invoke({
            "topic": user_prompt,
            "saved_filepath": "",
            "needs_research": False, 
            "queries": [],
            "evidence": [],
            "plan": None,
            "slides_content": [],
            "image_specs": []
        })
        
        # 3. Safely extract metadata to show the user
        try:
            filepath = result["saved_filepath"]
            generated_title = result["plan"].ppt_title
            num_slides = len(result["slides_content"])
        except (KeyError, AttributeError):
            filepath = "Unknown Path"
            generated_title = "Your Presentation"
            num_slides = "Multiple"
            
        # 4. Create the final UI response with the [DOWNLOAD_FILE:] tag 
        # (This tag can be parsed by your frontend to create a clickable button)
        reply = (
            "✅ **Presentation Generation Complete!**\n\n"
            f"I have successfully built **'{generated_title}'** with {num_slides} slides, complete with AI-generated images and custom styling.\n\n"
            "The `.pptx` file has been saved locally.\n\n"
            f"[DOWNLOAD_FILE:{filepath}]\n\n"
            "What would you like me to do next?"
        )
        
    except Exception as e:
        reply = f"❌ Sorry, there was an error generating the presentation: {str(e)}"

    # 5. Return the result to update the master database
    return {"messages": [AIMessage(content=reply)], "active_agent": "ppt_agent"}