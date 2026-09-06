"""
长文档统一滑窗底座（longread）
=============================

地位
----
聊天附件（``agents.attachment``）、超长世界观、超长大纲/角色聚合…
凡是“全文可能超过单次注入预算、需要分片+按需读取”的长文本，
统一接到这一层。切分仍复用既有基建：

- 粗切分：``core.file_ingest.chunking.TokenTextSplitter``
- 附件落盘：``agents.attachment.storage``

本模块只新增四样东西，不重复造切分器/存储：

1. ``SourceManifest``：不可变的全局地图（总数 + 每片标题行/token 数）。
   任务期间字节级稳定，是 Agent 回跳的依据，也是前缀缓存稳定的前提。
2. ``WindowClue`` / ``ClueLedger``：单调追加的线索账本。Agent 每读一片
   必须记一笔，折叠旧窗口时留下的是“线索 + 回跳指针”，而不是一句废话。
3. ``collapse_longread_tool_history``：带线索的折叠。只在“尾部变前缀”
   的那一刻做，不在任务中途反复改写中间历史，避免前缀缓存大面积失效。
4. ``LedgerStore``：账本落盘。账本随消息流转（内存态，零 IO 热路径），
   只在任务终态时一次性落盘到 ``{source}/.longread_ledger/{key}.json``；
   下一轮任务从落盘恢复，实现跨轮“找齐线索”。

前缀缓存布局约定（调用方必须遵守）
-----------------------------------
``system（稳定）+ manifest（稳定）+ ledger（只追加）+ 当前窗口（一片，尾部）
+ 本轮用户请求（最尾）``。

collapse 的输入是内存中的 LangChain messages，输出是“旧窗口 ToolMessage
原位替换成短占位符”。占位符只包含出处与线索摘要，不包含正文。替换只在
“尾部变前缀”（任务终态落盘 / 持久化前）发生一次；同一 user 任务的内存
消息链在任务进行中只追加、不改写中间历史。
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
from dataclasses import dataclass, field
from typing import Any, Sequence

from core.json_state import load_json_file, save_json_file_atomic
from core.utils import get_project_path


LONGREAD_TOOL_NAMES = frozenset({
    "read_attachment_chunk",
    "read_longread_window",
    "read_worldview_window",
})

LONGREAD_FALLBACK_PLACEHOLDER = (
    "[长文档窗口已折叠 - 原文已移出当前窗口；如需重新阅读请再次调用读取工具]"
)

LEDGER_DIR_NAME = ".longread_ledger"
LEDGER_FILENAME_FMT = "{key}.json"


def _clip(value: Any, limit: int) -> str:
    text = str(value or "").strip().replace("\r\n", "\n")
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def ledger_key(user_id: str, project_name: str, agent_id: str, context_key: str) -> str:
    """账本落盘 key：按房间隔离，避免跨会话串线索。"""
    raw = f"{user_id}:{project_name}:{agent_id}:{context_key or 'global'}"
    return hashlib.sha256(raw.encode("utf-8", errors="ignore")).hexdigest()[:16]


@dataclass(slots=True)
class SourceManifest:
    """长文档全局地图。生成后不可变，任务期间保持字节级稳定。"""

    source_id: str
    filename: str
    chunk_count: int
    total_tokens: int
    chunk_tokens: int = 0
    entries: tuple[str, ...] = ()

    def render(self) -> str:
        lines = [
            f"【长文档地图：{self.filename}】",
            f"- source_id={self.source_id}，共 {self.chunk_count} 个窗口，"
            f"约 {self.total_tokens} tokens",
        ]
        for index, entry in enumerate(self.entries):
            lines.append(f"- 窗口 {index}：{_clip(entry, 120)}")
        lines.append(
            "需要阅读时调用读取工具并指定窗口号；读完先记录线索再决定下一步。"
        )
        return "\n".join(lines)


@dataclass(slots=True)
class WindowClue:
    """单条线索。出处三元组（source_id/chunk_index/原文引用）必填。"""

    source_id: str
    chunk_index: int
    clue: str
    evidence: str = ""
    clue_type: str = "note"
    importance: int = 3


@dataclass
class ClueLedger:
    """单调追加的线索账本。只 append，不改旧行。"""

    entries: list[WindowClue] = field(default_factory=list)
    max_entries: int = 64

    def add(self, clue: WindowClue) -> WindowClue:
        cleaned = WindowClue(
            source_id=str(clue.source_id or "").strip(),
            chunk_index=int(clue.chunk_index or 0),
            clue=_clip(clue.clue, 500),
            evidence=_clip(clue.evidence, 500),
            clue_type=str(clue.clue_type or "note").strip() or "note",
            importance=max(1, min(5, int(clue.importance or 3))),
        )
        if not cleaned.source_id or not cleaned.clue:
            raise ValueError("线索缺少 source_id 或正文")
        self.entries.append(cleaned)
        overflow = len(self.entries) - max(1, int(self.max_entries or 64))
        if overflow > 0:
            del self.entries[:overflow]
        return cleaned

    def render(self) -> str:
        if not self.entries:
            return "【线索账本】暂无记录。"
        lines = ["【线索账本】（只追加，不改写旧行）"]
        for number, item in enumerate(self.entries, start=1):
            lines.append(
                f"{number}. [{item.source_id} 窗口{item.chunk_index}]"
                f"（{item.clue_type}/重要度{item.importance}）{item.clue}"
            )
            if item.evidence:
                lines.append(f"   出处：{item.evidence}")
        return "\n".join(lines)


def build_window_placeholder(
    *,
    source_id: str,
    chunk_index: int,
    filename: str = "",
    clues: Sequence[WindowClue] | None = None,
) -> str:
    """构造带线索的折叠占位符：出处 + 线索摘要 + 回跳指针。"""
    matched = [
        item for item in (clues or [])
        if str(item.source_id) == str(source_id)
        and int(item.chunk_index) == int(chunk_index)
    ]
    label = filename or str(source_id)
    lines = [f"[长文档窗口已折叠：{label} 第 {int(chunk_index) + 1} 部分]"]
    if matched:
        lines.append("本窗口已记录线索：")
        for item in matched[:3]:
            lines.append(f"- {item.clue}")
            if item.evidence:
                lines.append(f"  出处：{item.evidence}")
    else:
        lines.append("本窗口暂无线索记录；需要时可按窗口号重读。")
    lines.append(
        f"如需重新阅读请再次调用读取工具（source_id=\"{source_id}\", "
        f"chunk_index={int(chunk_index)}）。"
    )
    return "\n".join(lines)


def _tool_message_name(message: Any) -> str:
    return str(getattr(message, "name", "") or "")


def _tool_message_call_id(message: Any) -> str:
    return str(getattr(message, "tool_call_id", "") or "")


def collapse_longread_tool_history(
    messages: list,
    *,
    fresh_call_ids: set[str] | None = None,
    ledger: ClueLedger | None = None,
) -> int:
    """折叠旧 user 轮次的长读取窗口，保留当前轮次内的全部原文。

    与旧 ``collapse_long_read_tool_history`` 的区别：占位符携带该窗口的
    线索摘要与回跳指针；调用方应在折叠前把线索写入 ``ledger`` 并传入，
    否则退化为通用占位符。
    """
    from langchain_core.messages import HumanMessage as _HumanMessage
    from langchain_core.messages import ToolMessage as _ToolMessage

    fresh = fresh_call_ids or set()
    current_user_index = -1
    for index in range(len(messages) - 1, -1, -1):
        if isinstance(messages[index], _HumanMessage):
            current_user_index = index
            break

    collapsed = 0
    ledger_entries = list(ledger.entries) if ledger is not None else []
    for i, message in enumerate(messages):
        if not isinstance(message, _ToolMessage):
            continue
        if _tool_message_name(message) not in LONGREAD_TOOL_NAMES:
            continue
        if (
            (current_user_index >= 0 and i > current_user_index)
            or _tool_message_call_id(message) in fresh
        ):
            continue
        content = str(message.content or "")
        if content.startswith("[长文档窗口已折叠"):
            continue
        source_id, chunk_index = _parse_window_pointer(content)
        placeholder = build_window_placeholder(
            source_id=source_id or str(_tool_message_name(message)),
            chunk_index=chunk_index,
            clues=ledger_entries,
        )
        messages[i] = _ToolMessage(
            content=placeholder,
            tool_call_id=message.tool_call_id,
            name=message.name,
        )
        collapsed += 1
    return collapsed


def _parse_window_pointer(content: str) -> tuple[str, int]:
    """从窗口正文头部反查 source_id 与 chunk_index，失败返回空。"""
    import re

    text = str(content or "")
    match = re.search(
        r"\[source_id=\"(?P<source>[^\"]+)\"\s+chunk_index=(?P<index>\d+)\]",
        text,
    )
    if not match:
        return "", 0
    try:
        return match.group("source"), max(0, int(match.group("index")))
    except (TypeError, ValueError):
        return "", 0


class LedgerStore:
    """线索账本落盘：按房间 key 隔离，任务终态一次性写，下一轮恢复。

    热路径零 IO：任务进行中账本只活在 ``ClueLedger`` 内存对象里，随
    ``conversation_recorder`` / 任务终态回调流转；只有任务结束时调用
    一次 ``save``，下一轮任务开始时调用一次 ``load``。
    """

    _lock = threading.Lock()

    @classmethod
    def _ledger_path(cls, user_id: str, project_name: str, key: str) -> str:
        project_path = get_project_path(str(user_id), str(project_name))
        return os.path.join(project_path, LEDGER_DIR_NAME, LEDGER_FILENAME_FMT.format(key=key))

    @classmethod
    def load(
        cls,
        user_id: str,
        project_name: str,
        key: str,
        *,
        max_entries: int = 64,
    ) -> ClueLedger:
        path = cls._ledger_path(user_id, project_name, key)
        data = load_json_file(path, dict)
        ledger = ClueLedger(max_entries=max(1, int(max_entries or 64)))
        entries = data.get("entries") if isinstance(data, dict) else None
        if not isinstance(entries, list):
            return ledger
        for item in entries:
            if not isinstance(item, dict):
                continue
            try:
                ledger.entries.append(WindowClue(
                    source_id=str(item.get("source_id") or ""),
                    chunk_index=int(item.get("chunk_index") or 0),
                    clue=str(item.get("clue") or ""),
                    evidence=str(item.get("evidence") or ""),
                    clue_type=str(item.get("clue_type") or "note"),
                    importance=int(item.get("importance") or 3),
                ))
            except (TypeError, ValueError):
                continue
        overflow = len(ledger.entries) - ledger.max_entries
        if overflow > 0:
            del ledger.entries[:overflow]
        return ledger

    @classmethod
    def save(
        cls,
        user_id: str,
        project_name: str,
        key: str,
        ledger: ClueLedger | None,
    ) -> None:
        if ledger is None or not ledger.entries:
            return
        path = cls._ledger_path(user_id, project_name, key)
        payload = {
            "key": str(key),
            "entries": [
                {
                    "source_id": item.source_id,
                    "chunk_index": int(item.chunk_index),
                    "clue": item.clue,
                    "evidence": item.evidence,
                    "clue_type": item.clue_type,
                    "importance": int(item.importance),
                }
                for item in ledger.entries
            ],
        }
        with cls._lock:
            try:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                save_json_file_atomic(path, payload)
            except Exception:
                pass

    @classmethod
    def snapshot(cls, ledger: ClueLedger | None) -> dict:
        if ledger is None:
            return {"entries": []}
        return {
            "entries": [
                {
                    "source_id": item.source_id,
                    "chunk_index": int(item.chunk_index),
                    "clue": item.clue,
                    "evidence": item.evidence,
                    "clue_type": item.clue_type,
                    "importance": int(item.importance),
                }
                for item in ledger.entries
            ],
        }

    @classmethod
    def restore(cls, payload: Any, *, max_entries: int = 64) -> ClueLedger:
        ledger = ClueLedger(max_entries=max(1, int(max_entries or 64)))
        entries = payload.get("entries") if isinstance(payload, dict) else None
        if not isinstance(entries, list):
            return ledger
        for item in entries:
            if not isinstance(item, dict):
                continue
            try:
                ledger.entries.append(WindowClue(
                    source_id=str(item.get("source_id") or ""),
                    chunk_index=int(item.get("chunk_index") or 0),
                    clue=str(item.get("clue") or ""),
                    evidence=str(item.get("evidence") or ""),
                    clue_type=str(item.get("clue_type") or "note"),
                    importance=int(item.get("importance") or 3),
                ))
            except (TypeError, ValueError):
                continue
        return ledger


__all__ = [
    "LONGREAD_TOOL_NAMES",
    "LONGREAD_FALLBACK_PLACEHOLDER",
    "LEDGER_DIR_NAME",
    "SourceManifest",
    "WindowClue",
    "ClueLedger",
    "LedgerStore",
    "build_window_placeholder",
    "collapse_longread_tool_history",
    "ledger_key",
]
