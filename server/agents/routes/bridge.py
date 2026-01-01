"""
Bridge API - 场景衔接
"""

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse
import json

from core.auth import get_current_user
from core.request_context import current_project_name, set_agent_context

from agents import ScriptwriterAgent

from .schemas import BridgeRequest, _load_worldview_and_roles

bridge_router = APIRouter()


@bridge_router.post('/api/bridge/generate/stream')
async def bridge_generate_stream(data: BridgeRequest, user: dict = Depends(get_current_user)):
    """生成场景衔接（流式输出）"""
    user_id = str(user['user_id'])
    project_name = current_project_name.get() or data.projectName
    if not project_name:
        return JSONResponse(status_code=400, content={'error': '缺少项目名称'})

    set_agent_context(user_id, project_name)
    
    wv = _load_worldview_and_roles(user_id, project_name)
    worldview = wv.get('worldview', '')
    roles = wv.get('roles', '')

    agent = ScriptwriterAgent(user_id=user_id)

    async def generate():
        try:
            for chunk in agent.stream_bridge(
                prev_scene_content=data.prev_scene_content,
                next_scene_content=data.next_scene_content,
                guidance=data.guidance,
                worldview=worldview,
                roles=roles,
            ):
                yield {"event": "chunk", "data": json.dumps({"text": chunk}, ensure_ascii=False)}
            yield {"event": "done", "data": "{}"}
        except Exception as e:
            yield {"event": "error", "data": json.dumps({"error": str(e)}, ensure_ascii=False)}

    return EventSourceResponse(generate())
