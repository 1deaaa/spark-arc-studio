"""
LLM 用量追踪模块

架构说明
--------
本模块提供三个核心类：

1. UsageTrackingCallback（BaseCallbackHandler）
   - 通过 LangChain 官方 Callback 机制截获所有 LLM 调用事件
   - 自动覆盖全部 9 种调用方式（invoke/stream/batch/generate 及其异步变体）
   - 无需自定义 BaseChatModel，直接使用原生 ChatOpenAI，完全兼容 OpenAI 协议
   - Token 统计策略：
     * 优先读取 API 返回的真实 usage 字段（标准 OpenAI 协议）
     * 若 API 不返回 usage（国产模型、截断输出等），自动降级为本地 estimate_tokens 估算
   - 同时支持同步和异步（on_llm_end / on_llm_error 均有 async 版本）

2. LLMClient（具名返回对象）
    - get_user_llm() 的返回类型，包含 llm 与 usage 两个字段

3. LLMUsage（轻量句柄）
    - 随 ChatOpenAI 实例一同返回，携带用量查询方法
    - 精确到 user_id + model_id 维度，支持未来限额、限次、计费扩展
    - 用法：client = manager.get_user_llm(user_id)
              result = client.invoke(messages)
              usage = client.usage.get_usage_last_24h()

关于 streaming 参数
-------------------
⚠️ 不要向 get_user_llm() 传入 streaming 参数。
流式/非流式由调用方式决定，不由构造参数控制：
  - 非流式：llm.invoke() / llm.ainvoke()
  - 流式：  llm.stream() / llm.astream() / llm.astream_events()
streaming 参数（若传入）会被静默忽略，不会透传到底层 SDK。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, UTC
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import BaseMessage
from langchain_core.outputs import LLMResult, ChatGenerationChunk

from sqlalchemy import func
from sqlalchemy.orm import sessionmaker

from .models import UsageLogEntry
from .estimate_tokens import estimate_tokens


@dataclass(frozen=True)
class LLMClient:
    """
    get_user_llm() 的具名返回对象。

    属性：
    - llm: 已注入 UsageTrackingCallback 的 ChatOpenAI 实例
    - usage: 用量查询句柄（LLMUsage）

    调用方式：
    - 默认当作 LLM 使用：client.invoke(...) / client.stream(...)
    - 查询用量走子对象：client.usage.get_usage_last_24h()
    """

    llm: Any
    usage: "LLMUsage"

    def __getattr__(self, name: str) -> Any:
        """将未知属性/方法透传给内部 llm，实现 get_user_llm(...).invoke() 直调。"""
        return getattr(self.llm, name)

    def __dir__(self):
        """合并 llm 的可见属性，便于 IDE 自动补全。"""
        return sorted(set(super().__dir__()) | set(dir(self.llm)))


class UsageTrackingCallback(BaseCallbackHandler):
    """
    LLM 用量追踪 Callback。

    通过 LangChain Callback 机制自动截获所有调用事件，
    无需自定义 BaseChatModel，自动覆盖全部 9 种调用方式。

    Token 统计优先级：
    1. API 返回的真实 usage 字段（标准 OpenAI 协议）
    2. 本地 estimate_tokens 估算（兜底，适用于国产模型/截断输出）
    """

    def __init__(
        self,
        user_id: str,
        model_id: int,
        platform_id: int,
        model_name: str,
        platform_name: str,
        session_maker: sessionmaker,
        agent_name: Optional[str] = None,
    ):
        super().__init__()
        self.user_id = user_id
        self.model_id = model_id
        self.platform_id = platform_id
        self.model_name = model_name
        self.platform_name = platform_name
        self.agent_name = agent_name
        self._session_maker = session_maker

        # 流式累积缓冲区（按 run_id 隔离，支持并发）
        self._stream_buffers: Dict[str, List[str]] = {}
        # 输入 token 缓存（按 run_id）
        self._prompt_tokens_cache: Dict[str, int] = {}

    # ==================== 内部工具方法 ====================

    def _messages_to_text(self, messages: List[BaseMessage]) -> str:
        """将消息列表转换为文本，用于估算 Token"""
        parts = []
        for msg in messages:
            content = msg.content
            if isinstance(content, str):
                parts.append(content)
            elif isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        parts.append(block.get("text", ""))
        return "\n".join(parts)

    def _extract_token_usage(self, response: LLMResult) -> Optional[Dict[str, int]]:
        """
        尝试从 API 响应中提取真实 token 用量。
        兼容 OpenAI 标准格式及常见国产模型变体。
        返回 None 表示 API 未提供 usage，需要降级为本地估算。
        """
        llm_output = response.llm_output or {}

        # 标准 OpenAI 格式：token_usage
        usage = llm_output.get("token_usage") or llm_output.get("usage")
        if usage and isinstance(usage, dict):
            prompt = usage.get("prompt_tokens") or usage.get("input_tokens", 0)
            completion = usage.get("completion_tokens") or usage.get("output_tokens", 0)
            if prompt or completion:
                return {
                    "prompt_tokens": int(prompt or 0),
                    "completion_tokens": int(completion or 0),
                }

        return None  # API 未返回 usage，触发本地估算

    def _extract_completion_text(self, response: LLMResult) -> str:
        """从响应中提取 completion 文本，用于本地估算"""
        parts = []
        for gen_list in response.generations:
            for gen in gen_list:
                # ChatGeneration
                msg = getattr(gen, "message", None)
                if msg is not None:
                    content = getattr(msg, "content", "")
                    if isinstance(content, str):
                        parts.append(content)
                    elif isinstance(content, list):
                        for block in content:
                            if isinstance(block, dict) and block.get("type") == "text":
                                parts.append(block.get("text", ""))
                    # tool_calls 也计入 completion
                    tool_calls = getattr(msg, "tool_calls", None)
                    if tool_calls:
                        try:
                            parts.append(json.dumps(tool_calls, ensure_ascii=False))
                        except Exception:
                            pass
                else:
                    # 普通 Generation（text）
                    text = getattr(gen, "text", "")
                    if text:
                        parts.append(text)
        return "\n".join(p for p in parts if p)

    def _record_usage(
        self,
        prompt_tokens: int,
        completion_tokens: int,
        success: bool = True,
    ) -> None:
        """写入用量日志到数据库"""
        if self._session_maker is None:
            return
        total_tokens = prompt_tokens + completion_tokens
        with self._session_maker() as session:
            entry = UsageLogEntry(
                user_id=self.user_id,
                model_id=self.model_id,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                success=1 if success else 0,
                agent_name=self.agent_name,
            )
            session.add(entry)
            session.commit()

    async def _arecord_usage(
        self,
        prompt_tokens: int,
        completion_tokens: int,
        success: bool = True,
    ) -> None:
        """异步写入用量日志（在异步上下文中调用，避免阻塞事件循环）"""
        # SQLite 同步写入很快，直接调用同步版本即可
        # 如果未来切换到异步数据库驱动，在此处替换为 await session.commit()
        self._record_usage(prompt_tokens, completion_tokens, success)

    # ==================== 同步 Callback 事件 ====================

    def on_chat_model_start(
        self,
        serialized: Dict[str, Any],
        messages: List[List[BaseMessage]],
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        """调用开始：预估并缓存 prompt token 数"""
        all_messages = [msg for msg_list in messages for msg in msg_list]
        prompt_text = self._messages_to_text(all_messages)
        self._prompt_tokens_cache[str(run_id)] = estimate_tokens(prompt_text, self.model_name)
        self._stream_buffers[str(run_id)] = []

    def on_llm_end(
        self,
        response: LLMResult,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        """
        调用结束（invoke/batch/generate 路径）：记录用量。
        优先使用 API 返回的真实 usage，否则降级为本地估算。
        """
        run_key = str(run_id)
        prompt_tokens = self._prompt_tokens_cache.pop(run_key, 0)

        # 优先读取 API 真实 usage
        api_usage = self._extract_token_usage(response)
        if api_usage:
            prompt_tokens = api_usage["prompt_tokens"] or prompt_tokens
            completion_tokens = api_usage["completion_tokens"]
        else:
            # 降级：本地估算 completion
            completion_text = self._extract_completion_text(response)

            # 流式路径：completion 已在 on_llm_new_token 中累积
            stream_buf = self._stream_buffers.pop(run_key, [])
            if stream_buf:
                completion_text = "".join(stream_buf)

            completion_tokens = estimate_tokens(completion_text, self.model_name)

        self._stream_buffers.pop(run_key, None)
        self._record_usage(prompt_tokens, completion_tokens, success=True)

    def on_llm_new_token(
        self,
        token: str,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        """流式路径：累积每个 token chunk，用于本地估算兜底"""
        run_key = str(run_id)
        if run_key not in self._stream_buffers:
            self._stream_buffers[run_key] = []
        self._stream_buffers[run_key].append(token)

    def on_llm_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        """调用失败：记录失败用量（若已产生流式输出则按已输出内容估算 completion）"""
        run_key = str(run_id)
        prompt_tokens = self._prompt_tokens_cache.pop(run_key, 0)
        stream_buf = self._stream_buffers.pop(run_key, None) or []
        completion_tokens = 0
        if stream_buf:
            completion_text = "".join(stream_buf)
            completion_tokens = estimate_tokens(completion_text, self.model_name)
        self._record_usage(prompt_tokens, completion_tokens=completion_tokens, success=False)

    # ==================== 异步 Callback 事件（真异步，不阻塞事件循环）====================

    async def on_chat_model_start(  # type: ignore[override]
        self,
        serialized: Dict[str, Any],
        messages: List[List[BaseMessage]],
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        """异步版本：调用开始，预估 prompt token"""
        all_messages = [msg for msg_list in messages for msg in msg_list]
        prompt_text = self._messages_to_text(all_messages)
        self._prompt_tokens_cache[str(run_id)] = estimate_tokens(prompt_text, self.model_name)
        self._stream_buffers[str(run_id)] = []

    async def on_llm_end(  # type: ignore[override]
        self,
        response: LLMResult,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        """异步版本：调用结束，记录用量"""
        run_key = str(run_id)
        prompt_tokens = self._prompt_tokens_cache.pop(run_key, 0)

        api_usage = self._extract_token_usage(response)
        if api_usage:
            prompt_tokens = api_usage["prompt_tokens"] or prompt_tokens
            completion_tokens = api_usage["completion_tokens"]
        else:
            stream_buf = self._stream_buffers.pop(run_key, [])
            if stream_buf:
                completion_text = "".join(stream_buf)
            else:
                completion_text = self._extract_completion_text(response)
            completion_tokens = estimate_tokens(completion_text, self.model_name)

        self._stream_buffers.pop(run_key, None)
        await self._arecord_usage(prompt_tokens, completion_tokens, success=True)

    async def on_llm_new_token(  # type: ignore[override]
        self,
        token: str,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        """异步版本：流式 token 累积"""
        run_key = str(run_id)
        if run_key not in self._stream_buffers:
            self._stream_buffers[run_key] = []
        self._stream_buffers[run_key].append(token)

    async def on_llm_error(  # type: ignore[override]
        self,
        error: BaseException,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        """异步版本：调用失败，记录失败用量（若有已输出 token 则按已输出估算）"""
        run_key = str(run_id)
        prompt_tokens = self._prompt_tokens_cache.pop(run_key, 0)
        stream_buf = self._stream_buffers.pop(run_key, None) or []
        completion_tokens = 0
        if stream_buf:
            completion_text = "".join(stream_buf)
            completion_tokens = estimate_tokens(completion_text, self.model_name)
        await self._arecord_usage(prompt_tokens, completion_tokens=completion_tokens, success=False)


class LLMUsage:
    """
    LLM 用量查询句柄。

    随 ChatOpenAI 实例一同由 get_user_llm() 返回，
    提供精确到 user_id + model_id 维度的用量查询接口，
    支持未来限额、限次、计费等扩展。

    用法：
        client = manager.get_user_llm(user_id)
        result = client.invoke(messages)
        usage = client.usage.get_usage_last_24h()
        print(f"过去24小时: {usage['total_tokens']} tokens, {usage['requests']} 次请求")
    """

    def __init__(
        self,
        user_id: str,
        model_id: int,
        platform_id: int,
        model_name: str,
        platform_name: str,
        session_maker: sessionmaker,
        agent_name: Optional[str] = None,
    ):
        self.user_id = user_id
        self.model_id = model_id
        self.platform_id = platform_id
        self.model_name = model_name
        self.platform_name = platform_name
        self.agent_name = agent_name
        self._session_maker = session_maker

    def get_usage_last_24h(self) -> Dict[str, Any]:
        """获取过去 24 小时的用量"""
        return self._get_usage_since(timedelta(hours=24))

    def get_usage_last_week(self) -> Dict[str, Any]:
        """获取过去 7 天的用量"""
        return self._get_usage_since(timedelta(days=7))

    def get_usage_last_month(self) -> Dict[str, Any]:
        """获取过去 30 天的用量"""
        return self._get_usage_since(timedelta(days=30))

    def get_usage_total(self) -> Dict[str, Any]:
        """获取所有时间的总用量"""
        return self._get_usage_since(None)

    def get_usage_by_range(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """获取指定时间范围的用量"""
        with self._session_maker() as session:
            query = session.query(
                func.coalesce(func.sum(UsageLogEntry.total_tokens), 0).label("total_tokens"),
                func.coalesce(func.sum(UsageLogEntry.prompt_tokens), 0).label("prompt_tokens"),
                func.coalesce(func.sum(UsageLogEntry.completion_tokens), 0).label("completion_tokens"),
                func.count(UsageLogEntry.id).label("requests"),
                func.coalesce(func.sum(1 - UsageLogEntry.success), 0).label("errors"),
            ).filter(
                UsageLogEntry.user_id == self.user_id,
                UsageLogEntry.model_id == self.model_id,
            )
            if start_time is not None:
                query = query.filter(UsageLogEntry.created_at >= start_time)
            if end_time is not None:
                query = query.filter(UsageLogEntry.created_at <= end_time)
            result = query.first()
            return self._format_result(result)

    def _get_usage_since(self, delta: Optional[timedelta]) -> Dict[str, Any]:
        """内部方法：查询指定时间范围的用量"""
        with self._session_maker() as session:
            query = session.query(
                func.coalesce(func.sum(UsageLogEntry.total_tokens), 0).label("total_tokens"),
                func.coalesce(func.sum(UsageLogEntry.prompt_tokens), 0).label("prompt_tokens"),
                func.coalesce(func.sum(UsageLogEntry.completion_tokens), 0).label("completion_tokens"),
                func.count(UsageLogEntry.id).label("requests"),
                func.coalesce(func.sum(1 - UsageLogEntry.success), 0).label("errors"),
            ).filter(
                UsageLogEntry.user_id == self.user_id,
                UsageLogEntry.model_id == self.model_id,
            )
            if delta is not None:
                cutoff = datetime.now(UTC) - delta
                query = query.filter(UsageLogEntry.created_at >= cutoff)
            result = query.first()
            return self._format_result(result)

    @staticmethod
    def _format_result(result) -> Dict[str, Any]:
        return {
            "total_tokens": int(result.total_tokens or 0),
            "prompt_tokens": int(result.prompt_tokens or 0),
            "completion_tokens": int(result.completion_tokens or 0),
            "requests": int(result.requests or 0),
            "errors": int(result.errors or 0),
        }
