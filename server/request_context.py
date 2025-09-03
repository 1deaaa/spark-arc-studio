from contextvars import ContextVar
from functools import wraps
from typing import Optional
from flask import request

# Global context for current request (Agent/tools can read these)
current_user_id: ContextVar[Optional[str]] = ContextVar('current_user_id', default=None)
current_project_name: ContextVar[Optional[str]] = ContextVar('current_project_name', default=None)

def set_agent_context(user_id: str, project_name: str) -> None:
    """Set context for tools when running outside of a Flask request (e.g., Agent pipelines)."""
    current_user_id.set(user_id)
    current_project_name.set(project_name)


def _extract_project_name() -> Optional[str]:
    # Prefer query string first (SSE, GET), then JSON body
    pn = request.args.get('projectName') or request.args.get('project_name')
    if pn:
        return pn
    try:
        body = request.get_json(silent=True) or {}
        pn = body.get('projectName') or body.get('project_name')
        return pn
    except Exception:
        return None


def get_current_info(fn):
    """Decorator: populate current_user_id/current_project_name for the request.
    Use on routes that need uid/project context so tools can read them implicitly.
    """
    @wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            uid = None
            # require_auth should have set request.current_user
            cu = getattr(request, 'current_user', None)
            if isinstance(cu, dict):
                uid = str(cu.get('user_id') or cu.get('id') or '') or None
            if uid:
                current_user_id.set(uid)
            pn = _extract_project_name()
            if pn:
                current_project_name.set(pn)
        except Exception:
            # Do not block the route if context injection fails
            pass
        return fn(*args, **kwargs)
    return wrapper
