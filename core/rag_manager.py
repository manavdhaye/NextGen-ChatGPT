# core/rag_manager.py
import os
import uuid
from langchain_core.documents import Document
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter


# Import your cleanly separated utility functions
from utils.multimodal_processor import (
    extract_elements, categorize_and_chunk, 
    process_extracted_images, generate_summaries, ImageDeduplicator
)
from utils.video_processor import video_to_audio, audio_to_text, video_to_images

# --- INITIALIZE MASTER DATABASE ---
# We use one central database for all chats, isolated by metadata filtering
MASTER_DB_DIR = os.path.join(os.getcwd(), "data", "master_rag_db")
os.makedirs(MASTER_DB_DIR, exist_ok=True)

embeddings = HuggingFaceEmbeddings(model_name="BAAI/bge-small-en-v1.5")
master_vectorstore = Chroma(
    collection_name="unified_multimodal_rag",
    embedding_function=embeddings,
    persist_directory=MASTER_DB_DIR
)

def process_and_store_file(file_path: str, thread_id: str):
    """Routes the file, extracts data, and stores it in the Master DB with thread isolation."""
    file_name = os.path.basename(file_path)
    ext = os.path.splitext(file_path)[1].lower()
    final_documents = []

    print(f"\n--- 📥 INGESTING {file_name} INTO THREAD {thread_id} ---")
    def _add_to_docs(summaries, raw_content, c_type, modality="document"):
        if summaries and raw_content:
            for idx, summary in enumerate(summaries):
                content_str = str(raw_content[idx])
                
                # Truncate text/tables to save DB space, but keep full Base64 for images
                if c_type != "image":
                    content_str = content_str[:5000]
                    
                doc = Document(
                    page_content=summary, 
                    metadata={
                        "thread_id": thread_id,  # <--- CRITICAL: Isolates to this chat session
                        "file_name": file_name,
                        "modality": modality,    # "video" or "document"
                        "content_type": c_type,  # "text", "table", or "image"
                        "raw_content": content_str # Store original content in metadata
                    }
                )
                final_documents.append(doc)

    # ==========================================
    # PATH A: VIDEO PROCESSING
    # ==========================================
    if ext in ['.mp4', '.avi', '.mov']:
        print("🎬 Routing to Video Pipeline...")
        audio_path = os.path.join(os.getcwd(), "uploads", f"temp_{uuid.uuid4().hex[:6]}.wav")
        
        # Extract audio and transcribe
        video_to_audio(file_path, audio_path)
        transcript = audio_to_text(audio_path)
        
        if os.path.exists(audio_path):
            os.remove(audio_path) # Clean up temp audio file
            
        # Chunk the transcript
        splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        chunks = splitter.split_text(transcript)
        
        # Tag with Metadata
        for i, chunk in enumerate(chunks):
            doc = Document(
                page_content=chunk,
                metadata={
                    "thread_id": thread_id,      # <--- CRITICAL: Isolates to this chat session
                    "file_name": file_name,
                    "modality": "video",
                    "content_type": "transcript",
                    "raw_content": chunk
                }
            )
            final_documents.append(doc)

        print("🖼️ Extracting frames from video...")
        frames_dir = os.path.join(os.getcwd(), "uploads", f"frames_{uuid.uuid4().hex[:6]}")
        os.makedirs(frames_dir, exist_ok=True) # Ensure folder exists
        
        video_to_images(file_path, frames_dir)
        
        # Reuse your awesome multimodal image tools for the video frames!
        deduplicator = ImageDeduplicator()
        images_b64 = process_extracted_images(deduplicator, directory=frames_dir)
        
        # Summarize the frames using Groq Vision
        _, _, frame_sums = generate_summaries([], [], images_b64)
        
        # Add the summarized images to the database using the shared helper function
        _add_to_docs(frame_sums, images_b64, "image", modality="video")

    # ==========================================
    # PATH B: MULTIMODAL DOCUMENT PROCESSING
    # ==========================================
    elif ext in ['.pdf', '.docx', '.pptx', '.txt']:
        print("📄 Routing to Multimodal Document Pipeline...")
        
        deduplicator = ImageDeduplicator()
        raw_elements = extract_elements(file_path, deduplicator)
        texts, tables = categorize_and_chunk(raw_elements)
        images_b64 = process_extracted_images(deduplicator)
        
        # Generate summaries using your Groq Vision LLM
        text_sums, table_sums, image_sums = generate_summaries(texts, tables, images_b64)
        
        # def _add_to_docs(summaries, raw_content, c_type):
        #     if summaries and raw_content:
        #         for idx, summary in enumerate(summaries):
        #             content_str = str(raw_content[idx])
        #             if c_type != "image":
        #                 content_str = content_str[:5000]
        #             doc = Document(
        #                 page_content=summary, 
        #                 metadata={
        #                     "thread_id": thread_id,  # <--- CRITICAL: Isolates to this chat session
        #                     "file_name": file_name,
        #                     "modality": "document",
        #                     "content_type": c_type,
        #                     "raw_content": content_str # Store original content in metadata
        #                 }
        #             )
        #             final_documents.append(doc)

        _add_to_docs(text_sums, texts, "text")
        _add_to_docs(table_sums, tables, "table")
        _add_to_docs(image_sums, images_b64, "image")

    else:
        print(f"⚠️ Unsupported file type: {ext}")
        return False

    # ==========================================
    # SAVE TO MASTER DB
    # ==========================================
    if final_documents:
        master_vectorstore.add_documents(final_documents)
        print(f"✅ Successfully saved {len(final_documents)} embedded chunks for Thread: {thread_id}\n")
        return True
        
    return False

def get_retriever_for_thread(thread_id: str):
    """Creates a retriever that ONLY searches the current chat session's files."""
    return master_vectorstore.as_retriever(
        search_type="similarity",
        search_kwargs={
            "k": 12,
            "filter": {"thread_id": thread_id} # <--- THIS IGNORS ALL OTHER CHAT SESSIONS
        }
    )