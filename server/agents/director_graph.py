"""
Director SupervisorGraph - 基于 LangGraph 的导演调度升级版
"""
from __future__ import annotations

import json
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
    build_tool_stream_event,
    get_global_context,
    normalize_handoff_payload,
    normalize_tool_name,
    set_tool_event_sink,
    transfer_baton,
)
from llm.agen_matchbox.reasoning_compat import extract_visible_text_from_plain_text


# ==================== State 定义 ====================

class DirectorState(TypedDict):
    """导演调度图的共享状态"""
    user_id: str
    project_name: str
    
    messages: Annotated[list, operator.add]
    active_context: str
    
    pending_delegate: Optional[Dict[str, Any]]
    sub_agent_result: Optional[str]
    baton_holder: Optional[str]
    
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
    from agents.routes.chat import _create_agent_instance

    ctx = get_global_context()
    namespace = ctx._user_namespaces.setdefault(str(user_id), {})
    agent = namespace.get(agent_id)
    if agent is None:
        agent = _create_agent_instance(agent_id, user_id, project_name)
        if hasattr(agent, "bind_context"):
            agent.bind_context(ctx)
        else:
            ctx.register(agent)
    return agent


# ==================== 导演节点 ====================

def director_node(state: DirectorState) -> Dict[str, Any]:
    """
    导演节点：驱动 LLM，实时多路收集输出事件并利用 Sentinel 拦截委派动作。
    """
    from agents.agent_director import DirectorAgent
    from agents.agent_tools import get_tools_for_agent
    from llm.agen_matchbox import matchbox
    from llm.agen_matchbox.reasoning_compat import MessageEventStreamReasoningAdapter
    from langchain_core.messages import SystemMessage
    from agents.agent_utils import load_prompt

    writer = get_stream_writer()
    
    user_id = state["user_id"]
    project_name = state["project_name"]
    messages = state.get("messages", [])
    sub_agent_result = state.get("sub_agent_result")
    baton_holder = state.get("baton_holder") or "agent_director"
    
    # 注入子 Agent 结果
    if sub_agent_result:
        tool_call_id = state.get("pending_delegate", {}).get("call_id", "delegate_call")
        messages = messages + [
            ToolMessage(
                content=sub_agent_result,
                tool_call_id=tool_call_id,
                name="delegate_task",
            )
        ]
    
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
    tools = get_tools_for_agent("agent_director")
    if tools:
        stream_llm = stream_llm.bind_tools(tools)
    
    # ---- 构建 System Prompt（和 SparkBaseAgent.chat_stream 逻辑一致）----
    try:
        prompt_name = "director"  # agent_director -> director
        prompts = load_prompt(prompt_name)
        base_system_prompt = prompts.get("chat_system") or prompts.get("system", f"你是导演，负责协调团队中的专家。")
    except Exception:
        base_system_prompt = f"你是导演，负责协调团队中的专家。"
    
    # 每次导演轮次，从磁盘刷新项目实时状态（子 Agent 执行完毕写入文件后，导演下一轮能感知新内容）
    from agents.context_provider import get_agent_context as _refresh_project_ctx
    user_initial_context = state.get("active_context", "")
    try:
        fresh_project_status = _refresh_project_ctx(user_id, project_name, "agent_director") if project_name else ""
    except Exception:
        fresh_project_status = ""
    active_context = "\n\n".join(p for p in [fresh_project_status, user_initial_context] if p)
    system_instruction = director._build_tool_system_prompt(base_system_prompt, active_context)
    messages_with_system = [SystemMessage(content=system_instruction)] + list(messages)
    # -------------------------------------------------------------------
    
    tool_chunk_buffers: Dict[int, Dict] = {}
    started_tools = set()
    tool_intent_keys: Dict[str, str] = {}
    stream_events = []
    aggregated_chunk = None
    
    adapter = MessageEventStreamReasoningAdapter()
    
    for chunk in stream_llm.stream(messages_with_system):
        if aggregated_chunk is None:
            aggregated_chunk = chunk
        else:
            try:
                aggregated_chunk = aggregated_chunk + chunk
            except Exception:
                pass
        
        # 实时工具意图广播
        for tcc in getattr(chunk, "tool_call_chunks", None) or []:
            director._append_tool_call_chunk_buffer(tool_chunk_buffers, tcc)
            tcc_dict = director._tool_call_as_dict(tcc)
            tool_name = (
                tcc_dict.get("name")
                or getattr(tcc, "name", None)
                or tool_chunk_buffers.get(tcc_dict.get("index"), {}).get("name")
            )
            if tool_name and tool_name not in started_tools:
                tool_name = normalize_tool_name(tool_name)
                started_tools.add(tool_name)
                tool_call_key = director._extract_tool_call_id(tcc) or f"agent_director:{tool_name}:{tcc_dict.get('index', len(started_tools))}"
                tool_intent_keys[tool_name] = tool_call_key
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
    
    # 获取并恢复工具参数碎片
    tool_specs = []
    if aggregated_chunk is not None:
        tool_specs = director._extract_tool_call_specs_from_message(aggregated_chunk)
        # 清洗掉该轮生成的 think 标签（避免污染下一次输入的历史）
        if isinstance(aggregated_chunk.content, str):
            aggregated_chunk.content = extract_visible_text_from_plain_text(aggregated_chunk.content)
    tool_specs = director._hydrate_tool_specs_from_chunk_buffers(tool_specs, tool_chunk_buffers)
    
    updates: Dict[str, Any] = {
        "messages": [aggregated_chunk] if aggregated_chunk else [],
        "stream_events": stream_events,
        "sub_agent_result": None,
        "baton_holder": baton_holder,
    }
    
    pending_delegate = None
    
    # 工具路由检测
    if tool_specs:
        tool_results = []
        event_sink = queue.Queue()
        set_tool_event_sink(event_sink)
        
        try:
            for spec in tool_specs:
                tool_name = normalize_tool_name(spec.get("name", ""))
                call_id = director._extract_tool_call_id(spec.get("raw")) or f"call_{len(tool_results)}"
                tool_call_key = tool_intent_keys.get(tool_name) or call_id
                
                # 开始执行普通工具或拦截包含代理意图的工具
                progress = director._tool_progress_text(tool_name)
                # 从 spec args 提取额外信息以便前端展示更具体的标签
                _spec_args = spec.get("args") or {}
                _extra_start: dict = {}
                if tool_name == "delegate_task":
                    _ta = str(_spec_args.get("target_agent") or "").strip()
                    if _ta:
                        _extra_start["target_agent"] = _ta
                elif tool_name == "work_tracker":
                    _act = str(_spec_args.get("action") or "").strip()
                    if _act:
                        _extra_start["tool_action"] = _act
                evt_start = build_tool_stream_event(
                    "tool_exec_started",
                    tool_name,
                    source_agent="agent_director",
                    message=progress,
                    tool_call_key=tool_call_key,
                    **_extra_start,
                )
                if writer: writer(evt_start)
                
                tool_result = director._execute_tool_calls([spec])
                
                # 检查 Sentinel 拦截
                if isinstance(tool_result, str) and tool_result.startswith("__DELEGATE__:"):
                    delegate_data = json.loads(tool_result.split("__DELEGATE__:", 1)[1])
                    pending_delegate = normalize_handoff_payload(delegate_data, sender_id="agent_director")
                    pending_delegate["call_id"] = call_id

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
                        tool_results.append((call_id, tool_name, transfer_result.get("message", "委派失败")))
                        if writer:
                            writer(build_tool_stream_event(
                                "tool_exec_failed",
                                tool_name,
                                source_agent="agent_director",
                                message=transfer_result.get("message", "委派失败"),
                                tool_call_key=tool_call_key,
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
                        ))
                    break  # 停止后续工具调用，交给子图处理
                
                _drain_tool_event_sink_to_writer(writer, event_sink, "agent_director", exclude_tools={tool_name})
                _extra_done_director: dict = {}
                if tool_name == "work_tracker" and isinstance(tool_result, str) and tool_result.strip():
                    _extra_done_director["tool_result"] = tool_result
                evt_done = build_tool_stream_event(
                    "tool_exec_finished",
                    tool_name,
                    source_agent="agent_director",
                    tool_call_key=tool_call_key,
                    **_extra_done_director,
                )
                if writer: writer(evt_done)

                # 旁路检测：导演执行 trigger_auto_write → 推送 director_auto_write_started 给前端
                _SIDEBAND_MARKER = "__director_auto_write_started__:"
                if isinstance(tool_result, str) and tool_result.startswith(_SIDEBAND_MARKER):
                    print(f"[DirectorGraph] 检测到 Auto-Write 旁路标记，tool_name={tool_name}")
                    _nl = tool_result.find("\n")
                    _meta_str = tool_result[len(_SIDEBAND_MARKER):_nl] if _nl != -1 else tool_result[len(_SIDEBAND_MARKER):]
                    try:
                        _meta = json.loads(_meta_str.strip())
                        _sideband_evt = {"event": "director_auto_write_started", **_meta}
                        print(f"[DirectorGraph] 推送事件: {_sideband_evt}")
                        if writer:
                            writer(_sideband_evt)
                            print(f"[DirectorGraph] writer 调用成功")
                        else:
                            print(f"[DirectorGraph] 警告：writer 为 None，事件未推送！")
                    except Exception as e:
                        print(f"[DirectorGraph] 旁路事件解析失败: {e}")


                tool_results.append((call_id, tool_name, tool_result))

        finally:
            set_tool_event_sink(None)
            
        if not pending_delegate:
            tool_messages = [
                ToolMessage(content=str(r), tool_call_id=cid, name=n)
                for cid, n, r in tool_results
            ]
            updates["messages"] = (updates["messages"] or []) + tool_messages

    updates["pending_delegate"] = pending_delegate
    return updates


# ==================== 子 Agent 节点 ====================

def sub_agent_node(state: DirectorState) -> Dict[str, Any]:
    """
    子 Agent 节点：将目标 Agent 的整个 chat_stream 暴露在 LangGraph 流中。
    """
    from agents.routes.chat import _create_agent_instance
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
    skip_tool_confirmation = bool(delegate.get("skip_tool_confirmation")) or user_confirmation_state in {
        HANDOFF_CONFIRMATION_CONFIRMED,
        HANDOFF_CONFIRMATION_NOT_REQUIRED,
    }
    
    if not target_agent or not task_description:
        return {"sub_agent_result": "委派任务失败：缺少目标 Agent 或任务描述"}

    if baton_holder != target_agent:
        return {"sub_agent_result": f"委派任务失败：当前旗帜持有者为 {baton_holder}，不是目标专家 {target_agent}"}
    
    if writer:
        writer({"event": "agent_turn_started", "source_agent": target_agent,
                "message": f"🤖 委派给 {target_agent} 执行任务..."})
    
    inherited_active_context = (state.get("active_context") or "").strip()
    active_context = get_agent_context(
        user_id,
        project_name,
        target_agent,
        extra_context=inherited_active_context,
    )
    collaboration_context = [
        "### 协作任务元信息",
        f"- delegated_by: {delegate.get('delegated_by') or 'agent_director'}",
        f"- delivery_mode: {delivery_mode}",
        f"- completion_mode: {completion_mode}",
        f"- user_confirmation_state: {user_confirmation_state or 'needs_confirmation'}",
        f"- skip_tool_confirmation: {'true' if skip_tool_confirmation else 'false'}",
    ]
    merged_active_context = "\n\n".join([part for part in [active_context, "\n".join(collaboration_context)] if part])
    sub_agent = _ensure_graph_agent_registered(target_agent, user_id, project_name)
    if hasattr(sub_agent, "signals") and not sub_agent.signals.is_beacon_open:
        return {"sub_agent_result": f"委派任务失败：目标专家 {target_agent} 的信标未开启"}
    if hasattr(sub_agent, "signals") and not sub_agent.signals.has_baton:
        return {"sub_agent_result": f"委派任务失败：目标专家 {target_agent} 当前未持有旗帜"}
    
    buf = []
    event_sink = queue.Queue()
    set_tool_event_sink(event_sink)
    
    try:
        # NOTE: 此处不使用 yield，而是将生成内容全部截留后向 writer 推送同时汇聚 buf，
        # 从而实现将生成器转化为直接产生流事件。
        iterable = sub_agent.chat_stream(
            user_message=task_description,
            history=None,
            active_context=merged_active_context,
            skip_tool_confirmation=skip_tool_confirmation,
        )
        
        for delta in iterable:
            # Check tool event sink queue periodically and broadcast them
            while not event_sink.empty():
                evt = event_sink.get_nowait()
                if writer:
                    tagged_evt = {**evt, "source_agent": target_agent, "nested": True}
                    writer(tagged_evt)
            
            if isinstance(delta, dict):
                event_type = delta.get("event", "")
                tagged_delta = {**delta, "source_agent": target_agent, "nested": True}
                if writer: writer(tagged_delta)
                
                if event_type == "assistant_delta":
                    buf.append(delta.get("text", ""))
            elif isinstance(delta, str):
                if writer: writer({"event": "assistant_delta", "text": delta,
                                   "source_agent": target_agent, "nested": True})
                buf.append(delta)
        
        # Drain any remaining tool events
        while not event_sink.empty():
            evt = event_sink.get_nowait()
            if writer:
                tagged_evt = {**evt, "source_agent": target_agent, "nested": True}
                writer(tagged_evt)
    finally:
        set_tool_event_sink(None)
    
    # 清洗子 agent 收集到的正文，防止 </think> 残留正文进入导演的下一轮对话历史
    result = extract_visible_text_from_plain_text("".join(buf).strip())
    
    if writer:
        writer({"event": "agent_turn_finished", "source_agent": target_agent})

    if completion_mode == HANDOFF_COMPLETION_REPORT_TO_USER:
        sub_agent_result = result
    elif completion_mode == HANDOFF_COMPLETION_SILENT_CONTINUE:
        sub_agent_result = f"[{target_agent}] 静默执行结果:\n{result}"
    else:
        sub_agent_result = f"[{target_agent}] 执行结果:\n{result}"
    
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
    }

    if completion_mode in {HANDOFF_COMPLETION_RETURN_TO_DIRECTOR, HANDOFF_COMPLETION_SILENT_CONTINUE}:
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
            updates["sub_agent_result"] = f"[{target_agent}] 执行完成，但回交旗帜失败：{transfer_result.get('message', '未知错误')}\n\n{result}"

    return updates


# ==================== 图与路由 ====================

def route_after_director(state: DirectorState) -> str:
    """如果存在待委派的任务，走向 sub_agent 节点，否则终止当前对话循环。"""
    if state.get("pending_delegate"):
        return "sub_agent"
    
    # 补充：如果有最新消息并且它是函数调用的应答，可能需要返回 director 继续推敲
    # 结合当前需求，非 delegate 工具我们在节点内消化完了，直接 END
    msg_last = state["messages"][-1] if state.get("messages") else None
    if isinstance(msg_last, ToolMessage) and msg_last.name != "delegate_task":
        return "director"
    
    return END


def route_after_sub_agent(state: DirectorState) -> str:
    delegate = state.get("pending_delegate") or {}
    completion_mode = delegate.get("completion_mode") or (
        HANDOFF_COMPLETION_RETURN_TO_DIRECTOR
        if (delegate.get("delivery_mode") or HANDOFF_DELIVERY_DIRECT_TO_USER) == HANDOFF_DELIVERY_RETURN_TO_DIRECTOR
        else HANDOFF_COMPLETION_REPORT_TO_USER
    )
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
    lc_messages = []
    for msg in (history or [])[-10:]:
        role = msg.get("role")
        content = msg.get("content") or ""
        if not content: continue
        if isinstance(content, dict):
            content = json.dumps(content, ensure_ascii=False)
        if role == "user":
            lc_messages.append(HumanMessage(content=str(content)))
        elif role == "assistant":
            lc_messages.append(AIMessage(content=str(content)))
    
    lc_messages.append(HumanMessage(content=user_message))
    
    initial_state = {
        "user_id": user_id,
        "project_name": project_name,
        "messages": lc_messages,
        "active_context": active_context or "",
        "pending_delegate": None,
        "sub_agent_result": None,
        "baton_holder": "agent_director",
        "stream_events": [],
    }
    
    
    try:
        graph = create_director_graph()
        
        for chunk in graph.stream(
            initial_state,
            stream_mode=["custom", "values", "updates"],
            version="v2",
        ):
            if isinstance(chunk, tuple) and len(chunk) == 2:
                chunk_mode, chunk_data = chunk
                if chunk_mode == "custom":
                    yield chunk_data
            elif hasattr(chunk, "get") and chunk.get("type") == "custom":
                yield chunk["data"]
    except Exception as e:
        import traceback
        traceback.print_exc()
        from agents.routes.schemas import format_ai_error
        yield {"event": "error", "data": format_ai_error(e)}

