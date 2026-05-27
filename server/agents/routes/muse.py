"""
Muse API - 灵感工坊

统一的全局灵感管理系统。
灵感存储在用户级别（非项目级别），支持跨项目复用。
"""

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse, JSONResponse
from typing import Optional, Dict, List, Any
import threading

from core.auth import get_current_user
from core.request_context import normalize_project_name

from agents.setup_agents import MuseAgent
from llm.agen_matchbox.reasoning_compat import extract_text_content_from_message
from mcp_server.spark_inspiration.logic import (
    INSPIRATION_SCOPE_ALL,
    INSPIRATION_SCOPE_PROJECT,
    VALID_INSPIRATION_SCOPES,
    bind_inspiration_to_project,
    bind_inspiration_exclusive,
    save_inspiration,
    get_all_inspirations,
    update_inspiration,
    delete_inspiration,
    mark_as_read,
    get_unread_count,
    unbind_inspiration_from_project,
    current_user_id,
)

from .schemas import (
    InspirationBindRequest,
    InspirationCreateRequest,
    InspirationUpdateRequest,
    MuseRequest,
    format_ai_error,
)
from .streaming_utils import iterate_sync_iterable_in_thread

muse_router = APIRouter()


def _build_muse_tags(data: MuseRequest) -> Dict[str, List[str]]:
    return {
        "styles": [data.style] if data.style else [],
        "genres": data.genres or [],
        "tones": data.tones or [],
        "worldviews": data.worldviews or [],
        "pov": [data.pov] if data.pov else [],
        "lengthHint": [data.lengthHint] if data.lengthHint else [],
    }


# ==================== 灵感列表与管理 ====================

@muse_router.get('/api/inspirations')
async def get_inspirations(
    user: dict = Depends(get_current_user),
    scope: str = Query(
        INSPIRATION_SCOPE_ALL,
        description=(
            "过滤范围：all=全部（默认）；project=已绑定到指定项目的灵感（必须配合 project 参数）；"
            "drafts=未绑定任何项目的草稿"
        ),
    ),
    project: Optional[str] = Query(None, description="scope=project 时指定的项目名"),
):
    """获取用户的灵感列表（全局，按时间倒序）。

    新增可选过滤参数（向前兼容）：
    - scope=all（默认）→ 旧行为，返回全部灵感
    - scope=project + project=<名字> → 仅返回已绑定到该项目的灵感
    - scope=drafts → 仅返回未绑定到任何项目的草稿
    """
    user_id = str(user['user_id'])

    normalized_scope = (scope or INSPIRATION_SCOPE_ALL).strip().lower()
    if normalized_scope not in VALID_INSPIRATION_SCOPES:
        normalized_scope = INSPIRATION_SCOPE_ALL

    project_name = normalize_project_name(project) if project else None
    if normalized_scope == INSPIRATION_SCOPE_PROJECT and not project_name:
        return JSONResponse(
            status_code=400,
            content={
                'success': False,
                'error': "scope=project 必须同时提供 project 参数",
            },
        )

    inspirations = get_all_inspirations(
        user_id,
        project_name=project_name,
        scope=normalized_scope,
    )
    unread = get_unread_count(user_id)
    return {
        'success': True,
        'inspirations': inspirations,
        'unread_count': unread,
        'scope': normalized_scope,
        'project': project_name,
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
    if data.source is not None:
        updates['source'] = data.source
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


# ==================== 灵感 ↔ 项目 软关联 ====================
# bind/unbind 与 project_links 字段共同支撑“按项目隔离 AI 上下文”的设计。
# 详见 mcp_server/spark_inspiration/logic.py 顶部注释。


@muse_router.post('/api/inspirations/{entry_id}/bind')
async def bind_inspiration_entry(
    entry_id: str,
    data: InspirationBindRequest,
    user: dict = Depends(get_current_user),
):
    """将灵感条目绑定到指定项目。

    exclusive=True 时执行排他绑定：绑定新灵感的同时自动解绑该项目下的旧灵感，
    保证一个项目同一时刻只有一个"活跃灵感"。
    """
    user_id = str(user['user_id'])
    project_name = normalize_project_name(data.projectName) if data.projectName else None
    if not project_name:
        return JSONResponse(status_code=400, content={'success': False, 'error': '缺少有效的 projectName'})

    if data.exclusive:
        result = bind_inspiration_exclusive(user_id, entry_id, project_name)
        if result['success']:
            return {'success': True, 'project': project_name, 'unbound_ids': result.get('unbound_ids', [])}
        return JSONResponse(
            status_code=404,
            content={'success': False, 'error': '灵感不存在或绑定失败'},
        )
    else:
        success = bind_inspiration_to_project(user_id, entry_id, project_name)
        if success:
            return {'success': True, 'project': project_name}
        return JSONResponse(
            status_code=404,
            content={'success': False, 'error': '灵感不存在或绑定失败'},
        )


@muse_router.post('/api/inspirations/{entry_id}/unbind')
async def unbind_inspiration_entry(
    entry_id: str,
    data: InspirationBindRequest,
    user: dict = Depends(get_current_user),
):
    """将灵感条目从指定项目解绑（解绑后仍存在，可能变成草稿或仍属于其他项目）。"""
    user_id = str(user['user_id'])
    project_name = normalize_project_name(data.projectName) if data.projectName else None
    if not project_name:
        return JSONResponse(status_code=400, content={'success': False, 'error': '缺少有效的 projectName'})

    success = unbind_inspiration_from_project(user_id, entry_id, project_name)
    if success:
        return {'success': True, 'project': project_name}
    return JSONResponse(
        status_code=404,
        content={'success': False, 'error': '灵感不存在或本未绑定到该项目'},
    )


# ==================== 灵感扩展生成 ====================

@muse_router.post('/api/ai/muse')
async def muse_expand(request: Request, data: MuseRequest, user: dict = Depends(get_current_user)):
    """灵感扩展：通过后台线程桥接同步 LLM stream，避免长耗时生成阻塞事件循环。
    
    支持参数：
    - inspiration: 灵感种子文本
    - style: 预期风格（如：治愈、悬疑、恐怖）
    - genres: 题材标签列表
    - tones: 基调标签列表
    - worldviews: 世界观标签列表
    - lengthHint: 篇幅建议（短篇/中篇/长篇）
    - inspirationId: 可选，关联的灵感ID（用于更新已有灵感的 content）
    """
    raw_input = (data.inspiration or "").strip()
    user_id = str(user['user_id'])
    inspiration_id = data.inspirationId

    try:
        muse = MuseAgent(user_id)
    except ValueError as e:
        return JSONResponse(status_code=422, content={"error": str(e)})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"AI 服务初始化失败: {e}"})

    context = muse.build_context(
        operation="expand_inspiration",
        raw_input=raw_input,
        style=data.style,
        genres=data.genres,
        tones=data.tones,
        worldviews=data.worldviews,
        length_hint=data.lengthHint,
    )
    stop_event = threading.Event()
    
    async def generate():
        output_collector = []
        # cancelled_event 仅在客户端主动断开时被 iterate_sync_iterable_in_thread 设置，
        # 正常生成完成时不会被触发，可以安全地用于判断是否需要持久化结果。
        cancelled_event = threading.Event()
        try:
            async for chunk in iterate_sync_iterable_in_thread(
                lambda: muse.execute(context),
                request=request,
                stop_event=stop_event,
                cancelled_event=cancelled_event,
            ):
                if stop_event.is_set():
                    return
                if isinstance(chunk, str) and chunk:
                    output_collector.append(chunk)
                    yield chunk
        except Exception as e:
            if stop_event.is_set():
                return
            print(f"Muse Agent 灵感扩展失败: {e}")
            yield format_ai_error(e)
        finally:
            if output_collector and not cancelled_event.is_set():
                full_output = ''.join(output_collector)
                visible_output = extract_text_content_from_message({"content": full_output})
                if inspiration_id:
                    muse.write_result(visible_output, user_id=user_id, inspiration_id=inspiration_id)
                elif not raw_input:
                    ai_source = MuseAgent.generate_source_title(visible_output)
                    token = current_user_id.set(user_id)
                    try:
                        save_inspiration(source=ai_source, content=visible_output, tags=_build_muse_tags(data), origin="ui")
                    finally:
                        current_user_id.reset(token)

    return StreamingResponse(generate(), media_type='text/plain; charset=utf-8')


@muse_router.post('/api/ai/muse/generate')
async def muse_generate_and_save(request: Request, data: MuseRequest, user: dict = Depends(get_current_user)):
    """灵感扩展并保存：通过后台线程桥接同步 LLM stream，避免长耗时生成阻塞事件循环。
    
    与 /api/ai/muse 的区别：此接口会在生成完成后自动创建新的灵感条目。
    """
    raw_input = (data.inspiration or "").strip()
    user_id = str(user['user_id'])

    try:
        muse = MuseAgent(user_id)
    except ValueError as e:
        return JSONResponse(status_code=422, content={"error": str(e)})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"AI 服务初始化失败: {e}"})

    context = muse.build_context(
        operation="expand_inspiration",
        raw_input=raw_input,
        style=data.style,
        genres=data.genres,
        tones=data.tones,
        worldviews=data.worldviews,
        length_hint=data.lengthHint,
    )
    stop_event = threading.Event()

    async def generate():
        output_collector = []
        try:
            async for chunk in iterate_sync_iterable_in_thread(
                lambda: muse.execute(context),
                request=request,
                stop_event=stop_event,
            ):
                if stop_event.is_set():
                    return
                if isinstance(chunk, str) and chunk:
                    output_collector.append(chunk)
                    yield chunk
        except Exception as e:
            if stop_event.is_set():
                return
            print(f"Muse Agent 灵感扩展失败: {e}")
            yield format_ai_error(e)
        finally:
            if output_collector and not stop_event.is_set():
                full_output = ''.join(output_collector)
                visible_output = extract_text_content_from_message({"content": full_output})
                source = raw_input if raw_input else MuseAgent.generate_source_title(visible_output)
                muse.write_result(
                    visible_output,
                    user_id=user_id,
                    source=source,
                    tags=_build_muse_tags(data),
                    origin="ui",
                )

    return StreamingResponse(generate(), media_type='text/plain; charset=utf-8')

