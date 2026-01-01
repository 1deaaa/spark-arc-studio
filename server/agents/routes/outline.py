"""
Outline API - 大纲管理
"""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from datetime import datetime
import os
import json
from typing import List, Dict, Any

from core.auth import get_current_user
from core.utils import get_project_path, get_project_stories_path

from .schemas import _get_history_dir, _save_outline_to_history

outline_router = APIRouter()


def _generate_arc_content(chapter_num: int, chapter_title: str, chapter_desc: str, scenes: List[Dict[str, Any]]) -> str:
    lines: List[str] = []
    lines.append(f"<!-- 章节 {chapter_num}: {chapter_title} -->")
    lines.append(f"<!-- {chapter_desc} -->")
    lines.append("")

    if not scenes:
        lines.append(f"# {chapter_title}")
        if chapter_desc:
            lines.append("@intro")
            lines.extend([l for l in str(chapter_desc).split('\n') if l.strip()])
        lines.append("")
        lines.append("[-1]")
        lines.append("场景内容待填写...")
        lines.append("")
        return '\n'.join(lines)

    for idx, scene in enumerate(scenes):
        scene_title = scene.get('title', f'场景 {idx + 1}')
        scene_desc = scene.get('description', '场景内容待填写...')
        lines.append(f"# {scene_title}")
        if scene_desc:
            lines.append("@intro")
            lines.extend([l for l in str(scene_desc).split('\n') if l.strip()])
        lines.append("")
        lines.append("[-1]")
        lines.append("场景内容待填写...")
        lines.append("")
        if idx < len(scenes) - 1:
            lines.append("")

    return '\n'.join(lines)


@outline_router.get('/api/outline/{project_name}')
async def get_outline(project_name: str, user: dict = Depends(get_current_user)):
    user_id = str(user['user_id'])
    outline_path = os.path.join(get_project_path(user_id, project_name), 'outline.json')
    try:
        if os.path.exists(outline_path):
            with open(outline_path, 'r', encoding='utf-8') as f:
                outline = json.load(f)
            return {'success': True, 'outline': outline}
        return {
            'success': True,
            'outline': {
                'title': '新故事大纲',
                'nodes': [],
                'updatedAt': None
            }
        }
    except Exception as exc:
        return JSONResponse(status_code=500, content={'success': False, 'error': str(exc)})


@outline_router.post('/api/outline/{project_name}')
async def save_outline(project_name: str, request: Request, user: dict = Depends(get_current_user)):
    user_id = str(user['user_id'])
    data = await request.json()
    outline = data.get('outline', {})
    save_to_history = data.get('saveToHistory', False)
    outline['updatedAt'] = datetime.now().isoformat()

    outline_path = os.path.join(get_project_path(user_id, project_name), 'outline.json')
    try:
        with open(outline_path, 'w', encoding='utf-8') as f:
            json.dump(outline, f, ensure_ascii=False, indent=2)
        if save_to_history:
            _save_outline_to_history(user_id, project_name, outline)
        return {'success': True, 'message': '大纲已保存'}
    except Exception as exc:
        return JSONResponse(status_code=500, content={'success': False, 'error': str(exc)})


@outline_router.get('/api/history/outline/{project_name}')
async def get_outline_history(project_name: str, user: dict = Depends(get_current_user)):
    user_id = str(user['user_id'])
    history_file = os.path.join(_get_history_dir(user_id, project_name), 'outline_history.json')
    if os.path.exists(history_file):
        with open(history_file, 'r', encoding='utf-8') as f:
            history = json.load(f)
        return {'success': True, 'history': history}
    return {'success': True, 'history': []}


@outline_router.post('/api/history/outline/{project_name}')
async def save_outline_history_endpoint(project_name: str, request: Request, user: dict = Depends(get_current_user)):
    user_id = str(user['user_id'])
    data = await request.json()
    outline = data.get('outline', {})
    _save_outline_to_history(user_id, project_name, outline)
    return {'success': True}


@outline_router.delete('/api/history/outline/{project_name}/{entry_id}')
async def delete_outline_history(project_name: str, entry_id: int, user: dict = Depends(get_current_user)):
    user_id = str(user['user_id'])
    history_file = os.path.join(_get_history_dir(user_id, project_name), 'outline_history.json')
    if not os.path.exists(history_file):
        return JSONResponse(status_code=404, content={'success': False, 'error': '历史记录不存在'})
    with open(history_file, 'r', encoding='utf-8') as f:
        history = json.load(f)
    history = [h for h in history if h.get('id') != entry_id]
    with open(history_file, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
    return {'success': True}


@outline_router.post('/api/history/outline/{project_name}/{entry_id}/restore')
async def restore_outline_from_history(project_name: str, entry_id: int, user: dict = Depends(get_current_user)):
    user_id = str(user['user_id'])
    history_file = os.path.join(_get_history_dir(user_id, project_name), 'outline_history.json')
    if not os.path.exists(history_file):
        return JSONResponse(status_code=404, content={'success': False, 'error': '历史记录不存在'})
    with open(history_file, 'r', encoding='utf-8') as f:
        history = json.load(f)
    entry = next((h for h in history if h.get('id') == entry_id), None)
    if not entry:
        return JSONResponse(status_code=404, content={'success': False, 'error': '记录不存在'})
    outline = entry.get('outline', {})
    outline['updatedAt'] = datetime.now().isoformat()
    outline_path = os.path.join(get_project_path(user_id, project_name), 'outline.json')
    with open(outline_path, 'w', encoding='utf-8') as f:
        json.dump(outline, f, ensure_ascii=False, indent=2)
    return {'success': True, 'outline': outline}


@outline_router.post('/api/outline/{project_name}/export-to-files')
async def export_outline_to_files(
    project_name: str, 
    request: Request,
    user: dict = Depends(get_current_user)
):
    user_id = str(user['user_id'])
    data = await request.json() or {}
    overwrite = data.get('overwrite', False)
    check_only = data.get('check_only', False)

    outline_path = os.path.join(get_project_path(user_id, project_name), 'outline.json')
    if not os.path.exists(outline_path):
        return JSONResponse(status_code=404, content={'success': False, 'error': '大纲不存在'})

    with open(outline_path, 'r', encoding='utf-8') as f:
        outline = json.load(f)

    nodes = outline.get('nodes', [])
    if not nodes:
        return JSONResponse(status_code=400, content={'success': False, 'error': '大纲为空'})

    stories_path = os.path.join(get_project_path(user_id, project_name), 'stories')
    os.makedirs(stories_path, exist_ok=True)

    files_to_create = []
    existing_files = []

    for chapter in nodes:
        if chapter.get('type') != 'chapter':
            continue
        chapter_num = chapter.get('chapter', 1)
        chapter_title = chapter.get('title', f'第{chapter_num}章')
        safe_title = chapter_title.replace(':', '').replace('：', '').replace('/', '_').replace('\\', '_')
        filename = f"{safe_title}.arc"
        filepath = os.path.join(stories_path, filename)
        
        if os.path.exists(filepath):
            existing_files.append(filename)
        
        files_to_create.append({
            'chapter': chapter,
            'filename': filename,
            'filepath': filepath
        })

    if check_only:
        return {'success': True, 'existing': existing_files}

    if existing_files and not overwrite:
        return JSONResponse(
            status_code=409, 
            content={
                'success': False, 
                'error': 'CONFLICT', 
                'message': '检测到同名文件已存在',
                'existing': existing_files
            }
        )

    created_files = []
    for item in files_to_create:
        chapter = item['chapter']
        filepath = item['filepath']
        filename = item['filename']
        
        chapter_num = chapter.get('chapter', 1)
        chapter_title = chapter.get('title', f'第{chapter_num}章')
        chapter_desc = chapter.get('description', '')
        children = chapter.get('children', [])
        
        arc_content = _generate_arc_content(chapter_num, chapter_title, chapter_desc, children)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(arc_content)
            
        created_files.append({
            'chapter': chapter_num,
            'title': chapter_title,
            'filename': filename,
            'sceneCount': len(children)
        })

    return {'success': True, 'files': created_files, 'message': f'成功导出 {len(created_files)} 个 .arc 格式章节文件'}
