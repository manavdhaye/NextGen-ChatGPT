# agents/rag_agent.py
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from core.state import ChatState
from core.llm_setup import gemini_model as llm
from core.rag_manager import get_retriever_for_thread

def rag_agent(state: ChatState):
    """The LangGraph Node that answers questions about uploaded videos and documents."""
    print("--- 🧠 EXECUTING RAG AGENT ---")
    
    messages = state["messages"]
    user_query = messages[-1].content
    thread_id = state.get("thread_id", "default_thread")
    print(f"-> RAG Agent is searching inside Thread ID: {thread_id}")
    # 1. Get the filtered database for this specific chat session
    retriever = get_retriever_for_thread(thread_id)
    
    # 2. Retrieve the context (It will only return data tagged with this thread_id)
    try:
        retrieved_docs = retriever.invoke(user_query)
    except Exception as e:
        print(f"Retrieval Error: {e}")
        retrieved_docs = []
    
    # 3. Handle empty database scenario
    if not retrieved_docs:
        reply = "I couldn't find any information about that in the files currently uploaded to this chat session. Please make sure you have uploaded the correct document or video."
        return {"messages": [AIMessage(content=reply)], "active_agent": "rag_agent"}

    # 4. Format the Context for the LLM
    context_text = ""
    retrieved_images_markdown = []

    for idx, doc in enumerate(retrieved_docs):
        source_file = doc.metadata.get('file_name', 'Unknown Source')
        content_type = doc.metadata.get('content_type', 'data')
        if content_type == "image":
            # 1. Get the full Base64 string
            base64_str = doc.metadata.get('raw_content')
            
            # 2. Format it as an HTML/Markdown image tag so the frontend UI renders it
            img_tag = f"\n<img src='data:image/jpeg;base64,{base64_str}' width='400' style='border-radius:8px;'/>\n"
            
            # 3. Save the image to show the user later
            if img_tag not in retrieved_images_markdown:
                retrieved_images_markdown.append(img_tag)
                
            # 4. Tell the LLM what the image is about using the summary, NOT the base64 string
            context_text += f"\n--- Source: {source_file} (IMAGE DESCRIPTION) ---\n{doc.page_content}\n"
        else:
            # Handle standard text and tables
            actual_content = doc.metadata.get('raw_content', doc.page_content)
            context_text += f"\n--- Source: {source_file} ({content_type.upper()}) ---\n{actual_content}\n"

        # If it's a document, we put the raw text in the metadata. 
        # If it's a video transcript, it's directly in the page_content.

    # 5. Build the Prompt and Invoke the LLM
    system_prompt = """You are an elite Data Analyst and Research Assistant. 
    You are answering a user's question based strictly on the content they have uploaded (Videos, PDFs, PPTs, etc.).
    
    RULES:
    1. Base your answer ONLY on the provided context. Do not use outside knowledge.
    2. If the answer is not in the context, explicitly state: "Based on the uploaded files, I cannot answer this."
    3. Always cite the Source file name when providing facts or quoting data.
    4. Format your answer beautifully using Markdown (bullet points, bold text).
    5. IMAGE HANDLING: If you use context labeled as (IMAGE DESCRIPTION), answer confidently as if you are looking directly at the image. The system will automatically display the actual image to the user below your text, so you can use phrases like "As shown in the image below..." """

    prompt = f"USER QUESTION: {user_query}\n\nAVAILABLE CONTEXT:\n{context_text}"
    
    print(f"-> Sending {len(retrieved_docs)} contextual chunks to LLM...")
    response = llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=prompt)
    ])
    final_reply = response.content
    
    # If we found images, append them to the bottom of the LLM's text response!
    if retrieved_images_markdown:
        final_reply += "\n\n**Visual Context Retrieved:**\n"
        final_reply += "".join(retrieved_images_markdown)
    # 6. Return to LangGraph State
    return {
        "messages": [AIMessage(content=final_reply)], 
        "active_agent": "rag_agent"
    }