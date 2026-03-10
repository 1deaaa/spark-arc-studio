"""Director Agent - global routing + session recording.

This agent acts as the single entry point for the *global channel*:
- Understand a user's free-form request
- Decide which specialist agents should receive it
- Record the user's request into those agents' session histories
- Return a concise summary of routing decisions

Design note:
We intentionally keep execution lightweight: routing + recording first.
Specialist agents can later consume the recorded session messages as context.
"""

from __future__ import annotations

import json
import threading
import re
from typing import Any, Dict, List, Optional

from langchain_core.messages import HumanMessage, SystemMessage

from .chat_manager import ChatManager
from .registry import get_agent_registry
from llm.llm_mgr import LLM_Manager
from llm.llm_mgr.reasoning_compat import extract_reasoning_text_from_message, extract_text_content_from_message


def _normalize_text(text: str) -> str:
    return (text or "").strip().lower()


def _is_greeting(text: str) -> bool:
    t = _normalize_text(text)
    if not t:
        return False
    greetings = [
        "你好", "您好", "hi", "hello", "hey", "哈喽", "嗨", "在吗", "在不", "在嘛",
        "早", "早上好", "中午好", "下午好", "晚上好",
    ]
    return any(g in t for g in greetings)


def _format_targets(targets: List[str]) -> str:
    if not targets:
        return ""
    name_map = {a.get("key"): a.get("name") for a in get_agent_registry()}
    labels = [name_map.get(t, t) for t in targets]
    return "、".join(labels)


class DirectorAgent:
    """
    导演 Agent - 用户交互层的入口，负责路由分发和会话管理。
    
    注意：导演不继承 SparkBaseAgent，因为它不参与 Agent 间的自主通信（信标机制）。
    导演是用户和专家 Agent 之间的桥梁，属于用户交互层而非 Agent 自治层。
    """
    def __init__(self, user_id: str, project_name: str):
        self.user_id = str(user_id)
        self.project_name = project_name
        # 导演主要负责总结与上下文管理（倒向更稳的模型配置）
        # 非流式调用：llm.invoke()
        self.llm = LLM_Manager.get_user_llm(
            str(user_id),
            agent_name="agent_director",
        )
        # 流式调用：llm.stream()
        self.stream_llm = LLM_Manager.get_user_llm(
            str(user_id),
            agent_name="agent_director",
        )
        self.router = None # Deprecated

    def _match_agents_by_mention(self, user_text: str) -> List[str]:
        """根据文本里点名的 key 或展示名，匹配 agent_id。"""
        t = _normalize_text(user_text)
        if not t:
            return []

        hits: List[str] = []
        for info in get_agent_registry():
            key = (info.get("key") or "").strip()
            name = (info.get("name") or "").strip().lower()
            if not key:
                continue
            if key.lower() in t or (name and name in t):
                hits.append(key)
        # never self-route by mention unless explicitly needed
        return [k for k in hits if k != "agent_director"]

    def _decide_targets(
        self,
        user_message: str,
        explicit_targets: Optional[List[str]] = None,
        history: List[Dict[str, Any]] = None
    ) -> List[str]:
        """Encapsulated routing decision logic."""
        targets: List[str] = []

        # 1. Explicit targets have highest priority
        if explicit_targets:
            for t in explicit_targets:
                if t and t not in targets and t != "agent_director":
                    targets.append(t)
            if targets:
                return targets

        # 2. Mention-based targets (strong signal)
        targets.extend(self._match_agents_by_mention(user_message))
        
        # 3. LLM-based routing (Delegated to RouterAgent)
        llm_targets = self.router.decide_targets(user_message, history=history)
        for t in llm_targets:
            if t and t != "agent_director" and t not in targets:
                targets.append(t)

        # 4. Fallback: default to scriptwriter
        return targets

    def _get_agent_instruction(self) -> str:
        lines = ["你的团队成员（专家 Agent）："]
        for agent in get_agent_registry():
            k = agent.get("key")
            if k == "agent_director" or agent.get("routable") is False:
                continue
            name = agent.get("name")
            desc = agent.get("description")
            lines.append(f"- {name} ({k}): {desc}")
        return "\n".join(lines)

    def think_and_route(self, user_message: str, history: List[Dict[str, Any]] = None) -> List[str]:
        """思考并决定路由目标。返回空列表表示由导演直答。"""
        # 1. 显式点名检查 (Rule-based)
        mentions = self._match_agents_by_mention(user_message)
        if mentions:
            return mentions

        # 2. 寒暄检查 (Rule-based)
        if _is_greeting(user_message) and len(user_message) <= 12:
            return []

        # 3. LLM 决策
        # 使用导演此人格进行判断，可以更准确地理解“是否该我回答”
        system_text = (
            "你是 SparkArc 的导演（Director）。\n"
            "你的核心职责是：判断用户的需求应该由你自己回答，还是交给特定的专家处理。\n\n"
            f"{self._get_agent_instruction()}\n\n"
            "决策规则：\n"
            "1. 如果用户是在闲聊、问候、或者询问你的功能 -> 返回 DIRECT\n"
            "2. 如果用户是在请求具体创作（写大纲、写正文、查设定、提意见...） -> 返回最合适的一个或多个专家 Key (JSON list)\n"
            "3. 如果不确定，优先 DIRECT，由你进一步引导。\n\n"
            "请只输出 JSON 格式的结果，例如：\n"
            "{\"targets\": [\"agent_scriptwriter\"]} 或 {\"targets\": []}\n"
            "注意：targets 为空表示 DIRECT。"
        )

        msgs = [SystemMessage(content=system_text)]
        
        # 简化的历史上下文，帮助判断意图
        if history:
            history_text = ""
            for msg in history[-3:]:
                role = "用户" if msg.get("role") == "user" else "助手"
                content = str(msg.get("content", ""))[:100]
                history_text += f"{role}: {content}\n"
            if history_text:
                msgs.append(HumanMessage(content=f"【近期对话】\n{history_text}"))

        msgs.append(HumanMessage(content=f"用户输入：{user_message}"))

        try:
            resp = self.llm.invoke(msgs)
            content = resp.content
            # Extract JSON
            match = re.search(r'\{.*\}', content, re.DOTALL)
            if match:
                data = json.loads(match.group(0))
                targets = data.get("targets", [])
                if isinstance(targets, list):
                    return [str(t) for t in targets if t != "agent_director"]
        except Exception as e:
            print(f"[Director] Routing decision failed: {e}")
        
        return []

    def _decide_targets(
        self,
        user_message: str,
        explicit_targets: Optional[List[str]] = None,
        history: List[Dict[str, Any]] = None
    ) -> List[str]:
        """Encapsulated routing decision logic."""
        targets: List[str] = []

        # 1. Explicit targets have highest priority
        if explicit_targets:
            for t in explicit_targets:
                if t and t not in targets and t != "agent_director":
                    targets.append(t)
            if targets:
                return targets

        # 2. Logic is now unified in think_and_route, but this method is called by route_and_record.
        # However, route_and_record is usually called AFTER decision in the new flow.
        # Providing fallback if called directly.
        
        return self.think_and_route(user_message, history)


    def direct_reply(self, user_message: str, history: List[Dict[str, Any]] = None, active_context: Optional[str] = None) -> str:
        """导演直答（不路由）：用于寒暄、全局性讨论、泛问等。"""
        system = (
            "你是 SparkArc 的 AI 协调助手（导演）。\n"
            "你的职责：\n"
            "1) 直接、专业地回答用户的通用问题（如寒暄、闲聊、使用咨询）；\n"
            "2) 你的团队里有各领域的专家，如果用户需求模糊，你可以介绍你的团队能力，引导用户去指令专家；\n"
            "3) 禁止角色扮演，禁止使用括号描写动作，禁止用文学化语言渲染场景；\n"
            "4) 回复简洁、实用，像一个专业的项目助理。\n\n"
            f"{self._get_agent_instruction()}"
        )
        msgs = [SystemMessage(content=system)]
        if history:
            for m in history[-8:]:
                role = m.get("role")
                content = m.get("content")
                if not content:
                    continue
                if isinstance(content, dict):
                    content = json.dumps(content, ensure_ascii=False)
                if role == "user":
                    msgs.append(HumanMessage(content=str(content)))
                elif role == "assistant":
                    from langchain_core.messages import AIMessage
                    msgs.append(AIMessage(content=str(content)))

        if active_context and isinstance(active_context, str) and active_context.strip():
            ctx = active_context.strip()
            # keep it bounded
            if len(ctx) > 3000:
                ctx = ctx[:3000] + "\n...(省略)"
            msgs.append(HumanMessage(content=f"【当前上下文】\n{ctx}"))
        
        msgs.append(HumanMessage(content=user_message))
        resp = self.llm.invoke(msgs)
        resp_text = extract_text_content_from_message(resp)
        if resp_text:
            return resp_text
        return resp.content if isinstance(resp.content, str) else str(resp.content)

    def direct_and_record(
        self,
        *,
        user_id: str,
        project_name: str,
        context_key: str,
        user_message: str,
        active_context: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """导演直答并写入会话（不做路由）。"""
        cm = ChatManager(user_id=user_id, project_name=project_name)
        merged_meta = {**(metadata or {})}
        if active_context and isinstance(active_context, str) and active_context.strip():
            merged_meta["active_context"] = active_context

        cm.append_message(
            agent_id="agent_director",
            context_key=context_key,
            role="user",
            content=user_message,
            metadata=merged_meta,
        )

        history = cm.get_history(agent_id="agent_director", context_key=context_key, limit=10)
        reply = self.direct_reply(user_message, history=history, active_context=active_context)

        cm.append_message(
            agent_id="agent_director",
            context_key=context_key,
            role="assistant",
            content=reply,
            metadata={"type": "director_reply"},
        )

        return reply

    def direct_and_record_stream(
        self,
        *,
        user_id: str,
        project_name: str,
        context_key: str,
        user_message: str,
        active_context: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        stop_event: Optional[threading.Event] = None,
    ):
        """导演直答并写入会话（流式）。"""
        is_stopped = lambda: bool(stop_event and stop_event.is_set())
        cm = ChatManager(user_id=user_id, project_name=project_name)
        merged_meta = {**(metadata or {})}
        if active_context and isinstance(active_context, str) and active_context.strip():
            merged_meta["active_context"] = active_context

        cm.append_message(
            agent_id="agent_director",
            context_key=context_key,
            role="user",
            content=user_message,
            metadata=merged_meta,
        )

        history = cm.get_history(agent_id="agent_director", context_key=context_key, limit=10)

        system = (
            "你是 SparkArc 的 AI 协调助手。\n"
            "规则：直接回答用户的通用问题，不要调度专家。\n"
            "禁止角色扮演，禁止使用括号描写动作。回复简洁、专业。"
        )

        msgs = [SystemMessage(content=system)]
        if history:
            for m in history[-8:]:
                role = m.get("role")
                content = m.get("content")
                if not content:
                    continue
                if isinstance(content, dict):
                    content = json.dumps(content, ensure_ascii=False)
                if role == "user":
                    msgs.append(HumanMessage(content=str(content)))
                elif role == "assistant":
                    from langchain_core.messages import AIMessage
                    msgs.append(AIMessage(content=str(content)))

        if active_context and isinstance(active_context, str) and active_context.strip():
            ctx = active_context.strip()
            if len(ctx) > 3000:
                ctx = ctx[:3000] + "\n...(省略)"
            msgs.append(HumanMessage(content=f"【当前上下文】\n{ctx}"))

        msgs.append(HumanMessage(content=user_message))

        buf: List[str] = []
        for chunk in self.stream_llm.stream(msgs):
            if is_stopped():
                break
            reasoning = extract_reasoning_text_from_message(chunk)
            if reasoning:
                yield json.dumps({"event": "reasoning_delta", "text": reasoning}, ensure_ascii=False) + "\n"
            delta = extract_text_content_from_message(chunk)
            if not delta:
                continue
            buf.append(delta)
            yield json.dumps({"event": "assistant_delta", "text": delta}, ensure_ascii=False) + "\n"

        reply = "".join(buf).strip()
        if reply and not is_stopped():
            cm.append_message(
                agent_id="agent_director",
                context_key=context_key,
                role="assistant",
                content=reply,
                metadata={"type": "director_reply_stream"},
            )

    def route_and_record(
        self,
        *,
        user_id: str,
        project_name: str,
        context_key: str,
        user_message: str,
        active_context: Optional[str] = None,
        explicit_targets: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """处理全局对话的路由分发。

        返回路由摘要，并写入：
        - 用户消息到导演会话
        - （静默）用户消息到每个目标专家会话
        - 目标专家的回复到各自会话
        - 导演会话追加一条“最终回复”（避免只停留在“正在调度”）
        """
        cm = ChatManager(user_id=user_id, project_name=project_name)

        merged_meta = {**(metadata or {})}
        if active_context and isinstance(active_context, str) and active_context.strip():
            merged_meta["active_context"] = active_context

        # 1) record into director session
        cm.append_message(
            agent_id="agent_director",
            context_key=context_key,
            role="user",
            content=user_message,
            metadata=merged_meta,
        )

        # 2) 决策目标（路由）
        # 取最近历史用于路由判断
        history = cm.get_history(agent_id="agent_director", context_key=context_key, limit=5)
        targets = self._decide_targets(user_message, explicit_targets, history=history)

        # 禁止路由给自己
        targets = [t for t in targets if t and t != "agent_director"]
        # 如果没有目标，视为不需要路由

        # 3) silently record into each agent session
        routed = []
        for target in targets:
            cm.append_message(
                agent_id=target,
                context_key=context_key,
                role="user",
                content=user_message,
                metadata={
                    "routed_by": "agent_director",
                    "source_context": context_key,
                    "source_agent": "agent_director",
                    **merged_meta,
                },
            )
            routed.append(target)

        # 如果路由目标为空，则直接由导演回答：
        # 注意：用户消息在本方法开头已写入导演会话，这里只追加 assistant，避免重复写入。
        if not routed:
            history = cm.get_history(agent_id="agent_director", context_key=context_key, limit=10)
            reply = self.direct_reply(user_message, history=history, active_context=active_context)
            reply = (reply or "").strip()
            if reply:
                cm.append_message(
                    agent_id="agent_director",
                    context_key=context_key,
                    role="assistant",
                    content=reply,
                    metadata={"type": "director_reply"},
                )
            return {
                "routed_to": [],
                "context_key": context_key,
                "note": "未找到需要调度的专家，已由导演直接回复。",
                "status_text": "导演：未找到需要调度的专家，我先直接回答。",
                "reply": reply,
            }

        # 4) director assistant summary
        summary = {
            "routed_to": routed,
            "context_key": context_key,
            "note": "已将需求分发并写入各目标 Agent 的会话上下文。",
        }

        # UI 用可读状态文本（避免在聊天里展示 JSON）
        if routed:
            status_text = f"导演正在调度：{_format_targets(routed)}"
        else:
            status_text = "导演：未找到需要调度的专家，我先直接回答。"
        summary["status_text"] = status_text
        cm.append_message(
            agent_id="agent_director",
            context_key=context_key,
            role="assistant",
            content=status_text,
            metadata={"type": "routing_summary"},
        )

        # 5) 立即拉取目标专家回复并回传（修复只显示“正在调度”导致体验卡死）
        def _create_agent_instance(agent_id: str):
            from agents import ShowrunnerAgent, ScriptwriterAgent, CriticAgent
            from agents.agent_lorebook import WorldviewAgent
            from agents.setup_agents import MuseAgent
            from agents.communication import SparkBaseAgent

            agent_class_map = {
                "agent_showrunner": ShowrunnerAgent,
                "agent_scriptwriter": ScriptwriterAgent,
                "agent_critic": CriticAgent,
                "agent_lorebook": WorldviewAgent,
                "agent_muse": MuseAgent,
            }
            cls = agent_class_map.get(agent_id, SparkBaseAgent)
            return cls(user_id=user_id)

        replies: List[Dict[str, str]] = []
        for target in routed:
            agent_inst = _create_agent_instance(target)
            target_history = cm.get_history(agent_id=target, context_key=context_key, limit=10)
            try:
                reply_text = agent_inst.chat(user_message, history=target_history, active_context=active_context)
            except TypeError:
                # 兼容少数老 agent 的签名
                reply_text = agent_inst.chat(user_message)

            reply_text = (reply_text or "").strip()
            if reply_text:
                cm.append_message(
                    agent_id=target,
                    context_key=context_key,
                    role="assistant",
                    content=reply_text,
                    metadata={
                        "type": "routed_reply",
                        "routed_by": "agent_director",
                        "source_context": context_key,
                        "source_agent": "agent_director",
                    },
                )
            replies.append({"agent_id": target, "reply": reply_text})

        # 组织导演对用户的最终回复（不展示路由 JSON）
        if len(replies) == 1:
            final_reply = replies[0].get("reply", "")
        else:
            name_map = {a.get("key"): a.get("name") for a in get_agent_registry()}
            parts: List[str] = []
            for item in replies:
                aid = item.get("agent_id")
                label = name_map.get(aid, aid)
                content = (item.get("reply") or "").strip()
                if not content:
                    continue
                parts.append(f"【{label}】\n{content}")
            final_reply = "\n\n".join(parts).strip()

        if final_reply:
            cm.append_message(
                agent_id="agent_director",
                context_key=context_key,
                role="assistant",
                content=final_reply,
                metadata={"type": "director_routed_reply"},
            )

        summary["reply"] = final_reply
        return summary

    def route_and_record_stream(
        self,
        *,
        user_id: str,
        project_name: str,
        context_key: str,
        user_message: str,
        active_context: Optional[str] = None,
        explicit_targets: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        stop_event: Optional[threading.Event] = None,
    ):
        """路由并流式输出最终回复。

        行为：先输出“正在调度”状态，再继续输出目标专家的回复；最后把完整回复落库。
        """
        is_stopped = lambda: bool(stop_event and stop_event.is_set())
        cm = ChatManager(user_id=user_id, project_name=project_name)

        def _record_tool_trace(trace_map: Dict[str, Dict[str, Any]], delta: Any) -> None:
            if not isinstance(delta, dict):
                return

            import time

            event_type = str(delta.get("event") or "").strip()
            if event_type not in {"tool_intent_started", "tool_exec_started", "tool_exec_finished", "tool_exec_failed"}:
                return

            tool_name = str(delta.get("tool_name") or delta.get("toolName") or "").strip()
            if not tool_name:
                return

            ts = round(time.time(), 3)
            trace = dict(trace_map.get(tool_name) or {"tool_name": tool_name})

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

            trace_map[tool_name] = trace

        def _finalize_tool_traces(trace_map: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
            items: List[Dict[str, Any]] = []
            for trace in trace_map.values():
                tool_name = str(trace.get("tool_name") or "").strip()
                if not tool_name:
                    continue
                item = dict(trace)
                if isinstance(item.get("duration"), (int, float)):
                    item["duration"] = round(float(item["duration"]), 2)
                items.append(item)
            return items

        merged_meta = {**(metadata or {})}
        if active_context and isinstance(active_context, str) and active_context.strip():
            merged_meta["active_context"] = active_context

        # 1) record into director session
        cm.append_message(
            agent_id="agent_director",
            context_key=context_key,
            role="user",
            content=user_message,
            metadata=merged_meta,
        )

        # 2) decide targets
        history = cm.get_history(agent_id="agent_director", context_key=context_key, limit=5)
        targets = self._decide_targets(user_message, explicit_targets, history=history)
        targets = [t for t in targets if t and t != "agent_director"]

        # 3) silently record into each agent session
        routed: List[str] = []
        for target in targets:
            cm.append_message(
                agent_id=target,
                context_key=context_key,
                role="user",
                content=user_message,
                metadata={
                    "routed_by": "agent_director",
                    "source_context": context_key,
                    "source_agent": "agent_director",
                    **merged_meta,
                },
            )
            routed.append(target)

        # 无路由目标：转为导演直答（保持流式）
        if not routed:
            system = (
                "你是 SparkArc 的 AI 协调助手。\n"
                "规则：直接回答用户的通用问题，不要调度专家。\n"
                "禁止角色扮演，禁止使用括号描写动作。回复简洁、专业。"
            )

            msgs = [SystemMessage(content=system)]
            hist = cm.get_history(agent_id="agent_director", context_key=context_key, limit=10)
            if hist:
                for m in hist[-8:]:
                    role = m.get("role")
                    content = m.get("content")
                    if not content:
                        continue
                    if isinstance(content, dict):
                        content = json.dumps(content, ensure_ascii=False)
                    if role == "user":
                        msgs.append(HumanMessage(content=str(content)))
                    elif role == "assistant":
                        from langchain_core.messages import AIMessage
                        msgs.append(AIMessage(content=str(content)))

            if active_context and isinstance(active_context, str) and active_context.strip():
                ctx = active_context.strip()
                if len(ctx) > 3000:
                    ctx = ctx[:3000] + "\n...(省略)"
                msgs.append(HumanMessage(content=f"【当前上下文】\n{ctx}"))

            msgs.append(HumanMessage(content=user_message))

            buf: List[str] = []
            for chunk in self.stream_llm.stream(msgs):
                if is_stopped():
                    break
                reasoning = extract_reasoning_text_from_message(chunk)
                if reasoning:
                    yield json.dumps({"event": "reasoning_delta", "text": reasoning}, ensure_ascii=False) + "\n"
                delta = extract_text_content_from_message(chunk)
                if not delta:
                    continue
                buf.append(delta)
                yield json.dumps({"event": "assistant_delta", "text": delta}, ensure_ascii=False) + "\n"

            reply = "".join(buf).strip()
            if reply and not is_stopped():
                cm.append_message(
                    agent_id="agent_director",
                    context_key=context_key,
                    role="assistant",
                    content=reply,
                    metadata={"type": "director_reply_stream"},
                )
            return

        if is_stopped():
            return

        status_text = f"导演正在调度：{_format_targets(routed)}"
        cm.append_message(
            agent_id="agent_director",
            context_key=context_key,
            role="assistant",
            content=status_text,
            metadata={"type": "routing_summary"},
        )

        # 先把状态返回给前端（同一个流里）
        yield json.dumps({"event": "assistant_delta", "text": status_text + "\n\n"}, ensure_ascii=False) + "\n"

        def _create_agent_instance(agent_id: str):
            from agents import ShowrunnerAgent, ScriptwriterAgent, CriticAgent
            from agents.agent_lorebook import WorldviewAgent
            from agents.setup_agents import MuseAgent
            from agents.communication import SparkBaseAgent

            agent_class_map = {
                "agent_showrunner": ShowrunnerAgent,
                "agent_scriptwriter": ScriptwriterAgent,
                "agent_critic": CriticAgent,
                "agent_lorebook": WorldviewAgent,
                "agent_muse": MuseAgent,
            }
            cls = agent_class_map.get(agent_id, SparkBaseAgent)
            return cls(user_id=user_id)

        total_buf: List[str] = []
        director_tool_traces: List[Dict[str, Any]] = []
        for idx, target in enumerate(routed):
            if is_stopped():
                break
            agent_inst = _create_agent_instance(target)
            target_history = cm.get_history(agent_id=target, context_key=context_key, limit=10)

            prefix = ""
            if len(routed) > 1:
                name_map = {a.get("key"): a.get("name") for a in get_agent_registry()}
                label = name_map.get(target, target)
                prefix = f"【{label}】\n"
                yield json.dumps({"event": "assistant_delta", "text": prefix}, ensure_ascii=False) + "\n"
                total_buf.append(prefix)

            one_buf: List[str] = []
            one_tool_trace_map: Dict[str, Dict[str, Any]] = {}
            try:
                stream = agent_inst.chat_stream(user_message, history=target_history, active_context=active_context)
                for delta in stream:
                    if is_stopped():
                        break
                    if not delta:
                        continue
                    # chat_stream 返回的 delta 可能是 dict 事件或 string 纯文本
                    if isinstance(delta, dict):
                        _record_tool_trace(one_tool_trace_map, delta)
                        # 序列化 JSON 事件并 yield
                        yield json.dumps(delta, ensure_ascii=False) + "\n"
                        # 只把正文文本追加到 buf（推理内容不存入聊天历史）
                        if delta.get("event") == "assistant_delta":
                            text = delta.get("text", "")
                            if text:
                                one_buf.append(text)
                                total_buf.append(text)
                    else:
                        # 纯文本兼容
                        text = str(delta)
                        one_buf.append(text)
                        total_buf.append(text)
                        yield json.dumps({"event": "assistant_delta", "text": text}, ensure_ascii=False) + "\n"
            except TypeError:
                if is_stopped():
                    break
                reply_text = (agent_inst.chat(user_message) or "").strip()
                if reply_text:
                    one_buf.append(reply_text)
                    total_buf.append(reply_text)
                    yield json.dumps({"event": "assistant_delta", "text": reply_text}, ensure_ascii=False) + "\n"

            reply_text = "".join(one_buf).strip()
            finalized_tool_traces = _finalize_tool_traces(one_tool_trace_map)
            if finalized_tool_traces:
                director_tool_traces.extend([{**trace, "source_agent": target} for trace in finalized_tool_traces])
            if (reply_text or finalized_tool_traces) and not is_stopped():
                target_metadata = {
                    "type": "routed_reply_stream",
                    "routed_by": "agent_director",
                    "source_context": context_key,
                    "source_agent": "agent_director",
                }
                if finalized_tool_traces:
                    target_metadata["tool_traces"] = finalized_tool_traces
                cm.append_message(
                    agent_id=target,
                    context_key=context_key,
                    role="assistant",
                    content=reply_text,
                    metadata=target_metadata,
                )

            if idx != len(routed) - 1 and not is_stopped():
                sep = "\n\n"
                yield json.dumps({"event": "assistant_delta", "text": sep}, ensure_ascii=False) + "\n"
                total_buf.append(sep)

        final_reply = "".join(total_buf).strip()
        if (final_reply or director_tool_traces) and not is_stopped():
            director_metadata = {"type": "director_routed_reply_stream"}
            if director_tool_traces:
                director_metadata["tool_traces"] = director_tool_traces
            cm.append_message(
                agent_id="agent_director",
                context_key=context_key,
                role="assistant",
                content=final_reply,
                metadata=director_metadata,
            )
