"""系统工具 Agent。

该模块承载不会直接面对用户的系统级 LLM 任务，例如长上下文压缩。
它不注册到信标总线，也不参与导演委派；但通过 ``agent_utility`` 这个
agent_name 复用现有的模型绑定能力。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List

from langchain_core.messages import HumanMessage, SystemMessage

from agents.agent_utils import load_prompt
from core.file_ingest.chunking import TokenTextSplitter
from llm.agen_matchbox.estimate_tokens import estimate_tokens


UTILITY_AGENT_ID = "agent_utility"


@dataclass(slots=True)
class ChatAttachmentPreparation:
    """聊天附件解析、切分与落盘后的结构化结果。"""

    parsed: Any
    chunks: list[Any]
    chunk_info: dict
    attachment_id: str
    chunk_count: int
    total_tokens_estimated: int
    is_partial: bool


class AttachmentContextWindowExceededError(ValueError):
    """附件全文 token 数超过当前模型上下文窗口。"""

    def __init__(self, *, total_tokens: int, max_context_tokens: int):
        self.total_tokens = max(int(total_tokens or 0), 0)
        self.max_context_tokens = max(int(max_context_tokens or 0), 0)
        super().__init__(
            f"附件约 {self.total_tokens} tokens，超过当前模型 {self.max_context_tokens} tokens 的上下文窗口"
        )


class UtilityAgent:
    """系统内部工具 Agent。"""

    agent_id = UTILITY_AGENT_ID

    def __init__(self, user_id: str, project_name: str | None = None):
        self.user_id = str(user_id)
        self.project_name = project_name or ""

    def _get_llm(self):
        from llm.agen_matchbox import matchbox

        return matchbox().get_user_llm(self.user_id, agent_name=self.agent_id)

    @staticmethod
    def _json_dumps(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, indent=2)

    @staticmethod
    def _parse_json_object(raw: Any) -> Dict[str, Any]:
        text = str(raw or "").strip()
        if text.startswith("```"):
            text = text.strip("`").strip()
            if text.lower().startswith("json"):
                text = text[4:].strip()
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            text = text[start:end + 1]
        try:
            value = json.loads(text)
            if isinstance(value, dict):
                return value
        except Exception:
            pass
        return {
            "summary": text[:4000],
            "user_intent_anchors": [],
            "creative_state": {},
            "author_preferences": {},
            "current_progress": [],
            "important_facts": [],
            "decisions": [],
            "rejected_options": [],
            "conflicts_and_uncertainties": [],
            "open_tasks": [],
            "recent_turns": [],
            "tool_results": [],
            "retrieval_anchors": [],
            "handoff_notes": ["压缩模型未返回严格 JSON，已保留原始摘要文本。"],
        }

    def _compress_once(
        self,
        *,
        history_text: str,
        agent_id: str,
        model_name: str,
        target_tokens: int,
        current_user_message: str,
    ) -> Dict[str, Any]:
        prompt = load_prompt(
            "utility",
            "compress_context",
            agent_id=agent_id,
            model_name=model_name or "unknown",
            target_tokens=str(max(int(target_tokens or 0), 1)),
            current_user_message=current_user_message or "",
            history_text=history_text or "",
        )
        llm = self._get_llm()
        response = llm.invoke([
            SystemMessage(content=prompt.get("system", "")),
            HumanMessage(content=prompt.get("user", "")),
        ])
        content = getattr(response, "content", response)
        return self._parse_json_object(content)

    @staticmethod
    def _summary_token_count(
        summary: Dict[str, Any],
        *,
        model_name: str,
    ) -> int:
        return int(estimate_tokens(
            json.dumps(summary, ensure_ascii=False),
            model=model_name or None,
        ))

    def _enforce_summary_budget(
        self,
        *,
        summary: Dict[str, Any],
        agent_id: str,
        model_name: str,
        target_tokens: int,
        current_user_message: str,
    ) -> Dict[str, Any]:
        """超出目标时再做一次结构化收敛，仍超限则显式失败。"""
        safe_target = max(int(target_tokens or 0), 256)
        if self._summary_token_count(summary, model_name=model_name) <= safe_target:
            return summary

        compacted_again = self._compress_once(
            history_text=self._json_dumps(summary),
            agent_id=agent_id,
            model_name=model_name,
            target_tokens=safe_target,
            current_user_message=current_user_message,
        )
        actual_tokens = self._summary_token_count(
            compacted_again,
            model_name=model_name,
        )
        if actual_tokens > safe_target:
            raise ValueError(
                f"上下文摘要超过目标预算：{actual_tokens} > {safe_target} tokens"
            )
        return compacted_again

    def compress_chat_history(
        self,
        *,
        history_items: List[Dict[str, Any]],
        agent_id: str,
        model_name: str,
        target_tokens: int = 8000,
        current_user_message: str = "",
    ) -> Dict[str, Any]:
        """压缩聊天历史，必要时先分块摘要再合并。"""
        material = self._json_dumps(history_items)
        llm = self._get_llm()
        utility_model_name = str(getattr(getattr(llm, "usage", None), "model_name", "") or model_name or "")
        max_context = int(getattr(llm, "max_context_tokens", 0) or 100000)
        max_input_tokens = max(4000, int(max_context * 0.55))

        if estimate_tokens(material, model=utility_model_name or model_name) <= max_input_tokens:
            summary = self._compress_once(
                history_text=material,
                agent_id=agent_id,
                model_name=model_name,
                target_tokens=target_tokens,
                current_user_message=current_user_message,
            )
            return self._enforce_summary_budget(
                summary=summary,
                agent_id=agent_id,
                model_name=utility_model_name or model_name,
                target_tokens=target_tokens,
                current_user_message=current_user_message,
            )

        splitter = TokenTextSplitter(
            chunk_tokens=max_input_tokens,
            min_tokens=1000,
            max_tokens=max(2000, max_input_tokens),
            estimate_model=utility_model_name or model_name or None,
        )
        partials: list[Dict[str, Any]] = []
        for chunk in splitter.split(material):
            partials.append(self._compress_once(
                history_text=chunk.text,
                agent_id=agent_id,
                model_name=model_name,
                target_tokens=max(1200, int(target_tokens / 2)),
                current_user_message=current_user_message,
            ))

        summary = self._compress_once(
            history_text=self._json_dumps(partials),
            agent_id=agent_id,
            model_name=model_name,
            target_tokens=target_tokens,
            current_user_message=current_user_message,
        )
        return self._enforce_summary_budget(
            summary=summary,
            agent_id=agent_id,
            model_name=utility_model_name or model_name,
            target_tokens=target_tokens,
            current_user_message=current_user_message,
        )

    @staticmethod
    def prepare_chat_attachment(
        *,
        user_id: str,
        project_name: str,
        file_path: str,
        filename: str,
        chunk_tokens: int,
        estimate_model: str | None = None,
        max_context_tokens: int | None = None,
    ) -> ChatAttachmentPreparation:
        """聊天附件解析、Token 切分与附件缓存落盘的统一 facade。"""
        from agents.attachment import save_attachment
        from core.file_ingest.service import parse_uploaded_file

        parsed = parse_uploaded_file(file_path, filename, estimate_model)
        total_tokens_estimated = estimate_tokens(parsed.full_text, model=estimate_model)
        normalized_context_limit = max(int(max_context_tokens or 0), 0)
        if normalized_context_limit and total_tokens_estimated > normalized_context_limit:
            raise AttachmentContextWindowExceededError(
                total_tokens=total_tokens_estimated,
                max_context_tokens=normalized_context_limit,
            )

        splitter = TokenTextSplitter(
            chunk_tokens=chunk_tokens,
            tail_merge_threshold_ratio=0.5,
            tail_merge_cap_ratio=1.5,
            estimate_model=estimate_model,
        )
        chunks, chunk_info = splitter.split_with_info(parsed.full_text)
        total_tokens_estimated = int(chunk_info.get("total_tokens_estimated") or total_tokens_estimated)
        from core.project_settings import CHAT_ATTACHMENT_DIRECT_INJECTION_MAX_TOKENS

        is_partial = total_tokens_estimated > CHAT_ATTACHMENT_DIRECT_INJECTION_MAX_TOKENS
        meta = save_attachment(
            user_id=user_id,
            project_name=project_name,
            filename=parsed.filename or filename,
            source_format=parsed.source_format,
            full_text=parsed.full_text,
            chunks=[c.text for c in chunks],
            total_tokens=total_tokens_estimated,
        )
        return ChatAttachmentPreparation(
            parsed=parsed,
            chunks=chunks,
            chunk_info=chunk_info,
            attachment_id=meta.attachment_id,
            chunk_count=len(chunks),
            total_tokens_estimated=total_tokens_estimated,
            is_partial=is_partial,
        )
