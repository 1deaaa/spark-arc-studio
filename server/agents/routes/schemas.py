"""
共享的 Pydantic 模型和辅助函数
"""

from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
import os
import json

from core.utils import get_project_path


# ==================== Pydantic Models ====================
class SingleNodeRequest(BaseModel):
    projectName: Optional[str] = None
    context: str = ""
    length: int = 100
    character_ids: List[int] = []


class MultiNodeRequest(BaseModel):
    projectName: Optional[str] = None
    context: str = ""
    guidance: str = ""
    character_ids: List[int] = []
    segment_count: int = 3
    current_file: str
    scene_name: str
    after_node_id: int
    last_node_text: str = ""
    confirm_continue: bool = False
    rewrite: bool = False  # 重写整个场景模式



class FeedbackRequest(BaseModel):
    user_input: str = ""
    projectName: Optional[str] = None
    context: str = ""
    last_content: str = ""


class CriticReviewRequest(BaseModel):
    projectName: Optional[str] = None
    context: str = ""
    guidance: str = ""
    script_nodes: List[Dict[str, Any]]


class AgentChatRequest(BaseModel):
    projectName: Optional[str] = None
    query: str


class ChatSendRequest(BaseModel):
    projectName: Optional[str] = None
    agentId: str
    contextKey: str = 'global'
    message: str
    activeContext: Optional[str] = None
    targets: Optional[List[str]] = None


class ChatHistoryRequest(BaseModel):
    projectName: Optional[str] = None
    agentId: str
    contextKey: str = 'global'
    limit: int = 50


class ChatClearRequest(BaseModel):
    projectName: Optional[str] = None
    agentId: str
    contextKey: str = 'global'


class ChatMessageDeleteRequest(BaseModel):
    projectName: Optional[str] = None
    messageId: int


class ChatMessageEditRequest(BaseModel):
    projectName: Optional[str] = None
    agentId: str
    contextKey: str = 'global'
    messageId: int
    content: str
    activeContext: Optional[str] = None


class BridgeRequest(BaseModel):
    projectName: Optional[str] = None
    prev_scene_content: str
    next_scene_content: str
    guidance: str = ""


class StyleAnalysisRequest(BaseModel):
    projectName: Optional[str] = None
    text: str
    author_name: str = "Unknown"


class StructureRequest(BaseModel):
    projectName: Optional[str] = None
    content: str


class OutlineRequest(BaseModel):
    projectName: Optional[str] = None
    outline: Dict[str, Any]


class LorebookRequest(BaseModel):
    projectName: Optional[str] = None
    fileName: str
    content: str


class WorldviewRequest(BaseModel):
    projectName: Optional[str] = None
    content: str


class MuseRequest(BaseModel):
    projectName: Optional[str] = None  # 保留兼容性，但不再使用
    inspiration: str
    style: Optional[str] = None
    genres: Optional[List[str]] = None
    tones: Optional[List[str]] = None
    worldviews: Optional[List[str]] = None
    lengthHint: Optional[str] = None
    inspirationId: Optional[str] = None  # 关联的灵感ID，用于更新已有灵感


class InspirationCreateRequest(BaseModel):
    """创建新灵感的请求"""
    source: str  # 灵感原始文本
    content: Optional[str] = None  # 扩展内容（可选）
    tags: Optional[Dict[str, List[str]]] = None  # 四维标签


class InspirationUpdateRequest(BaseModel):
    """更新灵感的请求"""
    content: Optional[str] = None
    tags: Optional[Dict[str, List[str]]] = None
    status: Optional[str] = None  # "unread" / "read"


class SynopsisRequest(BaseModel):
    projectName: Optional[str] = None
    logline: str
    guidance: str = ""


class BeatSheetRequest(BaseModel):
    projectName: Optional[str] = None
    synopsis: str
    guidance: str = ""


class WorldviewGenerateRequest(BaseModel):
    seed: str
    projectName: Optional[str] = None
    reset: bool = False


class LorebookResetRequest(BaseModel):
    projectName: str


class SynopsisSaveRequest(BaseModel):
    projectName: str
    synopsis: Dict[str, Any]


class BeatSheetSaveRequest(BaseModel):
    projectName: str
    beatSheet: Dict[str, Any]


class CharacterSettingsCreate(BaseModel):
    projectName: Optional[str] = None
    name: str = "新角色"


class CharacterSettingsSave(BaseModel):
    projectName: Optional[str] = None
    id: int
    content: str = ""


class CharacterSettingsRename(BaseModel):
    projectName: Optional[str] = None
    id: int
    newName: str


class CharacterSettingsDelete(BaseModel):
    projectName: Optional[str] = None
    id: int


class StyleApplyRequest(BaseModel):
    styleName: str
    projectName: str


class BeaconToggleRequest(BaseModel):
    agent_id: str
    active: bool


class CustomTagsRequest(BaseModel):
    styles: Optional[List[str]] = []
    genres: Optional[List[str]] = []


# ==================== 辅助函数 ====================
def _load_worldview_and_roles(user_id: str, project_name: Optional[str]) -> Dict[str, str]:
    if not project_name:
        return {"worldview": "", "roles": ""}
    project_path = get_project_path(user_id, project_name)

    worldview = ""
    worldview_path = os.path.join(project_path, '世界观.txt')
    if os.path.exists(worldview_path):
        with open(worldview_path, 'r', encoding='utf-8') as f:
            worldview = f.read()

    roles = ""
    roles_path = os.path.join(project_path, '角色设定.txt')
    if os.path.exists(roles_path):
        try:
            with open(roles_path, 'r', encoding='utf-8') as f:
                all_roles = json.load(f)
                if isinstance(all_roles, list):
                    roles = "\n".join([f"- {r.get('name', '')}: {r.get('settings', '')}" for r in all_roles])
        except Exception:
            with open(roles_path, 'r', encoding='utf-8') as f:
                roles = f.read()

    return {"worldview": worldview, "roles": roles}


def _get_history_dir(user_id: str, project_name: str) -> str:
    return os.path.join(get_project_path(user_id, project_name), 'history')


def _ensure_history_dir(user_id: str, project_name: str) -> str:
    history_dir = _get_history_dir(user_id, project_name)
    os.makedirs(history_dir, exist_ok=True)
    return history_dir


def _save_outline_to_history(user_id: str, project_name: str, outline: Dict[str, Any]) -> None:
    history_dir = _ensure_history_dir(user_id, project_name)
    history_file = os.path.join(history_dir, 'outline_history.json')

    history: List[Dict[str, Any]] = []
    if os.path.exists(history_file):
        with open(history_file, 'r', encoding='utf-8') as f:
            history = json.load(f)

    entry = {
        "id": len(history) + 1,
        "timestamp": datetime.now().isoformat(),
        "title": outline.get('title', '未命名大纲'),
        "nodeCount": len(outline.get('nodes', [])),
        "outline": outline
    }
    history.insert(0, entry)
    history = history[:20]

    with open(history_file, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)




def _load_worldview_and_characters(user_id: str, project_name: str) -> Dict[str, Any]:
    worldview = ""
    characters: List[Dict[str, Any]] = []
    project_path = get_project_path(user_id, project_name)

    worldview_path = os.path.join(project_path, 'worldview.txt')
    if os.path.exists(worldview_path):
        with open(worldview_path, 'r', encoding='utf-8') as f:
            worldview = f.read()

    chr_bind_path = os.path.join(project_path, 'chr', 'chr.bind')
    if os.path.exists(chr_bind_path):
        with open(chr_bind_path, 'r', encoding='utf-8') as f:
            chr_data = json.load(f)
            for chr_id, info in chr_data.items():
                if isinstance(info, dict):
                    characters.append({'id': int(chr_id), 'name': info.get('name', ''), 'desc': info.get('desc', '')})
                else:
                    characters.append({'id': int(chr_id), 'name': str(info), 'desc': ''})

    return {"worldview": worldview, "characters": characters}


def _load_project_outline_text(user_id: str, project_name: str) -> str:
    try:
        outline_path = os.path.join(get_project_path(user_id, project_name), 'outline.json')
        if not os.path.exists(outline_path):
            return ''
        with open(outline_path, 'r', encoding='utf-8') as f:
            outline = json.load(f)
        return json.dumps(outline, ensure_ascii=False, indent=2)
    except Exception:
        return ''


def _resolve_effective_active_context(
    user_id: str,
    project_name: str,
    agent_id: str,
    active_context: Optional[str]
) -> Optional[str]:
    if active_context and isinstance(active_context, str) and active_context.strip():
        return active_context

    if agent_id in {'agent_director', 'agent_showrunner'}:
        outline_text = _load_project_outline_text(user_id, project_name)
        if outline_text:
            return f"### 当前项目大纲 (outline.json)\n{outline_text}"
    return active_context


def _format_targets(targets: List[str]) -> str:
    from agents.registry import get_agent_registry
    if not targets:
        return ""
    name_map = {a.get("key"): a.get("name") for a in get_agent_registry()}
    labels = [name_map.get(t, t) for t in targets]
    return "、".join(labels)


def _write_worldview(user_id: str, project_name: str, content: str) -> None:
    from core.utils import (
        get_project_worldview_path,
        ensure_project_worldview_and_character_settings,
        ensure_project_directory,
    )
    ensure_project_worldview_and_character_settings(user_id, project_name)
    worldview_path = get_project_worldview_path(user_id, project_name)
    ensure_project_directory(user_id, project_name)
    with open(worldview_path, 'w', encoding='utf-8') as f:
        f.write(content)


def _save_project_outline(user_id: str, project_name: str, outline: Dict[str, Any]) -> None:
    """保存大纲到项目文件"""
    outline_path = os.path.join(get_project_path(user_id, project_name), 'outline.json')
    with open(outline_path, 'w', encoding='utf-8') as f:
        json.dump(outline, f, ensure_ascii=False, indent=2)
