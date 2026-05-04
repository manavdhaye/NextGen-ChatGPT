# utils/thread.py
import uuid

def generate_thread_id() -> str:
    """Generates a unique string ID for a new chat thread."""
    return str(uuid.uuid4())