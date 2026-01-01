"""
Production API - 剧本生成（单段/多段续写）
"""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse
from typing import List, Dict, Any
import json

from core.auth import get_current_user
from core.request_context import current_project_name, set_agent_context

from agents import ScriptwriterAgent, run_story_generation_workflow
from agents.agent_lorebook import get_all_characters, get_character_info

from .schemas import (
    SingleNodeRequest, MultiNodeRequest, FeedbackRequest, CriticReviewRequest,
    _load_worldview_and_roles, _load_worldview_and_characters,
)

production_router = APIRouter()


@production_router.post('/api/production/single-generate/stream')
async def single_generate_stream(data: SingleNodeRequest, user: dict = Depends(get_current_user)):
    """单段续写（流式输出）"""
    user_id = str(user['user_id'])
    project_name = current_project_name.get() or data.projectName
    if not project_name:
        return JSONResponse(status_code=400, content={'error': '缺少项目名称'})

    set_agent_context(user_id, project_name)
    
    wv = _load_worldview_and_roles(user_id, project_name)
    worldview = wv.get('worldview', '')
    roles = wv.get('roles', '')
    
    # 获取角色信息
    characters_text = ""
    if data.character_ids:
        char_infos = []
        for cid in data.character_ids:
            info = get_character_info(user_id, project_name, cid)
            if info:
                char_infos.append(f"- {info.get('name', '')}: {info.get('desc', '')}")
        if char_infos:
            characters_text = "\n".join(char_infos)

    agent = ScriptwriterAgent(user_id=user_id)

    async def generate():
        try:
            for chunk in agent.stream_single_node(
                context=data.context,
                worldview=worldview,
                roles=roles,
                characters=characters_text,
                length=data.length,
            ):
                yield {"event": "chunk", "data": json.dumps({"text": chunk}, ensure_ascii=False)}
            yield {"event": "done", "data": "{}"}
        except Exception as e:
            yield {"event": "error", "data": json.dumps({"error": str(e)}, ensure_ascii=False)}

    return EventSourceResponse(generate())


@production_router.post('/api/production/multi-generate/stream')
async def multi_generate_stream(data: MultiNodeRequest, user: dict = Depends(get_current_user)):
    """多段续写（流式输出）"""
    user_id = str(user['user_id'])
    project_name = current_project_name.get() or data.projectName
    if not project_name:
        return JSONResponse(status_code=400, content={'error': '缺少项目名称'})

    set_agent_context(user_id, project_name)
    
    wv = _load_worldview_and_characters(user_id, project_name)
    worldview = wv.get('worldview', '')
    characters = wv.get('characters', [])

    async def generate():
        try:
            async for event in run_story_generation_workflow(
                user_id=user_id,
                project_name=project_name,
                context=data.context,
                guidance=data.guidance,
                worldview=worldview,
                characters=characters,
                segment_count=data.segment_count,
                current_file=data.current_file,
                scene_name=data.scene_name,
                after_node_id=data.after_node_id,
                last_node_text=data.last_node_text,
                confirm_continue=data.confirm_continue,
            ):
                yield event
        except Exception as e:
            import traceback
            traceback.print_exc()
            yield {"event": "error", "data": json.dumps({"error": str(e)}, ensure_ascii=False)}

    return EventSourceResponse(generate())


@production_router.post('/api/production/feedback/stream')
async def feedback_stream(data: FeedbackRequest, user: dict = Depends(get_current_user)):
    """反馈/修改建议（流式输出）"""
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
            for chunk in agent.stream_feedback(
                user_input=data.user_input,
                context=data.context,
                last_content=data.last_content,
                worldview=worldview,
                roles=roles,
            ):
                yield {"event": "chunk", "data": json.dumps({"text": chunk}, ensure_ascii=False)}
            yield {"event": "done", "data": "{}"}
        except Exception as e:
            yield {"event": "error", "data": json.dumps({"error": str(e)}, ensure_ascii=False)}

    return EventSourceResponse(generate())
