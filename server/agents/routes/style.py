"""
Style API - 风格分析
"""

from fastapi import APIRouter, Depends, Request, File, UploadFile
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
from sse_starlette.sse import EventSourceResponse
import os
import shutil
import tempfile
import json

from core.auth import get_current_user
from core.request_context import current_project_name

from agents.agent_style.workflow import save_style_profile, stream_save_style_profile
from agents.agent_style.utils import (
    extract_text_from_epub, load_style_profile_from_file,
    list_all_authors, delete_author_style, get_style_filepath
)

from .schemas import StyleApplyRequest

style_router = APIRouter()


@style_router.post('/api/ai/style-apply')
async def apply_style(data: StyleApplyRequest, user: dict = Depends(get_current_user)):
    user_id = str(user['user_id'])
    source_style_name = data.styleName
    target_project_name = data.projectName
    
    source_profile = load_style_profile_from_file(source_style_name, user_id=user_id)
    if not source_profile:
        return JSONResponse(status_code=404, content={'error': '源风格档案不存在'})
        
    target_author_id = f"{user_id}_{target_project_name}"
    target_path = get_style_filepath(target_author_id, user_id=user_id)
    
    try:
        with open(target_path, 'w', encoding='utf-8') as f:
            json.dump(source_profile, f, ensure_ascii=False, indent=2)
        return {'success': True}
    except Exception as e:
        return JSONResponse(status_code=500, content={'error': str(e)})


@style_router.post('/api/ai/style-analyze-stream')
async def analyze_style_stream(
    request: Request,
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user)
):
    user_id = str(user['user_id'])
    form = await request.form()
    project_name = current_project_name.get()
    if not project_name:
        project_name = form.get('projectName') or form.get('project_name')
    
    style_name = form.get('styleName')
    
    if style_name:
        author_id = style_name
    elif project_name:
        author_id = f"{user_id}_{project_name}"
    else:
        author_id = f"{user_id}_default"

    suffix = os.path.splitext(file.filename or '')[1].lower()
    if suffix not in {'.epub', '.txt'}:
        return JSONResponse(status_code=400, content={'error': '仅支持 .epub 或 .txt 文件'})

    fd, tmp_path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    
    try:
        with open(tmp_path, 'wb') as f:
            shutil.copyfileobj(file.file, f)

        def _extract_chapters(path: str, ext: str):
            if ext == '.epub':
                return extract_text_from_epub(path, merge_short_chapters=True, min_chunk_size=3000)
            with open(path, 'r', encoding='utf-8') as f:
                text = f.read()
            return [text[i:i+5000] for i in range(0, len(text), 5000)]

        chapters = await run_in_threadpool(_extract_chapters, tmp_path, suffix)

        if not chapters:
            return JSONResponse(status_code=400, content={'error': '无法从文件中提取文本'})

        force_regenerate_str = form.get('forceRegenerate', 'false')
        force_regenerate = force_regenerate_str.lower() in ('true', '1', 'yes')

        async def event_generator():
            try:
                async for progress in stream_save_style_profile(
                    author_id=author_id,
                    chapter_texts=chapters,
                    force_regenerate=force_regenerate,
                    user_id=user_id
                ):
                    if await request.is_disconnected():
                        return
                    yield {"data": json.dumps(progress, ensure_ascii=False)}
            except Exception as e:
                if await request.is_disconnected():
                    return
                yield {"data": json.dumps({"step": "error", "message": str(e)}, ensure_ascii=False)}

        return EventSourceResponse(event_generator())

    except Exception as e:
        return JSONResponse(status_code=500, content={'error': str(e)})
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except:
                pass


@style_router.get('/api/ai/styles')
async def list_styles(user: dict = Depends(get_current_user)):
    """列出用户所有的风格档案"""
    user_id = str(user['user_id'])
    styles = list_all_authors(user_id=user_id)
    return {'success': True, 'styles': styles}


@style_router.delete('/api/ai/styles/{style_name}')
async def delete_style(style_name: str, user: dict = Depends(get_current_user)):
    """删除指定的风格档案"""
    user_id = str(user['user_id'])
    success = delete_author_style(style_name, user_id=user_id)
    if success:
        return {'success': True}
    return JSONResponse(status_code=500, content={'error': '删除失败'})


@style_router.get('/api/ai/style-profile')
async def get_style_profile(request: Request, user: dict = Depends(get_current_user)):
    user_id = str(user['user_id'])
    style_name = request.query_params.get('styleName')
    project_name = current_project_name.get()
    if not project_name:
        project_name = request.query_params.get('projectName')

    if style_name:
        author_id = style_name
    elif project_name:
        author_id = f"{user_id}_{project_name}"
    else:
        return JSONResponse(status_code=400, content={'success': False, 'message': '缺少 styleName 或 projectName'})

    profile = load_style_profile_from_file(author_id, user_id=user_id)
    if profile:
        return {'success': True, 'style_profile': profile, 'style_name': author_id}
    return JSONResponse(status_code=404, content={'success': False, 'message': '未找到风格分析结果'})
