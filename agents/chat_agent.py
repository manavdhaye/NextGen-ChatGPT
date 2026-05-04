import json
from langchain_core.messages import SystemMessage,ToolMessage
from core.state import ChatState
from core.llm_setup import gemini_model as model
from tools.tool_manager import get_tools_for_thread

def chatmodal(state: ChatState):
    """The general chat and multi-tool agent."""
    messages = state["messages"]
    thread_id = state.get("thread_id", "default")
    tools = get_tools_for_thread(thread_id)

    new_images = []
    # If the last message was a tool result, check if it contains an image path
    if messages and isinstance(messages[-1], ToolMessage):
        if "IMAGE_PATH:" in str(messages[-1].content):
            path = str(messages[-1].content).split("IMAGE_PATH:")[1].strip()
            new_images.append(path)
            
    # --- DETAILED SYSTEM PROMPT ---
    current_pending_email = state.get("pending_email", None)
    
    if messages and isinstance(messages[-1], ToolMessage):
        content_str = str(messages[-1].content)
        
        # If the AI just drafted an email, save the JSON to the Lan gGraph state
        if "DRAFT_STAGED:" in content_str:
            try:
                draft_json = content_str.split("DRAFT_STAGED:")[1].strip()
                current_pending_email = json.loads(draft_json)
            except Exception as e:
                print(f"Error parsing email draft: {e}")
                
        # If the AI successfully sent the email, clear the draft from the state
        elif "SUCCESS: Email sent" in content_str:
            current_pending_email = None

    # --- 3. DETAILED SYSTEM PROMPT WITH HITL RULES ---
    system_prompt = """You are NextGen ChatGPT, an advanced and helpful AI assistant.
    You can have normal, friendly conversations AND use tools when requested.

    TOOL USAGE GUIDELINES:
    - Use 'calculator' for mathematical operations.
    - Use 'get_stock_price' to fetch current stock prices.
    - Use 'whatsapp_tool' to send WhatsApp messages to specific numbers.
    - Use 'create_image_tool' for generating new images from text.
    - Use 'analyze_image_tool' ONLY when the user asks a question about an uploaded image file.
      🚨 CRITICAL IMAGE RULE 🚨: The exact image filename is provided to you in the hidden [SYSTEM CONTEXT] block at the end of the user's message. DO NOT ask the user for the filename! Extract the filename from the context and execute the analyze_image_tool IMMEDIATELY!

    EMAIL WORKFLOW (STRICT RULES):
    1. NEVER send an email immediately. 
    2. If the user asks to send an email, you MUST invoke the 'draft_email_tool' first to stage it.
    3. DO NOT write the email subject or body in your regular text response. ONLY pass them into the tool parameters.
    4. After the draft tool runs successfully, just ask the user: "I have prepared the email draft. Does it look good to send?"
    5. If the user asks for edits, use 'draft_email_tool' again to update the draft.
    6. ONLY use 'send_email_tool' when the user explicitly says "yes", "send it", or approves.

    IMPORTANT: Answer general questions directly. Only trigger tools when specifically needed.
    If a tool returns an image path, write a short confirmation message. Do NOT try to output image links yourself."""
    
    if not messages or not isinstance(messages[0], SystemMessage):
        messages = [SystemMessage(content=system_prompt)] + messages
    
    # Bind the tools to the LLM so it knows it can use them
    llm_with_tools = model.bind_tools(tools)
    result = llm_with_tools.invoke(messages)
    print(result.content)

    if new_images:
        for img_path in new_images:
            # Note the leading slash (/) so the browser knows to look at the root domain
            result.content += f"\n\n![Generated Image](/{img_path})"

    
    # CRITICAL: Tag this agent as active so tools know where to return
    return {
        "messages": [result], 
        "active_agent": "chatmodal", 
        "pending_email": current_pending_email}
