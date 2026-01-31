"""
Muse API - 灵感工坊

统一的全局灵感管理系统。
灵感存储在用户级别（非项目级别），支持跨项目复用。
"""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse, JSONResponse
from typing import Optional, Dict, List, Any

from core.auth import get_current_user

from agents.setup_agents import MuseAgent
from mcp_server.spark_inspiration.logic import (
    save_inspiration,
    get_all_inspirations,
    update_inspiration,
    delete_inspiration,
    mark_as_read,
    get_unread_count,
    current_user_id
)

from .schemas import MuseRequest, InspirationCreateRequest, InspirationUpdateRequest, format_ai_error

muse_router = APIRouter()


# ==================== 灵感列表与管理 ====================

@muse_router.get('/api/inspirations')
async def get_inspirations(user: dict = Depends(get_current_user)):
    """获取用户的所有灵感（全局，按时间倒序）"""
    user_id = str(user['user_id'])
    inspirations = get_all_inspirations(user_id)
    unread = get_unread_count(user_id)
    return {
        'success': True,
        'inspirations': inspirations,
        'unread_count': unread
    }


@muse_router.get('/api/inspirations/unread-count')
async def get_inspiration_unread_count(user: dict = Depends(get_current_user)):
    """获取未读灵感数量"""
    user_id = str(user['user_id'])
    count = get_unread_count(user_id)
    return {'success': True, 'count': count}


@muse_router.post('/api/inspirations')
async def create_inspiration(data: InspirationCreateRequest, user: dict = Depends(get_current_user)):
    """创建新灵感（手动输入）"""
    user_id = str(user['user_id'])
    
    # 设置 context var 供 save_inspiration 使用
    token = current_user_id.set(user_id)
    try:
        result = save_inspiration(
            source=data.source,
            content=data.content or "",
            tags=data.tags,
            origin="ui"
        )
        return result
    finally:
        current_user_id.reset(token)


@muse_router.patch('/api/inspirations/{entry_id}')
async def update_inspiration_entry(
    entry_id: str,
    data: InspirationUpdateRequest,
    user: dict = Depends(get_current_user)
):
    """更新灵感条目（内容、标签、状态）"""
    user_id = str(user['user_id'])
    
    updates = {}
    if data.content is not None:
        updates['content'] = data.content
    if data.tags is not None:
        updates['tags'] = data.tags
    if data.status is not None:
        updates['status'] = data.status
    
    if not updates:
        return JSONResponse(status_code=400, content={'success': False, 'error': '没有要更新的字段'})
    
    success = update_inspiration(user_id, entry_id, updates)
    if success:
        return {'success': True}
    else:
        return JSONResponse(status_code=404, content={'success': False, 'error': '灵感不存在'})


@muse_router.post('/api/inspirations/{entry_id}/read')
async def mark_inspiration_read(entry_id: str, user: dict = Depends(get_current_user)):
    """标记灵感为已读"""
    user_id = str(user['user_id'])
    success = mark_as_read(user_id, entry_id)
    if success:
        return {'success': True}
    else:
        return JSONResponse(status_code=404, content={'success': False, 'error': '灵感不存在'})


@muse_router.delete('/api/inspirations/{entry_id}')
async def delete_inspiration_entry(entry_id: str, user: dict = Depends(get_current_user)):
    """删除灵感条目"""
    user_id = str(user['user_id'])
    success = delete_inspiration(user_id, entry_id)
    if success:
        return {'success': True}
    else:
        return JSONResponse(status_code=404, content={'success': False, 'error': '灵感不存在'})


# ==================== 灵感扩展生成 ====================

@muse_router.post('/api/ai/muse')
async def muse_expand(data: MuseRequest, user: dict = Depends(get_current_user)):
    """灵感扩展: 使用 AI 扩展灵感种子 (流式响应)
    
    支持参数：
    - inspiration: 灵感种子文本
    - style: 预期风格（如：治愈、悬疑、恐怖）
    - genres: 题材标签列表
    - tones: 基调标签列表
    - worldviews: 世界观标签列表
    - lengthHint: 篇幅建议（短篇/中篇/长篇）
    - inspirationId: 可选，关联的灵感ID（用于更新已有灵感的 content）
    """
    raw_input = data.inspiration
    user_id = str(user['user_id'])
    inspiration_id = data.inspirationId

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
                tones=data.tones,
                worldviews=data.worldviews,
                length_hint=data.lengthHint
            ):
                output_collector.append(chunk)
                yield chunk
        except Exception as e:
            print(f"Muse Agent 灵感扩展失败: {e}")
            yield format_ai_error(e)
        finally:
            # 如果提供了 inspirationId，更新对应灵感的 content
            if inspiration_id and output_collector:
                full_output = ''.join(output_collector)
                update_inspiration(user_id, inspiration_id, {"content": full_output})

    return StreamingResponse(generate(), media_type='text/plain')


@muse_router.post('/api/ai/muse/generate')
async def muse_generate_and_save(data: MuseRequest, user: dict = Depends(get_current_user)):
    """灵感扩展并保存: 生成灵感并直接创建新条目 (流式响应)
    
    与 /api/ai/muse 的区别：此接口会在生成完成后自动创建新的灵感条目。
    """
    raw_input = data.inspiration
    user_id = str(user['user_id'])

    if not raw_input:
        return JSONResponse(status_code=400, content={"error": "Missing inspiration input"})

    muse = MuseAgent(user_id)
    
    # 构建 tags
    tags = {
        "styles": [data.style] if data.style else [],
        "genres": data.genres or [],
        "tones": data.tones or [],
        "worldviews": data.worldviews or []
    }
    
    async def generate():
        output_collector = []
        try:
            for chunk in muse.expand_inspiration(
                raw_input,
                style=data.style,
                genres=data.genres,
                tones=data.tones,
                worldviews=data.worldviews,
                length_hint=data.lengthHint
            ):
                output_collector.append(chunk)
                yield chunk
        except Exception as e:
            print(f"Muse Agent 灵感扩展失败: {e}")
            yield format_ai_error(e)
        finally:
            # 生成完成后保存灵感
            if output_collector:
                full_output = ''.join(output_collector)
                token = current_user_id.set(user_id)
                try:
                    save_inspiration(
                        source=raw_input,
                        content=full_output,
                        tags=tags,
                        origin="ui"
                    )
                finally:
                    current_user_id.reset(token)

    return StreamingResponse(generate(), media_type='text/plain')
