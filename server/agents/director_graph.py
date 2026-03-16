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

from agents.communication import set_tool_event_sink
from llm.llm_mgr.reasoning_compat import extract_visible_text_from_plain_text


# ==================== State 定义 ====================

class DirectorState(TypedDict):
    """导演调度图的共享状态"""
    user_id: str
    project_name: str
    
    messages: Annotated[list, operator.add]
    active_context: str
    
    pending_delegate: Optional[Dict[str, Any]]
    sub_agent_result: Optional[str]
    
    stream_events: Annotated[list, operator.add]


# ==================== 辅助方法 ====================

def _drain_tool_event_sink_to_writer(writer, sink: queue.Queue, source_agent: str) -> None:
    """
    把 ToolEventSink 中的嵌套工具事件通过 LangGraph StreamWriter 广播给前端。
    """
    if not sink:
        return
    while not sink.empty():
        try:
            evt = sink.get_nowait()
            if isinstance(evt, dict):
                evt["nested"] = True
                evt["source_agent"] = source_agent
                writer(evt)
        except queue.Empty:
            break


# ==================== 导演节点 ====================

def director_node(state: DirectorState) -> Dict[str, Any]:
    """
    导演节点：驱动 LLM，实时多路收集输出事件并利用 Sentinel 拦截委派动作。
    """
    from agents.agent_director import DirectorAgent
    from agents.agent_tools import get_tools_for_agent
    from llm.llm_mgr import LLM_Manager
    from llm.llm_mgr.reasoning_compat import MessageEventStreamReasoningAdapter
    from langchain_core.messages import SystemMessage
    from agents.agent_utils import load_prompt

    writer = get_stream_writer()
    
    user_id = state["user_id"]
    project_name = state["project_name"]
    messages = state.get("messages", [])
    sub_agent_result = state.get("sub_agent_result")
    
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
    
    if writer:
        writer({"event": "agent_turn_started", "source_agent": "agent_director"})
    
    stream_llm = LLM_Manager.get_user_llm(user_id, agent_name="agent_director")
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
    
    active_context = state.get("active_context", "")
    system_instruction = director._build_tool_system_prompt(base_system_prompt, active_context)
    messages_with_system = [SystemMessage(content=system_instruction)] + list(messages)
    # -------------------------------------------------------------------
    
    tool_chunk_buffers: Dict[int, Dict] = {}
    started_tools = set()
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
                started_tools.add(tool_name)
                progress = director._tool_progress_text(tool_name)
                evt = {"event": "tool_intent_started", "tool_name": tool_name,
                       "message": progress, "source_agent": "agent_director"}
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
    }
    
    pending_delegate = None
    
    # 工具路由检测
    if tool_specs:
        tool_results = []
        event_sink = queue.Queue()
        set_tool_event_sink(event_sink)
        
        try:
            for spec in tool_specs:
                tool_name = spec.get("name", "")
                call_id = director._extract_tool_call_id(spec.get("raw")) or f"call_{len(tool_results)}"
                
                # 开始执行普通工具或拦截包含代理意图的工具
                progress = director._tool_progress_text(tool_name)
                evt_start = {"event": "tool_exec_started", "tool_name": tool_name,
                             "message": progress, "source_agent": "agent_director"}
                if writer: writer(evt_start)
                
                tool_result = director._execute_tool_calls([spec])
                
                # 检查 Sentinel 拦截
                if isinstance(tool_result, str) and tool_result.startswith("__DELEGATE__:"):
                    import json
                    delegate_data = json.loads(tool_result.split("__DELEGATE__:", 1)[1])
                    pending_delegate = {
                        "target_agent": delegate_data.get("target_agent", ""),
                        "task_description": delegate_data.get("task_description", ""),
                        "call_id": call_id,
                    }
                    if writer: writer({"event": "tool_exec_finished", "tool_name": tool_name, "source_agent": "agent_director"})
                    break  # 停止后续工具调用，交给子图处理
                
                _drain_tool_event_sink_to_writer(writer, event_sink, "agent_director")
                evt_done = {"event": "tool_exec_finished", "tool_name": tool_name,
                            "source_agent": "agent_director"}
                if writer: writer(evt_done)
                
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
    from llm.llm_mgr.reasoning_compat import extract_visible_text_from_plain_text

    writer = get_stream_writer()
    
    user_id = state["user_id"]
    project_name = state["project_name"]
    delegate = state.get("pending_delegate") or {}
    target_agent = delegate.get("target_agent", "")
    task_description = delegate.get("task_description", "")
    
    if not target_agent or not task_description:
        return {"sub_agent_result": "委派任务失败：缺少目标 Agent 或任务描述"}
    
    if writer:
        writer({"event": "agent_turn_started", "source_agent": target_agent,
                "message": f"🤖 委派给 {target_agent} 执行任务..."})
    
    active_context = get_agent_context(user_id, project_name, target_agent)
    sub_agent = _create_agent_instance(target_agent, user_id, project_name)
    
    buf = []
    event_sink = queue.Queue()
    set_tool_event_sink(event_sink)
    
    try:
        # NOTE: 此处不使用 yield，而是将生成内容全部截留后向 writer 推送同时汇聚 buf，
        # 从而实现将生成器转化为直接产生流事件。
        iterable = sub_agent.chat_stream(
            user_message=task_description,
            history=None,
            active_context=active_context,
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
    
    return {
        "sub_agent_result": f"[{target_agent}] 执行结果:\n{result}",
        "stream_events": [{"event": "sub_agent_result", "source_agent": target_agent,
                           "result_preview": result[:200]}]
    }


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
    builder.add_edge("sub_agent", "director")
    
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
        yield {"event": "assistant_delta", "text": f"\n[调度引擎内部错误: {e}]"}
