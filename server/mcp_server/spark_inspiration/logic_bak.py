
import os
import json
import uuid
import time
from datetime import datetime
from typing import List, Optional, Dict, Any

# Define the storage path relative to the server root
# Assuming this file is in server/mcp/spark_inspiration/logic.py
# We want server/_userdata/inspiration_inbox.jsonl
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
USERDATA_DIR = os.path.join(BASE_DIR, "_userdata")
INBOX_FILE = os.path.join(USERDATA_DIR, "inspiration_inbox.jsonl")

def ensure_inbox_exists():
    """Ensure the userdata directory and inbox file exist."""
    if not os.path.exists(USERDATA_DIR):
        os.makedirs(USERDATA_DIR, exist_ok=True)
    
    # We don't need to create the file if it doesn't exist, append mode will handle it.
    # But ensuring the dir is critical.

def save_inspiration(
    summary: str,
    content: str,
    original_slice: str,
    thought_process: str,
    tags: List[str],
    source: str = "Unknown"
) -> Dict[str, Any]:
    """
    Save a new inspiration entry to the inbox.
    """
    ensure_inbox_exists()
    
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
        "status": "unread"  # Use this to show 'new' badge in UI later
    }
    
    # Use 'a' mode for append, with utf-8 encoding
    try:
        with open(INBOX_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return {"success": True, "id": entry_id, "message": "Inspiration captured"}
    except Exception as e:
        print(f"Error saving inspiration: {e}")
        return {"success": False, "error": str(e)}

def get_recent_inspirations(limit: int = 5) -> List[Dict[str, Any]]:
    """
    Get recent inspirations (for debugging or optional read tools).
    """
    results = []
    if not os.path.exists(INBOX_FILE):
        return results
        
    try:
        with open(INBOX_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
            # Read from end
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
        print(f"Error reading inbox: {e}")
        
    return results
