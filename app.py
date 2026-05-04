# app.py
from flask import Flask, render_template, request, jsonify, session, send_from_directory, Response, stream_with_context
from werkzeug.utils import secure_filename
import os
import secrets
import json
import traceback
import re
import mimetypes
import tempfile
import uuid
from groq import Groq
from gtts import gTTS
from langdetect import detect

# Import your multi-agent workflow
from core.workflow import workflow 
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from core.rag_manager import process_and_store_file

# Helper functions 
from utils.thread import generate_thread_id
from utils.helpers import retrieve_all_threads, load_thread_titles, save_thread_titles
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
# app.secret_key = secrets.token_hex(16)
app.secret_key = os.getenv("SECRET_KEY", secrets.token_hex(16))

# Configuration
BASE_DIR = os.getcwd()
app.config['UPLOAD_FOLDER'] = os.path.join(BASE_DIR, 'uploads')
app.config['EXPORTS_FOLDER'] = os.path.join(BASE_DIR, 'exports')
app.config['IMAGES_FOLDER'] = os.path.join(BASE_DIR, 'images')
app.config['MAX_CONTENT_LENGTH'] = 200 * 1024 * 1024  
app.config['AUDIO_FOLDER'] = os.path.join(BASE_DIR, 'audio')
os.makedirs(app.config['AUDIO_FOLDER'], exist_ok=True)

# Initialize Groq for Whisper API
# (It's best to put this key in your .env file as GROQ_API_KEY)
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY_FOR_AUDIO"))

# Ensure directories exist
for folder in [app.config['UPLOAD_FOLDER'], app.config['EXPORTS_FOLDER'], app.config['IMAGES_FOLDER'], os.path.join(BASE_DIR, 'data')]:
    os.makedirs(folder, exist_ok=True)

# --- Routes for Serving Generated Files ---
@app.route('/exports/<path:filename>')
def download_file(filename):
    return send_from_directory(app.config['EXPORTS_FOLDER'], filename, as_attachment=True)

@app.route('/images/<path:filename>')
def serve_image(filename):
    return send_from_directory(app.config['IMAGES_FOLDER'], filename)

@app.route('/uploads/<path:filename>')
def serve_upload(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

def load_conversation(thread_id):
    """Load conversation history for a thread from SQLite"""
    try:
        config = {"configurable": {"thread_id": thread_id}}
        state = workflow.get_state(config=config)
        if state is None: return []
        
        messages = state.values.get("messages", [])
        temp_message = []
        
        for msg in messages:
            if isinstance(msg, HumanMessage):
                content = msg.content
                attachments = []
            
                # 1. 🚨 INDESTRUCTIBLE REGEX: Catches filenames in any format
                match = re.search(r"\[SYSTEM CONTEXT: The user just uploaded the following files:\s*(.*?)\.\s*RULE 1", content, re.DOTALL)
                
                if match:
                    file_names = [f.strip() for f in match.group(1).split(',')]
                    for fname in file_names:
                        if not fname: 
                            continue
                            
                        # 2. 🚨 BYPASS MIMETYPES: Hardcode the image check so Windows doesn't break it!
                        mime_type, _ = mimetypes.guess_type(fname)
                        is_img = mime_type and mime_type.startswith('image/')
                    
                        attachments.append({
                            "name": fname,
                            "type": mime_type or "application/octet-stream",
                            "url": f"/uploads/{fname}" if is_img else None
                        })

                        print("attactment : ",attachments)
                # 3. NON-GREEDY CLEANUP: Safely hide the text
                clean_content = re.sub(r"\s*\[SYSTEM CONTEXT:.*?\]", "", content, flags=re.IGNORECASE | re.DOTALL)
                
                # 🚨 THE FIX: This deletes the forced tool directive
                clean_content = re.sub(r"\s*\[SYSTEM DIRECTIVE:.*?\]", "", clean_content, flags=re.IGNORECASE | re.DOTALL)
            
                temp_message.append({
                    "role": "user", 
                    "content": clean_content.strip(), 
                    "attachments": attachments  
                })

            elif isinstance(msg, AIMessage) and not msg.tool_calls:
                content = msg.content
                if isinstance(content, list):
                    content = "".join([item.get('text', '') if isinstance(item, dict) else str(item) for item in content])
                elif isinstance(content, dict):
                    content = content.get('text', '')
                else:
                    content = str(content)
                
                if content.strip():
                    temp_message.append({"role": "assistant", "content": content})
                    
        return temp_message
    except Exception as e:
        print(f"❌ Error loading conversation: {e}")
        traceback.print_exc()
        return []

@app.route('/')
def index():
    if 'thread_id' not in session:
        session['thread_id'] = generate_thread_id()
    return render_template('index.html')

@app.route('/api/threads', methods=['GET'])
def get_threads():
    threads = retrieve_all_threads()
    thread_titles = load_thread_titles()
    result = [{'id': tid, 'title': thread_titles.get(tid, f"Chat {tid[:10]}")} for tid in threads]
    return jsonify({'threads': result, 'current_thread': session.get('thread_id')})

@app.route('/api/new-chat', methods=['POST'])
def new_chat():
    new_thread_id = generate_thread_id()
    session['thread_id'] = new_thread_id
    return jsonify({'thread_id': new_thread_id, 'success': True})

@app.route('/api/switch-thread/<thread_id>', methods=['POST'])
def switch_thread(thread_id):
    session['thread_id'] = thread_id
    messages = load_conversation(thread_id)
    return jsonify({'messages': messages, 'success': True})

ALLOWED_EXTENSIONS = {'pdf', 'txt', 'docx', 'pptx', 'png', 'jpg', 'jpeg', 'mp4'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/api/upload', methods=['POST'])
def upload_file():
    if 'files' not in request.files: return jsonify({'error': 'No files'}), 400
    files = request.files.getlist('files')
    thread_id = session.get('thread_id', 'default_thread')
    if not thread_id or thread_id == "default_thread":
        thread_id = generate_thread_id()
        session['thread_id'] = thread_id
    try:
        uploaded_files = []
        for file in files:
            if file.filename:
                if not file.filename:
                    continue
            
                    # ✅ VALIDATE EXTENSION
                if not allowed_file(file.filename):
                    return jsonify({'error': f'File type not allowed: {file.filename}'}), 400
                
                filename = secure_filename( file.filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                # class FileWrapper:
                #     def __init__(self, path, original_name):
                #         self.path = path
                #         self.name = original_name
                #     def read(self):
                #         with open(self.path, 'rb') as f: return f.read()
                uploaded_files.append(filepath)
        
       
        for file_obj in uploaded_files:
            ext = os.path.splitext(file_obj)[1].lower()
            # 🚨 THE FIX: Skip RAG ingestion for standalone images!
            if ext in ['.png', '.jpg', '.jpeg']:
                print(f"🖼️ Image saved. Skipping RAG database for: {file_obj}")
                # The image is safely in the uploads folder for the analyze_image_tool to use!
            else:
                # Process PDFs, DOCX, and MP4s through RAG as normal
                print(f"Triggering RAG manager for: {file_obj}")
                process_and_store_file(file_obj, thread_id)
                
        return jsonify({'success': True, 'message': 'Documents uploaded and embedded successfully!'})
    except Exception as e:
        print(f"Upload Error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/chat', methods=['POST'])
def chat():
    """Streaming Multi-Agent Chat Endpoint"""
    data = request.json
    user_message = data.get('message', '').strip()
    forced_agent = data.get("forced_agent")
    forced_tool = data.get("forced_tool")
    thread_id = session.get('thread_id',"default_thread")

    
    if not thread_id or thread_id == "default_thread":
        thread_id = generate_thread_id()
        session['thread_id'] = thread_id

    if forced_tool:
        user_message += f"\n\n[SYSTEM DIRECTIVE: You MUST execute the '{forced_tool}' tool to answer this query. Do not use any other tool.]"
        forced_agent = "chatmodal"

    thread_titles = load_thread_titles()
    if thread_id not in thread_titles:
        clean_title = data.get('message', '').strip()[:40]
        thread_titles[thread_id] = clean_title if clean_title else f"Chat {thread_id[:8]}"
        save_thread_titles(thread_titles)
        
    config = {"configurable": {"thread_id": thread_id}, "run_name": "chat_turn"}
    state_input = {
        "messages": [HumanMessage(content=user_message)],
        "thread_id": thread_id
    }
    
    # Pass the forced agent to the state if one was selected
    if forced_agent:
        state_input["forced_agent"] = forced_agent
    
    def generate_stream():
        tools_used = []
        active_agent = "Supervisor"
        
        try:
            for event, metadata in workflow.stream(
                state_input,
                config=config,
                stream_mode="messages" 
            ):
                if isinstance(event, ToolMessage):
                    if event.name not in tools_used: 
                        tools_used.append(event.name)
                        yield f"data: {json.dumps({'type': 'tool', 'tool': event.name})}\n\n"
            
                elif isinstance(event, AIMessage) and not event.tool_calls:
                    content = event.content
                    
                    # --- THE FIX: Safely parse text from lists/dicts during streaming ---
                    if isinstance(content, list):
                        content = "".join([item.get('text', '') if isinstance(item, dict) else str(item) for item in content])
                    elif isinstance(content, dict):
                        content = content.get('text', '')
                    else:
                        content = str(content)
                        
                    if content.strip():
                        # Skip internal LangChain system tokens if they accidentally leak
                        if not any(word in content for word in ['substant', 'Lau', 'zimmer']):
                            yield f"data: {json.dumps({'type': 'chunk', 'text': content})}\n\n"
                            
                                
            # 3. Stream Complete: Grab final metadata
            current_state = workflow.get_state(config).values
            
            final_agent = current_state.get("active_agent", active_agent)
            pending_email = current_state.get("pending_email", None)
            
            yield f"data: {json.dumps({'type': 'done', 'agent': final_agent,'pending_email': pending_email})}\n\n"

        except Exception as e:
            print("\n" + "!"*50)
            print("🚨 BACKEND CRASH DETECTED 🚨")
            print("!"*50)
            traceback.print_exc()
            print("!"*50 + "\n")
            yield f"data: {json.dumps({'type': 'error', 'text': str(e)})}\n\n"

    return Response(stream_with_context(generate_stream()), mimetype='text/event-stream')

# --- NEW: Serve Audio Files ---
@app.route('/audio/<path:filename>')
def serve_audio(filename):
    return send_from_directory(app.config['AUDIO_FOLDER'], filename)

# --- NEW: Transcribe Mic Input via Groq Whisper ---
@app.route('/api/transcribe', methods=['POST'])
def transcribe_audio():
    if 'audio' not in request.files:
        return jsonify({'error': 'No audio file provided'}), 400
    
    audio_file = request.files['audio']
    
    try:
        # Save blob temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as temp_audio:
            audio_file.save(temp_audio.name)
            temp_audio_path = temp_audio.name

        # Send to Groq Whisper
        with open(temp_audio_path, "rb") as file:
            transcription = groq_client.audio.transcriptions.create(
                file=("audio.webm", file.read()),
                model="whisper-large-v3-turbo",
            )
            
        # Clean up temp file
        os.remove(temp_audio_path)
        
        return jsonify({'success': True, 'text': transcription.text})
    except Exception as e:
        print(f"Transcription error: {e}")
        return jsonify({'error': str(e)}), 500

# --- NEW: Text-to-Speech (TTS) for AI Answers ---
@app.route('/api/tts', methods=['POST'])
def generate_tts():
    data = request.json
    text = data.get('text', '')
    if not text: return jsonify({'error': 'No text'}), 400
    
    try:
        # Clean markdown symbols so the AI doesn't read "asterisk asterisk bold asterisk asterisk"
        clean_text = re.sub(r'[*#_~`]', '', text)
        clean_text = re.sub(r'\[.*?\]\(.*?\)', '', clean_text) # remove markdown links
        
        detected_lang = detect(clean_text)
        tts = gTTS(text=clean_text, lang=detected_lang)
        
        filename = f"tts_{uuid.uuid4().hex}.mp3"
        filepath = os.path.join(app.config['AUDIO_FOLDER'], filename)
        tts.save(filepath)
        
        return jsonify({'success': True, 'audio_url': f'/audio/{filename}'})
    except Exception as e:
        print(f"TTS error: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    import sys
    sys.stdout.reconfigure(line_buffering=True)
    app.run(debug=True, port=5000, use_reloader=False)