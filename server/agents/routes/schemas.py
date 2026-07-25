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
    exclusive 为 True 时执行排他绑定：绑定新灵感的同时解绑该项目下的旧灵感。
    """
    projectName: str
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


def _get_history_dir(user_id: str, project_name: str) -> str:
    return os.path.join(get_project_path(user_id, project_name), 'history')


def _ensure_history_dir(user_id: str, project_name: str) -> str:
    history_dir = _get_history_dir(user_id, project_name)
    os.makedirs(history_dir, exist_ok=True)
    return history_dir


def _save_outline_to_history(user_id: str, project_name: str, markup_text: str) -> None:
    """保存大纲 Markup 文本到历史记录"""
    from story.outline_parser import parse_outline_markup
    history_dir = _ensure_history_dir(user_id, project_name)
    history_file = os.path.join(history_dir, 'outline_history.json')

    history: List[Dict[str, Any]] = []
    if os.path.exists(history_file):
        with open(history_file, 'r', encoding='utf-8') as f:
            history = json.load(f)

    # 解析 Markup 以提取标题和节点数用于索引
    parsed = parse_outline_markup(markup_text)
    entry = {
        "id": len(history) + 1,
        "timestamp": datetime.now().isoformat(),
        "title": parsed.get('title', '未命名大纲'),
        "nodeCount": len(parsed.get('nodes', [])),
        "markup": markup_text
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
    from agents.language_policy import get_current_locale
    if not targets:
        return ""
    name_map = {a.get("key"): a.get("name") for a in get_agent_registry(get_current_locale())}
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


def _save_project_markup(user_id: str, project_name: str, filename: str, markup_text: str) -> None:
    """通用纯文本写入：将 markup_text 写入项目目录下的指定文件名"""
    filepath = os.path.join(get_project_path(user_id, project_name), filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(markup_text)


def _save_project_outline(user_id: str, project_name: str, markup_text: str) -> None:
    """保存大纲到项目文件（Markup 纯文本）"""
    _save_project_markup(user_id, project_name, '大纲.txt', markup_text)


def _save_project_synopsis(user_id: str, project_name: str, markup_text: str) -> None:
    """保存梗概到项目文件（Markup 纯文本）"""
    _save_project_markup(user_id, project_name, '梗概.txt', markup_text)


def _save_project_beat_sheet(user_id: str, project_name: str, markup_text: str) -> None:
    """保存节拍表到项目文件（Markup 纯文本）"""
    _save_project_markup(user_id, project_name, '节拍表.txt', markup_text)


# ==================== LLM 错误码四语映射 ====================

# 每条映射格式: (匹配函数, {locale: 友好提示})
# 匹配函数接收原始错误消息(小写)，返回 True 表示命中


def _llm_error_mappings() -> list:
    """返回 LLM 常见错误码的四语友好提示映射表。"""
    return [
        # 401 / authentication_error / auth_unavailable → 鉴权失败
        (
            lambda m: "401" in m or "authentication_error" in m or "auth_unavailable" in m or "invalid_api_key" in m or "invalid x-api-key" in m,
            {
                "zh-CN": "鉴权失败，请检查 API 密钥是否正确填写、是否已过期或被撤销。",
                "en-US": "Authentication failed. Please check if the API key is correct, expired, or revoked.",
                "ja-JP": "認証に失敗しました。API キーが正しく設定されているか、有効期限切れや取り消されていないかご確認ください。",
                "ko-KR": "인증에 실패했습니다. API 키가 올바르게 입력되었는지, 만료되었거나 취소되었는지 확인해 주세요.",
            },
            "401",
        ),
        # 只有提供商明确返回内容安全标记时才归类为内容审计，不能用通用 400 猜测。
        (
            lambda m: (
                "content_filter" in m
                or "content_policy" in m
                or "moderation_blocked" in m
                or "prohibited content" in m
                or ("safety" in m and ("refused" in m or "blocked" in m))
            ),
            {
                "zh-CN": "请求因内容安全策略被提供商拒绝。请根据原始信息检查提示词或输入内容。",
                "en-US": "The provider rejected the request under its content safety policy. Check the prompt or input against the original error details.",
                "ja-JP": "コンテンツ安全ポリシーにより、プロバイダがリクエストを拒否しました。元のエラー情報をもとにプロンプトまたは入力内容をご確認ください。",
                "ko-KR": "콘텐츠 안전 정책에 따라 제공업체가 요청을 거부했습니다. 원본 오류 정보를 바탕으로 프롬프트 또는 입력 내용을 확인해 주세요.",
            },
            "content_policy",
        ),
        # 严格 OpenAI 兼容实现常把工具或结构化输出 Schema 错误返回为 400。
        (
            lambda m: (
                "schema validation" in m
                or "standard_violation" in m
                or "invalid request content" in m
                or ("required" in m and "array" in m)
                or ("invalid-argument" in m and "schema" in m)
            ),
            {
                "zh-CN": "请求参数未通过提供商的 Schema 校验。请检查工具定义、结构化输出、Extra Body 和厂商特定参数是否符合该端点要求。",
                "en-US": "The request failed the provider's schema validation. Check tool definitions, structured output, Extra Body, and provider-specific parameters for this endpoint.",
                "ja-JP": "リクエストパラメータがプロバイダの Schema 検証に失敗しました。ツール定義、構造化出力、Extra Body、プロバイダ固有パラメータをご確認ください。",
                "ko-KR": "요청 매개변수가 제공업체의 Schema 검증을 통과하지 못했습니다. 도구 정의, 구조화 출력, Extra Body 및 제공업체별 매개변수를 확인해 주세요.",
            },
            "schema_validation",
        ),
        # 429 / rate_limit_error → 请求频率限制
        (
            lambda m: "429" in m or "rate_limit" in m or "too_many_requests" in m or "quota_exceeded" in m,
            {
                "zh-CN": "请求过于频繁，已触发提供商速率限制。请等待片刻后重试，或检查您的套餐配额。",
                "en-US": "Too many requests. Rate limit reached. Please wait a moment and retry, or check your plan quota.",
                "ja-JP": "リクエストが多すぎます。レート制限に達しました。しばらく待ってから再試行するか、プランの割り当てをご確認ください。",
                "ko-KR": "요청이 지나치게 빈번하여 제공업체의 속도 제한에 도달했습니다. 잠시 후 다시 시도하거나 요금제 할당량을 확인해 주세요.",
            },
            "429",
        ),
        # 404 + model → 模型不存在
        (
            lambda m: "404" in m and "model" in m,
            {
                "zh-CN": "模型不存在或无法访问。请检查模型名称是否拼写正确，或该模型是否已下线。",
                "en-US": "Model not found or inaccessible. Please verify the model name spelling, or check if the model has been deprecated.",
                "ja-JP": "モデルが存在しないかアクセスできません。モデル名のスペルや、モデルが非公開になっていないかご確認ください。",
                "ko-KR": "모델이 존재하지 않거나 액세스할 수 없습니다. 모델 이름의 철자가 올바른지, 혹은 모델 서비스가 종료되었는지 확인해 주세요.",
            },
            "404",
        ),
        # 500 / internal_server_error → 提供商内部错误
        (
            lambda m: "500" in m or "internal_server_error" in m,
            {
                "zh-CN": "模型提供商内部错误。这通常是提供商侧的临时故障，请稍后重试。",
                "en-US": "Internal server error from the model provider. This is usually a temporary issue on their side. Please retry later.",
                "ja-JP": "モデルプロバイダの内部エラーです。プロバイダ側の一時的な障害であることが多いです。後ほど再試行してください。",
                "ko-KR": "모델 제공업체의 내부 서버 오류입니다. 이는 대개 제공업체 측의 일시적인 장애이므로 나중에 다시 시도해 주세요.",
            },
            "500",
        ),
        # 503 / service_unavailable → 服务不可用
        (
            lambda m: "503" in m or "service_unavailable" in m,
            {
                "zh-CN": "模型提供商服务不可用，通常是由于过载或维护中。请稍后再试。",
                "en-US": "Model provider service unavailable, usually due to overload or maintenance. Please try again later.",
                "ja-JP": "モデルプロバイダのサービスが利用できません。過負荷やメンテナンス中のことが多いです。後ほど再試行してください。",
                "ko-KR": "모델 제공업체 서비스를 이용할 수 없습니다. 대개 서버 과부하 또는 점검 중이므로 나중에 다시 시도해 주세요.",
            },
            "503",
        ),
        # context_length_exceeded / max_context → 上下文超限
        (
            lambda m: "context_length" in m or "max_context" in m or "token_limit" in m or "maximum context" in m,
            {
                "zh-CN": "上下文长度超出模型限制。请尝试缩短输入内容或切换到更大上下文窗口的模型。",
                "en-US": "Context length exceeds model limit. Please try shortening the input or switching to a model with a larger context window.",
                "ja-JP": "コンテキスト長がモデルの制限を超えています。入力を短くするか、より大きなコンテキストウィンドウを持つモデルに切り替えてください。",
                "ko-KR": "컨텍스트 길이가 모델 제한을 초과했습니다. 입력 내용을 줄이거나 더 큰 컨텍스트 창을 지원하는 모델로 전환해 주세요.",
            },
            "context_length",
        ),
        # insufficient_quota → 额度不足
        (
            lambda m: "insufficient_quota" in m or "billing_hard_limit" in m or "quota_exceeded" in m,
            {
                "zh-CN": "API 账户额度不足。请检查您的提供商账户余额或配额。",
                "en-US": "Insufficient API quota. Please check your provider account balance or quota.",
                "ja-JP": "API アカウントのクォータが不足しています。プロバイダのアカウント残高や割り当てをご確認ください。",
                "ko-KR": "API 계정의 잔액 또는 할당량이 부족합니다. 서비스 제공업체 계정의 잔액이나 쿼터를 확인해 주세요.",
            },
            "insufficient_quota",
        ),
        # 其余 400 只说明请求无效，不能臆测为内容审计。
        (
            lambda m: (
                "400" in m
                or "invalid_request_error" in m
                or "invalid argument" in m
                or "invalid-argument" in m
            ),
            {
                "zh-CN": "模型提供商认为请求无效。请根据原始信息检查模型名称、端点协议、工具或结构化输出 Schema、Extra Body 及厂商特定参数。",
                "en-US": "The model provider rejected the request as invalid. Check the model name, endpoint protocol, tool or structured-output schema, Extra Body, and provider-specific parameters against the original error.",
                "ja-JP": "モデルプロバイダがリクエストを無効と判断しました。元のエラー情報をもとに、モデル名、エンドポイントプロトコル、ツールまたは構造化出力の Schema、Extra Body、プロバイダ固有パラメータをご確認ください。",
                "ko-KR": "모델 제공업체가 요청을 유효하지 않은 것으로 판단했습니다. 원본 오류를 바탕으로 모델 이름, 엔드포인트 프로토콜, 도구 또는 구조화 출력 Schema, Extra Body 및 제공업체별 매개변수를 확인해 주세요.",
            },
            "invalid_request",
        ),
        # connection / timeout → 网络连接问题
        (
            lambda m: "timeout" in m or "connection" in m and ("refused" in m or "reset" in m or "timed out" in m),
            {
                "zh-CN": "网络连接异常（超时或拒绝）。请检查网络连接，或确认模型端点地址是否正确。",
                "en-US": "Network connection error (timeout or refused). Please check your network, or verify the model endpoint URL.",
                "ja-JP": "ネットワーク接続エラー（タイムアウトまたは拒否）。ネットワーク接続やモデルエンドポイントの URL をご確認ください。",
                "ko-KR": "네트워크 연결이 비정상적입니다(시간 초과 또는 거부). 네트워크 연결을 확인하거나 모델 엔드포인트 주소가 올바른지 확인해 주세요.",
            },
            "connection",
        ),
    ]


def format_ai_error(e: Exception) -> str:
    """将 AI 生成错误格式化为前端可直接展示的友好文本（四语），尾部附原始报错。"""
    from core.request_context import get_current_locale

    msg = " ".join(str(e).strip().split()) or e.__class__.__name__
    msg_lower = msg.lower()
    locale = get_current_locale()

    # 遍历错误码映射表，命中则返回四语友好提示 + 原始报错
    for matcher, translations, code_tag in _llm_error_mappings():
        if matcher(msg_lower):
            friendly = translations.get(locale, translations["zh-CN"])
            return f"{friendly} (原始信息: {msg})"

    # 默认返回原始错误信息
    return f"[错误: {msg}]"
