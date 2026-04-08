"""
共享的 Pydantic 模型和辅助函数
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
import os
import json

from core.utils import get_project_path


# ==================== Pydantic Models ====================


class ScriptwriterComposeRequest(BaseModel):
    operation: str = "continue"
    mode: str = "multi-node"
    projectName: Optional[str] = None
    filePath: str = ""
    sceneName: str = ""
    nodeId: int = 0
    selectedCharacterIds: List[int] = []
    guidance: str = ""
    segmentCount: int = 3
    lastNodeText: str = ""
    context: str = ""
    confirmContinue: bool = False
    rewrite: bool = False
    length: int = 100
    prevScene: Optional[Dict[str, Any]] = None
    nextScene: Optional[Dict[str, Any]] = None
    pacing: str = "normal"
    mood: str = ""
    exportFormat: str = "arc"


class ScriptwriterFeedbackRequest(BaseModel):
    projectName: Optional[str] = None
    user_input: str = ""
    context: str = ""
    last_content: str = ""


class CriticReviewRequest(BaseModel):
    projectName: Optional[str] = None
    context: str = ""
    guidance: str = ""
    activeContext: Optional[str] = None
    script_nodes: List[Dict[str, Any]] = Field(default_factory=list)
    script_text: str = ""
    sceneName: str = ""
    filePath: str = ""
    exportFormat: str = "arc"


class AgentChatRequest(BaseModel):
    projectName: Optional[str] = None
    query: str


class ChatSendRequest(BaseModel):
    projectName: Optional[str] = None
    agentId: str
    contextKey: str = 'global'
    message: str
    activeContext: Optional[str] = None
    activeMeta: Optional[Dict[str, Any]] = None
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
    activeMeta: Optional[Dict[str, Any]] = None


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
    inspiration: Optional[str] = None
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
    style_profile: Optional[Any] = None
    lengthHint: Optional[str] = None


class BeatSheetRequest(BaseModel):
    projectName: Optional[str] = None
    synopsis: str
    guidance: str = ""
    lengthHint: Optional[str] = None


class WorldviewGenerateRequest(BaseModel):
    seed: str
    projectName: Optional[str] = None
    reset: bool = False
    lengthHint: Optional[str] = None


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


class AgentSignalToggleRequest(BaseModel):
    agent_id: str
    active: bool


class CustomTagsRequest(BaseModel):
    styles: Optional[List[str]] = []
    genres: Optional[List[str]] = []
    tones: Optional[List[str]] = []
    worldviews: Optional[List[str]] = []


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
def _resolve_effective_active_context(
    user_id: str,
    project_name: str,
    agent_id: str,
    active_context: Optional[str]
) -> Optional[str]:
    """
    解析并构建有效的 active_context。
    
    对于创作型 Agent，自动注入相关业务数据（灵感、大纲、场景、世界观、角色等）。
    """
    from agents.context_provider import AgentContextProvider
    
    # 如果前端已传入上下文，作为额外上下文处理
    extra_context = ""
    if active_context and isinstance(active_context, str) and active_context.strip():
        extra_context = active_context.strip()
    
    # 使用上下文提供器构建 Agent 专属上下文
    if project_name and agent_id:
        try:
            provider = AgentContextProvider(user_id, project_name)
            agent_context = provider.build_context_for_agent(agent_id, extra_context)
            if agent_context:
                return agent_context
        except Exception as e:
            print(f"[schemas] Error building agent context: {e}")

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


def format_ai_error(e: Exception) -> str:
    """将 AI 生成错误格式化为前端可直接展示的友好文本，并尽量保留原始报错。"""
    msg = " ".join(str(e).strip().split()) or e.__class__.__name__

    def with_raw(prefix: str) -> str:
        return f"{prefix} 原始信息: {msg}"

    # 检查常见的错误代码或关键字
    if "401" in msg or "authentication_error" in msg.lower():
        return with_raw("[错误: 鉴权失败，请检查密钥 (401)]")
    if "429" in msg or "rate_limit_error" in msg.lower():
        return with_raw("[错误: 请求过于频繁，请检查您的提供商限制 (429)]")
    if "404" in msg and "model" in msg.lower():
        return with_raw("[错误: 模型不存在或无法访问 (404)]")
    if "500" in msg:
        return with_raw("[错误: 模型提供商内部错误 (500)]")
    if "400" in msg:
        return with_raw("[错误: 模型提供商拦截了此请求，可能是触发了内容审计。请检查您的提示词是否合规。]")
    if "503" in msg:
        return with_raw("[错误: 模型提供商服务不可用，通常是由于过载导致。请稍后再试。]")
    # 默认返回原始错误信息
    return f"[错误: {msg}]"
