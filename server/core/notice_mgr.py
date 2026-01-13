
import os
import json
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
NOTICES_FILE = os.path.join(DATA_DIR, "notices.json")

def ensure_data_dir():
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR, exist_ok=True)

def _load_notices() -> List[Dict[str, Any]]:
    ensure_data_dir()
    if not os.path.exists(NOTICES_FILE):
        # 兼容旧的 notice.md
        old_notice_path = os.path.join(BASE_DIR, "notice.md")
        if os.path.exists(old_notice_path):
            try:
                with open(old_notice_path, "r", encoding="utf-8") as f:
                    content = f.read()
                # 创建初始公告
                initial_notice = {
                    "id": str(uuid.uuid4()),
                    "content": content,
                    "timestamp": datetime.now().isoformat(),
                    "title": "系统公告 (迁移)"
                }
                _save_notices([initial_notice])
                return [initial_notice]
            except:
                return []
        return []
    
    try:
        with open(NOTICES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []

def _save_notices(notices: List[Dict[str, Any]]):
    ensure_data_dir()
    with open(NOTICES_FILE, "w", encoding="utf-8") as f:
        json.dump(notices, f, ensure_ascii=False, indent=2)

def get_notices() -> List[Dict[str, Any]]:
    """获取所有公告并按时间倒序排列"""
    notices = _load_notices()
    # 按照 timestamp 降序排列
    notices.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    return notices

def get_latest_notice() -> Optional[Dict[str, Any]]:
    """获取最新的一条公告"""
    notices = get_notices()
    return notices[0] if notices else None

def add_notice(title: str, content: str) -> Dict[str, Any]:
    """添加新公告"""
    notices = _load_notices()
    new_notice = {
        "id": str(uuid.uuid4()),
        "title": title,
        "content": content,
        "timestamp": datetime.now().isoformat()
    }
    notices.append(new_notice)
    _save_notices(notices)
    return new_notice

def update_notice(notice_id: str, title: str, content: str) -> bool:
    """更新公告"""
    notices = _load_notices()
    for notice in notices:
        if notice["id"] == notice_id:
            notice["title"] = title
            notice["content"] = content
            notice["timestamp"] = datetime.now().isoformat()
            _save_notices(notices)
            return True
    return False

def delete_notice(notice_id: str) -> bool:
    """删除公告"""
    notices = _load_notices()
    new_notices = [n for n in notices if n["id"] != notice_id]
    if len(new_notices) < len(notices):
        _save_notices(new_notices)
        return True
    return False
