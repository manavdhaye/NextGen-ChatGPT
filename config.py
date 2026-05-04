import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    # Base directory of the project
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))

    # Flask Settings
    SECRET_KEY = os.getenv("SECRET_KEY", "default-dev-key")
    DEBUG = os.getenv("FLASK_ENV") == "development"

    # API Keys
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

    

    # File System Paths
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
    VECTORSTORE_PATH = os.path.join(BASE_DIR, "rag", "vectorstores")
    
    # Database Paths
    DB_PATH = os.path.join(BASE_DIR, "database", "chatbot.db")
    THREAD_META_FILE = os.path.join(BASE_DIR, "database", "threads.json")

    # App Constraints
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB max upload size
    ALLOWED_EXTENSIONS = {'pdf', 'txt', 'docx', 'pptx', 'png', 'jpg', 'jpeg'}

# Helper function to ensure necessary directories exist
def init_directories():
    directories = [
        Config.UPLOAD_FOLDER,
        Config.VECTORSTORE_PATH,
        os.path.join(Config.BASE_DIR, "database")
    ]
    for directory in directories:
        os.makedirs(directory, exist_ok=True)