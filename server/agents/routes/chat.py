"""
Chat / Session History API - 通用会话机制
"""

# ─────────────────────────────────────────────────────────────────────────────
# 关于Segment 时序记录
#
# 【背景与问题】
#   聊天流（chat_stream）本质上是 AI 在时间线上交替输出多种内容的序列，例如：
#     推理(reasoning_delta) → 正文(assistant_delta) → 工具(tool_*) → 推理 → 正文
#   _collect_segment_from_event 与 _finalize_segments 是一对旁路函数：
#   - 与既有的 buf / reasoning_buf / tool_trace_map 并列运行，互不干扰；
#   - 监听每一个流事件，同步维护带顺序的 segments 列表；
#   - 流结束后，通过 metadata['segments'] 写入 SQLite（chat_messages.metadata_json 字段）。
#   - 前端 chatStore.js 的 _normalizeHistoryMessage 会优先读取 metadata.segments，
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
# 【新增业务流接入规范】
#   若将来新增了自定义流式路由（非标准 chat_stream），且希望支持 segment 时序记录：
#   1. 在 generate() 内声明：
#        segments: List[Dict[str, Any]] = []
#        _seg_invocation_counter: List[int] = [0]
#   2. 在每个 delta 事件处理处，与 _collect_tool_trace_from_event 平行调用：
#        _collect_segment_from_event(segments, _seg_invocation_counter, delta)
#   3. 在 finally 落盘时：
#        finalized_segments = _finalize_segments(segments)
#        if finalized_segments:
#            metadata['segments'] = finalized_segments
# ─────────────────────────────────────────────────────────────────────────────
from fastapi import APIRouter, Depends, Request, HTTPException, Query
from fastapi.responses import StreamingResponse, JSONResponse
from starlette.concurrency import run_in_threadpool
from typing import Any, Dict, List
import asyncio
import queue
import threading
import time
import json

from core.auth import get_current_user
from core.models import UserInfoSession, ChatMessage
from core.request_context import (
    get_current_project_name,
    resolve_project_name,
    set_current_inspiration_context,
)

from agents.chat_manager import ChatManager
from agents.agent_director import DirectorAgent
from agents import ShowrunnerAgent, ScriptwriterAgent, CriticAgent

from agents.agent_lorebook import WorldviewAgent
from agents.agent_style_chat import StyleChatAgent
from agents.setup_agents import MuseAgent
from agents.communication import SparkBaseAgent

from .schemas import (
    ChatSendRequest, ChatMessageEditRequest, ChatTaskCancelRequest,
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
    list_running_tasks,
    list_recent_tasks,
    build_task_status_payload,
)

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
        if delta.get("tool_action"):
            trace["tool_action"] = delta["tool_action"]
    elif event_type == "tool_exec_finished":
        trace["status"] = "finished"
        trace["finished_at"] = ts
        if delta.get("tool_result"):
            trace["tool_result"] = delta["tool_result"]
    elif event_type == "tool_exec_failed":
        trace["status"] = "failed"
        trace["finished_at"] = ts

    started_at = trace.get("started_at")
    finished_at = trace.get("finished_at")
    if isinstance(started_at, (int, float)) and isinstance(finished_at, (int, float)) and finished_at >= started_at:
        trace["duration"] = round(finished_at - started_at, 2)

    tool_trace_map[tool_name] = trace


def _append_text_segment(
    segments: List[Dict[str, Any]],
    *,
    seg_type: str,
    text: str,
    source_agent: str = "",
) -> None:
    if not text:
        return

    last = segments[-1] if segments else None
    if (
        last
        and last.get("type") == seg_type
        and (last.get("source_agent") or "") == (source_agent or "")
    ):
        last["text"] = str(last.get("text") or "") + text
        return

    segment = {"type": seg_type, "text": text}
    if source_agent:
        segment["source_agent"] = source_agent
    segments.append(segment)


def _append_or_upgrade_tool_segment(
    segments: List[Dict[str, Any]],
    *,
    tool_name: str,
    status: str,
    ts: float,
    source_agent: str = "",
    nested: bool = False,
    invocation_counter: List[int] | None = None,
    tool_action: str = "",
) -> None:
    for seg in reversed(segments):
        if (
            seg.get("type") == "tool_trace"
            and seg.get("tool_name") == tool_name
            and (seg.get("source_agent") or "") == (source_agent or "")
            and bool(seg.get("nested")) == bool(nested)
            and seg.get("status") not in ("finished", "failed", "cancelled")
        ):
            if status == "running" and seg.get("status") == "started":
                seg["status"] = "running"
                seg["exec_started_at"] = ts
                if tool_action:
                    seg["tool_action"] = tool_action
            return

    seg_id = ""
    if invocation_counter is not None:
        invocation_counter[0] += 1
        seg_id = f"{tool_name}::{source_agent}:{invocation_counter[0]}"

    segments.append({
        "type": "tool_trace",
        "tool_name": tool_name,
        "status": status,
        "started_at": ts,
        "source_agent": source_agent,
        "nested": nested,
        **({"exec_started_at": ts} if status == "running" else {}),
        **({"_seg_id": seg_id} if seg_id else {}),
        **({"tool_action": tool_action} if tool_action else {}),
    })


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

def _collect_segment_from_event(
    segments: List[Dict[str, Any]],
    invocation_counter: List[int],
    delta: Any,
    now_ts: float | None = None,
) -> None:
    """根据单个流式事件，同步追加或更新 segments 时序列表。

    此函数是旁路观察者，不影响 buf / reasoning_buf / tool_trace_map 的既有逻辑。
    应在每次 yield 前与 _collect_tool_trace_from_event 平行调用。
    """
    import time

    ts = round(float(now_ts if now_ts is not None else time.time()), 3)

    if not isinstance(delta, dict):
        raw_text = str(delta) if delta else ""
        if raw_text:
            _append_text_segment(segments, seg_type="text", text=raw_text)
        return

    event_type = str(delta.get("event") or "").strip()
    source_agent = str(delta.get("source_agent") or "").strip()

    # --- 推理文本段落：相邻同类合并 ---
    if event_type == "reasoning_delta":
        text = str(delta.get("text") or delta.get("content") or "")
        if not text:
            return
        _append_text_segment(segments, seg_type="reasoning", text=text, source_agent=source_agent)
        return

    # --- 正文文本段落：相邻同类合并 ---
    if event_type == "assistant_delta":
        raw_text = str(delta.get("text") or delta.get("content") or "")
        if not raw_text:
            return
        _append_text_segment(segments, seg_type="text", text=raw_text, source_agent=source_agent)
        return

    # --- 工具调用段落：开始时追加，结束时原地更新 ---
    tool_name = str(delta.get("tool_name") or delta.get("toolName") or "").strip()
    if not tool_name:
        return

    is_nested = bool(delta.get("nested"))

    if event_type == "tool_intent_started":
        _append_or_upgrade_tool_segment(
            segments,
            tool_name=tool_name,
            status="started",
            ts=ts,
            source_agent=source_agent,
            nested=is_nested,
            invocation_counter=invocation_counter,
        )
        return

    if event_type == "tool_exec_started":
        tool_action = str(delta.get("tool_action") or "").strip()
        _append_or_upgrade_tool_segment(
            segments,
            tool_name=tool_name,
            status="running",
            ts=ts,
            source_agent=source_agent,
            nested=is_nested,
            invocation_counter=invocation_counter,
            tool_action=tool_action,
        )
        return

    if event_type in {"tool_exec_finished", "tool_exec_failed"}:
        # 精确定位：找到最近一个未结束的同名（同 source_agent）工具段落并原地更新
        final_status = "finished" if event_type == "tool_exec_finished" else "failed"
        tool_result = str(delta.get("tool_result") or "").strip()
        for seg in reversed(segments):
            if (
                seg.get("type") == "tool_trace"
                and seg.get("tool_name") == tool_name
                and (seg.get("source_agent") or "") == source_agent
                and seg.get("status") not in ("finished", "failed")
            ):
                seg["status"] = final_status
                seg["finished_at"] = ts
                started = seg.get("started_at")
                if isinstance(started, (int, float)):
                    seg["duration"] = round(ts - started, 2)
                if tool_result:
                    seg["tool_result"] = tool_result
                break
        return


def _finalize_segments(segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """终态清理：将流结束时仍处于中间状态的工具段落标记为 finished。

    正常情况下不应有遗漏（tool_exec_finished 都应已到达），此函数仅作安全兜底。
    """
    import time
    now_ts = round(time.time(), 3)
    for seg in segments:
        if seg.get("type") == "tool_trace" and seg.get("status") not in ("finished", "failed", "cancelled"):
            seg["status"] = "finished"
            seg["finished_at"] = now_ts
            started = seg.get("started_at")
            if isinstance(started, (int, float)):
                seg["duration"] = round(now_ts - started, 2)
    return segments


def _get_agent_class_map():
    return {
        'agent_director': DirectorAgent,
        'agent_showrunner': ShowrunnerAgent,
        'agent_scriptwriter': ScriptwriterAgent,
        'agent_critic': CriticAgent,
        'agent_lorebook': WorldviewAgent,
        'agent_muse': MuseAgent,
        'agent_style': StyleChatAgent,
    }


def _create_agent_instance(agent_id: str, user_id: str, project_name: str):
    """统一构建聊天 Agent，避免各路由分支各自硬编码初始化参数。"""
    
    if agent_id == "agent_director":
        # --------- 【LangGraph 升级新增】--------- 
        # 导演 Agent 改由 DirectorGraph 接管，以利用其调度和流式事件广播优势
        from agents.director_graph import run_director_stream
        
        class DirectorGraphWrapper:
            def __init__(self, uid, pname):
                self.user_id = uid
                self.project_name = pname
                self.agent_id = "agent_director"
                self.name = "主控导演"
                
                # mock 必要的属性以通过后续层级检查
                class MockBeacon:
                    is_open = True
                self.beacon = MockBeacon()
            
            def chat_stream(self, user_message, history=None, active_context=None, **kwargs):
                return run_director_stream(
                    user_id=self.user_id,
                    project_name=self.project_name,
                    user_message=user_message,
                    history=history,
                    active_context=active_context or "",
                )
        return DirectorGraphWrapper(user_id, project_name)
        # --------- 【LangGraph 升级结束】---------

    agent_class_map = _get_agent_class_map()
    cls = agent_class_map.get(agent_id, SparkBaseAgent)
    if cls == SparkBaseAgent:
        return cls(agent_id=agent_id, user_id=user_id)
    if cls in (StyleChatAgent, DirectorAgent):
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
    progress_queue = queue.Queue()
    entry = ChatTaskEntry(
        task_key=task_key,
        user_id=user_id,
        project_name=project_name,
        agent_id=data.agentId,
        context_key=data.contextKey,
        stop_event=stop_event,
        progress_queue=progress_queue,
        status='running',
        started_at=time.time(),
        channel='edit_reply_stream',
    )
    register_task(entry)

    history = cm.get_history(agent_id=data.agentId, context_key=data.contextKey, limit=10)
    agent_inst = _create_agent_instance(data.agentId, user_id, project_name)

    # ── 后台线程：执行 chat_stream 并写入进度队列 + 数据库 ──
    def _run_chat_background():
        import contextvars
        from core.request_context import current_user_id, current_project_name

        ctx = contextvars.copy_context()

        def _in_context():
            current_user_id.set(str(user_id))
            current_project_name.set(project_name)

            buf: List[str] = []
            reasoning_buf: List[str] = []
            tool_trace_map: Dict[str, Dict[str, Any]] = {}
            reasoning_end_time = None
            terminated_early = False
            segments: List[Dict[str, Any]] = []
            _seg_invocation_counter: List[int] = [0]
            start_time = time.time()

            try:
                for delta in agent_inst.chat_stream(data.content, history=history, active_context=effective_active_context):
                    if stop_event.is_set():
                        terminated_early = True
                        break
                    if not delta:
                        continue

                    _collect_tool_trace_from_event(tool_trace_map, delta)
                    _collect_segment_from_event(segments, _seg_invocation_counter, delta)

                    event_type = delta.get("event") if isinstance(delta, dict) else "assistant_delta"

                    if event_type == "reasoning_delta":
                        reasoning_buf.append(str(delta.get("text") or ""))

                    if event_type == "assistant_delta" and reasoning_end_time is None and reasoning_buf:
                        reasoning_end_time = time.time()

                    text = _extract_visible_text(delta)
                    if text:
                        buf.append(text)

                    # 写入进度队列供 SSE 观察者读取
                    progress_queue.put(delta)

            except Exception as e:
                if stop_event.is_set():
                    terminated_early = True
                else:
                    from .schemas import format_ai_error
                    err = f"\n{format_ai_error(e)}"
                    buf.append(err)
                    progress_queue.put({"event": "error", "message": err})
                    update_task_status(task_key, 'error', error_message=err)
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

                finalized_segments = _finalize_segments(segments)
                if finalized_segments:
                    metadata['segments'] = finalized_segments

                result_msg_id = None
                if reply or reasoning or finalized_tool_traces:
                    msg_obj = cm.append_message(
                        agent_id=data.agentId,
                        context_key=data.contextKey,
                        role='assistant',
                        content=reply,
                        metadata=metadata,
                    )
                    result_msg_id = msg_obj.id

                final_status = 'cancelled' if terminated_early else 'completed'
                update_task_status(
                    task_key, final_status,
                    result_message_id=result_msg_id,
                    result_content=reply,
                    result_metadata=metadata,
                )

                progress_queue.put(None)
                cleanup_task(task_key)

        ctx.run(_in_context)

    thread = threading.Thread(target=_run_chat_background, daemon=True, name=f"chat_edit_bg_{task_key}")
    thread.start()

    # ── SSE 观察者：从进度队列读取事件并转发给前端 ──
    async def observe():
        heartbeat_interval = 5.0
        last_heartbeat = time.time()
        while True:
            try:
                event = progress_queue.get_nowait()
            except queue.Empty:
                if request and await request.is_disconnected():
                    break
                current = time.time()
                if current - last_heartbeat >= heartbeat_interval:
                    # NDJSON 心跳（非 SSE 注释），前端 _consumeStream 会忽略 heartbeat 事件
                    yield _serialize_stream_event({"event": "heartbeat"})
                    last_heartbeat = current
                await asyncio.sleep(0.05)
                continue
            if event is None:
                break
            yield _serialize_stream_event(event)

    return StreamingResponse(observe(), media_type=_NDJSON_MEDIA_TYPE)


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

    # 统一处理所有 Agent（包括导演）
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

    task_key = _make_task_key(user_id, project_name, agent_id, context_key)

    # 检查是否已有同 key 的活跃任务
    existing = get_task_by_parts(user_id, project_name, agent_id, context_key)
    if existing and existing.status == 'running':
        raise HTTPException(status_code=409, detail='该会话已有任务在执行')

    # 创建任务入口
    stop_event = threading.Event()
    progress_queue = queue.Queue()
    entry = ChatTaskEntry(
        task_key=task_key,
        user_id=user_id,
        project_name=project_name,
        agent_id=agent_id,
        context_key=context_key,
        stop_event=stop_event,
        progress_queue=progress_queue,
        status='running',
        started_at=time.time(),
        channel='direct_reply_stream',
    )
    register_task(entry)

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

    # ── 后台线程：执行 chat_stream 并写入进度队列 + 数据库 ──
    def _run_chat_background():
        import contextvars
        from core.request_context import current_user_id, current_project_name

        # 复制请求级 ContextVar 到后台线程
        ctx = contextvars.copy_context()

        def _in_context():
            current_user_id.set(str(user_id))
            current_project_name.set(project_name)

            buf: List[str] = []
            reasoning_buf: List[str] = []
            tool_trace_map: Dict[str, Dict[str, Any]] = {}
            reasoning_end_time = None
            terminated_early = False
            segments: List[Dict[str, Any]] = []
            _seg_invocation_counter: List[int] = [0]
            start_time = time.time()

            try:
                for delta in agent_inst.chat_stream(message, history=history, active_context=effective_active_context):
                    if stop_event.is_set():
                        terminated_early = True
                        break
                    if not delta:
                        continue

                    _collect_tool_trace_from_event(tool_trace_map, delta)
                    _collect_segment_from_event(segments, _seg_invocation_counter, delta)

                    event_type = delta.get("event") if isinstance(delta, dict) else "assistant_delta"

                    if event_type == "reasoning_delta":
                        reasoning_buf.append(str(delta.get("text") or ""))

                    if event_type == "assistant_delta" and reasoning_end_time is None and reasoning_buf:
                        reasoning_end_time = time.time()

                    text = _extract_visible_text(delta)
                    if text:
                        buf.append(text)

                    # 写入进度队列供 SSE 观察者读取
                    progress_queue.put(delta)

            except Exception as e:
                if stop_event.is_set():
                    terminated_early = True
                else:
                    from .schemas import format_ai_error
                    err = f"\n{format_ai_error(e)}"
                    buf.append(err)
                    progress_queue.put({"event": "error", "message": err})
                    update_task_status(task_key, 'error', error_message=err)
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

                finalized_segments = _finalize_segments(segments)
                if finalized_segments:
                    metadata['segments'] = finalized_segments

                result_msg_id = None
                if reply or reasoning or finalized_tool_traces:
                    msg = cm.append_message(
                        agent_id=agent_id,
                        context_key=context_key,
                        role='assistant',
                        content=reply,
                        metadata=metadata,
                    )
                    result_msg_id = msg.id

                # 更新任务状态
                final_status = 'cancelled' if terminated_early else 'completed'
                update_task_status(
                    task_key, final_status,
                    result_message_id=result_msg_id,
                    result_content=reply,
                    result_metadata=metadata,
                )

                # 结束哨兵
                progress_queue.put(None)

                # 延迟清理注册表
                cleanup_task(task_key)

        ctx.run(_in_context)

    thread = threading.Thread(target=_run_chat_background, daemon=True, name=f"chat_bg_{task_key}")
    thread.start()

    # ── SSE 观察者：从进度队列读取事件并转发给前端 ──
    async def observe():
        heartbeat_interval = 5.0
        last_heartbeat = time.time()
        while True:
            try:
                event = progress_queue.get_nowait()
            except queue.Empty:
                # 检查前端是否断连
                if request and await request.is_disconnected():
                    # 前端断连 → 观察者退出，但后台线程继续
                    break
                current = time.time()
                if current - last_heartbeat >= heartbeat_interval:
                    # NDJSON 心跳（非 SSE 注释），前端 _consumeStream 会忽略 heartbeat 事件
                    yield _serialize_stream_event({"event": "heartbeat"})
                    last_heartbeat = current
                await asyncio.sleep(0.05)
                continue
            if event is None:
                break
            yield _serialize_stream_event(event)

    return StreamingResponse(observe(), media_type=_NDJSON_MEDIA_TYPE)


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


@chat_router.get('/api/chat/running-tasks')
async def get_chat_running_tasks(
    request: Request,
    user: dict = Depends(get_current_user),
):
    """列出当前用户在当前项目下所有运行中的聊天任务。"""
    user_id = str(user['user_id'])
    project_name = resolve_project_name(get_current_project_name(), request.query_params.get('projectName'))
    if not project_name:
        return JSONResponse(status_code=400, content={'error': '缺少项目名称'})

    tasks = list_running_tasks(user_id, project_name)
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
    user: dict = Depends(get_current_user),
):
    """重连到正在运行的后台聊天任务，消费 progress_queue 中的后续事件。

    前端关闭/刷新后重新进入时调用此端点：
    - running → 新 SSE 观察者接入 progress_queue，实时推送后续 delta
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

    # 任务仍在运行：作为新观察者接入 progress_queue
    progress_queue = entry.progress_queue

    async def observe():
        heartbeat_interval = 5.0
        last_heartbeat = time.time()
        while True:
            try:
                event = progress_queue.get_nowait()
            except queue.Empty:
                if request and await request.is_disconnected():
                    break
                # 任务可能已完成但队列还没被消费完，检查状态
                if entry.status != 'running' and progress_queue.empty():
                    break
                current = time.time()
                if current - last_heartbeat >= heartbeat_interval:
                    yield _serialize_stream_event({"event": "heartbeat"})
                    last_heartbeat = current
                await asyncio.sleep(0.05)
                continue
            if event is None:
                break
            yield _serialize_stream_event(event)

    return StreamingResponse(observe(), media_type=_NDJSON_MEDIA_TYPE)
