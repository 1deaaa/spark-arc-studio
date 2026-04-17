from contextvars import ContextVar, Token
from typing import Optional, Dict, Any

from fastapi import Request


def normalize_project_name(project_name: Optional[str]) -> Optional[str]:
    if project_name is None:
        return None
    if not isinstance(project_name, str):
        project_name = str(project_name)
    normalized = project_name.strip()
    if not normalized or normalized.lower() in {'null', 'undefined'}:
        return None
    return normalized


# 兼容旧内部调用名，后续新代码统一使用 normalize_project_name
_normalize_project_name = normalize_project_name


def resolve_project_name(*candidates: Optional[str]) -> Optional[str]:
    """按顺序返回第一个有效项目名。"""
    for candidate in candidates:
        normalized = normalize_project_name(candidate)
        if normalized:
            return normalized
    return None


def get_current_project_name() -> Optional[str]:
    """读取当前请求上下文里的项目名，并做规范化。"""
    return resolve_project_name(current_project_name.get())


# Global context for current request (Agent/tools can read these)
current_user_id: ContextVar[Optional[str]] = ContextVar('current_user_id', default=None)
current_project_name: ContextVar[Optional[str]] = ContextVar('current_project_name', default=None)
current_inspiration_id: ContextVar[Optional[str]] = ContextVar('current_inspiration_id', default=None)
current_agent_id: ContextVar[Optional[str]] = ContextVar('current_agent_id', default=None)
# 当前请求的输出格式上下文（如 'arc' / 'novel'）。
# 供 Agent 的 _get_tool_prompt_references 等方法按格式动态选择注入规范。
# 目前仅 ScriptwriterAgent 使用；若将来其他 Agent 也有双格式工具，可直接复用。
current_export_format: ContextVar[Optional[str]] = ContextVar('current_export_format', default=None)
current_response_locale: ContextVar[Optional[str]] = ContextVar('current_response_locale', default='zh-CN')


def normalize_response_locale(locale: Optional[str]) -> str:
    value = str(locale or '').strip()
    if not value:
        return 'zh-CN'

    lower = value.lower()
    if lower.startswith('zh'):
        return 'zh-CN'
    if lower.startswith('ja'):
        return 'ja-JP'
    if lower.startswith('en'):
        return 'en-US'

    return 'zh-CN'


def set_current_locale(locale: Optional[str]) -> Token:
    return current_response_locale.set(normalize_response_locale(locale))


def reset_current_locale(token: Token) -> None:
    current_response_locale.reset(token)


def get_current_locale() -> str:
    return normalize_response_locale(current_response_locale.get())


def get_current_agent_id() -> Optional[str]:
    """读取当前工具调用上下文里的 Agent ID。"""
    agent_id = current_agent_id.get()
    if agent_id is None:
        return None
    value = str(agent_id).strip()
    return value or None


def set_agent_context(user_id: str, project_name: str) -> None:
    """Set context for tools when running outside of a request (e.g., Agent pipelines)."""
    current_user_id.set(user_id)
    current_project_name.set(normalize_project_name(project_name))


async def extract_project_name(
    request: Request,
    path_params: Optional[Dict[str, Any]] = None,
    body: Optional[Dict[str, Any]] = None
) -> Optional[str]:
    """从多个来源提取项目名称。
    优先级: query -> path params -> form -> JSON body.
    """
    # 1) Query string (GET/SSE)
    pn = resolve_project_name(
        request.query_params.get('projectName'),
        request.query_params.get('project_name'),
    )
    if pn:
        return pn
    
    # 2) Path parameters
    if path_params:
        pn = resolve_project_name(
            path_params.get('project_name'),
            path_params.get('projectName'),
        )
        if pn:
            return pn
    
    # 3) Form data (multipart/form-data)
    try:
        content_type = request.headers.get('content-type', '')
        if 'multipart/form-data' in content_type or 'application/x-www-form-urlencoded' in content_type:
            form = await request.form()
            pn = resolve_project_name(form.get('projectName'), form.get('project_name'))
            if pn:
                return pn
    except Exception:
        pass
    
    # 4) JSON body (如果已经解析过则使用传入的body)
    if body:
        pn = resolve_project_name(body.get('projectName'), body.get('project_name'))
        if pn:
            return pn
    
    # 5) 尝试解析 JSON body
    try:
        json_body = await request.json()
        return resolve_project_name(
            json_body.get('projectName'),
            json_body.get('project_name'),
        )
    except Exception:
        return None


def set_current_context(user_id: Optional[str], project_name: Optional[str]) -> None:
    """设置当前请求的上下文信息。"""
    if user_id:
        current_user_id.set(user_id)
    normalized_project_name = normalize_project_name(project_name)
    if normalized_project_name:
        current_project_name.set(normalized_project_name)
    else:
        current_project_name.set(None)


def set_current_inspiration_context(inspiration_id: Optional[str]) -> None:
    """设置当前请求的灵感条目上下文。"""
    current_inspiration_id.set(str(inspiration_id) if inspiration_id else None)


def set_current_export_format(export_format: Optional[str]) -> None:
    """设置当前请求的输出格式上下文。

    目前支持 'arc'（互动剧本）和 'novel'（纯文学小说）两种值，
    无效值回退为 None（get_current_export_format 返回默认 'arc'）。
    若将来新增格式（如 'screenplay' 等），在此处白名单中追加即可。
    """
    value = (export_format or '').strip().lower()
    current_export_format.set(value if value in ('arc', 'novel') else None)


def get_current_export_format() -> str:
    """读取当前请求的输出格式，默认 'arc'。

    Agent 可在 _get_tool_prompt_references 等方法中调用此函数，
    根据返回值动态选择注入哪套提示词规范，避免格式间泄漏。
    """
    return current_export_format.get() or 'arc'
