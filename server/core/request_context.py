"""请求上下文管理模块 - FastAPI 版本

提供 ContextVar 用于在异步请求中传递用户ID和项目名称上下文。
"""

from contextvars import ContextVar
from typing import Optional, Dict, Any

from fastapi import Request

# Global context for current request (Agent/tools can read these)
current_user_id: ContextVar[Optional[str]] = ContextVar('current_user_id', default=None)
current_project_name: ContextVar[Optional[str]] = ContextVar('current_project_name', default=None)


def set_agent_context(user_id: str, project_name: str) -> None:
    """Set context for tools when running outside of a request (e.g., Agent pipelines)."""
    current_user_id.set(user_id)
    current_project_name.set(project_name)


async def extract_project_name(
    request: Request,
    path_params: Optional[Dict[str, Any]] = None,
    body: Optional[Dict[str, Any]] = None
) -> Optional[str]:
    """从多个来源提取项目名称。
    优先级: query -> path params -> form -> JSON body.
    """
    # 1) Query string (GET/SSE)
    pn = request.query_params.get('projectName') or request.query_params.get('project_name')
    if pn:
        return pn
    
    # 2) Path parameters
    if path_params:
        pn = path_params.get('project_name') or path_params.get('projectName')
        if pn:
            return pn
    
    # 3) Form data (multipart/form-data)
    try:
        content_type = request.headers.get('content-type', '')
        if 'multipart/form-data' in content_type or 'application/x-www-form-urlencoded' in content_type:
            form = await request.form()
            pn = form.get('projectName') or form.get('project_name')
            if pn:
                return str(pn)
    except Exception:
        pass
    
    # 4) JSON body (如果已经解析过则使用传入的body)
    if body:
        pn = body.get('projectName') or body.get('project_name')
        if pn:
            return pn
    
    # 5) 尝试解析 JSON body
    try:
        json_body = await request.json()
        pn = json_body.get('projectName') or json_body.get('project_name')
        return pn
    except Exception:
        return None


def set_current_context(user_id: Optional[str], project_name: Optional[str]) -> None:
    """设置当前请求的上下文信息。"""
    if user_id:
        current_user_id.set(user_id)
    if project_name:
        current_project_name.set(project_name)
