"""
TrackedChatModel - 带用量追踪的 LLM 包装器

自动记录每次调用的 Token 消耗和请求次数到数据库。
业务代码无需手动调用 record_usage。
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, Iterator, List, Optional, Union

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult

from sqlalchemy import func
from sqlalchemy.orm import sessionmaker

from .models import UsageLogEntry
from .estimate_tokens import estimate_tokens


class TrackedChatModel(BaseChatModel):
    """
    包装 BaseChatModel，自动追踪并记录 Token 使用量。
    
    用法：
        llm = manager.get_user_llm(user_id, agent_name="agent_muse")
        result = llm.invoke(messages)
        
        # 查询用量
        usage = llm.get_usage_last_24h()
        print(f"过去24小时: {usage['tokens']} tokens, {usage['requests']} 次请求")
    """
    
    # Pydantic 字段声明
    user_id: str
    model_id: int
    platform_id: int
    model_name: str
    platform_name: str
    agent_name: Optional[str] = None
    _session_maker: Any = None  # 私有属性，不参与序列化
    
    # Pydantic v2 配置
    model_config = {"arbitrary_types_allowed": True}

    # 私有属性，不参与序列化
    _inner_llm: BaseChatModel = None
    _session_maker: Any = None

    def __init__(
        self,
        inner_llm: BaseChatModel,
        user_id: str,
        model_id: int,
        platform_id: int,
        model_name: str,
        platform_name: str,
        session_maker: sessionmaker,
        agent_name: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(
            user_id=user_id,
            model_id=model_id,
            platform_id=platform_id,
            model_name=model_name,
            platform_name=platform_name,
            agent_name=agent_name,
            **kwargs,
        )
        self._inner_llm = inner_llm
        self._session_maker = session_maker

    @property
    def _llm_type(self) -> str:
        return f"tracked-{self._inner_llm._llm_type}"

    @property
    def _identifying_params(self) -> Dict[str, Any]:
        return {
            "inner_llm": self._inner_llm._identifying_params,
            "user_id": self.user_id,
            "model_id": self.model_id,
        }

    def _messages_to_text(self, messages: List[BaseMessage]) -> str:
        """将消息列表转换为文本，用于估算 Token"""
        text_parts = []
        for msg in messages:
            content = msg.content
            if isinstance(content, str):
                text_parts.append(content)
            elif isinstance(content, list):
                # 处理多模态消息列表 (e.g. [{"type": "text", "text": "..."}])
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        text_parts.append(block.get("text", ""))
        return "\n".join(text_parts)

    def _record_usage(
        self,
        prompt_tokens: int,
        completion_tokens: int,
        success: bool = True,
        context_key: Optional[str] = None,
    ) -> None:
        """记录一次调用到数据库"""
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
                context_key=context_key,
            )
            session.add(entry)
            session.commit()

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        """同步生成，自动记录用量"""
        try:
            result = self._inner_llm._generate(messages, stop, run_manager, **kwargs)
            
            # 使用本地估算
            prompt_text = self._messages_to_text(messages)
            completion_text = ""
            if result.generations:
                completion_text = result.generations[0].message.content
                # Handle list content in response if any (unlikely for text gen but possible)
                if isinstance(completion_text, list):
                    completion_text = "\n".join(
                        block.get("text", "")
                        for block in completion_text
                        if isinstance(block, dict) and block.get("type") == "text"
                    )

            prompt_tokens = estimate_tokens(prompt_text, self.model_name)
            completion_tokens = estimate_tokens(completion_text, self.model_name)

            self._record_usage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                success=True,
            )
            return result
        except Exception:
            # 即使失败也尝试估算 prompt (如果有 messages)
            try:
                prompt_text = self._messages_to_text(messages)
                prompt_tokens = estimate_tokens(prompt_text, self.model_name)
            except:
                prompt_tokens = 0
            
            self._record_usage(prompt_tokens=prompt_tokens, completion_tokens=0, success=False)
            raise

    def _stream(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> Iterator[ChatGenerationChunk]:
        """流式生成，在流结束后记录用量"""
        completion_text_buffer = []
        success = True
        
        try:
            for chunk in self._inner_llm._stream(messages, stop, run_manager, **kwargs):
                content = chunk.message.content
                if isinstance(content, str):
                    completion_text_buffer.append(content)
                elif isinstance(content, list):
                     for block in content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            completion_text_buffer.append(block.get("text", ""))

                yield chunk
        except Exception:
            success = False
            raise
        finally:
            # 估算用量
            prompt_text = self._messages_to_text(messages)
            completion_text = "".join(completion_text_buffer)
            
            prompt_tokens = estimate_tokens(prompt_text, self.model_name)
            completion_tokens = estimate_tokens(completion_text, self.model_name)

            self._record_usage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                success=success,
            )

    # ==================== 用量查询接口 ====================

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

    def _get_usage_since(self, delta: Optional[timedelta]) -> Dict[str, Any]:
        """内部方法：查询指定时间范围的用量"""
        if self._session_maker is None:
            return {"tokens": 0, "prompt_tokens": 0, "completion_tokens": 0, "requests": 0, "errors": 0}
        
        with self._session_maker() as session:
            query = session.query(
                func.coalesce(func.sum(UsageLogEntry.total_tokens), 0).label("tokens"),
                func.coalesce(func.sum(UsageLogEntry.prompt_tokens), 0).label("prompt_tokens"),
                func.coalesce(func.sum(UsageLogEntry.completion_tokens), 0).label("completion_tokens"),
                func.count(UsageLogEntry.id).label("requests"),
                func.sum(1 - UsageLogEntry.success).label("errors"),
            ).filter(
                UsageLogEntry.user_id == self.user_id,
                UsageLogEntry.model_id == self.model_id,
            )
            
            if delta is not None:
                cutoff = datetime.utcnow() - delta
                query = query.filter(UsageLogEntry.created_at >= cutoff)
            
            result = query.first()
            
            return {
                "tokens": int(result.tokens or 0),
                "prompt_tokens": int(result.prompt_tokens or 0),
                "completion_tokens": int(result.completion_tokens or 0),
                "requests": int(result.requests or 0),
                "errors": int(result.errors or 0),
            }

    def get_usage_by_range(
        self, 
        start_time: Optional[datetime] = None, 
        end_time: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """获取指定时间范围的用量"""
        if self._session_maker is None:
            return {"tokens": 0, "prompt_tokens": 0, "completion_tokens": 0, "requests": 0, "errors": 0}
        
        with self._session_maker() as session:
            query = session.query(
                func.coalesce(func.sum(UsageLogEntry.total_tokens), 0).label("tokens"),
                func.coalesce(func.sum(UsageLogEntry.prompt_tokens), 0).label("prompt_tokens"),
                func.coalesce(func.sum(UsageLogEntry.completion_tokens), 0).label("completion_tokens"),
                func.count(UsageLogEntry.id).label("requests"),
                func.sum(1 - UsageLogEntry.success).label("errors"),
            ).filter(
                UsageLogEntry.user_id == self.user_id,
                UsageLogEntry.model_id == self.model_id,
            )
            
            if start_time is not None:
                query = query.filter(UsageLogEntry.created_at >= start_time)
            if end_time is not None:
                query = query.filter(UsageLogEntry.created_at <= end_time)
            
            result = query.first()
            
            return {
                "tokens": int(result.tokens or 0),
                "prompt_tokens": int(result.prompt_tokens or 0),
                "completion_tokens": int(result.completion_tokens or 0),
                "requests": int(result.requests or 0),
                "errors": int(result.errors or 0),
            }

    # ==================== 代理方法（透传到内部 LLM）====================

    def bind_tools(self, *args, **kwargs):
        """代理 bind_tools 方法"""
        new_inner = self._inner_llm.bind_tools(*args, **kwargs)
        return TrackedChatModel(
            inner_llm=new_inner,
            user_id=self.user_id,
            model_id=self.model_id,
            platform_id=self.platform_id,
            model_name=self.model_name,
            platform_name=self.platform_name,
            session_maker=self._session_maker,
            agent_name=self.agent_name,
        )

    def with_structured_output(self, *args, **kwargs):
        """代理 with_structured_output 方法"""
        new_inner = self._inner_llm.with_structured_output(*args, **kwargs)
        # 注意：with_structured_output 返回的不一定是 BaseChatModel
        # 如果返回的是 Runnable，我们需要特殊处理
        if isinstance(new_inner, BaseChatModel):
            return TrackedChatModel(
                inner_llm=new_inner,
                user_id=self.user_id,
                model_id=self.model_id,
                platform_id=self.platform_id,
                model_name=self.model_name,
                platform_name=self.platform_name,
                session_maker=self._session_maker,
                agent_name=self.agent_name,
            )
        # 如果不是 BaseChatModel，直接返回（可能丢失追踪能力，但保持功能正常）
        return new_inner
