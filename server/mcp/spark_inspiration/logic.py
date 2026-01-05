
import os
import json
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
from contextvars import ContextVar

# ContextVar to store the current user_id for the request
current_user_id: ContextVar[Optional[str]] = ContextVar("current_user_id", default=None)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
USERDATA_ROOT = os.path.join(BASE_DIR, "_userdata")

def get_user_inbox_path(user_id: str) -> str:
    """Get the inbox path for a specific user."""
    return os.path.join(USERDATA_ROOT, f"uid_{user_id}", "inspiration_inbox.jsonl")

def ensure_user_inbox_dir(user_id: str):
    """Ensure the user's data directory exists."""
    path = os.path.dirname(get_user_inbox_path(user_id))
    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)

def save_inspiration(
    summary: str,
    content: str,
    original_slice: str,
    thought_process: str,
    tags: List[str],
    source: str = "Unknown"
) -> Dict[str, Any]:
    """
    Save a new inspiration entry to the inbox of the authenticated user.
    """
    user_id = current_user_id.get()
    if not user_id:
        return {"success": False, "error": "Authentication required. User context missing."}
        
    try:
        ensure_user_inbox_dir(user_id)
        inbox_file = get_user_inbox_path(user_id)
        
        entry_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()
        
        entry = {
            "id": entry_id,
            "timestamp": timestamp,
            "summary": summary,
            "content": content,
            "original_slice": original_slice,
            "thought_process": thought_process,
            "tags": tags,
            "source": source,
            "status": "unread"
        }
        
        with open(inbox_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            
        return {"success": True, "id": entry_id, "message": "Inspiration captured"}
        
    except Exception as e:
        print(f"Error saving inspiration for user {user_id}: {e}")
        return {"success": False, "error": str(e)}

def get_recent_inspirations(limit: int = 5) -> List[Dict[str, Any]]:
    """
    Get recent inspirations for the authenticated user.
    """
    user_id = current_user_id.get()
    if not user_id:
        return []
        
    results = []
    inbox_file = get_user_inbox_path(user_id)
    
    if not os.path.exists(inbox_file):
        return results
        
    try:
        with open(inbox_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
            for line in reversed(lines):
                if not line.strip():
                    continue
                try:
                    results.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
                if len(results) >= limit:
                    break
    except Exception as e:
        print(f"Error reading inbox for user {user_id}: {e}")
        
    return results
