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
import re
from typing import Any, Dict, List, Optional

from langchain_core.messages import HumanMessage, SystemMessage

from .chat_manager import ChatManager
from .registry import get_agent_registry
from .agent_router import RouterAgent
from llm.llm_mgr import LLM_Manager


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
        # 导演主要负责总结与上下文管理（倾向更稳的模型配置）
        self.llm = LLM_Manager.get_user_llm(
            user_id,
            agent_name="agent_director",
            streaming=False,
            temperature=0.1
        )
        # 路由交由专门的 RouterAgent（倾向更快的模型配置）
        self.router = RouterAgent(user_id)

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

    def should_route(self, user_message: str, explicit_targets: Optional[List[str]] = None) -> bool:
        text = (user_message or "").strip()
        if not text:
            return False

        # 1) 显式指定目标：必路由
        if explicit_targets:
            return True

        # 2) 简单寒暄：不路由（导演自己回复）
        if _is_greeting(text) and len(text) <= 12:
            return False

        # 3) 明确点名某个专家：路由
        if self._match_agents_by_mention(text):
            return True

        # 4) 交给路由 Agent 判断（返回空 targets 表示无需路由）
        try:
            targets = self.router.decide_targets(text, history=[])
            return bool(targets)
        except Exception:
            return False

    def direct_reply(self, user_message: str, history: List[Dict[str, Any]] = None, active_context: Optional[str] = None) -> str:
        """导演直答（不路由）：用于寒暄、全局性讨论、泛问等。"""
        system = (
            "你是 SparkArc 剧组的导演。\n"
            "工作方式：\n"
            "1) 对寒暄/测试/闲聊/全局性问题：你要直接回答，不要调度专家；\n"
            "2) 只有当用户的请求明显属于某个专家职责时，才建议调度，并说明为什么；\n"
            "3) 回复要简洁、可执行，像片场导演一样高效。"
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
        return resp.content

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
    ):
        """导演直答并写入会话（流式）。"""
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
            "你是 SparkArc 剧组的导演。\n"
            "规则：寒暄/测试/闲聊/全局性问题请直接回答，不要调度专家。\n"
            "回复简洁、可执行。"
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
        for chunk in self.llm.stream(msgs):
            delta = getattr(chunk, "content", "")
            if not delta:
                continue
            buf.append(delta)
            yield delta

        reply = "".join(buf).strip()
        if reply:
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
    ):
        """路由并流式输出最终回复。

        行为：先输出“正在调度”状态，再继续输出目标专家的回复；最后把完整回复落库。
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
                "你是 SparkArc 剧组的导演。\n"
                "规则：寒暄/测试/闲聊/全局性问题请直接回答，不要调度专家。\n"
                "回复简洁、可执行。"
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
            for chunk in self.llm.stream(msgs):
                delta = getattr(chunk, "content", "")
                if not delta:
                    continue
                buf.append(delta)
                yield delta

            reply = "".join(buf).strip()
            if reply:
                cm.append_message(
                    agent_id="agent_director",
                    context_key=context_key,
                    role="assistant",
                    content=reply,
                    metadata={"type": "director_reply_stream"},
                )
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
        yield status_text + "\n\n"

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
        for idx, target in enumerate(routed):
            agent_inst = _create_agent_instance(target)
            target_history = cm.get_history(agent_id=target, context_key=context_key, limit=10)

            prefix = ""
            if len(routed) > 1:
                name_map = {a.get("key"): a.get("name") for a in get_agent_registry()}
                label = name_map.get(target, target)
                prefix = f"【{label}】\n"
                yield prefix
                total_buf.append(prefix)

            one_buf: List[str] = []
            try:
                stream = agent_inst.chat_stream(user_message, history=target_history, active_context=active_context)
                for delta in stream:
                    if not delta:
                        continue
                    one_buf.append(delta)
                    total_buf.append(delta)
                    yield delta
            except TypeError:
                reply_text = (agent_inst.chat(user_message) or "").strip()
                if reply_text:
                    one_buf.append(reply_text)
                    total_buf.append(reply_text)
                    yield reply_text

            reply_text = "".join(one_buf).strip()
            if reply_text:
                cm.append_message(
                    agent_id=target,
                    context_key=context_key,
                    role="assistant",
                    content=reply_text,
                    metadata={
                        "type": "routed_reply_stream",
                        "routed_by": "agent_director",
                        "source_context": context_key,
                        "source_agent": "agent_director",
                    },
                )

            if idx != len(routed) - 1:
                sep = "\n\n"
                yield sep
                total_buf.append(sep)

        final_reply = "".join(total_buf).strip()
        if final_reply:
            cm.append_message(
                agent_id="agent_director",
                context_key=context_key,
                role="assistant",
                content=final_reply,
                metadata={"type": "director_routed_reply_stream"},
            )
