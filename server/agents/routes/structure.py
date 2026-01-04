"""
Structure API - 剧情结构（Synopsis, Beat Sheet, Outline AI）
"""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from datetime import datetime
import os
import json

from core.auth import get_current_user
from core.request_context import current_project_name
from core.utils import get_project_path

from agents import ShowrunnerAgent

from .schemas import (
    SynopsisRequest, BeatSheetRequest, SynopsisSaveRequest, BeatSheetSaveRequest,
    _load_worldview_and_roles, _save_outline_to_history, _save_project_outline,
)

structure_router = APIRouter()


@structure_router.post('/api/ai/synopsis')
async def generate_synopsis_ai(data: SynopsisRequest, user: dict = Depends(get_current_user)):
    """生成故事梗概 (Synopsis)"""
    project_name = current_project_name.get() or data.projectName
    if not project_name:
        return JSONResponse(status_code=400, content={'error': '缺少项目名称'})

    user_id = str(user['user_id'])
    info = _load_worldview_and_roles(user_id, project_name)
    try:
        showrunner = ShowrunnerAgent(user_id)
        synopsis = showrunner.generate_synopsis(
            logline=data.logline,
            worldview=info['worldview'],
            roles=info['roles'],
            guidance=data.guidance
        )
        return {'success': True, 'synopsis': synopsis}
    except Exception as exc:
        return JSONResponse(status_code=500, content={'error': str(exc)})


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


@structure_router.post('/api/ai/beat-sheet')
async def generate_beat_sheet_ai(data: BeatSheetRequest, user: dict = Depends(get_current_user)):
    """生成节拍表 (Beat Sheet)"""
    project_name = current_project_name.get() or data.projectName
    if not project_name:
        return JSONResponse(status_code=400, content={'error': '缺少项目名称'})

    user_id = str(user['user_id'])
    info = _load_worldview_and_roles(user_id, project_name)
    try:
        showrunner = ShowrunnerAgent(user_id)
        beat_sheet = showrunner.generate_beat_sheet(
            synopsis=data.synopsis,
            worldview=info['worldview'],
            roles=info['roles'],
            guidance=data.guidance
        )
        return {'success': True, 'beat_sheet': beat_sheet}
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


@structure_router.post('/api/ai/outline')
async def generate_outline_ai(request: Request, user: dict = Depends(get_current_user)):
    data = await request.json() or {}
    context = data.get('context', '')
    guidance = data.get('guidance', '')
    chapter_count = data.get('chapterCount', 5)
    beat_sheet = data.get('beatSheet', '')
    save_to_project = data.get('saveToProject', True)
    save_to_history = data.get('saveToHistory', True)

    user_id = str(user['user_id'])
    project_name = data.get('projectName') or data.get('project_name') or current_project_name.get()
    if not project_name:
        return JSONResponse(status_code=400, content={'error': '缺少项目名称'})

    info = _load_worldview_and_roles(user_id, project_name)
    try:
        showrunner = ShowrunnerAgent(user_id)
        outline = showrunner.generate_outline(
            context=context,
            worldview=info['worldview'],
            roles=info['roles'],
            guidance=guidance,
            chapter_count=chapter_count,
            beat_sheet=beat_sheet
        )
        outline['updatedAt'] = datetime.now().isoformat()
        outline['generatedAt'] = datetime.now().isoformat()

        if save_to_project:
            _save_project_outline(user_id, project_name, outline)

        if save_to_history:
            _save_outline_to_history(user_id, project_name, outline)

        return {'success': True, 'outline': outline}
    except Exception as exc:
        return JSONResponse(status_code=500, content={'error': str(exc)})
