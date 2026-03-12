"""
Chat / Session History API - 通用会话机制
"""

from fastapi import APIRouter, Depends, Request, HTTPException, Query
from fastapi.responses import StreamingResponse, JSONResponse
from starlette.concurrency import run_in_threadpool
from typing import Any, Dict, List
import threading
import json

from core.auth import get_current_user
from core.models import UserInfoSession, ChatMessage
from core.request_context import current_project_name, set_current_inspiration_context

from agents.chat_manager import ChatManager
from agents.agent_director import DirectorAgent
from agents import ShowrunnerAgent, ScriptwriterAgent, CriticAgent
from agents.agent_lorebook import WorldviewAgent
from agents.agent_style_chat import StyleChatAgent
from agents.setup_agents import MuseAgent
from agents.communication import SparkBaseAgent

from .schemas import (
    ChatSendRequest, ChatMessageEditRequest,
    _resolve_effective_active_context, _format_targets
)
from .streaming_utils import iterate_sync_iterable_in_thread

chat_router = APIRouter()


def _apply_request_runtime_meta(active_meta: Dict[str, Any] | None) -> None:
    inspiration_id = None
    if isinstance(active_meta, dict):
        inspiration_id = active_meta.get('inspirationId') or active_meta.get('inspiration_id')
    set_current_inspiration_context(str(inspiration_id) if inspiration_id else None)


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


def _extract_visible_text(delta) -> str:
    if isinstance(delta, str):
        return delta
    if isinstance(delta, dict):
        event_type = delta.get("event")
        if event_type == "assistant_delta":
            return str(delta.get("text") or "")
        if event_type == "error":
            return str(delta.get("message") or "")
    return ""


def _collect_tool_trace_from_event(tool_trace_map: Dict[str, Dict[str, Any]], delta: Any, now_ts: float | None = None) -> None:
    if not isinstance(delta, dict):
        return

    event_type = str(delta.get("event") or "").strip()
    if event_type not in {"tool_intent_started", "tool_exec_started", "tool_exec_finished", "tool_exec_failed"}:
        return

    tool_name = str(delta.get("tool_name") or delta.get("toolName") or "").strip()
    if not tool_name:
        return

    import time

    ts = round(float(now_ts if now_ts is not None else time.time()), 3)
    trace = dict(tool_trace_map.get(tool_name) or {"tool_name": tool_name})

    if event_type in {"tool_intent_started", "tool_exec_started"} and not isinstance(trace.get("started_at"), (int, float)):
        trace["started_at"] = ts

    if event_type == "tool_intent_started":
        trace["status"] = "started"
    elif event_type == "tool_exec_started":
        trace["status"] = "running"
        trace["exec_started_at"] = ts
    elif event_type == "tool_exec_finished":
        trace["status"] = "finished"
        trace["finished_at"] = ts
    elif event_type == "tool_exec_failed":
        trace["status"] = "failed"
        trace["finished_at"] = ts

    started_at = trace.get("started_at")
    finished_at = trace.get("finished_at")
    if isinstance(started_at, (int, float)) and isinstance(finished_at, (int, float)) and finished_at >= started_at:
        trace["duration"] = round(finished_at - started_at, 2)

    tool_trace_map[tool_name] = trace


def _finalize_tool_traces(tool_trace_map: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    traces: List[Dict[str, Any]] = []
    for trace in tool_trace_map.values():
        tool_name = str(trace.get("tool_name") or "").strip()
        if not tool_name:
            continue
        item = dict(trace)
        if isinstance(item.get("duration"), (int, float)):
            item["duration"] = round(float(item["duration"]), 2)
        traces.append(item)
    return traces


def _get_agent_class_map():
    return {
        'agent_showrunner': ShowrunnerAgent,
        'agent_scriptwriter': ScriptwriterAgent,
        'agent_critic': CriticAgent,
        'agent_lorebook': WorldviewAgent,
        'agent_muse': MuseAgent,
        'agent_style': StyleChatAgent,
    }


def _create_agent_instance(agent_id: str, user_id: str, project_name: str):
    """统一构建聊天 Agent，避免各路由分支各自硬编码初始化参数。"""
    agent_class_map = _get_agent_class_map()
    cls = agent_class_map.get(agent_id, SparkBaseAgent)
    if cls == SparkBaseAgent:
        return cls(agent_id=agent_id, user_id=user_id)
    if cls == StyleChatAgent:
        return cls(user_id=user_id, project_name=project_name)
    return cls(user_id=user_id)


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
    project_name = current_project_name.get() or request.query_params.get('projectName')
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
    project_name = current_project_name.get() or request.query_params.get('projectName')
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
    project_name = current_project_name.get() or request.query_params.get('projectName')
    if not project_name:
        return JSONResponse(status_code=400, content={'error': '缺少项目名称'})

    cm = ChatManager(user_id=user_id, project_name=project_name)
    ok = cm.delete_message(messageId)
    return {'success': True, 'deleted': ok}


@chat_router.post('/api/chat/edit')
async def edit_chat_message(data: ChatMessageEditRequest, user: dict = Depends(get_current_user)):
    """编辑消息并重新开始对话。
    
    逻辑：
    1. 找到该消息，更新其内容。
    2. 删除该消息之后的所有消息。
    3. 如果是用户消息，则触发 Agent 重新回复。
    """
    user_id = str(user['user_id'])
    project_name = current_project_name.get() or data.projectName
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
        
        # 特殊处理导演：支持重新路由
        if data.agentId == 'agent_director':
            try:
                print(f"[EditChat] Re-triggering Director for: {project_name}")
                director = DirectorAgent(user_id=user_id, project_name=project_name)
                
                history = cm.get_history(agent_id="agent_director", context_key=data.contextKey, limit=5)
                targets = await run_in_threadpool(director.think_and_route, data.content, history=history)
                
                if targets:
                    for target in targets:
                        cm.append_message(
                            agent_id=target,
                            context_key=data.contextKey,
                            role="user",
                            content=data.content,
                            metadata={
                                "routed_by": "agent_director",
                                "source_context": data.contextKey,
                                "source_agent": "agent_director",
                                "active_context": effective_active_context
                            },
                        )
                    
                    status_text = f"导演正在重新调度：{_format_targets(targets)}"
                    cm.append_message(
                        agent_id="agent_director",
                        context_key=data.contextKey,
                        role="assistant",
                        content=status_text,
                        metadata={"type": "routing_summary", "channel": "edit_route"},
                    )
                    return {'success': True, 'status': status_text}
                else:
                    reply = await run_in_threadpool(director.direct_reply, data.content, history=None, active_context=effective_active_context)
                    cm.append_message(
                        agent_id="agent_director",
                        context_key=data.contextKey,
                        role="assistant",
                        content=reply,
                        metadata={"type": "director_reply", "channel": "edit_direct"},
                    )
                    return {'success': True, 'reply': reply}
            except Exception as e:
                print(f"[EditChat] Director re-trigger failed: {e}")
                return JSONResponse(status_code=500, content={'error': f'导演重新调度失败: {str(e)}'})

        # 实例化专家 Agent 并获取回复
        agent_class_map = _get_agent_class_map()
        history = cm.get_history(agent_id=data.agentId, context_key=data.contextKey, limit=10)

        try:
            print(f"[EditChat] Triggering reply for expert agent: {data.agentId}")
            agent_inst = _create_agent_instance(data.agentId, user_id, project_name)
                
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
            return JSONResponse(status_code=500, content={'error': f'Agent 重新生成失败: {str(e)}'})

    return {'success': True}


@chat_router.post('/api/chat/edit/stream')
async def edit_chat_message_stream(request: Request, data: ChatMessageEditRequest, user: dict = Depends(get_current_user)):
    """编辑消息并重新开始对话（流式输出）。"""
    user_id = str(user['user_id'])
    project_name = current_project_name.get() or data.projectName
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
    stop_event = threading.Event()

    if data.agentId == 'agent_director':
        director = DirectorAgent(user_id=user_id, project_name=project_name)
        try:
            history = cm.get_history(agent_id='agent_director', context_key=data.contextKey, limit=5)
            targets = await run_in_threadpool(director.think_and_route, data.content, history=history)

            if targets:
                for target in targets:
                    cm.append_message(
                        agent_id=target,
                        context_key=data.contextKey,
                        role='user',
                        content=data.content,
                        metadata={
                            'routed_by': 'agent_director',
                            'source_context': data.contextKey,
                            'source_agent': 'agent_director',
                            'active_context': effective_active_context,
                        },
                    )

                status_text = f"导演正在重新调度：{_format_targets(targets)}"
                cm.append_message(
                    agent_id='agent_director',
                    context_key=data.contextKey,
                    role='assistant',
                    content=status_text,
                    metadata={'type': 'routing_summary', 'channel': 'edit_route_stream'},
                )
                return StreamingResponse(
                    iter([_serialize_stream_event({"event": "assistant_delta", "text": status_text})]),
                    media_type=_NDJSON_MEDIA_TYPE,
                )

            async def director_generate():
                async for chunk in iterate_sync_iterable_in_thread(
                    lambda: director.direct_and_record_stream(
                        user_id=user_id,
                        project_name=project_name,
                        context_key=data.contextKey,
                        user_message=data.content,
                        active_context=effective_active_context,
                        metadata={'channel': 'edit_direct_stream'},
                        stop_event=stop_event,
                    ),
                    request=request,
                    stop_event=stop_event,
                ):
                    yield chunk

            return StreamingResponse(director_generate(), media_type=_NDJSON_MEDIA_TYPE)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f'导演重新调度失败: {str(e)}')

    history = cm.get_history(agent_id=data.agentId, context_key=data.contextKey, limit=10)
    agent_inst = _create_agent_instance(data.agentId, user_id, project_name)

    async def generate():
        import time
        start_time = time.time()
        buf: List[str] = []
        reasoning_buf: List[str] = []
        tool_trace_map: Dict[str, Dict[str, Any]] = {}
        reasoning_end_time = None
        terminated_early = False

        try:
            async for delta in iterate_sync_iterable_in_thread(
                lambda: agent_inst.chat_stream(data.content, history=history, active_context=effective_active_context),
                request=request,
                stop_event=stop_event,
            ):
                if stop_event.is_set():
                    terminated_early = True
                    break
                if not delta:
                    continue

                _collect_tool_trace_from_event(tool_trace_map, delta)
                 
                event_type = delta.get("event") if isinstance(delta, dict) else "assistant_delta"
                 
                if event_type == "reasoning_delta":
                    reasoning_buf.append(str(delta.get("text") or ""))
                
                if event_type == "assistant_delta" and reasoning_end_time is None and reasoning_buf:
                    reasoning_end_time = time.time()
                    
                text = _extract_visible_text(delta)
                if text:
                    buf.append(text)
                yield _serialize_stream_event(delta)
        except Exception as e:
            if stop_event.is_set():
                terminated_early = True
                return
            err = f"\n[Agent Error] 重新生成失败: {e}"
            buf.append(err)
            yield _serialize_stream_event({"event": "error", "message": err})
        finally:
            end_time = time.time()
            reply = ''.join(buf).strip()
            reasoning = ''.join(reasoning_buf).strip()
            
            if reasoning and reasoning_end_time is None:
                reasoning_duration = end_time - start_time
            elif reasoning:
                reasoning_duration = reasoning_end_time - start_time
            else:
                reasoning_duration = 0.0
                
            metadata = {'channel': 'edit_reply_stream'}
            if terminated_early:
                metadata['interrupted'] = True
                metadata['finish_reason'] = 'cancelled'
            if reasoning:
                metadata['reasoning'] = reasoning
                metadata['reasoning_duration'] = round(reasoning_duration, 2)

            finalized_tool_traces = _finalize_tool_traces(tool_trace_map)
            if finalized_tool_traces:
                metadata['tool_traces'] = finalized_tool_traces
              
            if reply or reasoning or finalized_tool_traces:
                cm.append_message(
                    agent_id=data.agentId,
                    context_key=data.contextKey,
                    role='assistant',
                    content=reply,
                    metadata=metadata,
                )

    return StreamingResponse(generate(), media_type='application/x-ndjson; charset=utf-8')


@chat_router.post('/api/chat/send')
async def send_chat_message(data: ChatSendRequest, user: dict = Depends(get_current_user)):
    """发送消息。

规则：
- 对导演(agent_director)说：执行路由，并把消息"静默写入"多个目标 Agent 的会话
- 对具体 Agent 说：仅写入该 Agent 的会话（不重复写到导演）
"""
    user_id = str(user['user_id'])
    project_name = current_project_name.get() or data.projectName
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

    # 导演：先判断是否需要路由（单次思考）
    if agent_id == 'agent_director':
        director = DirectorAgent(user_id=user_id, project_name=project_name)
        
        # 优先使用显式目标，否则由导演思考
        targets = data.targets
        if not targets:
            cm = ChatManager(user_id=user_id, project_name=project_name)
            # 获取最近历史辅助判断
            history = cm.get_history(agent_id="agent_director", context_key=context_key, limit=5)
            targets = await run_in_threadpool(director.think_and_route, message, history=history)

        if targets:
            summary = await run_in_threadpool(
                director.route_and_record,
                user_id=user_id,
                project_name=project_name,
                context_key=context_key,
                user_message=message,
                active_context=effective_active_context,
                explicit_targets=targets,
                metadata={'channel': 'global'},
            )
            return {
                'success': True,
                'mode': 'director',
                'routed': True,
                'status': summary.get('status_text', '导演正在调度...'),
                'routed_to': summary.get('routed_to', []),
                'reply': summary.get('reply', ''),
            }

        reply = await run_in_threadpool(
            director.direct_and_record,
            user_id=user_id,
            project_name=project_name,
            context_key=context_key,
            user_message=message,
            active_context=effective_active_context,
            metadata={'channel': 'global'},
        )
        return {
            'success': True,
            'mode': 'director',
            'routed': False,
            'reply': reply,
        }

    # Direct-to-agent: record message and TRIGGER Agent reply
    cm = ChatManager(user_id=user_id, project_name=project_name)
    
    # 1. Record user message
    cm.append_message(
        agent_id=agent_id,
        context_key=context_key,
        role='user',
        content=message,
        metadata={
            'channel': 'direct',
            **({'active_context': effective_active_context} if effective_active_context else {}),
        },
    )

    # 2. Instantiate Agent and get reply
    history = cm.get_history(agent_id=agent_id, context_key=context_key, limit=10)

    try:
        agent_inst = _create_agent_instance(agent_id, user_id, project_name)
        
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
        return JSONResponse(status_code=500, content={'error': f'Agent 对话失败: {str(e)}'})


@chat_router.post('/api/chat/send/stream')
async def send_chat_message_stream(request: Request, data: ChatSendRequest, user: dict = Depends(get_current_user)):
    """发送消息（流式输出，text/plain）。

    与 /api/chat/send 规则一致，但 AI 回复以流式文本返回。
    """
    user_id = str(user['user_id'])
    project_name = current_project_name.get() or data.projectName
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
    stop_event = threading.Event()

    # 导演：需要路由时仅流式返回状态文本；不需要路由时由导演流式直答。
    if agent_id == 'agent_director':
        director = DirectorAgent(user_id=user_id, project_name=project_name)
        
        # 优先使用显式目标，否则由导演思考
        targets = data.targets
        if not targets:
            cm = ChatManager(user_id=user_id, project_name=project_name)
            history = cm.get_history(agent_id="agent_director", context_key=context_key, limit=5)
            # 这里的思考是同步/非流式的（通常很快），拿到结果后再决定后续流式逻辑
            targets = director.think_and_route(message, history=history)

        if targets:
            async def routed_generate():
                async for chunk in iterate_sync_iterable_in_thread(
                    lambda: director.route_and_record_stream(
                        user_id=user_id,
                        project_name=project_name,
                        context_key=context_key,
                        user_message=message,
                        active_context=effective_active_context,
                        explicit_targets=targets,
                        metadata={'channel': 'global'},
                        stop_event=stop_event,
                    ),
                    request=request,
                    stop_event=stop_event,
                ):
                    yield chunk

            return StreamingResponse(routed_generate(), media_type=_NDJSON_MEDIA_TYPE)

        async def direct_generate():
            async for chunk in iterate_sync_iterable_in_thread(
                lambda: director.direct_and_record_stream(
                    user_id=user_id,
                    project_name=project_name,
                    context_key=context_key,
                    user_message=message,
                    active_context=effective_active_context,
                    metadata={'channel': 'global'},
                    stop_event=stop_event,
                ),
                request=request,
                stop_event=stop_event,
            ):
                yield chunk

        return StreamingResponse(direct_generate(), media_type=_NDJSON_MEDIA_TYPE)

    cm = ChatManager(user_id=user_id, project_name=project_name)
    cm.append_message(
        agent_id=agent_id,
        context_key=context_key,
        role='user',
        content=message,
        metadata={
            'channel': 'direct',
            **({'active_context': effective_active_context} if effective_active_context else {}),
        },
    )

    history = cm.get_history(agent_id=agent_id, context_key=context_key, limit=10)
    agent_inst = _create_agent_instance(agent_id, user_id, project_name)

    async def generate():
        import time
        start_time = time.time()
        buf: List[str] = []
        reasoning_buf: List[str] = []
        tool_trace_map: Dict[str, Dict[str, Any]] = {}
        reasoning_end_time = None
        terminated_early = False

        try:
            async for delta in iterate_sync_iterable_in_thread(
                lambda: agent_inst.chat_stream(message, history=history, active_context=effective_active_context),
                request=request,
                stop_event=stop_event,
            ):
                if stop_event.is_set():
                    terminated_early = True
                    break
                if not delta:
                    continue

                _collect_tool_trace_from_event(tool_trace_map, delta)
                 
                event_type = delta.get("event") if isinstance(delta, dict) else "assistant_delta"
                 
                if event_type == "reasoning_delta":
                    reasoning_buf.append(str(delta.get("text") or ""))
                
                if event_type == "assistant_delta" and reasoning_end_time is None and reasoning_buf:
                    reasoning_end_time = time.time()
                    
                text = _extract_visible_text(delta)
                if text:
                    buf.append(text)
                yield _serialize_stream_event(delta)
        except Exception as e:
            if stop_event.is_set():
                terminated_early = True
                return
            err = f"\n[Agent Error] 对话失败: {e}"
            buf.append(err)
            yield _serialize_stream_event({"event": "error", "message": err})
        finally:
            end_time = time.time()
            reply = ''.join(buf).strip()
            reasoning = ''.join(reasoning_buf).strip()
            
            if reasoning and reasoning_end_time is None:
                reasoning_duration = end_time - start_time
            elif reasoning:
                reasoning_duration = reasoning_end_time - start_time
            else:
                reasoning_duration = 0.0
                
            metadata = {'channel': 'direct_reply_stream'}
            if terminated_early:
                metadata['interrupted'] = True
                metadata['finish_reason'] = 'cancelled'
            if reasoning:
                metadata['reasoning'] = reasoning
                metadata['reasoning_duration'] = round(reasoning_duration, 2)

            finalized_tool_traces = _finalize_tool_traces(tool_trace_map)
            if finalized_tool_traces:
                metadata['tool_traces'] = finalized_tool_traces
              
            if reply or reasoning or finalized_tool_traces:
                cm.append_message(
                    agent_id=agent_id,
                    context_key=context_key,
                    role='assistant',
                    content=reply,
                    metadata=metadata,
                )

    return StreamingResponse(generate(), media_type=_NDJSON_MEDIA_TYPE)
