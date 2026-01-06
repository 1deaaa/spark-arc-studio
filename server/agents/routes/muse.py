"""
Muse API - 创意助手
"""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse, JSONResponse
import os
import json

from core.auth import get_current_user
from core.request_context import current_project_name
from core.utils import get_project_path

from agents.setup_agents import MuseAgent

from .schemas import MuseRequest, _save_muse_history, _get_history_dir

muse_router = APIRouter()


@muse_router.post('/api/ai/muse')
async def muse_inspiration(data: MuseRequest, user: dict = Depends(get_current_user)):
    """灵感种子: 灵感扩展 (流式响应)
    
    支持参数：
    - inspiration: 灵感碎片文本
    - style: 预期风格（如：治愈、悬疑、恐怖）
    - genres: 题材标签列表（如：['校园', '日常']）
    - lengthHint: 篇幅建议（短篇/中篇/长篇）
    """
    raw_input = data.inspiration
    user_id = str(user['user_id'])
    project_name = data.projectName or current_project_name.get()

    if not raw_input:
        return JSONResponse(status_code=400, content={"error": "Missing inspiration input"})

    muse = MuseAgent(user_id)
    
    async def generate():
        output_collector = []
        try:
            for chunk in muse.expand_inspiration(
                raw_input, 
                style=data.style, 
                genres=data.genres, 
                length_hint=data.lengthHint
            ):
                output_collector.append(chunk)
                yield chunk
        except Exception as e:
            print(f"Muse Agent 灵感扩展失败: {e}")
            raise
        finally:
            if project_name and output_collector:
                full_output = ''.join(output_collector)
                _save_muse_history(user_id, project_name, raw_input, full_output)

    return StreamingResponse(generate(), media_type='text/plain')


@muse_router.get('/api/history/muse/{project_name}')
async def get_muse_history(project_name: str, user: dict = Depends(get_current_user)):
    user_id = str(user['user_id'])
    history_file = os.path.join(_get_history_dir(user_id, project_name), 'muse_history.json')
    if os.path.exists(history_file):
        with open(history_file, 'r', encoding='utf-8') as f:
            history = json.load(f)
        return {'success': True, 'history': history}
    return {'success': True, 'history': []}


@muse_router.post('/api/history/muse/{project_name}')
async def save_muse_history_endpoint(project_name: str, request: Request, user: dict = Depends(get_current_user)):
    user_id = str(user['user_id'])
    data = await request.json()
    input_text = data.get('input', '')
    output_text = data.get('output', '')
    _save_muse_history(user_id, project_name, input_text, output_text)
    history_file = os.path.join(_get_history_dir(user_id, project_name), 'muse_history.json')
    with open(history_file, 'r', encoding='utf-8') as f:
        history = json.load(f)
    return {'success': True, 'entry': history[0] if history else {}}


@muse_router.delete('/api/history/muse/{project_name}/{entry_id}')
async def delete_muse_history(project_name: str, entry_id: int, user: dict = Depends(get_current_user)):
    user_id = str(user['user_id'])
    history_file = os.path.join(_get_history_dir(user_id, project_name), 'muse_history.json')
    if not os.path.exists(history_file):
        return JSONResponse(status_code=404, content={'success': False, 'error': '历史记录不存在'})
    with open(history_file, 'r', encoding='utf-8') as f:
        history = json.load(f)
    history = [h for h in history if h.get('id') != entry_id]
    with open(history_file, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
    return {'success': True}


@muse_router.patch('/api/history/muse/{project_name}/{entry_id}')
async def update_muse_history_title(
    project_name: str, 
    entry_id: int, 
    request: Request, 
    user: dict = Depends(get_current_user)
):
    """更新灵感历史条目的标题"""
    user_id = str(user['user_id'])
    data = await request.json()
    new_title = data.get('title', '')
    
    history_file = os.path.join(_get_history_dir(user_id, project_name), 'muse_history.json')
    if not os.path.exists(history_file):
        return JSONResponse(status_code=404, content={'success': False, 'error': '历史记录不存在'})
    
    with open(history_file, 'r', encoding='utf-8') as f:
        history = json.load(f)
    
    found = False
    for h in history:
        if h.get('id') == entry_id:
            h['title'] = new_title
            found = True
            break
    
    if not found:
        return JSONResponse(status_code=404, content={'success': False, 'error': '条目不存在'})
    
    with open(history_file, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
    
    return {'success': True}
