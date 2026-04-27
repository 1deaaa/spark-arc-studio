"""
Chat / Session History API - 通用会话机制
"""

# ─────────────────────────────────────────────────────────────────────────────
# 关于Segment 时序记录
#
# 【背景与问题】
#   聊天流（chat_stream）本质上是 AI 在时间线上交替输出多种内容的序列，例如：
#     推理(reasoning_delta) → 正文(assistant_delta) → 工具(tool_*) → 推理 → 正文
#   ChatTaskEntry + ChatStreamAccumulator 是聊天流恢复的唯一状态源：
#   - 每个事件先写入 append-only event_log，并同步进入 accumulator；
#   - accumulator 维护 content / reasoning / tool_traces / segments / stream_seq；
#   - 运行中 checkpoint 到同一条 assistant 消息，完成时写最终 metadata；
#   - 前端 chatStore.ts 的历史归一化会优先读取 metadata.segments，
#     从而在刷新后完整还原交错时序的 UI 渲染效果。
#
# 【Segment 数据规范（供开发者遵循）】
#   segments 是一个有序列表，每个元素为 Dict：
#
#   推理段落：
#     { "type": "reasoning", "text": "AI 的思考过程..." }
#
#   正文段落：
#     { "type": "text", "text": "AI 对用户说的话..." }
#
#   工具调用段落：
#     { "type": "tool_trace", "tool_name": "update_character",
#       "status": "finished",        # started | running | finished | failed | cancelled
#       "started_at": 1710450001.0,  # Unix 时间戳（秒，三位小数）
#       "finished_at": 1710450003.5,
#       "duration": 2.5,             # 秒
#       "source_agent": "",          # 嵌套调用时为子 Agent ID，直接调用为空
#       "nested": False,             # 是否为委派后的嵌套调用
#       "_seg_id": "update_character::agent_lorebook:1"  # 跨事件精确匹配的唯一标识
#     }
#
#   规则：
#   - reasoning / text 类型：相邻同类 segment 会合并，避免碎片化。
#   - tool_trace 类型：以 _seg_id 唯一标识同一次调用，finished/failed 事件
#     会原地更新对应项，而非追加新项（精确还原单次工具调用完整生命周期）。
#   - 这份数据只用于 UI 渲染时序还原，tool_traces 字段仍保留用于聚合统计。
#
# 【新增聊天事件接入规范】
#   若将来新增 chat_stream 事件类型，优先扩展 chat_persistence.py 的
#   ChatStreamAccumulator / _collect_segment_from_event / _collect_tool_trace_from_event，
#   不要在路由层重新维护一套 buf / segments / tool_trace_map。
# ─────────────────────────────────────────────────────────────────────────────
from fastapi import APIRouter, Depends, Request, HTTPException, Query
from fastapi.responses import StreamingResponse, JSONResponse
from starlette.concurrency import run_in_threadpool
from typing import Any, Dict
import asyncio
import threading
import time
import json

from core.auth import get_current_user
from core.models import UserInfoSession, ChatMessage
from core.request_context import (
    get_current_project_name,
    resolve_project_name,
    set_current_inspiration_context,
    set_current_export_format,
)

from agents.agent_factory import create_agent_instance
from agents.chat_manager import ChatManager

from .schemas import (
    ChatSendRequest, ChatMessageEditRequest, ChatTaskCancelRequest,
    ChatMessageAttachmentRemoveRequest,
    _resolve_effective_active_context,
)
from .streaming_utils import iterate_sync_iterable_in_thread
from .chat_task import (
    ChatTaskEntry,
    _make_task_key,
    register_task,
    get_task_by_parts,
    cancel_task,
    update_task_status,
    cleanup_task,
    list_recent_tasks,
    build_task_status_payload,
)
chat_router = APIRouter()


def _apply_request_runtime_meta(active_meta: Dict[str, Any] | None) -> None:
    inspiration_id = None
    export_format = None
    if isinstance(active_meta, dict):
        inspiration_id = active_meta.get('inspirationId') or active_meta.get('inspiration_id')
        export_format = active_meta.get('exportFormat') or active_meta.get('export_format')
    set_current_inspiration_context(str(inspiration_id) if inspiration_id else None)
    set_current_export_format(export_format)


def _extract_imported_file_meta(active_meta: Dict[str, Any] | None) -> Dict[str, Any] | None:
    if not isinstance(active_meta, dict):
        return None
    imported_file = active_meta.get('importedFile')
    if not isinstance(imported_file, dict):
        return None
    filename = str(imported_file.get('filename') or '').strip()
    if not filename:
        return None
    warnings = imported_file.get('warnings')
    normalized_warnings = []
    if isinstance(warnings, list):
        for item in warnings:
            if not isinstance(item, dict):
                continue
            code = str(item.get('code') or '').strip()
            message = str(item.get('message') or '').strip()
            if code or message:
                normalized_warnings.append({
                    'code': code,
                    'message': message,
                })
    return {
        'filename': filename,
        'sourceFormat': str(imported_file.get('sourceFormat') or '').strip(),
        'totalTokens': int(imported_file.get('totalTokens') or 0),
        'chunkTokens': int(imported_file.get('chunkTokens') or 0),
        'isPartial': bool(imported_file.get('isPartial')),
        'warnings': normalized_warnings,
        'uploadedAt': int(imported_file.get('uploadedAt') or 0),
    }


def _as_stream_event(delta) -> dict:
    if isinstance(delta, dict):
        return delta
    if isinstance(delta, str):
        return {"event": "assistant_delta", "text": delta}
    return {"event": "assistant_delta", "text": str(delta)}


def _serialize_stream_event(delta) -> str:
    event = _as_stream_event(delta)
    return json.dumps(event, ensure_ascii=False) + "\n"


_NDJSON_MEDIA_TYPE = 'application/x-ndjson; charset=utf-8'

# 旁路标记前缀：用于从工具返回文本中提取导演触发 Auto-Write 的结构化元数据
_SIDEBAND_PREFIX = "__director_auto_write_started__:"


def _extract_director_sideband(text: str):
    """从工具返回文本中提取导演触发 Auto-Write 的旁路元数据。

    若文本首行包含 __director_auto_write_started__:{json}，则：
    - 返回 (json_str, 去除首行后的剩余文本)
    否则返回 (None, 原文本)。
    """
    if not isinstance(text, str) or not text.startswith(_SIDEBAND_PREFIX):
        return None, text
    newline_pos = text.find("\n")
    if newline_pos == -1:
        meta_str = text[len(_SIDEBAND_PREFIX):]
        rest = ""
    else:
        meta_str = text[len(_SIDEBAND_PREFIX):newline_pos]
        rest = text[newline_pos + 1:]
    return meta_str.strip(), rest


_CHAT_CHECKPOINT_INTERVAL = 0.5


def _checkpoint_chat_task(cm: ChatManager, entry: ChatTaskEntry, *, force: bool = False, stream_status: str | None = None) -> None:
    """Persist the current running assistant snapshot into its placeholder row."""
    if entry.assistant_message_id is None:
        return
    now = time.time()
    if not force:
        if entry.last_checkpoint_seq == entry.next_seq:
            return
        if now - float(entry.last_checkpoint_at or 0) < _CHAT_CHECKPOINT_INTERVAL:
            return

    status = stream_status or entry.status or 'running'
    metadata = entry.build_metadata(stream_status=status)
    content = entry.accumulator.content if entry.accumulator is not None else ''
    cm.update_message_content_metadata(entry.assistant_message_id, content, metadata)
    entry.last_checkpoint_seq = entry.next_seq
    entry.last_checkpoint_at = now


async def _observe_chat_task_events(request: Request, entry: ChatTaskEntry, *, after_seq: int = 0, include_snapshot: bool = True):
    """Yield replayable NDJSON events for one observer without consuming the task log."""
    cursor = max(0, int(after_seq or 0))
    if include_snapshot:
        snapshot = entry.build_snapshot()
        yield _serialize_stream_event(snapshot)
        cursor = max(cursor, int(snapshot.get("seq") or 0))

    heartbeat_interval = 5.0
    last_heartbeat = time.time()
    while True:
        events = entry.get_events_after(cursor)
        if events:
            for event in events:
                cursor = max(cursor, int(event.get("seq") or 0))
                yield _serialize_stream_event(event)
            continue

        if entry.status != 'running':
            break
        if request and await request.is_disconnected():
            break

        current = time.time()
        if current - last_heartbeat >= heartbeat_interval:
            yield _serialize_stream_event({"event": "heartbeat"})
            last_heartbeat = current
        await asyncio.sleep(0.05)


@chat_router.get('/api/chat/history')
async def get_chat_history(
    request: Request,
    agentId: str = Query(..., alias='agentId'),
    contextKey: str = Query('global', alias='contextKey'),
    limit: int = Query(50),
    user: dict = Depends(get_current_user),
):
    """获取指定 Agent + contextKey 的历史记录。"""
    user_id = str(user['user_id'])
    project_name = resolve_project_name(get_current_project_name(), request.query_params.get('projectName'))
    if not project_name:
        return JSONResponse(status_code=400, content={'error': '缺少项目名称'})

    cm = ChatManager(user_id=user_id, project_name=project_name)
    history = cm.get_history(agent_id=agentId, context_key=contextKey, limit=limit)
    return {'success': True, 'history': history}


@chat_router.delete('/api/chat/history')
async def clear_chat_history(
    request: Request,
    agentId: str = Query(..., alias='agentId'),
    contextKey: str = Query('global', alias='contextKey'),
    user: dict = Depends(get_current_user),
):
    """清空指定 Agent + contextKey 的会话。"""
    user_id = str(user['user_id'])
    project_name = resolve_project_name(get_current_project_name(), request.query_params.get('projectName'))
    if not project_name:
        return JSONResponse(status_code=400, content={'error': '缺少项目名称'})

    cm = ChatManager(user_id=user_id, project_name=project_name)
    ok = cm.clear_session(agent_id=agentId, context_key=contextKey)
    return {'success': True, 'cleared': ok}


@chat_router.delete('/api/chat/message')
async def delete_chat_message(
    request: Request,
    messageId: int = Query(..., alias='messageId'),
    user: dict = Depends(get_current_user),
):
    """删除单条消息。"""
    user_id = str(user['user_id'])
    project_name = resolve_project_name(get_current_project_name(), request.query_params.get('projectName'))
    if not project_name:
        return JSONResponse(status_code=400, content={'error': '缺少项目名称'})

    with UserInfoSession() as session:
        msg = session.get(ChatMessage, messageId)
        if not msg or str(msg.user_id) != user_id:
            return JSONResponse(status_code=404, content={'error': '消息不存在'})
        if msg.project_name != project_name:
            return JSONResponse(status_code=403, content={'error': '无权操作此项目的消息'})
        msg_role = msg.role
        agent_id = msg.agent_id
        context_key = msg.context_key
        msg_id = msg.id

    cm = ChatManager(user_id=user_id, project_name=project_name)
    ok = cm.delete_message(messageId)
    return {'success': True, 'deleted': bool(ok)}


@chat_router.post('/api/chat/message/attachment')
async def remove_chat_message_attachment(data: ChatMessageAttachmentRemoveRequest, user: dict = Depends(get_current_user)):
    """移除消息的附件上下文（不删除消息本身）。

    语义：
    - 将 metadata.importedFile 标记为 deleted，并将 active_context 中对应文件内容替换为占位文本。
    - 不删除消息，不删除后续回复。
    """
    user_id = str(user['user_id'])
    project_name = resolve_project_name(get_current_project_name(), data.projectName)
    if not project_name:
        return JSONResponse(status_code=400, content={'error': '缺少项目名称'})

    with UserInfoSession() as session:
        msg = session.get(ChatMessage, data.messageId)
        if not msg or str(msg.user_id) != user_id:
            return JSONResponse(status_code=404, content={'error': '消息不存在'})
        if msg.project_name != project_name:
            return JSONResponse(status_code=403, content={'error': '无权操作此项目的消息'})
        if msg.role != 'user':
            return JSONResponse(status_code=400, content={'error': '仅用户消息支持移除附件'})

    cm = ChatManager(user_id=user_id, project_name=project_name)
    with UserInfoSession() as session:
        msg = session.get(ChatMessage, data.messageId)
        if not msg:
            return JSONResponse(status_code=404, content={'error': '消息不存在'})
        meta = dict(msg.metadata_json or {})

        # 标记 importedFile 为已删除
        imported_file = meta.get('importedFile')
        if isinstance(imported_file, dict):
            imported_file['deleted'] = True
            imported_file['deletedAt'] = int(time.time())

        # 将 active_context 中文件内容替换为占位
        active_ctx = meta.get('active_context')
        if isinstance(active_ctx, str) and active_ctx.strip():
            filename = imported_file.get('filename', '未知文件') if isinstance(imported_file, dict) else '未知文件'
            meta['active_context'] = f'[附件 "{filename}" 已被删除]'

        msg.metadata_json = meta
        session.commit()

    return {'success': True}


@chat_router.post('/api/chat/edit')
async def edit_chat_message(data: ChatMessageEditRequest, user: dict = Depends(get_current_user)):
    """编辑消息并重新开始对话。
    
    逻辑：
    1. 找到该消息，更新其内容。
    2. 删除该消息之后的所有消息。
    3. 如果是用户消息，则触发 Agent 重新回复。
    """
    user_id = str(user['user_id'])
    project_name = resolve_project_name(get_current_project_name(), data.projectName)
    if not project_name:
        return JSONResponse(status_code=400, content={'error': '缺少项目名称'})

    cm = ChatManager(user_id=user_id, project_name=project_name)
    
    # 获取消息详情以获得时间戳
    with UserInfoSession() as session:
        msg = session.get(ChatMessage, data.messageId)
        if not msg or str(msg.user_id) != user_id:
            return JSONResponse(status_code=404, content={'error': '消息不存在'})
        
        # 安全检查
        if msg.project_name != project_name:
            return JSONResponse(status_code=403, content={'error': '无权操作此项目的消息'})
        
        # 信赖数据库中真实的房间归属
        data.agentId = msg.agent_id
        data.contextKey = msg.context_key
        
        timestamp = msg.timestamp.timestamp()
        role = msg.role
        msg_id = msg.id

    # 1. 更新内容
    cm.update_message(data.messageId, data.content)

    # 2. 删除之后的消息（使用 message_id 更可靠）
    cm.delete_after(agent_id=data.agentId, context_key=data.contextKey, message_id=msg_id)

    # 3. 如果是用户消息，则重新触发回复
    if role == 'user':
        effective_active_context = _resolve_effective_active_context(user_id, project_name, data.agentId, data.activeContext)
        _apply_request_runtime_meta(data.activeMeta)
        
        # 统一实例化 Agent（包括导演）并获取回复
        # get_history 返回的历史已含编辑后的用户消息，需移除以避免与 data.content 双喂
        history = cm.get_history(agent_id=data.agentId, context_key=data.contextKey, limit=10)
        if history and history[-1].get('role') == 'user':
            history = history[:-1]

        try:
            print(f"[EditChat] Triggering reply for expert agent: {data.agentId}")
            agent_inst = create_agent_instance(data.agentId, user_id, project_name)

            reply = await run_in_threadpool(agent_inst.chat, data.content, history=history, active_context=effective_active_context)
            print(f"[EditChat] Agent reply length: {len(reply) if reply else 0}")
            
            cm.append_message(
                agent_id=data.agentId,
                context_key=data.contextKey,
                role='assistant',
                content=reply,
                metadata={'channel': 'edit_reply'},
            )
            return {'success': True, 'reply': reply}
        except Exception as e:
            import traceback
            traceback.print_exc()
            from .schemas import format_ai_error
            return JSONResponse(status_code=500, content={'error': format_ai_error(e)})

    return {'success': True}


@chat_router.post('/api/chat/edit/stream')
async def edit_chat_message_stream(request: Request, data: ChatMessageEditRequest, user: dict = Depends(get_current_user)):
    """编辑消息并重新开始对话（流式输出）。

    后台线程模式：前端断连后 AI 继续执行，直到任务自然完成或被显式取消。
    """
    user_id = str(user['user_id'])
    project_name = resolve_project_name(get_current_project_name(), data.projectName)
    if not project_name:
        raise HTTPException(status_code=400, detail='缺少项目名称')

    cm = ChatManager(user_id=user_id, project_name=project_name)

    with UserInfoSession() as session:
        msg = session.get(ChatMessage, data.messageId)
        if not msg or str(msg.user_id) != user_id:
            raise HTTPException(status_code=404, detail='消息不存在')

        if msg.project_name != project_name:
            raise HTTPException(status_code=403, detail='无权操作此项目的消息')
        
        # 信赖数据库中真实的房间归属
        data.agentId = msg.agent_id
        data.contextKey = msg.context_key

        role = msg.role
        msg_id = msg.id

    cm.update_message(data.messageId, data.content)
    cm.delete_after(agent_id=data.agentId, context_key=data.contextKey, message_id=msg_id)

    if role != 'user':
        return StreamingResponse(iter(['']), media_type='text/plain')

    effective_active_context = _resolve_effective_active_context(user_id, project_name, data.agentId, data.activeContext)
    _apply_request_runtime_meta(data.activeMeta)

    task_key = _make_task_key(user_id, project_name, data.agentId, data.contextKey)

    # 检查是否已有同 key 的活跃任务
    existing = get_task_by_parts(user_id, project_name, data.agentId, data.contextKey)
    if existing and existing.status == 'running':
        raise HTTPException(status_code=409, detail='该会话已有任务在执行')

    # 创建任务入口
    stop_event = threading.Event()
    entry = ChatTaskEntry(
        task_key=task_key,
        user_id=user_id,
        project_name=project_name,
        agent_id=data.agentId,
        context_key=data.contextKey,
        stop_event=stop_event,
        status='running',
        started_at=time.time(),
        channel='edit_reply_stream',
    )
    register_task(entry)

    assistant_msg = cm.append_message(
        agent_id=data.agentId,
        context_key=data.contextKey,
        role='assistant',
        content='',
        metadata={
            'channel': 'edit_reply_stream',
            'stream_status': 'running',
            'stream_seq': 0,
            'task_id': entry.task_id,
        },
    )
    entry.assistant_message_id = assistant_msg.id
    entry.result_message_id = assistant_msg.id
    _checkpoint_chat_task(cm, entry, force=True, stream_status='running')

    # get_history 返回的历史已含编辑后的用户消息，需移除以避免与 data.content 双喂
    history = cm.get_history(agent_id=data.agentId, context_key=data.contextKey, limit=10)
    if history and history[-1].get('role') == 'user':
        history = history[:-1]
    agent_inst = create_agent_instance(data.agentId, user_id, project_name)

    # ── 后台线程：执行 chat_stream 并写入进度队列 + 数据库 ──
    def _run_chat_background():
        import contextvars
        from core.request_context import current_user_id, current_project_name

        ctx = contextvars.copy_context()

        def _in_context():
            current_user_id.set(str(user_id))
            current_project_name.set(project_name)

            terminated_early = False
            final_error_message = ''

            try:
                for delta in agent_inst.chat_stream(
                    data.content,
                    history=history,
                    active_context=effective_active_context,
                    stop_event=stop_event,
                ):
                    if stop_event.is_set():
                        terminated_early = True
                        break
                    if not delta:
                        continue
                    event = entry.append_event(delta)
                    event_type = event.get("event")
                    _checkpoint_chat_task(
                        cm,
                        entry,
                        force=event_type in {"tool_intent_started", "tool_exec_started", "tool_exec_finished", "tool_exec_failed", "error"},
                        stream_status='running',
                    )
                if stop_event.is_set():
                    terminated_early = True

            except Exception as e:
                if stop_event.is_set():
                    terminated_early = True
                else:
                    from .schemas import format_ai_error
                    err = f"\n{format_ai_error(e)}"
                    final_error_message = err
                    entry.error_message = err
                    entry.append_event({"event": "error", "message": err})
            finally:
                if terminated_early:
                    final_status = 'cancelled'
                elif final_error_message:
                    final_status = 'error'
                else:
                    final_status = 'completed'

                reply = entry.accumulator.content if entry.accumulator is not None else ''
                metadata = entry.build_metadata(stream_status=final_status)
                _checkpoint_chat_task(cm, entry, force=True, stream_status=final_status)
                entry.append_control_event({
                    "event": "task_done",
                    "status": final_status,
                    "assistant_message_id": entry.assistant_message_id,
                    "result_message_id": entry.assistant_message_id,
                    **({"error": final_error_message} if final_error_message else {}),
                })
                update_task_status(
                    task_key, final_status,
                    result_message_id=entry.assistant_message_id,
                    result_content=reply,
                    result_metadata=metadata,
                    error_message=final_error_message,
                )
                cleanup_task(task_key)

        ctx.run(_in_context)

    thread = threading.Thread(target=_run_chat_background, daemon=True, name=f"chat_edit_bg_{task_key}")
    thread.start()

    return StreamingResponse(_observe_chat_task_events(request, entry, include_snapshot=True), media_type=_NDJSON_MEDIA_TYPE)


@chat_router.post('/api/chat/send')
async def send_chat_message(data: ChatSendRequest, user: dict = Depends(get_current_user)):
    """发送消息。

规则：
- 对导演(agent_director)说：执行路由，并把消息"静默写入"多个目标 Agent 的会话
- 对具体 Agent 说：仅写入该 Agent 的会话（不重复写到导演）
"""
    user_id = str(user['user_id'])
    project_name = resolve_project_name(get_current_project_name(), data.projectName)
    if not project_name:
        return JSONResponse(status_code=400, content={'error': '缺少项目名称'})

    agent_id = (data.agentId or '').strip()
    if not agent_id:
        return JSONResponse(status_code=400, content={'error': '缺少 agentId'})

    context_key = (data.contextKey or 'global').strip() or 'global'
    message = (data.message or '').strip()
    if not message:
        return JSONResponse(status_code=400, content={'error': '消息为空'})

    effective_active_context = _resolve_effective_active_context(user_id, project_name, agent_id, data.activeContext)
    _apply_request_runtime_meta(data.activeMeta)
    imported_file_meta = _extract_imported_file_meta(data.activeMeta)

    # 统一处理所有 Agent（包括导演）
    cm = ChatManager(user_id=user_id, project_name=project_name)

    # 1. 先取历史（不含当前消息），避免双喂
    history = cm.get_history(agent_id=agent_id, context_key=context_key, limit=10)

    # 2. 保存用户消息到 DB
    cm.append_message(
        agent_id=agent_id,
        context_key=context_key,
        role='user',
        content=message,
        metadata={
            'channel': 'direct',
            **({'active_context': effective_active_context} if effective_active_context else {}),
            **({'importedFile': imported_file_meta} if imported_file_meta else {}),
        },
    )

    try:
        agent_inst = create_agent_instance(agent_id, user_id, project_name)

        reply = await run_in_threadpool(agent_inst.chat, message, history=history, active_context=effective_active_context)

        # 3. Record AI reply
        cm.append_message(
            agent_id=agent_id,
            context_key=context_key,
            role='assistant',
            content=reply,
            metadata={'channel': 'direct_reply'},
        )
        
        return {'success': True, 'mode': 'direct', 'reply': reply}
    except Exception as e:
        print(f"[Direct Chat] Failed for {agent_id}: {e}")
        from .schemas import format_ai_error
        return JSONResponse(status_code=500, content={'error': format_ai_error(e)})


@chat_router.post('/api/chat/send/stream')
async def send_chat_message_stream(request: Request, data: ChatSendRequest, user: dict = Depends(get_current_user)):
    """发送消息（流式输出，NDJSON）。

    与 /api/chat/send 规则一致，但 AI 回复以流式文本返回。
    后台线程模式：前端断连后 AI 继续执行，直到任务自然完成或被显式取消。
    """
    user_id = str(user['user_id'])
    project_name = resolve_project_name(get_current_project_name(), data.projectName)
    if not project_name:
        raise HTTPException(status_code=400, detail='缺少项目名称')

    agent_id = (data.agentId or '').strip()
    if not agent_id:
        raise HTTPException(status_code=400, detail='缺少 agentId')

    context_key = (data.contextKey or 'global').strip() or 'global'
    message = (data.message or '').strip()
    if not message:
        raise HTTPException(status_code=400, detail='消息为空')

    effective_active_context = _resolve_effective_active_context(user_id, project_name, agent_id, data.activeContext)
    _apply_request_runtime_meta(data.activeMeta)
    imported_file_meta = _extract_imported_file_meta(data.activeMeta)

    task_key = _make_task_key(user_id, project_name, agent_id, context_key)

    # 检查是否已有同 key 的活跃任务
    existing = get_task_by_parts(user_id, project_name, agent_id, context_key)
    if existing and existing.status == 'running':
        raise HTTPException(status_code=409, detail='该会话已有任务在执行')

    # 创建任务入口
    stop_event = threading.Event()
    entry = ChatTaskEntry(
        task_key=task_key,
        user_id=user_id,
        project_name=project_name,
        agent_id=agent_id,
        context_key=context_key,
        stop_event=stop_event,
        status='running',
        started_at=time.time(),
        channel='direct_reply_stream',
    )
    register_task(entry)

    cm = ChatManager(user_id=user_id, project_name=project_name)

    # 先取历史（不含当前消息），避免双喂
    history = cm.get_history(agent_id=agent_id, context_key=context_key, limit=10)

    # 保存用户消息到 DB（在取历史之后，确保 history 不含当前消息）
    cm.append_message(
        agent_id=agent_id,
        context_key=context_key,
        role='user',
        content=message,
        metadata={
            'channel': 'direct',
            **({'active_context': effective_active_context} if effective_active_context else {}),
            **({'importedFile': imported_file_meta} if imported_file_meta else {}),
        },
    )

    assistant_msg = cm.append_message(
        agent_id=agent_id,
        context_key=context_key,
        role='assistant',
        content='',
        metadata={
            'channel': 'direct_reply_stream',
            'stream_status': 'running',
            'stream_seq': 0,
            'task_id': entry.task_id,
        },
    )
    entry.assistant_message_id = assistant_msg.id
    entry.result_message_id = assistant_msg.id
    _checkpoint_chat_task(cm, entry, force=True, stream_status='running')

    agent_inst = create_agent_instance(agent_id, user_id, project_name)

    # ── 后台线程：执行 chat_stream 并写入进度队列 + 数据库 ──
    def _run_chat_background():
        import contextvars
        from core.request_context import current_user_id, current_project_name

        # 复制请求级 ContextVar 到后台线程
        ctx = contextvars.copy_context()

        def _in_context():
            current_user_id.set(str(user_id))
            current_project_name.set(project_name)

            # ── 自动重试配置 ──
            _MAX_RETRIES = 3
            _RETRY_DELAY = 2.0

            terminated_early = False
            last_error_summary: str = ''
            retry_count = 0
            final_error_message = ''

            try:
                for attempt in range(1, _MAX_RETRIES + 1):
                    # 重试前清空上一轮残留
                    if attempt > 1:
                        entry.reset_for_retry()
                        _checkpoint_chat_task(cm, entry, force=True, stream_status='running')
                        entry.append_control_event(entry.build_snapshot())

                    try:
                        for delta in agent_inst.chat_stream(
                            message,
                            history=history,
                            active_context=effective_active_context,
                            stop_event=stop_event,
                        ):
                            if stop_event.is_set():
                                terminated_early = True
                                break
                            if not delta:
                                continue
                            event = entry.append_event(delta)
                            event_type = event.get("event")
                            _checkpoint_chat_task(
                                cm,
                                entry,
                                force=event_type in {"tool_intent_started", "tool_exec_started", "tool_exec_finished", "tool_exec_failed", "error"},
                                stream_status='running',
                            )

                        if stop_event.is_set():
                            terminated_early = True
                            break

                        # chat_stream 正常结束，跳出重试循环
                        break

                    except Exception as e:
                        if stop_event.is_set():
                            terminated_early = True
                            break

                        from .schemas import format_ai_error
                        last_error_summary = format_ai_error(e)
                        retry_count = attempt

                        if attempt < _MAX_RETRIES:
                            # 推送重试事件，告知前端即将重试
                            entry.append_event({
                                "event": "retry_attempt",
                                "attempt": attempt,
                                "max_retries": _MAX_RETRIES,
                                "error_summary": last_error_summary,
                            }, accumulate=False)
                            update_task_status(task_key, 'running', retry_count=attempt)
                            if stop_event.wait(_RETRY_DELAY):
                                terminated_early = True
                                break
                        else:
                            # 3 次均失败，报具体错误
                            err = f"\n{last_error_summary}"
                            final_error_message = err
                            entry.error_message = err
                            entry.append_event({"event": "error", "message": err})
                            update_task_status(task_key, 'error', error_message=err, retry_count=attempt)
            finally:
                if terminated_early:
                    final_status = 'cancelled'
                elif final_error_message:
                    final_status = 'error'
                else:
                    final_status = 'completed'

                reply = entry.accumulator.content if entry.accumulator is not None else ''
                metadata = entry.build_metadata(stream_status=final_status)
                _checkpoint_chat_task(cm, entry, force=True, stream_status=final_status)
                entry.append_control_event({
                    "event": "task_done",
                    "status": final_status,
                    "assistant_message_id": entry.assistant_message_id,
                    "result_message_id": entry.assistant_message_id,
                    **({"error": final_error_message} if final_error_message else {}),
                })
                update_task_status(
                    task_key, final_status,
                    result_message_id=entry.assistant_message_id,
                    result_content=reply,
                    result_metadata=metadata,
                    error_message=final_error_message,
                    retry_count=retry_count,
                )
                cleanup_task(task_key)

        ctx.run(_in_context)

    thread = threading.Thread(target=_run_chat_background, daemon=True, name=f"chat_bg_{task_key}")
    thread.start()

    return StreamingResponse(_observe_chat_task_events(request, entry, include_snapshot=True), media_type=_NDJSON_MEDIA_TYPE)


# ─────────────────────────────────────────────────────────────────────────────
# 聊天后台任务管理 API
# ─────────────────────────────────────────────────────────────────────────────


@chat_router.get('/api/chat/task-status')
async def get_chat_task_status(
    request: Request,
    agentId: str = Query(..., alias='agentId'),
    contextKey: str = Query('global', alias='contextKey'),
    user: dict = Depends(get_current_user),
):
    """查询指定会话是否有后台聊天任务在运行。

    返回格式：
    - hasTask: bool — 是否存在任务（包括已完成/取消但尚未清理的）
    - status: str — running | completed | cancelled | error
    - agentId / contextKey — 任务标识
    - resultMessageId — 完成后的消息 ID（用于前端刷新历史）
    - error — 错误信息（仅 error 状态）
    """
    user_id = str(user['user_id'])
    project_name = resolve_project_name(get_current_project_name(), request.query_params.get('projectName'))
    if not project_name:
        return JSONResponse(status_code=400, content={'error': '缺少项目名称'})

    entry = get_task_by_parts(user_id, project_name, agentId, contextKey)
    if not entry:
        return {'hasTask': False}

    return build_task_status_payload(entry)


@chat_router.get('/api/chat/recent-tasks')
async def get_chat_recent_tasks(
    request: Request,
    user: dict = Depends(get_current_user),
):
    """列出当前用户在当前项目下尚未清理的聊天任务，用于刷新恢复。"""
    user_id = str(user['user_id'])
    project_name = resolve_project_name(get_current_project_name(), request.query_params.get('projectName'))
    if not project_name:
        return JSONResponse(status_code=400, content={'error': '缺少项目名称'})

    tasks = list_recent_tasks(user_id, project_name)
    return {
        'tasks': [build_task_status_payload(t) for t in tasks],
        'count': len(tasks),
    }


@chat_router.post('/api/chat/task-cancel')
async def cancel_chat_task(request: Request, data: ChatTaskCancelRequest, user: dict = Depends(get_current_user)):
    """手动取消指定会话的后台聊天任务（对应前端"停止"按钮）。"""
    user_id = str(user['user_id'])
    project_name = resolve_project_name(get_current_project_name(), data.projectName)
    if not project_name:
        raise HTTPException(status_code=400, detail='缺少项目名称')

    agent_id = (data.agentId or '').strip()
    if not agent_id:
        raise HTTPException(status_code=400, detail='缺少 agentId')

    context_key = (data.contextKey or 'global').strip() or 'global'

    task_key = _make_task_key(user_id, project_name, agent_id, context_key)
    ok = cancel_task(task_key)
    if not ok:
        return {'success': False, 'reason': '任务不存在或已结束'}
    return {'success': True}


@chat_router.get('/api/chat/task-stream')
async def reconnect_chat_task_stream(
    request: Request,
    agentId: str = Query(..., alias='agentId'),
    contextKey: str = Query('global', alias='contextKey'),
    afterSeq: int = Query(0, alias='afterSeq'),
    user: dict = Depends(get_current_user),
):
    """重连到正在运行的后台聊天任务，按 cursor 回放事件。

    前端关闭/刷新后重新进入时调用此端点：
    - running → 新 NDJSON 观察者读取 task_snapshot，并按 afterSeq 回放 event_log 后续事件
    - completed/cancelled/error → 返回最终状态 JSON（含 resultMessageId）
    - 不存在 → 返回 {hasTask: false}
    """
    user_id = str(user['user_id'])
    project_name = resolve_project_name(get_current_project_name(), request.query_params.get('projectName'))
    if not project_name:
        return JSONResponse(status_code=400, content={'error': '缺少项目名称'})

    entry = get_task_by_parts(user_id, project_name, agentId, contextKey)

    # 任务不存在
    if not entry:
        return {'hasTask': False}

    # 任务已结束：返回最终状态
    if entry.status != 'running':
        return build_task_status_payload(entry)

    return StreamingResponse(
        _observe_chat_task_events(request, entry, after_seq=afterSeq, include_snapshot=True),
        media_type=_NDJSON_MEDIA_TYPE,
    )
