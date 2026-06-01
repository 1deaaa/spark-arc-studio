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
            "user_goal": [],
            "current_progress": [],
            "important_facts": [],
            "decisions": [],
            "open_tasks": [],
            "recent_turns": [],
            "tool_results": [],
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
            return self._compress_once(
                history_text=material,
                agent_id=agent_id,
                model_name=model_name,
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

        return self._compress_once(
            history_text=self._json_dumps(partials),
            agent_id=agent_id,
            model_name=model_name,
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
    ) -> ChatAttachmentPreparation:
        """聊天附件解析、Token 切分与附件缓存落盘的统一 facade。"""
        from agents.attachment import save_attachment
        from core.file_ingest.service import parse_uploaded_file

        parsed = parse_uploaded_file(file_path, filename, estimate_model)
        splitter = TokenTextSplitter(
            chunk_tokens=chunk_tokens,
            tail_merge_threshold_ratio=0.5,
            tail_merge_cap_ratio=1.5,
            estimate_model=estimate_model,
        )
        chunks, chunk_info = splitter.split_with_info(parsed.full_text)
        total_tokens_estimated = int(chunk_info.get("total_tokens_estimated") or 0)
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
        )
