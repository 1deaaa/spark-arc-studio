"""
共享的 Pydantic 模型和辅助函数
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

from agents.error_formatting import format_ai_error
from agents.project_content import write_worldview as _write_worldview
from agents.structure_artifacts import (
    get_outline_history_dir as _get_history_dir,
    save_outline_to_history as _save_outline_to_history,
    save_project_beat_sheet as _save_project_beat_sheet,
    save_project_outline as _save_project_outline,
    save_project_synopsis as _save_project_synopsis,
)


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


class ChatMessageAttachmentRemoveRequest(BaseModel):
    projectName: Optional[str] = None
    messageId: int
    # 多附件场景下用于精确定位要移除的附件；不传时选择列表首项。
    attachmentId: Optional[str] = None


class ChatMessageEditRequest(BaseModel):
    projectName: Optional[str] = None
    agentId: str
    contextKey: str = 'global'
    messageId: int
    content: str
    activeContext: Optional[str] = None
    activeMeta: Optional[Dict[str, Any]] = None


class ChatTaskCancelRequest(BaseModel):
    projectName: Optional[str] = None
    agentId: str
    contextKey: str = 'global'


class ChatContextCompactRequest(BaseModel):
    projectName: Optional[str] = None
    agentId: str
    contextKey: str = 'global'
    targetTokens: int = 8000


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
    pov: Optional[str] = None
    lengthHint: Optional[str] = None
    inspirationId: Optional[str] = None  # 关联的灵感ID，用于更新已有灵感


class InspirationCreateRequest(BaseModel):
    """创建新灵感的请求"""
    source: str  # 灵感原始文本
    content: Optional[str] = None  # 扩展内容（可选）
    tags: Optional[Dict[str, List[str]]] = None  # 四维标签


class InspirationUpdateRequest(BaseModel):
    """更新灵感的请求"""
    source: Optional[str] = None
    content: Optional[str] = None
    tags: Optional[Dict[str, List[str]]] = None
    status: Optional[str] = None  # "unread" / "read"


class InspirationBindRequest(BaseModel):
    """灵感与项目绑定/解绑的请求体。

    project_name 必填：哪怕灵感库是用户级别的，绑定关系仍以项目名为粒度。
    当前所有绑定请求都会将该灵感设为项目当前灵感。
    activate / exclusive 仅保留用于兼容不同版本的客户端请求体。
    """
    projectName: str
    activate: bool = False
    exclusive: bool = False


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
    markup: str


class BeatSheetSaveRequest(BaseModel):
    projectName: str
    markup: str


class CharacterSettingsCreate(BaseModel):
    projectName: Optional[str] = None
    name: str = "新角色"
    content: Optional[str] = None


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


class CharacterRelationCreate(BaseModel):
    projectName: Optional[str] = None
    source: int
    target: int
    relation: str
    note: str = ""


class CharacterRelationUpdate(CharacterRelationCreate):
    pass


class StyleApplyRequest(BaseModel):
    styleId: str
    projectName: str
    applied: bool = True


class AgentSignalToggleRequest(BaseModel):
    agent_id: str
    active: bool


class CustomTagsRequest(BaseModel):
    styles: Optional[List[str]] = []
    genres: Optional[List[str]] = []
    tones: Optional[List[str]] = []
    worldviews: Optional[List[str]] = []


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
    from agents.language_policy import get_current_locale
    if not targets:
        return ""
    name_map = {a.get("key"): a.get("name") for a in get_agent_registry(get_current_locale())}
    labels = [name_map.get(t, t) for t in targets]
    return "、".join(labels)
