"""
Director SupervisorGraph - 基于 LangGraph 的导演调度升级版
"""
from __future__ import annotations

import json
import os
import queue
import operator
from typing import TypedDict, Annotated, Any, Dict, Optional

from langgraph.graph import StateGraph, START, END
from langgraph.config import get_stream_writer
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

from agents.communication import (
    HANDOFF_COMPLETION_REPORT_TO_USER,
    HANDOFF_COMPLETION_RETURN_TO_DIRECTOR,
    HANDOFF_COMPLETION_SILENT_CONTINUE,
    HANDOFF_CONFIRMATION_CONFIRMED,
    HANDOFF_CONFIRMATION_NOT_REQUIRED,
    HANDOFF_DELIVERY_DIRECT_TO_USER,
    HANDOFF_DELIVERY_RETURN_TO_DIRECTOR,
    ModelStreamRetryExhaustedError,
    ModelTurnRetryNotice,
    build_tool_stream_event,
    get_tool_result_failure_message,
    get_global_context,
    is_tool_result_failure,
    is_stop_event_set,
    stream_model_turn_with_retry,
    normalize_handoff_payload,
    normalize_tool_name,
    set_tool_event_sink,
    transfer_baton,
)
from llm.agen_matchbox.reasoning_compat import extract_visible_text_from_plain_text

from agents.agent_factory import create_agent_instance
from agents.prompt_layout import build_current_user_message
from agents.work_tracker import build_work_tracker_prompt_context
from llm.agen_matchbox.tool_protocol import build_tool_result_messages

# ==================== State 定义 ====================

class DirectorState(TypedDict):
    """导演调度图的共享状态"""
    user_id: str
    project_name: str
    
    messages: Annotated[list, operator.add]
    active_context: str
    current_user_message: str
    
    pending_delegate: Optional[Dict[str, Any]]
    sub_agent_result: Optional[str]
    baton_holder: Optional[str]
    force_return_to_director: Optional[bool]
    stop_event: Any
    
    stream_events: Annotated[list, operator.add]


# ==================== 辅助方法 ====================

def _drain_tool_event_sink_to_writer(writer, sink: queue.Queue, source_agent: str, exclude_tools: set | None = None) -> None:
    """
    把 ToolEventSink 中的嵌套工具事件通过 LangGraph StreamWriter 广播给前端。
    exclude_tools: 需要过滤掉的工具名集合（外层已显式 yield 了 started/finished，避免重复）。
    """
    if not sink:
        return
    while not sink.empty():
        try:
            evt = sink.get_nowait()
            if isinstance(evt, dict):
                # 过滤掉与外层正在执行的同名工具事件，避免前端收到重复 segment
                evt_tool = normalize_tool_name(evt.get("tool_name") or "")
                if exclude_tools and evt_tool in exclude_tools:
                    continue
                evt["nested"] = True
                evt["source_agent"] = evt.get("source_agent") or source_agent
                writer(evt)
        except queue.Empty:
            break


def _ensure_graph_agent_registered(agent_id: str, user_id: str, project_name: str):
    ctx = get_global_context()
    namespace = ctx._user_namespaces.setdefault(str(user_id), {})
    agent = namespace.get(agent_id)
    if agent is None:
        agent = create_agent_instance(agent_id, user_id, project_name)
        if hasattr(agent, "bind_context"):
            agent.bind_context(ctx)
        else:
            ctx.register(agent)
    return agent


def _is_scriptwriter_persist_tool(tool_name: str) -> bool:
    """判断 Scriptwriter 是否执行了会改变项目结构或正文的落盘工具。

    委派模式下结构维护同样是有效交付；不能只把正文重写工具当作成功，
    否则 rename/reorder 成功后会被导演误报为“未完成落盘”。
    """
    return normalize_tool_name(tool_name) in {
        "create_chapter",
        "create_or_rewrite_script",
        "patch_script",
        "organize_scenes_to_chapter",
        "rename_chapter",
        "rename_scene",
        "reorder_chapters",
        "reorder_scenes",
        "batch_rename_chapters",
        "batch_rename_scenes",
        "batch_update_story_metadata",
        "update_project_story_tags",
    }


def _director_tracker_has_open_items(user_id: str, project_name: str) -> bool:
    """读取导演任务板，判断是否仍有待推进的任务。"""
    if not user_id or not project_name:
        return False
    try:
        from agents.work_tracker import load_work_tracker

        items = load_work_tracker(user_id, project_name, "agent_director").get("items") or []
        if not isinstance(items, list):
            return False
        return any(
            isinstance(item, dict)
            and str(item.get("status") or "pending").strip() != "completed"
            for item in items
        )
    except Exception:
        return False


def _is_tracker_progress_update(tool_name: str, tool_args: Any, tool_result: Any) -> bool:
    """判断本次工具调用是否完成了可展示的任务板进度更新。"""
    if normalize_tool_name(tool_name) != "work_tracker" or not isinstance(tool_args, dict):
        return False

    items = (
        tool_args.get("items")
        if "items" in tool_args
        else tool_args.get("tasks", tool_args.get("todo_items"))
    )
    operations = tool_args.get("operations")
    has_overwrite = bool(tool_args.get("overwrite")) and isinstance(items, list)
    has_operations = isinstance(operations, list) and bool(operations)
    if not has_overwrite and not has_operations:
        return False

    result_text = str(tool_result or "")
    return "任务板更新失败" not in result_text and "未知操作类型" not in result_text


def _tracker_update_required_message() -> str:
    """返回不会把失败回交误判为完成的任务板协议提示。"""
    return (
        "进度板协议错误：刚收到专家回交结果，且导演任务板仍有未完成条目。"
        "请调用 work_tracker(operations=[增量操作])，并按实际结果更新："
        "成功才标为 completed；执行失败或质量不达标时保持 in_progress，"
        "在 notes 记录失败原因和重做要求；只有确实无法继续时才标为 blocked。"
        "更新后可以立即重新委派原专家重做，也可以更换专家，不会终止当前流程。"
    )


def _build_director_message_update(
    *,
    persisted_prefix: list[Any],
    director: Any,
    response: Any = None,
    tool_specs: list[Dict[str, Any]] | None = None,
    tool_results: list[tuple[str, str, Any]] | None = None,
) -> list[Any]:
    """构造 Director 节点要提交给 LangGraph 的完整消息增量。

    ``persisted_prefix`` 用于携带本节点请求前临时注入、但必须在下一节点继续存在的
    ToolMessage，例如子 Agent 回交结果。它不能只存在于本地请求变量中。
    """
    specs = list(tool_specs or [])
    messages = list(persisted_prefix or [])
    if response is not None:
        if specs:
            messages.append(director._build_tool_history_message(response, specs))
        elif getattr(response, "content", None):
            messages.append(response)
    messages.extend(build_tool_result_messages(tool_results or []))
    return messages


def _build_director_prompt_context(
    director: Any,
    *,
    user_id: str,
    project_name: str,
    active_context: str,
) -> tuple[str, str]:
    """统一构建导演稳定系统前缀与本轮动态项目上下文。"""
    from agents.agent_utils import load_prompt

    try:
        prompts = load_prompt("director")
        base_system_prompt = prompts.get("chat_system") or prompts.get(
            "system",
            "你是导演，负责协调团队中的专家。",
        )
    except Exception:
        base_system_prompt = "你是导演，负责协调团队中的专家。"

    from agents.context_provider import get_agent_context

    try:
        fresh_project_status = (
            get_agent_context(user_id, project_name, "agent_director")
            if project_name
            else ""
        )
    except Exception:
        fresh_project_status = ""

    runtime_context = "\n\n".join(
        part for part in [fresh_project_status, active_context] if part
    )
    system_instruction = director._build_tool_system_prompt(
        base_system_prompt,
        runtime_context,
    )
    return system_instruction, runtime_context


def _append_director_runtime_user_message(
    messages: List[Any],
    *,
    current_user_message: str,
    active_context: str,
    runtime_tail: str,
) -> List[Any]:
    """保留历史前缀，在末尾追加本轮刷新后的动态项目现场。"""
    result = list(messages)
    if active_context or runtime_tail:
        result.append(HumanMessage(content=build_current_user_message(
            user_message=current_user_message,
            active_context=active_context,
            runtime_tail=runtime_tail,
        )))
    return result


# ==================== 导演节点 ====================

def director_node(state: DirectorState) -> Dict[str, Any]:
    """
    导演节点：驱动 LLM，实时多路收集输出事件并利用 Sentinel 拦截委派动作。
    """
    from agents.agent_director import DirectorAgent
    from agents.tools.registry import get_tools_for_agent
    from llm.agen_matchbox import matchbox
    from llm.agen_matchbox.reasoning_compat import MessageEventStreamReasoningAdapter
    from langchain_core.messages import SystemMessage

    writer = get_stream_writer()
    
    user_id = state["user_id"]
    project_name = state["project_name"]
    messages = state.get("messages", [])
    sub_agent_result = state.get("sub_agent_result")
    tracker_update_required = bool(sub_agent_result) and _director_tracker_has_open_items(
        user_id,
        project_name,
    )
    baton_holder = state.get("baton_holder") or "agent_director"
    stop_event = state.get("stop_event")

    if is_stop_event_set(stop_event):
        return {
            "messages": [],
            "stream_events": [],
            "sub_agent_result": None,
            "baton_holder": baton_holder,
            "pending_delegate": None,
        }
    
    # 注入子 Agent 结果；该 ToolMessage 既要用于本次请求，也必须提交回图状态。
    persisted_prefix: list[Any] = []
    if sub_agent_result:
        pending = state.get("pending_delegate") or {}
        tool_call_id = str(pending.get("call_id") or "").strip()
        if not tool_call_id:
            raise ValueError("Director 回交结果缺少对应的 delegate_task tool_call_id。")
        handoff_result = ToolMessage(
            content=sub_agent_result,
            tool_call_id=tool_call_id,
            name="delegate_task",
        )
        persisted_prefix.append(handoff_result)
        messages = messages + persisted_prefix
    
    director = DirectorAgent(user_id=user_id, project_name=project_name)
    ctx = get_global_context()
    director.bind_context(ctx)
    director.open_beacon()
    director.raise_horn()
    if baton_holder == "agent_director":
        director.take_baton()
    else:
        director.return_baton()
    
    if writer:
        writer({"event": "agent_turn_started", "source_agent": "agent_director"})
    
    stream_llm = matchbox().get_user_llm(user_id, agent_name="agent_director")
    base_stream_llm = stream_llm
    tools = get_tools_for_agent("agent_director", user_id=user_id)
    if tools:
        stream_llm = stream_llm.bind_tools(tools)
    
    # 每轮从磁盘刷新项目状态；动态现场只进入最后一条 user，稳定前缀保持可缓存。
    system_instruction, active_context = _build_director_prompt_context(
        director,
        user_id=user_id,
        project_name=project_name,
        active_context=state.get("active_context", ""),
    )
    messages_with_system = [SystemMessage(content=system_instruction)] + list(messages)
    # -------------------------------------------------------------------
    
    current_user_message = str(state.get("current_user_message") or "")
    if not current_user_message:
        for message in reversed(messages):
            if isinstance(message, HumanMessage):
                content = getattr(message, "content", "")
                if isinstance(content, str):
                    current_user_message = content
                else:
                    try:
                        current_user_message = json.dumps(content, ensure_ascii=False)
                    except Exception:
                        current_user_message = str(content)
                break

    runtime_tail = build_work_tracker_prompt_context(
        user_id,
        project_name,
        "agent_director",
    )
    # 项目状态会在委派后刷新。只能追加到历史尾部，不能覆盖最早用户消息，
    # 否则一次状态变化会让它之后的全部历史前缀失去缓存。
    messages_with_system = _append_director_runtime_user_message(
        messages_with_system,
        current_user_message=current_user_message,
        active_context=active_context,
        runtime_tail=runtime_tail,
    )

    stream_events = []
    from agents.context_budget import rebudget_existing_messages

    budget_events: list[dict] = []
    messages_with_system = rebudget_existing_messages(
        user_id=user_id,
        project_name=project_name,
        agent_id="agent_director",
        messages=messages_with_system,
        llm_client=base_stream_llm,
        emit_event=budget_events.append,
        current_user_message=current_user_message,
    ).messages
    for evt in budget_events:
        evt["source_agent"] = "agent_director"
        if writer:
            writer(evt)
        stream_events.append(evt)

    tool_chunk_buffers: Dict[int, Dict] = {}
    started_tools = set()
    tool_intent_keys: Dict[str, str] = {}
    aggregated_chunk = None
    
    adapter = MessageEventStreamReasoningAdapter()
    
    for chunk in stream_model_turn_with_retry(
        stream_llm,
        messages_with_system,
        stop_event=stop_event,
    ):
        if isinstance(chunk, ModelTurnRetryNotice):
            aggregated_chunk = None
            tool_chunk_buffers = {}
            started_tools = set()
            tool_intent_keys = {}
            adapter = MessageEventStreamReasoningAdapter()
            evt = {
                "event": "retry_attempt",
                "attempt": chunk.attempt,
                "max_retries": chunk.max_attempts,
                "error_summary": chunk.error,
                "retry_scope": "model_turn",
                "source_agent": "agent_director",
            }
            if writer:
                writer(evt)
            stream_events.append(evt)
            continue
        if is_stop_event_set(stop_event):
            return {
                "messages": [],
                "stream_events": stream_events,
                "sub_agent_result": None,
                "baton_holder": baton_holder,
                "pending_delegate": None,
            }

        if aggregated_chunk is None:
            aggregated_chunk = chunk
        else:
            try:
                aggregated_chunk = aggregated_chunk + chunk
            except Exception:
                pass
        
        # 实时工具意图广播
        for tcc in getattr(chunk, "tool_call_chunks", None) or []:
            buffer_index = director._append_tool_call_chunk_buffer(tool_chunk_buffers, tcc)
            tcc_dict = director._tool_call_as_dict(tcc)
            tool_index = tcc_dict.get("index")
            if tool_index is None:
                tool_index = getattr(tcc, "index", None)
            if tool_index is None:
                tool_index = buffer_index
            tool_name = (
                tcc_dict.get("name")
                or getattr(tcc, "name", None)
                or tool_chunk_buffers.get(tool_index, {}).get("name")
            )
            if tool_name:
                tool_name = normalize_tool_name(tool_name)
                tool_call_key = director._tool_call_event_key(tool_name, tcc, tool_index, len(started_tools))
                if tool_call_key in started_tools:
                    continue
                started_tools.add(tool_call_key)
                tool_intent_keys[tool_call_key] = tool_call_key
                raw_call_id = director._extract_tool_call_id(tcc)
                if raw_call_id:
                    tool_intent_keys[raw_call_id] = tool_call_key
                tool_intent_keys.setdefault(tool_name, tool_call_key)
                progress = director._tool_progress_text(tool_name)
                evt = build_tool_stream_event(
                    "tool_intent_started",
                    tool_name,
                    source_agent="agent_director",
                    message=progress,
                    tool_call_key=tool_call_key,
                )
                if writer: writer(evt)
                stream_events.append(evt)
        
        # 实时推理/正文广播
        reasoning, content = adapter.push_message(chunk)
        if reasoning:
            evt = {"event": "reasoning_delta", "text": reasoning, "source_agent": "agent_director"}
            if writer: writer(evt)
            stream_events.append(evt)
        if content:
            evt = {"event": "assistant_delta", "text": content, "source_agent": "agent_director"}
            if writer: writer(evt)
            stream_events.append(evt)
    
    trailing_reasoning, trailing_content = adapter.flush()
    if trailing_reasoning:
        evt = {"event": "reasoning_delta", "text": trailing_reasoning, "source_agent": "agent_director"}
        if writer: writer(evt)
        stream_events.append(evt)
    if trailing_content:
        evt = {"event": "assistant_delta", "text": trailing_content, "source_agent": "agent_director"}
        if writer: writer(evt)
        stream_events.append(evt)
    
    if is_stop_event_set(stop_event):
        return {
            "messages": [],
            "stream_events": stream_events,
            "sub_agent_result": None,
            "baton_holder": baton_holder,
            "pending_delegate": None,
        }

    # 获取并恢复工具参数碎片
    tool_specs = []
    if aggregated_chunk is not None:
        tool_specs = director._extract_tool_call_specs_from_message(aggregated_chunk)
        # 清洗掉该轮生成的 think 标签（避免污染下一次输入的历史）
        if isinstance(aggregated_chunk.content, str):
            aggregated_chunk.content = extract_visible_text_from_plain_text(aggregated_chunk.content)
    tool_specs = director._hydrate_tool_specs_from_chunk_buffers(tool_specs, tool_chunk_buffers)
    tool_specs = director._prepare_tool_specs_for_execution(tool_specs)
    
    updates: Dict[str, Any] = {
        "messages": _build_director_message_update(
            persisted_prefix=persisted_prefix,
            director=director,
            response=aggregated_chunk,
        ),
        "stream_events": stream_events,
        "sub_agent_result": None,
        "baton_holder": baton_holder,
        "force_return_to_director": False,
    }
    
    pending_delegate = None
    
    # 工具路由检测
    if tool_specs:
        tool_results = []
        event_sink = queue.Queue()
        set_tool_event_sink(event_sink)
        
        try:
            for spec in tool_specs:
                if is_stop_event_set(stop_event):
                    pending_delegate = None
                    break

                tool_name = normalize_tool_name(spec.get("name", ""))
                spec_index = spec.get("index")
                raw_call_id = spec["call_id"]
                indexed_tool_call_key = director._tool_call_event_key(tool_name, spec.get("raw"), spec_index, len(tool_results)) if spec_index is not None else ""
                call_id = (
                    raw_call_id
                    or indexed_tool_call_key
                    or f"call_{len(tool_results)}"
                )
                tool_call_key = (
                    (tool_intent_keys.get(raw_call_id) if raw_call_id else "")
                    or (tool_intent_keys.get(indexed_tool_call_key) if indexed_tool_call_key else "")
                    or (tool_intent_keys.get(tool_name) if len(tool_specs) == 1 else "")
                    or indexed_tool_call_key
                    or call_id
                )
                
                # 开始执行普通工具或拦截包含代理意图的工具
                progress = director._tool_progress_text(tool_name)
                # 从 spec args 提取额外信息以便前端展示更具体的标签
                _spec_args = spec.get("args") or {}
                _extra_start: dict = {}
                if tool_name == "delegate_task":
                    _ta = str(_spec_args.get("target_agent") or "").strip()
                    if _ta:
                        _extra_start["target_agent"] = _ta
                evt_start = build_tool_stream_event(
                    "tool_exec_started",
                    tool_name,
                    source_agent="agent_director",
                    message=progress,
                    tool_call_key=tool_call_key,
                    tool_input=_spec_args,
                    **_extra_start,
                )
                if writer: writer(evt_start)

                if is_stop_event_set(stop_event):
                    pending_delegate = None
                    break

                if tool_name == "delegate_task" and tracker_update_required:
                    protocol_error = _tracker_update_required_message()
                    tool_results.append((call_id, tool_name, protocol_error))
                    updates["force_return_to_director"] = True
                    if writer:
                        writer(build_tool_stream_event(
                            "tool_exec_failed",
                            tool_name,
                            source_agent="agent_director",
                            message=protocol_error,
                            tool_call_key=tool_call_key,
                            tool_input=_spec_args,
                            tool_error=protocol_error,
                        ))
                    continue
                
                tool_result = director._execute_tool_calls([spec])

                if is_stop_event_set(stop_event):
                    pending_delegate = None
                    break
                
                # 检查 Sentinel 拦截
                if isinstance(tool_result, str) and tool_result.startswith("__DELEGATE__:"):
                    delegate_data = json.loads(tool_result.split("__DELEGATE__:", 1)[1])
                    pending_delegate = normalize_handoff_payload(delegate_data, sender_id="agent_director")
                    pending_delegate["call_id"] = call_id
                    updates["messages"] = _build_director_message_update(
                        persisted_prefix=persisted_prefix,
                        director=director,
                        response=aggregated_chunk,
                        tool_specs=[spec],
                    )

                    target_agent = pending_delegate.get("target_agent", "")
                    grant_baton_to = pending_delegate.get("grant_baton_to") or target_agent
                    _ensure_graph_agent_registered(target_agent, user_id, project_name)
                    transfer_result = transfer_baton(
                        ctx,
                        user_id,
                        to_agent_id=grant_baton_to,
                        from_agent_id="agent_director",
                    )
                    if transfer_result.get("status") != "ok":
                        pending_delegate = None
                        tool_results.append((call_id, tool_name, transfer_result.get("message", "Delegation failed")))
                        if writer:
                            writer(build_tool_stream_event(
                                "tool_exec_failed",
                                tool_name,
                                source_agent="agent_director",
                                message=transfer_result.get("message", "Delegation failed"),
                                tool_call_key=tool_call_key,
                                tool_input=_spec_args,
                                tool_error=transfer_result.get("message", "Delegation failed"),
                            ))
                        continue
                    updates["baton_holder"] = transfer_result.get("baton_holder") or grant_baton_to
                    if writer:
                        writer(build_tool_stream_event(
                            "tool_exec_finished",
                            tool_name,
                            source_agent="agent_director",
                            tool_call_key=tool_call_key,
                            target_agent=target_agent,
                            tool_input=_spec_args,
                            tool_result=delegate_data,
                        ))
                    break  # 停止后续工具调用，交给子图处理
                
                _drain_tool_event_sink_to_writer(writer, event_sink, "agent_director", exclude_tools={tool_name})
                _is_tool_failure = is_tool_result_failure(tool_name, tool_result)
                if _is_tool_failure:
                    evt_done = build_tool_stream_event(
                        "tool_exec_failed",
                        tool_name,
                        source_agent="agent_director",
                        tool_call_key=tool_call_key,
                        message=get_tool_result_failure_message(tool_name, tool_result),
                        tool_input=_spec_args,
                        tool_error=tool_result,
                    )
                else:
                    evt_done = build_tool_stream_event(
                        "tool_exec_finished",
                        tool_name,
                        source_agent="agent_director",
                        tool_call_key=tool_call_key,
                        tool_input=_spec_args,
                        tool_result=tool_result,
                    )
                if writer: writer(evt_done)

                if tracker_update_required and _is_tracker_progress_update(
                    tool_name,
                    _spec_args,
                    tool_result,
                ):
                    tracker_update_required = False

                # 旁路检测：导演执行 trigger_auto_write → 推送 director_auto_write_started 给前端
                _SIDEBAND_MARKER = "__director_auto_write_started__:"
                if isinstance(tool_result, str) and tool_result.startswith(_SIDEBAND_MARKER):
                    print(f"[DirectorGraph] Detected Auto-Write sideband marker, tool_name={tool_name}")
                    _nl = tool_result.find("\n")
                    _meta_str = tool_result[len(_SIDEBAND_MARKER):_nl] if _nl != -1 else tool_result[len(_SIDEBAND_MARKER):]
                    try:
                        _meta = json.loads(_meta_str.strip())
                        _sideband_evt = {"event": "director_auto_write_started", **_meta}
                        print(f"[DirectorGraph] Pushing event: {_sideband_evt}")
                        if writer:
                            writer(_sideband_evt)
                            print(f"[DirectorGraph] Writer called successfully")
                        else:
                            print(f"[DirectorGraph] Warning: writer is None, event not pushed!")
                    except Exception as e:
                        print(f"[DirectorGraph] Sideband event parse failed: {e}")


                tool_results.append((call_id, tool_name, tool_result))

        finally:
            set_tool_event_sink(None)
            
        if not pending_delegate:
            completed_call_ids = {cid for cid, _, _ in tool_results}
            completed_specs = [
                spec for spec in tool_specs
                if spec.get("call_id") in completed_call_ids
            ]
            updates["messages"] = _build_director_message_update(
                persisted_prefix=persisted_prefix,
                director=director,
                response=aggregated_chunk,
                tool_specs=completed_specs,
                tool_results=tool_results,
            )

    updates["pending_delegate"] = pending_delegate
    return updates


# ==================== 子 Agent 节点 ====================

def sub_agent_node(state: DirectorState) -> Dict[str, Any]:
    """
    子 Agent 节点：将目标 Agent 的整个 chat_stream 暴露在 LangGraph 流中。
    """
    from agents.context_provider import get_agent_context
    from llm.agen_matchbox.reasoning_compat import extract_visible_text_from_plain_text

    writer = get_stream_writer()
    
    user_id = state["user_id"]
    project_name = state["project_name"]
    delegate = state.get("pending_delegate") or {}
    target_agent = delegate.get("target_agent", "")
    task_description = delegate.get("task_description", "")
    delivery_mode = delegate.get("delivery_mode") or HANDOFF_DELIVERY_DIRECT_TO_USER
    completion_mode = delegate.get("completion_mode") or (
        HANDOFF_COMPLETION_RETURN_TO_DIRECTOR
        if delivery_mode == HANDOFF_DELIVERY_RETURN_TO_DIRECTOR
        else HANDOFF_COMPLETION_REPORT_TO_USER
    )
    return_to = delegate.get("return_to") or "agent_director"
    baton_holder = state.get("baton_holder") or delegate.get("grant_baton_to") or target_agent
    user_confirmation_state = str(delegate.get("user_confirmation_state") or "").strip()
    stop_event = state.get("stop_event")
    skip_tool_confirmation = bool(delegate.get("skip_tool_confirmation")) or user_confirmation_state in {
        HANDOFF_CONFIRMATION_CONFIRMED,
        HANDOFF_CONFIRMATION_NOT_REQUIRED,
    }
    
    # 子 Agent 输出格式由项目 story tags 统一决定，payload 中的旧字段只作兼容。
    from core.request_context import set_current_export_format
    try:
        from core.project_settings import get_workspace_mode

        resolved_export_format = "novel" if get_workspace_mode(str(user_id), str(project_name)) == "novel" else "arc"
    except Exception:
        resolved_export_format = delegate.get("export_format")
    set_current_export_format(resolved_export_format)
    
    if not target_agent or not task_description:
        return {"sub_agent_result": "Delegation failed: missing target agent or task description"}

    if is_stop_event_set(stop_event):
        return {
            "sub_agent_result": f"[{target_agent}] Delegation cancelled",
            "stream_events": [],
            "pending_delegate": None,
            "baton_holder": baton_holder,
        }

    if baton_holder != target_agent:
        return {"sub_agent_result": f"Delegation failed: current baton holder is {baton_holder}, not target agent {target_agent}"}
    
    if writer:
        writer({"event": "agent_turn_started", "source_agent": target_agent,
                "message": f"🤖 Delegating to {target_agent}..."})
    
    inherited_active_context = (state.get("active_context") or "").strip()
    active_context = get_agent_context(
        user_id,
        project_name,
        target_agent,
        extra_context=inherited_active_context,
    )
    handoff_context = ""
    if target_agent == "agent_scriptwriter" and project_name:
        try:
            from agents.routes.context_builder import build_scriptwriter_handoff_context

            handoff_context = build_scriptwriter_handoff_context(
                user_id,
                project_name,
                task_description=task_description,
                chapter_name=str(delegate.get("chapter_name") or ""),
                scene_name=str(delegate.get("scene_name") or ""),
                scene_file_path=str(delegate.get("scene_file_path") or ""),
                scene_guidance=str(delegate.get("scene_guidance") or ""),
                scene_characters=delegate.get("scene_characters") or [],
            )
        except Exception as e:
            print(f"[DirectorGraph] Scriptwriter 委派交接包构建失败（已降级）：{e}")
    collaboration_context = [
        "### 协作任务元信息",
        f"- delegated_by: {delegate.get('delegated_by') or 'agent_director'}",
        f"- delivery_mode: {delivery_mode}",
        f"- completion_mode: {completion_mode}",
        f"- user_confirmation_state: {user_confirmation_state or 'needs_confirmation'}",
        f"- skip_tool_confirmation: {'true' if skip_tool_confirmation else 'false'}",
    ]
    merged_active_context = "\n\n".join([part for part in [active_context, handoff_context, "\n".join(collaboration_context)] if part])
    sub_agent = _ensure_graph_agent_registered(target_agent, user_id, project_name)
    if hasattr(sub_agent, "signals") and not sub_agent.signals.is_beacon_open:
        return {"sub_agent_result": f"Delegation failed: target agent {target_agent} beacon is not open"}
    if hasattr(sub_agent, "signals") and not sub_agent.signals.has_baton:
        return {"sub_agent_result": f"Delegation failed: target agent {target_agent} does not hold the baton"}
    
    buf = []
    event_sink = queue.Queue()
    set_tool_event_sink(event_sink)
    cancelled = False
    suppress_scriptwriter_draft = target_agent == "agent_scriptwriter" and skip_tool_confirmation
    scriptwriter_saved = False
    pipeline_completion_receipt = ""
    
    try:
        # NOTE: 此处不使用 yield，而是将生成内容全部截留后向 writer 推送同时汇聚 buf，
        # 从而实现将生成器转化为直接产生流事件。
        iterable = sub_agent.chat_stream(
            user_message=task_description,
            history=None,
            active_context=merged_active_context,
            skip_tool_confirmation=skip_tool_confirmation,
            stop_event=stop_event,
            stop_after_pipeline_completion=(
                completion_mode == HANDOFF_COMPLETION_SILENT_CONTINUE
            ),
        )
        
        for delta in iterable:
            if is_stop_event_set(stop_event):
                cancelled = True
                break

            # Check tool event sink queue periodically and broadcast them
            while not event_sink.empty():
                if is_stop_event_set(stop_event):
                    cancelled = True
                    break
                evt = event_sink.get_nowait()
                if isinstance(evt, dict) and _is_scriptwriter_persist_tool(str(evt.get("tool_name") or "")):
                    event_name = str(evt.get("event") or "")
                    if event_name == "tool_exec_finished":
                        scriptwriter_saved = True
                if writer:
                    tagged_evt = {**evt, "source_agent": target_agent, "nested": True}
                    writer(tagged_evt)

            if cancelled:
                break
            
            if isinstance(delta, dict):
                event_type = delta.get("event", "")
                if event_type == "pipeline_step_completed":
                    pipeline_completion_receipt = str(delta.get("receipt") or "").strip()
                    continue
                tagged_delta = {**delta, "source_agent": target_agent, "nested": True}
                tool_name = str(delta.get("tool_name") or "")
                if _is_scriptwriter_persist_tool(tool_name) and event_type == "tool_exec_finished":
                    scriptwriter_saved = True

                if writer and not (
                    suppress_scriptwriter_draft
                    and event_type == "assistant_delta"
                    and not scriptwriter_saved
                ):
                    writer(tagged_delta)
                
                if event_type == "assistant_delta":
                    if not (suppress_scriptwriter_draft and not scriptwriter_saved):
                        buf.append(delta.get("text", ""))
                elif event_type == "error" and delta.get("retryable") is False:
                    error_text = str(delta.get("message") or delta.get("data") or "子 Agent 模型流异常中断")
                    raise ModelStreamRetryExhaustedError(error_text)
            elif isinstance(delta, str):
                if not suppress_scriptwriter_draft or scriptwriter_saved:
                    if writer: writer({"event": "assistant_delta", "text": delta,
                                       "source_agent": target_agent, "nested": True})
                    buf.append(delta)

            if is_stop_event_set(stop_event):
                cancelled = True
                break
        
        # Drain any remaining tool events
        while not cancelled and not event_sink.empty():
            if is_stop_event_set(stop_event):
                cancelled = True
                break
            evt = event_sink.get_nowait()
            if isinstance(evt, dict) and _is_scriptwriter_persist_tool(str(evt.get("tool_name") or "")):
                event_name = str(evt.get("event") or "")
                if event_name == "tool_exec_finished":
                    scriptwriter_saved = True
            if writer:
                tagged_evt = {**evt, "source_agent": target_agent, "nested": True}
                writer(tagged_evt)
    finally:
        set_tool_event_sink(None)

    if is_stop_event_set(stop_event):
        cancelled = True

    if cancelled:
        if writer:
            writer({"event": "agent_turn_finished", "source_agent": target_agent, "status": "cancelled"})
        return {
            "sub_agent_result": f"[{target_agent}] Delegation cancelled",
            "stream_events": [],
            "pending_delegate": None,
            "baton_holder": baton_holder,
        }
    
    # 清洗子 agent 收集到的正文，防止 </think> 残留正文进入导演的下一轮对话历史
    result = pipeline_completion_receipt or extract_visible_text_from_plain_text("".join(buf).strip())

    if suppress_scriptwriter_draft and not scriptwriter_saved:
        result = (
            "Scriptwriter 未完成落盘：本轮只生成了正文草稿，但没有调用 "
            "create_chapter / create_or_rewrite_script / patch_script 保存到项目文件。"
            "请重新委派同一场景，并明确要求先创建章节、再调用 create_or_rewrite_script 落盘；"
            "不要把未保存草稿视为已完成章节。"
        )
    
    if writer:
        writer({"event": "agent_turn_finished", "source_agent": target_agent})

    if suppress_scriptwriter_draft and not scriptwriter_saved:
        sub_agent_result = f"[{target_agent}] Execution failed:\n{result}"
    elif completion_mode == HANDOFF_COMPLETION_REPORT_TO_USER:
        sub_agent_result = result
    elif completion_mode == HANDOFF_COMPLETION_SILENT_CONTINUE and pipeline_completion_receipt:
        sub_agent_result = pipeline_completion_receipt
    elif completion_mode == HANDOFF_COMPLETION_SILENT_CONTINUE:
        sub_agent_result = f"[{target_agent}] Silent execution result:\n{result}"
    else:
        sub_agent_result = f"[{target_agent}] Execution result:\n{result}"
    
    updates = {
        "sub_agent_result": sub_agent_result,
        "stream_events": [{
            "event": "sub_agent_result",
            "source_agent": target_agent,
            "result_preview": result[:200],
            "delivery_mode": delivery_mode,
            "completion_mode": completion_mode,
        }],
        "baton_holder": target_agent,
        "force_return_to_director": False,
    }

    tracker_requires_director = (
        completion_mode == HANDOFF_COMPLETION_REPORT_TO_USER
        and _director_tracker_has_open_items(user_id, project_name)
    )
    if tracker_requires_director:
        updates["force_return_to_director"] = True
        updates["stream_events"][0]["completion_mode_effective"] = HANDOFF_COMPLETION_RETURN_TO_DIRECTOR
        updates["sub_agent_result"] = (
            f"[{target_agent}] 子任务结果已回交导演：导演任务板仍有未完成条目，"
            f"需要继续推进后续步骤。\n{result}"
        )

    if (
        completion_mode in {HANDOFF_COMPLETION_RETURN_TO_DIRECTOR, HANDOFF_COMPLETION_SILENT_CONTINUE}
        or (suppress_scriptwriter_draft and not scriptwriter_saved)
        or tracker_requires_director
    ):
        _ensure_graph_agent_registered(return_to, user_id, project_name)
        transfer_result = transfer_baton(
            get_global_context(),
            user_id,
            to_agent_id=return_to,
            from_agent_id=target_agent,
        )
        if transfer_result.get("status") == "ok":
            updates["baton_holder"] = transfer_result.get("baton_holder") or return_to
        else:
            updates["sub_agent_result"] = f"[{target_agent}] Execution complete, but baton handback failed: {transfer_result.get('message', 'unknown error')}\n\n{result}"

    return updates


# ==================== 图与路由 ====================

def route_after_director(state: DirectorState) -> str:
    """如果存在待委派的任务，走向 sub_agent 节点，否则终止当前对话循环。"""
    if is_stop_event_set(state.get("stop_event")):
        return END

    if state.get("pending_delegate"):
        return "sub_agent"

    if state.get("force_return_to_director"):
        return "director"
    
    # 补充：如果有最新消息并且它是函数调用的应答，可能需要返回 director 继续推敲
    # 结合当前需求，非 delegate 工具我们在节点内消化完了，直接 END
    msg_last = state["messages"][-1] if state.get("messages") else None
    if isinstance(msg_last, ToolMessage) and msg_last.name != "delegate_task":
        return "director"
    
    return END


def route_after_sub_agent(state: DirectorState) -> str:
    if is_stop_event_set(state.get("stop_event")):
        return END

    delegate = state.get("pending_delegate") or {}
    completion_mode = delegate.get("completion_mode") or (
        HANDOFF_COMPLETION_RETURN_TO_DIRECTOR
        if (delegate.get("delivery_mode") or HANDOFF_DELIVERY_DIRECT_TO_USER) == HANDOFF_DELIVERY_RETURN_TO_DIRECTOR
        else HANDOFF_COMPLETION_REPORT_TO_USER
    )
    sub_agent_result = str(state.get("sub_agent_result") or "")
    if (
        delegate.get("target_agent") == "agent_scriptwriter"
        and "未完成落盘" in sub_agent_result
    ):
        return "director"
    if state.get("force_return_to_director"):
        return "director"
    if completion_mode in {HANDOFF_COMPLETION_RETURN_TO_DIRECTOR, HANDOFF_COMPLETION_SILENT_CONTINUE}:
        return "director"
    return END

def create_director_graph():
    builder = StateGraph(DirectorState)
    builder.add_node("director", director_node)
    builder.add_node("sub_agent", sub_agent_node)
    
    builder.add_edge(START, "director")
    builder.add_conditional_edges("director", route_after_director, {
        "sub_agent": "sub_agent",
        "director": "director",
        END: END,
    })
    builder.add_conditional_edges("sub_agent", route_after_sub_agent, {
        "director": "director",
        END: END,
    })
    
    return builder.compile()


# ==================== 接口封装 ====================

def run_director_stream(
    user_id: str,
    project_name: str,
    user_message: str,
    history: list = None,
    active_context: str = "",
    **kwargs,
):
    """
    运行导演图的入口，返回同步迭代器
    """
    stop_event = kwargs.get("stop_event")
    if is_stop_event_set(stop_event):
        return

    try:
        from agents.agent_director import DirectorAgent
        from agents.context_budget import (
            prepare_chat_messages_with_budget,
            stream_context_budget_events,
        )
        from agents.prompt_layout import build_chat_prompt_layout
        from llm.agen_matchbox import matchbox

        director = DirectorAgent(user_id=user_id, project_name=project_name)
        base_llm = matchbox().get_user_llm(user_id, agent_name="agent_director")
        system_instruction, runtime_context = _build_director_prompt_context(
            director,
            user_id=user_id,
            project_name=project_name,
            active_context=active_context or "",
        )
        prompt_layout = build_chat_prompt_layout(
            system_instruction=system_instruction,
            user_message=user_message,
            active_context=runtime_context,
            runtime_tail=build_work_tracker_prompt_context(
                user_id,
                project_name,
                "agent_director",
            ),
        )

        budget_stream = stream_context_budget_events(
            prepare_chat_messages_with_budget,
            user_id=user_id,
            project_name=project_name,
            agent_id="agent_director",
            system_instruction=prompt_layout.system_instruction,
            history=history,
            user_message=prompt_layout.user_message,
            llm_client=base_llm,
        )
        while True:
            try:
                yield next(budget_stream)
            except StopIteration as completed:
                budget_result = completed.value
                break

        # system 前缀由 director_node 每轮实时重建，图状态只保存动态消息体。
        lc_messages = list(budget_result.messages[1:])
        initial_state = {
            "user_id": user_id,
            "project_name": project_name,
            "messages": lc_messages,
            "active_context": active_context or "",
            "current_user_message": user_message,
            "pending_delegate": None,
            "sub_agent_result": None,
            "baton_holder": "agent_director",
            "force_return_to_director": False,
            "stream_events": [],
            "stop_event": stop_event,
        }

        graph = create_director_graph()
        
        for chunk in graph.stream(
            initial_state,
            stream_mode=["custom", "values", "updates"],
            version="v2",
        ):
            if is_stop_event_set(stop_event):
                break

            if isinstance(chunk, tuple) and len(chunk) == 2:
                chunk_mode, chunk_data = chunk
                if chunk_mode == "custom":
                    yield chunk_data
            elif hasattr(chunk, "get") and chunk.get("type") == "custom":
                yield chunk["data"]
    except Exception as e:
        from agents.context_budget import NonRetryableChatError

        if isinstance(e, NonRetryableChatError):
            yield e.to_event()
            return
        import traceback
        traceback.print_exc()
        from agents.routes.schemas import format_ai_error
        yield {
            "event": "error",
            "data": format_ai_error(e),
            "retryable": not isinstance(e, ModelStreamRetryExhaustedError),
        }
