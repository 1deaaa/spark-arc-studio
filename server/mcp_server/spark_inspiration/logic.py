
"""
灵感系统核心逻辑

统一的灵感数据格式:
{
    "id": "uuid-string",
    "timestamp": "ISO-8601",
    "origin": "mcp",     # mcp / ui / legacy
    "source": "灵感原始文本（用户输入或AI生成的种子）",
    "content": "灵感工坊生成的扩展内容（可为空）",
    "tags": {
        "styles": [],      # 风格：治愈、悬疑、恐怖等
        "genres": [],      # 题材：校园、都市、冒险等
        "tones": [],       # 基调：现实主义、梦核等
        "worldviews": [],  # 世界观：架空、规则怪谈等
        "lengthHint": []   # 篇幅建议：短篇、中篇、长篇
    },
    "status": "unread",    # unread / read （未读仅对 origin=mcp 生效）
    "project_links": []    # 已绑定到的项目名列表，[] 表示草稿；一条灵感可供多个项目采用
}

隔离原则：
- 灵感存储在用户级别（非项目级别），跨项目复用
- AI 上下文注入仅看 project_links 命中当前项目的条目（草稿不进 prompt）
- 草稿条目仅对用户可见，需用户主动绑定到项目才会被 Agent 感知
"""

import os
import json
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
from contextvars import ContextVar

# 列表过滤范围：
#   all      → 返回全部条目
#   project  → 返回 project_links 命中指定项目的条目
#   drafts   → 返回 project_links 为空的条目（即未绑定到任何项目的草稿）
INSPIRATION_SCOPE_ALL = "all"
INSPIRATION_SCOPE_PROJECT = "project"
INSPIRATION_SCOPE_DRAFTS = "drafts"
VALID_INSPIRATION_SCOPES = {INSPIRATION_SCOPE_ALL, INSPIRATION_SCOPE_PROJECT, INSPIRATION_SCOPE_DRAFTS}

# ContextVar to store the current user_id for the request
current_user_id: ContextVar[Optional[str]] = ContextVar("current_user_id", default=None)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
USERDATA_ROOT = os.path.join(BASE_DIR, "_userdata")


def get_user_inspiration_path(user_id: str) -> str:
    """获取用户的全局灵感文件路径"""
    return os.path.join(USERDATA_ROOT, f"uid_{user_id}", "inspirations", "inspirations.jsonl")


def ensure_user_dir(user_id: str):
    """确保用户数据目录存在"""
    path = os.path.dirname(get_user_inspiration_path(user_id))
    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)


def save_inspiration(
    source: str,
    content: str = "",
    tags: Optional[Dict[str, List[str]]] = None,
    origin: str = "ui"
) -> Dict[str, Any]:
    """
    保存新的灵感条目到用户的全局灵感库。
    
    Args:
        source: 灵感原始文本（用户输入或AI生成的种子）
        content: 灵感工坊生成的扩展内容（可为空，待后续生成）
        tags: 四维标签 {"styles": [], "genres": [], "tones": [], "worldviews": []}
        origin: 条目来源标记。
            - ui: 页面手动创建或页面手动扩写产生的条目，默认视为已读
            - mcp: 通过 MCP 捕获进入灵感库的条目，默认视为未读
            - legacy: 老版本历史数据补标记，表示该条目最初没有来源字段
    
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
            "worldviews": [],
            "lengthHint": []
        }
        if tags:
            for key in normalized_tags:
                if key in tags and isinstance(tags[key], list):
                    normalized_tags[key] = tags[key]
        
        # origin 是“来源语义字段”，不是展示字段：
        # - mcp: 用于驱动未读提醒与 MCP 侧列表逻辑
        # - ui: 表示来自页面或普通交互，不参与未读提醒
        # - legacy: 历史兼容值，表示旧数据在补齐来源字段后的状态
        # 仅 MCP 写入的条目默认 unread；其他来源默认 read（不产生未读提示）
        normalized_origin = (origin or "ui").strip().lower()
        if normalized_origin not in {"mcp", "ui", "legacy"}:
            normalized_origin = "ui"

        # project_links：写入侧默认空数组（即草稿）。
        # 这里**不**自动绑定到“当前项目”，避免随手记的灵感被静默归档。
        # 用户在前端或工具侧显式调用 bind 才会写入项目名。
        entry = {
            "id": entry_id,
            "timestamp": timestamp,
            "origin": normalized_origin,
            "source": source,
            "content": content,
            "tags": normalized_tags,
            "status": "unread" if normalized_origin == "mcp" else "read",
            "project_links": [],
        }
        
        with open(inspiration_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            
        return {"success": True, "id": entry_id, "message": "灵感已捕获"}
        
    except Exception as e:
        print(f"Error saving inspiration for user {user_id}: {e}")
        return {"success": False, "error": str(e)}


def _normalize_project_links(value: Any) -> List[str]:
    """把任意输入规范化为去重后的项目名列表。"""
    if not isinstance(value, list):
        return []
    seen: set[str] = set()
    cleaned: List[str] = []
    for item in value:
        if not isinstance(item, str):
            continue
        name = item.strip()
        if not name or name in seen:
            continue
        seen.add(name)
        cleaned.append(name)
    return cleaned


def _ensure_entry_defaults(entry: Dict[str, Any]) -> Dict[str, Any]:
    """为单条灵感条目补齐新字段默认值，保持旧数据向后兼容。
    
    历史数据没有 origin 字段，统一标为 legacy 并视为草稿（project_links=[]）。
    """
    if not isinstance(entry, dict):
        return entry
    if "origin" not in entry:
        entry["origin"] = "legacy"
    entry["project_links"] = _normalize_project_links(entry.get("project_links"))
    return entry


def get_all_inspirations(
    user_id: str,
    project_name: Optional[str] = None,
    scope: str = INSPIRATION_SCOPE_ALL,
) -> List[Dict[str, Any]]:
    """
    获取用户的所有灵感（按时间倒序）。

    Args:
        user_id: 用户 ID
        project_name: 仅在 scope='project' 时生效；指定要过滤的项目名
        scope: 过滤范围，必须是 INSPIRATION_SCOPE_* 常量之一
            - all：全部条目（默认，保持向后兼容）
            - project：仅返回 project_links 命中 project_name 的条目
            - drafts：仅返回未绑定任何项目的草稿
    """
    results: List[Dict[str, Any]] = []
    inspiration_file = get_user_inspiration_path(user_id)

    if not os.path.exists(inspiration_file):
        return results

    normalized_scope = (scope or INSPIRATION_SCOPE_ALL).strip().lower()
    if normalized_scope not in VALID_INSPIRATION_SCOPES:
        normalized_scope = INSPIRATION_SCOPE_ALL

    try:
        with open(inspiration_file, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    entry = json.loads(line)
                    if not isinstance(entry, dict):
                        continue
                    _ensure_entry_defaults(entry)
                    results.append(entry)
                except json.JSONDecodeError:
                    continue
        # 按时间倒序
        results.reverse()
    except Exception as e:
        print(f"Error reading inspirations for user {user_id}: {e}")
        return results

    if normalized_scope == INSPIRATION_SCOPE_DRAFTS:
        return [item for item in results if not item.get("project_links")]

    if normalized_scope == INSPIRATION_SCOPE_PROJECT:
        target = (project_name or "").strip()
        if not target:
            # scope=project 但未给出项目名，按草稿语义返回空列表，避免误导调用方
            return []
        return [
            item
            for item in results
            if isinstance(item.get("project_links"), list)
            and target in item["project_links"]
        ]

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
                    if key in ["content", "tags", "status", "source"]:
                        entry[key] = value
                    elif key == "project_links":
                        entry["project_links"] = _normalize_project_links(value)
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
    # 未读提示只对 MCP 生成的灵感生效
    return sum(
        1
        for i in inspirations
        if i.get("origin") == "mcp" and i.get("status") == "unread"
    )


# ========== 项目当前灵感关联 ==========
# 设计原则：
# 1. 草稿优先：写入侧不自动绑定，避免随手记的灵感静默归档到当前项目；
# 2. 用户主动：仅在用户/AI 显式调用 bind 时建立关联；
# 3. 基数约束：一条灵感可被多个项目采用，但每个项目只保留一条当前灵感；
# 4. 删除自我修复：项目删除/重命名时同步清理 / 替换 project_links 中的引用，
#    避免出现“鬼绑定”——指向已不存在的项目的灵感。


def _rewrite_inspiration_file(
    inspiration_file: str,
    transform,
) -> int:
    """通用：读取整个 jsonl，逐条让 transform 决定是否更新，最后回写。
    
    Args:
        transform: callable(entry) -> bool，返回 True 表示该条被修改
    Returns:
        被修改的条目数量；若文件不存在或读失败，返回 -1
    """
    if not os.path.exists(inspiration_file):
        return -1

    entries: List[Dict[str, Any]] = []
    try:
        with open(inspiration_file, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except Exception as e:
        print(f"Error reading inspirations file {inspiration_file}: {e}")
        return -1

    changed = 0
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        _ensure_entry_defaults(entry)
        if transform(entry):
            changed += 1

    if changed > 0:
        try:
            with open(inspiration_file, "w", encoding="utf-8") as f:
                for entry in entries:
                    f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as e:
            print(f"Error writing inspirations file {inspiration_file}: {e}")
            return -1

    return changed


def bind_inspiration_to_project(user_id: str, entry_id: str, project_name: str) -> bool:
    """低级兼容函数：向灵感追加项目引用。

    业务入口必须使用 activate_inspiration_for_project，以维持一个项目一条当前灵感。
    """
    project_name = (project_name or "").strip()
    if not entry_id or not project_name:
        return False

    inspiration_file = get_user_inspiration_path(user_id)
    if not os.path.exists(inspiration_file):
        return False

    found = {"value": False}

    def _bind(entry: Dict[str, Any]) -> bool:
        if entry.get("id") != entry_id:
            return False
        found["value"] = True
        links = list(entry.get("project_links") or [])
        if project_name in links:
            return False  # 已绑定，无需写回（幂等）
        links.append(project_name)
        entry["project_links"] = _normalize_project_links(links)
        return True

    changed = _rewrite_inspiration_file(inspiration_file, _bind)
    return found["value"] and changed >= 0


def activate_inspiration_for_project(user_id: str, entry_id: str, project_name: str) -> Dict[str, Any]:
    """将灵感设为项目当前灵感，同时移除该项目对其他灵感的引用。

    语义约束：
    - 一条灵感可以绑定到多个项目
    - 一个项目同一时刻只能有一个当前灵感
    - 激活只调整当前项目的归属，不会移除目标灵感已绑定的其他项目

    Returns:
        {"success": bool, "unbound_ids": [...]}  unbound_ids 是被解绑的旧灵感 ID 列表
    """
    project_name = (project_name or "").strip()
    if not entry_id or not project_name:
        return {"success": False, "unbound_ids": []}

    inspiration_file = get_user_inspiration_path(user_id)
    if not os.path.exists(inspiration_file):
        return {"success": False, "unbound_ids": []}

    unbound_ids: List[str] = []
    found = {"value": False}

    def _activate(entry: Dict[str, Any]) -> bool:
        links = list(entry.get("project_links") or [])
        eid = entry.get("id", "")

        if eid == entry_id:
            found["value"] = True
            # 目标灵感：确保 project_name 在 links 中
            if project_name in links:
                return False  # 已绑定，无需写回
            links.append(project_name)
            entry["project_links"] = _normalize_project_links(links)
            return True
        else:
            # 其他灵感：如果绑定了同一项目，则解绑
            if project_name not in links:
                return False
            entry["project_links"] = [name for name in links if name != project_name]
            unbound_ids.append(eid)
            return True

    changed = _rewrite_inspiration_file(inspiration_file, _activate)
    return {"success": found["value"] and changed >= 0, "unbound_ids": unbound_ids}


def bind_inspiration_exclusive(user_id: str, entry_id: str, project_name: str) -> Dict[str, Any]:
    """兼容旧调用名；新代码统一使用 activate_inspiration_for_project。"""
    return activate_inspiration_for_project(user_id, entry_id, project_name)


def unbind_inspiration_from_project(user_id: str, entry_id: str, project_name: str) -> bool:
    """将灵感条目从指定项目解绑（解绑后变成草稿或仍属于其他项目）。"""
    project_name = (project_name or "").strip()
    if not entry_id or not project_name:
        return False

    inspiration_file = get_user_inspiration_path(user_id)
    if not os.path.exists(inspiration_file):
        return False

    found = {"value": False}

    def _unbind(entry: Dict[str, Any]) -> bool:
        if entry.get("id") != entry_id:
            return False
        found["value"] = True
        links = list(entry.get("project_links") or [])
        if project_name not in links:
            return False  # 本就未绑定，无需写回
        entry["project_links"] = [name for name in links if name != project_name]
        return True

    changed = _rewrite_inspiration_file(inspiration_file, _unbind)
    return found["value"] and changed >= 0


def cleanup_project_from_all_inspirations(user_id: str, project_name: str) -> int:
    """项目删除时调用：从所有灵感的 project_links 中移除该项目名。
    
    返回受影响的条目数量；项目本就无任何灵感引用时返回 0。
    """
    project_name = (project_name or "").strip()
    if not project_name:
        return 0

    inspiration_file = get_user_inspiration_path(user_id)
    if not os.path.exists(inspiration_file):
        return 0

    def _cleanup(entry: Dict[str, Any]) -> bool:
        links = list(entry.get("project_links") or [])
        if project_name not in links:
            return False
        entry["project_links"] = [name for name in links if name != project_name]
        return True

    changed = _rewrite_inspiration_file(inspiration_file, _cleanup)
    return max(changed, 0)


def rename_project_in_all_inspirations(user_id: str, old_name: str, new_name: str) -> int:
    """项目重命名时调用：把所有灵感 project_links 中的 old_name 替换为 new_name。"""
    old_name = (old_name or "").strip()
    new_name = (new_name or "").strip()
    if not old_name or not new_name or old_name == new_name:
        return 0

    inspiration_file = get_user_inspiration_path(user_id)
    if not os.path.exists(inspiration_file):
        return 0

    def _rename(entry: Dict[str, Any]) -> bool:
        links = list(entry.get("project_links") or [])
        if old_name not in links:
            return False
        # 替换：保持顺序，去重以兼容已经包含 new_name 的边界场景
        seen: set[str] = set()
        renamed: List[str] = []
        for name in links:
            target = new_name if name == old_name else name
            if target in seen:
                continue
            seen.add(target)
            renamed.append(target)
        entry["project_links"] = renamed
        return True

    changed = _rewrite_inspiration_file(inspiration_file, _rename)
    return max(changed, 0)


def get_inspirations_for_project(user_id: str, project_name: str) -> List[Dict[str, Any]]:
    """获取已绑定到指定项目的灵感条目（按时间倒序）。
    
    便捷函数：等价于 get_all_inspirations(user_id, project_name=..., scope='project')。
    AI 上下文注入主要走这条路径，避免草稿污染 prompt。
    """
    return get_all_inspirations(
        user_id,
        project_name=project_name,
        scope=INSPIRATION_SCOPE_PROJECT,
    )
