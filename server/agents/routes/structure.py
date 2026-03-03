"""
Structure API - 剧情结构（Synopsis, Beat Sheet, Outline AI）
"""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from datetime import datetime
import os
import json
from sse_starlette.sse import EventSourceResponse

from core.auth import get_current_user
from core.request_context import current_project_name, set_agent_context
from core.utils import get_project_path

from agents import ShowrunnerAgent

from .schemas import (
    SynopsisRequest, BeatSheetRequest, SynopsisSaveRequest, BeatSheetSaveRequest,
    _load_worldview_and_roles, _save_outline_to_history, _save_project_outline,
    format_ai_error
)

structure_router = APIRouter()


@structure_router.post('/api/ai/synopsis-stream')
async def generate_synopsis_stream_ai(data: SynopsisRequest, user: dict = Depends(get_current_user)):
    """流式生成故事梗概 (Synopsis) - 纯文本流"""
    from fastapi.responses import StreamingResponse
    
    user_id = str(user['user_id'])
    project_name = current_project_name.get() or data.projectName
    if not project_name:
        return JSONResponse(status_code=400, content={'error': '缺少项目名称'})

    set_agent_context(user_id, project_name)
    info = _load_worldview_and_roles(user_id, project_name)
    
    try:
        showrunner = ShowrunnerAgent(user_id)
    except ValueError as e:
        return JSONResponse(status_code=422, content={'error': str(e)})
    except Exception as e:
        return JSONResponse(status_code=500, content={'error': f'AI 服务初始化失败: {e}'})

    def generate():
        try:
            for chunk in showrunner.generate_synopsis_stream(
                logline=data.logline,
                worldview=info['worldview'],
                roles=info['roles'],
                guidance=data.guidance,
                style_profile=data.style_profile,
                length_hint=data.lengthHint
            ):
                if chunk['type'] == 'chunk':
                    yield chunk['content']
                # done 和 error 不 yield，因为纯文本流只传内容
        except Exception as e:
            yield f"\n\n{format_ai_error(e)}"

    return StreamingResponse(generate(), media_type='text/plain; charset=utf-8')



@structure_router.get('/api/synopsis/{project_name}')
async def get_synopsis(project_name: str, user: dict = Depends(get_current_user)):
    user_id = str(user['user_id'])
    synopsis_path = os.path.join(get_project_path(user_id, project_name), 'synopsis.json')
    if os.path.exists(synopsis_path):
        with open(synopsis_path, 'r', encoding='utf-8') as f:
            return {'success': True, 'synopsis': json.load(f)}
    return {'success': True, 'synopsis': None}


@structure_router.post('/api/synopsis')
async def save_synopsis(data: SynopsisSaveRequest, user: dict = Depends(get_current_user)):
    user_id = str(user['user_id'])
    project_name = data.projectName
    synopsis_path = os.path.join(get_project_path(user_id, project_name), 'synopsis.json')
    try:
        with open(synopsis_path, 'w', encoding='utf-8') as f:
            json.dump(data.synopsis, f, ensure_ascii=False, indent=2)
        return {'success': True}
    except Exception as exc:
        return JSONResponse(status_code=500, content={'error': str(exc)})



@structure_router.get('/api/beat-sheet/{project_name}')
async def get_beat_sheet(project_name: str, user: dict = Depends(get_current_user)):
    user_id = str(user['user_id'])
    beats_path = os.path.join(get_project_path(user_id, project_name), 'beats.json')
    if os.path.exists(beats_path):
        with open(beats_path, 'r', encoding='utf-8') as f:
            return {'success': True, 'beat_sheet': json.load(f)}
    return {'success': True, 'beat_sheet': None}


@structure_router.post('/api/beat-sheet')
async def save_beat_sheet(data: BeatSheetSaveRequest, user: dict = Depends(get_current_user)):
    user_id = str(user['user_id'])
    project_name = data.projectName
    beats_path = os.path.join(get_project_path(user_id, project_name), 'beats.json')
    try:
        with open(beats_path, 'w', encoding='utf-8') as f:
            json.dump(data.beatSheet, f, ensure_ascii=False, indent=2)
        return {'success': True}
    except Exception as exc:
        return JSONResponse(status_code=500, content={'error': str(exc)})



@structure_router.post('/api/ai/beat-sheet-stream')
async def generate_beat_sheet_stream_ai(data: BeatSheetRequest, user: dict = Depends(get_current_user)):
    """流式生成节拍表 (Beat Sheet) - 不阻塞后端"""
    from fastapi.responses import StreamingResponse
    
    user_id = str(user['user_id'])
    project_name = current_project_name.get() or data.projectName
    if not project_name:
        return JSONResponse(status_code=400, content={'error': '缺少项目名称'})

    set_agent_context(user_id, project_name)
    info = _load_worldview_and_roles(user_id, project_name)
    
    try:
        showrunner = ShowrunnerAgent(user_id)
    except ValueError as e:
        return JSONResponse(status_code=422, content={'error': str(e)})
    except Exception as e:
        return JSONResponse(status_code=500, content={'error': f'AI 服务初始化失败: {e}'})

    def generate():
        try:
            for chunk in showrunner.generate_beat_sheet_stream(
                synopsis=data.synopsis,
                worldview=info['worldview'],
                roles=info['roles'],
                guidance=data.guidance,
                length_hint=data.lengthHint
            ):
                if chunk['type'] == 'chunk':
                    yield chunk['content']
        except Exception as e:
            yield f"\n\n{format_ai_error(e)}"

    return StreamingResponse(generate(), media_type='text/plain; charset=utf-8')


@structure_router.post('/api/ai/outline-stream')
async def generate_outline_stream_ai(request: Request, user: dict = Depends(get_current_user)):
    """流式生成大纲 (Outline) - 不阻塞后端"""
    from fastapi.responses import StreamingResponse
    
    data = await request.json() or {}
    context = data.get('context', '')
    guidance = data.get('guidance', '')
    chapter_count = data.get('chapterCount', 5)
    scene_count_per_chapter = data.get('sceneCountPerChapter', 3)
    beat_sheet = data.get('beatSheet', '')
    style_profile = data.get('style_profile')
    save_to_project = data.get('saveToProject', True)
    save_to_history = data.get('saveToHistory', True)

    user_id = str(user['user_id'])
    project_name = data.get('projectName') or data.get('project_name') or current_project_name.get()
    if not project_name:
        return JSONResponse(status_code=400, content={'error': '缺少项目名称'})

    set_agent_context(user_id, project_name)
    info = _load_worldview_and_roles(user_id, project_name)
    try:
        showrunner = ShowrunnerAgent(user_id)
    except ValueError as e:
        return JSONResponse(status_code=422, content={'error': str(e)})
    except Exception as e:
        return JSONResponse(status_code=500, content={'error': f'AI 服务初始化失败: {e}'})

    final_outline = None

    def generate():
        nonlocal final_outline
        try:
            for chunk in showrunner.generate_outline_stream(
                context=context,
                worldview=info['worldview'],
                roles=info['roles'],
                guidance=guidance,
                chapter_count=chapter_count,
                scene_count_per_chapter=scene_count_per_chapter,
                beat_sheet=beat_sheet,
                style_profile=style_profile
            ):
                if chunk['type'] == 'chunk':
                    yield chunk['content']
                elif chunk['type'] == 'done':
                    final_outline = chunk['outline']
                    final_outline['updatedAt'] = datetime.now().isoformat()
                    final_outline['generatedAt'] = datetime.now().isoformat()
                    
                    # 保存操作在生成完成后执行
                    if save_to_project:
                        _save_project_outline(user_id, project_name, final_outline)
                    if save_to_history:
                        _save_outline_to_history(user_id, project_name, final_outline)
        except Exception as e:
            yield f"\n\n{format_ai_error(e)}"

    return StreamingResponse(generate(), media_type='text/plain; charset=utf-8')
