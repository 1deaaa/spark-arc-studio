"""
Bridge API - 场景衔接

注意：为保持前端兼容性，保留旧版 /api/bridge/generate 和 /api/ai/bridge 端点
"""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
from sse_starlette.sse import EventSourceResponse
from typing import List, Dict, Any, Optional
import threading
import json

from core.auth import get_current_user
from core.request_context import current_project_name, set_agent_context

from agents import ScriptwriterAgent
from agents.agent_style.utils import load_style_profile_from_file

from .schemas import BridgeRequest, _load_worldview_and_roles, _load_worldview_and_characters
from .streaming_utils import iterate_sync_iterable_in_thread
from .stream_semantics import semantic_event_data, merge_semantics, on_delta, on_done, on_error, on_progress, on_start, on_stats

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
        result = await run_in_threadpool(
            _run_bridge_agent,
            user_id,
            prev_scene,
            next_scene,
            guidance=guidance
        )
        return {'success': True, **result}
    except Exception as exc:
        return JSONResponse(status_code=500, content={'error': str(exc)})


# ==================== 新版端点（SSE流式） ====================

@bridge_router.post('/api/bridge/generate/stream')
async def bridge_generate_stream(request: Request, user: dict = Depends(get_current_user)):
    """完整场景结构的过渡生成 (流式输出)"""
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

    set_agent_context(user_id, project_name)

    meta = _load_worldview_and_characters(user_id, project_name)
    characters = data.get('characters') or meta['characters']
    author_id = f"{user_id}_{project_name}"
    style_profile = load_style_profile_from_file(author_id, user_id=user_id)

    try:
        writer = ScriptwriterAgent(user_id)
    except ValueError as e:
        return JSONResponse(status_code=422, content={'error': str(e)})
    except Exception as e:
        return JSONResponse(status_code=500, content={'error': f'AI 服务初始化失败: {e}'})

    stop_event = threading.Event()

    async def generate():
        full_text = ""
        started_at = threading.get_native_id()
        try:
            yield semantic_event_data(
                "progress",
                message="场景过渡生成已启动",
                stage="start",
                **merge_semantics(
                    on_start("场景过渡生成已启动"),
                    on_progress("正在准备桥接上下文...", stage="start"),
                ),
            )
            # We assume agent.stream_bridge_full exists or we use stream_bridge with adapters.
            # However, looking at ScriptwriterAgent, we need to check if it supports full object streaming.
            # Assuming it returns text chunks for the transition.
            
            # Since ScriptwriterAgent.bridge_scenes returns a dict, we need to stream that dict generation or just text.
            # If the underlying LLM call is just generating text for the bridge, we can stream that.
            
            # For now, let's wrap the blocking call if streaming isn't fully supported for complex objects,
            # OR better, since the user asked to prevent blocking, we should implement a proper stream.
            # But wait, looking at the existing `stream_bridge` in agent, it takes strings.
            # Let's adapt the inputs to strings for `stream_bridge` if that's what's available,
            # or check if we can stream the `bridge_scenes` equivalent.
            
            # The previous `bridge_generate_stream` implementation used `stream_bridge` which takes strings.
            # The `bridge_generate` takes dicts.
            
            # Let's construct the prompt inputs from the dicts similar to how `bridge_scenes` might do it,
            # or simplify by just streaming the text generation part if that's the main bottleneck.
            
            # Actually, let's reuse the existing `stream_bridge` but feed it content from the scene objects.
            
            prev_content = ""
            if 'dia' in prev_scene:
                prev_content = "\n".join([d.get('txt', '') for d in prev_scene['dia']])
            
            next_content = ""
            if 'dia' in next_scene:
                next_content = "\n".join([d.get('txt', '') for d in next_scene['dia']])
                
            async for chunk in iterate_sync_iterable_in_thread(
                lambda: writer.stream_bridge(
                    prev_scene_content=prev_content,
                    next_scene_content=next_content,
                    guidance=guidance,
                    worldview=meta['worldview'],
                    roles=json.dumps(characters, ensure_ascii=False),
                    style_profile=style_profile,
                ),
                request=request,
                stop_event=stop_event,
            ):
                if stop_event.is_set():
                    return
                full_text += chunk
                total_chars = len(full_text)
                yield semantic_event_data(
                    "chunk",
                    text=chunk,
                    chars=total_chars,
                    **merge_semantics(
                        on_delta(chunk),
                        on_progress("正在生成场景过渡...", stage="streaming"),
                        on_stats(chars=total_chars),
                    ),
                )

            if stop_event.is_set():
                return
            
            # Construct the final result object expected by frontend
            result = {
                "transition": full_text,
                "analysis": "Generated via stream"
            }
            yield semantic_event_data(
                "done",
                **result,
                chars=len(full_text),
                **merge_semantics(
                    on_done("场景过渡生成完成"),
                    on_stats(chars=len(full_text)),
                ),
            )
            
        except Exception as e:
            if stop_event.is_set():
                return
            yield semantic_event_data("error", error=str(e), **merge_semantics(on_progress(str(e), stage='error'), on_error(str(e))))

    return EventSourceResponse(generate())
