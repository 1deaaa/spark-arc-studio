"""
Bridge API - 场景衔接

注意：为保持前端兼容性，保留旧版 /api/bridge/generate 和 /api/ai/bridge 端点
"""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse
from typing import List, Dict, Any, Optional
import json

from core.auth import get_current_user
from core.request_context import current_project_name, set_agent_context

from agents import ScriptwriterAgent
from agents.agent_style.utils import load_style_profile_from_file

from .schemas import BridgeRequest, _load_worldview_and_roles, _load_worldview_and_characters

bridge_router = APIRouter()


def _run_bridge_agent(
    user_id: str,
    prev_scene: Dict[str, Any],
    next_scene: Dict[str, Any],
    worldview: str = "",
    characters: Optional[List[Dict[str, Any]]] = None,
    pacing: str = "normal",
    mood: str = "",
    guidance: str = "",
    style_profile: object = None,
) -> Dict[str, Any]:
    writer = ScriptwriterAgent(user_id)
    return writer.bridge_scenes(
        prev_scene=prev_scene,
        next_scene=next_scene,
        worldview=worldview,
        characters=characters or [],
        pacing=pacing,
        mood=mood,
        guidance=guidance,
        style_profile=style_profile,
    )


# ==================== 旧版端点（前端兼容） ====================

@bridge_router.post('/api/ai/bridge')
async def generate_bridge_simple(
    data: BridgeRequest,
    user: dict = Depends(get_current_user)
):
    """简化场景过渡接口 (保留与旧前端兼容)"""
    project_name = current_project_name.get() or data.projectName
    if not project_name:
        return JSONResponse(status_code=400, content={"error": "缺少项目名称"})

    user_id = str(user['user_id'])
    prev_scene = {'scene': '上一场景', 'guide': '', 'dia': [{'txt': data.prev_scene_content}]}
    next_scene = {'scene': '下一场景', 'guide': '', 'dia': [{'txt': data.next_scene_content}]}
    bridge_ctx = _load_worldview_and_roles(user_id, project_name)
    author_id = f"{user_id}_{project_name}"
    style_profile = load_style_profile_from_file(author_id, user_id=user_id)

    try:
        result = _run_bridge_agent(
            user_id=user_id,
            prev_scene=prev_scene,
            next_scene=next_scene,
            worldview=bridge_ctx.get('worldview', ''),
            guidance=data.guidance,
            style_profile=style_profile,
        )
        return {"success": True, **result}
    except Exception as exc:
        return JSONResponse(status_code=500, content={"error": f"生成过渡失败: {exc}"})


@bridge_router.post('/api/bridge/generate')
async def bridge_generate(request: Request, user: dict = Depends(get_current_user)):
    """完整场景结构的过渡生成 (与旧版接口保持一致)"""
    data = await request.json()
    prev_scene = data.get('prevScene') or {}
    next_scene = data.get('nextScene') or {}
    pacing = data.get('pacing', 'normal')
    mood = data.get('mood', '')
    guidance = data.get('guidance', '')
    project_name = current_project_name.get() or data.get('projectName') or data.get('project_name')

    user_id = str(user['user_id'])
    if not project_name:
        return JSONResponse(status_code=400, content={'error': '缺少项目名称'})

    meta = _load_worldview_and_characters(user_id, project_name)
    characters = data.get('characters') or meta['characters']
    author_id = f"{user_id}_{project_name}"
    style_profile = load_style_profile_from_file(author_id, user_id=user_id)

    try:
        result = _run_bridge_agent(
            user_id=user_id,
            prev_scene=prev_scene,
            next_scene=next_scene,
            worldview=meta['worldview'],
            characters=characters,
            pacing=pacing,
            mood=mood,
            guidance=guidance,
            style_profile=style_profile,
        )
        return {'success': True, **result}
    except Exception as exc:
        return JSONResponse(status_code=500, content={'error': str(exc)})


@bridge_router.post('/api/bridge/preview')
async def bridge_preview(request: Request, user: dict = Depends(get_current_user)):
    """实时预览过渡内容 (无需完整项目数据)"""
    data = await request.json()
    prev_text = data.get('prevText', '')
    next_text = data.get('nextText', '')
    guidance = data.get('guidance', '')
    user_id = str(user['user_id'])

    prev_scene = {'scene': '上一场景', 'guide': '', 'dia': [{'txt': prev_text}]}
    next_scene = {'scene': '下一场景', 'guide': '', 'dia': [{'txt': next_text}]}

    try:
        result = _run_bridge_agent(user_id, prev_scene, next_scene, guidance=guidance)
        return {'success': True, **result}
    except Exception as exc:
        return JSONResponse(status_code=500, content={'error': str(exc)})


# ==================== 新版端点（SSE流式） ====================

@bridge_router.post('/api/bridge/generate/stream')
async def bridge_generate_stream(data: BridgeRequest, user: dict = Depends(get_current_user)):
    """生成场景衔接（流式输出）- 新版 SSE 端点"""
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
