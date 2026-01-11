
"""
灵感系统核心逻辑

统一的灵感数据格式:
{
    "id": "uuid-string",
    "timestamp": "ISO-8601",
    "source": "灵感原始文本（用户输入或AI生成的种子）",
    "content": "灵感工坊生成的扩展内容（可为空）",
    "tags": {
        "styles": [],      # 风格：治愈、悬疑、恐怖等
        "genres": [],      # 题材：校园、都市、冒险等
        "tones": [],       # 基调：现实主义、梦核等
        "worldviews": []   # 世界观：架空、规则怪谈等
    },
    "status": "unread"     # unread / read
}
"""

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


def get_user_inspiration_path(user_id: str) -> str:
    """获取用户的全局灵感文件路径"""
    return os.path.join(USERDATA_ROOT, f"uid_{user_id}", "inspirations.jsonl")


def ensure_user_dir(user_id: str):
    """确保用户数据目录存在"""
    path = os.path.dirname(get_user_inspiration_path(user_id))
    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)


def save_inspiration(
    source: str,
    content: str = "",
    tags: Optional[Dict[str, List[str]]] = None
) -> Dict[str, Any]:
    """
    保存新的灵感条目到用户的全局灵感库。
    
    Args:
        source: 灵感原始文本（用户输入或AI生成的种子）
        content: 灵感工坊生成的扩展内容（可为空，待后续生成）
        tags: 四维标签 {"styles": [], "genres": [], "tones": [], "worldviews": []}
    
    Returns:
        包含成功状态和灵感ID的字典
    """
    user_id = current_user_id.get()
    if not user_id:
        return {"success": False, "error": "Authentication required. User context missing."}
        
    try:
        ensure_user_dir(user_id)
        inspiration_file = get_user_inspiration_path(user_id)
        
        entry_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()
        
        # 规范化 tags 结构
        normalized_tags = {
            "styles": [],
            "genres": [],
            "tones": [],
            "worldviews": []
        }
        if tags:
            for key in normalized_tags:
                if key in tags and isinstance(tags[key], list):
                    normalized_tags[key] = tags[key]
        
        entry = {
            "id": entry_id,
            "timestamp": timestamp,
            "source": source,
            "content": content,
            "tags": normalized_tags,
            "status": "unread"
        }
        
        with open(inspiration_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            
        return {"success": True, "id": entry_id, "message": "灵感已捕获"}
        
    except Exception as e:
        print(f"Error saving inspiration for user {user_id}: {e}")
        return {"success": False, "error": str(e)}


def get_all_inspirations(user_id: str) -> List[Dict[str, Any]]:
    """
    获取用户的所有灵感（按时间倒序）
    """
    results = []
    inspiration_file = get_user_inspiration_path(user_id)
    
    if not os.path.exists(inspiration_file):
        return results
        
    try:
        with open(inspiration_file, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    results.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        # 按时间倒序
        results.reverse()
    except Exception as e:
        print(f"Error reading inspirations for user {user_id}: {e}")
        
    return results


def update_inspiration(user_id: str, entry_id: str, updates: Dict[str, Any]) -> bool:
    """
    更新指定灵感条目
    
    Args:
        user_id: 用户ID
        entry_id: 灵感ID
        updates: 要更新的字段 (content, tags, status 等)
    
    Returns:
        是否更新成功
    """
    inspiration_file = get_user_inspiration_path(user_id)
    if not os.path.exists(inspiration_file):
        return False
    
    try:
        # 读取所有条目
        entries = []
        with open(inspiration_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        
        # 查找并更新
        found = False
        for entry in entries:
            if entry.get("id") == entry_id:
                for key, value in updates.items():
                    if key in ["content", "tags", "status"]:
                        entry[key] = value
                found = True
                break
        
        if not found:
            return False
        
        # 重写文件
        with open(inspiration_file, "w", encoding="utf-8") as f:
            for entry in entries:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        
        return True
        
    except Exception as e:
        print(f"Error updating inspiration {entry_id} for user {user_id}: {e}")
        return False


def delete_inspiration(user_id: str, entry_id: str) -> bool:
    """
    删除指定灵感条目
    """
    inspiration_file = get_user_inspiration_path(user_id)
    if not os.path.exists(inspiration_file):
        return False
    
    try:
        entries = []
        with open(inspiration_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        entry = json.loads(line)
                        if entry.get("id") != entry_id:
                            entries.append(entry)
                    except json.JSONDecodeError:
                        continue
        
        with open(inspiration_file, "w", encoding="utf-8") as f:
            for entry in entries:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        
        return True
        
    except Exception as e:
        print(f"Error deleting inspiration {entry_id} for user {user_id}: {e}")
        return False


def mark_as_read(user_id: str, entry_id: str) -> bool:
    """将灵感标记为已读"""
    return update_inspiration(user_id, entry_id, {"status": "read"})


def get_unread_count(user_id: str) -> int:
    """获取未读灵感数量"""
    inspirations = get_all_inspirations(user_id)
    return sum(1 for i in inspirations if i.get("status") == "unread")
