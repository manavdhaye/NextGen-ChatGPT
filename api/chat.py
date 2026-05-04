# api/chat.py (Snippet to integrate into your Flask app)
from flask import Blueprint, request, jsonify, session
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from core.workflow import workflow  # Import the compiled graph
import json

chat_blueprint = Blueprint('chat', __name__)

@chat_blueprint.route('/chat', methods=['POST'])
def chat():
    data = request.json
    user_message = data.get('message', '').strip()
    thread_id = session.get('thread_id', 'default_thread')
    
    config = {
        "configurable": {"thread_id": thread_id},
        "run_name": "chat_turn",
    }
    
    try:
        collected_content = []
        tools_used = []
        active_agent = "Supervisor" # Track who is doing the work
        
        # We start the stream with the HumanMessage
        for event in workflow.stream(
            {"messages": [HumanMessage(content=user_message)],"thread_id": thread_id},
            config=config,
            stream_mode="values" # 'values' is often cleaner for complex multi-agent graphs than 'messages'
        ):
            # Inspect the current state
            current_messages = event.get("messages", [])
            if not current_messages:
                continue
                
            last_message = current_messages[-1]
            
            # Track which agent is currently active based on your state design
            if "active_agent" in event:
                active_agent = event["active_agent"]

            if isinstance(last_message, ToolMessage):
                tool_name = getattr(last_message, "name", "tool")
                if tool_name not in tools_used:
                    tools_used.append(tool_name)
            
            elif isinstance(last_message, AIMessage) and not last_message.tool_calls:
                # Capture the final AI response (ignoring intermediate tool-call intents)
                content = last_message.content
                if isinstance(content, str) and content.strip():
                    collected_content = [content] # Overwrite with the latest complete thought

        final_message = collected_content[0] if collected_content else "Task completed."

        return jsonify({
            'success': True,
            'message': final_message,
            'tools_used': tools_used,
            'agent_used': active_agent
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500