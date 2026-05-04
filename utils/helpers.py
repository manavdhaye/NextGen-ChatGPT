# utils/helpers.py
import json
import os

# Save the titles in the data folder next to your chatbot.db
THREAD_META_FILE = os.path.join(os.getcwd(), "data", "thread_titles.json")

def load_thread_titles():
    """Loads the dictionary of thread IDs and their titles."""
    if not os.path.exists(THREAD_META_FILE):
        return {}
    try:
        with open(THREAD_META_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_thread_titles(data):
    """Saves the dictionary of thread IDs and titles."""
    os.makedirs(os.path.dirname(THREAD_META_FILE), exist_ok=True)
    with open(THREAD_META_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def retrieve_all_threads():
    """Returns a list of all thread IDs based on the saved titles."""
    titles = load_thread_titles()
    return list(titles.keys())