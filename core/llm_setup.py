# core/llm_setup.py
import os
from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI

# Your main routing/chat model
groq_model = ChatGroq(
    model="llama-3.3-70b-versatile",
    api_key=os.getenv("GROQ_API_KEY"),
    temperature=0.1,
)

# You can add Gemini here if you want to use it for specific tasks
gemini_model = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash", 
    google_api_key=os.getenv("GOOGLE_API_KEY")
)