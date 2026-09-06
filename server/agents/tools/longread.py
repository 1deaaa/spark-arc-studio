"""长文档滑窗读取工具（longread 底座的工具面）。

统一收口（AGENTS.md §4.3 工具门面约束）：
- schema 与实现按域落在本文件，注册只在 ``agents/tools/registry.py``，
  对外导出只经 ``agents/agent_tools.py``。
- 附件是第一个接入方：``read_attachment_chunk`` 保留为兼容入口，
  内部转调 ``read_longread_window(source_id=attachment_id)``。
- 世界观是第二个接入方：``read_worldview_window`` 只读
  ``世界观.txt`` 的逻辑切片视图，不复制文件、不双写。

前缀缓存约定：
- 工具返回的窗口正文头部固定携带
  ``[source_id="..." chunk_index=N]`` 指针，供折叠时反查出处；
- 正文只在任务尾部出现一次，折叠后只留线索占位符，不反复改写中间历史。
"""

from __future__ import annotations

from langchain.tools import tool
from pydantic import BaseModel, Field

from .common import ToolExecutionContext


def _window_header(*, source_id: str, chunk_index: int, filename: str, total: int) -> str:
    return (
        f'【长文档窗口 "{filename}" 第 {chunk_index + 1} 部分（共 {total} 部分）】\n'
        f'[source_id="{source_id}" chunk_index={chunk_index}]'
    )


def _window_footer(*, source_id: str, chunk_index: int, total: int, tool_name: str) -> str:
    if chunk_index >= total - 1:
        return "[说明] 这是最后一个窗口，长文档已完整读取。"
    next_index = chunk_index + 1
    call = f'{tool_name}(source_id="{source_id}", chunk_index={next_index})'
    if tool_name == "read_attachment_chunk":
        call = f'read_attachment_chunk(attachment_id="{source_id}", chunk_index={next_index})'
    return (
        f"[说明] 这是第 {chunk_index + 1} 部分，剩余 {total - chunk_index - 1} 部分未读取。\n"
        f"请先调用 `note_window_clues` 记录本窗口的关键线索（人物/伏笔/矛盾/时间"
        f" + 出处原文引用），再决定是否继续：`{call}`。\n"
        "需要回看已读窗口时，直接按账本里的窗口号跳转，不要线性逐片重扫。"
    )


def _read_attachment_window_text(
    user_id: str,
    project_name: str,
    source_id: str,
    chunk_index: int,
) -> tuple[str, str]:
    """返回 (正文块, 错误文本)。成功时错误文本为空。"""
    from agents.attachment import (
        AttachmentNotFoundError,
        get_attachment_meta,
        load_chunks,
        touch_last_referenced,
    )
    from core.project_settings import LONGREAD_MAX_WINDOW_TOKENS
    from llm.agen_matchbox.estimate_tokens import estimate_tokens

    meta = get_attachment_meta(user_id, project_name, source_id)
    if meta is None:
        return "", f'[读取失败] 长文档 "{source_id}" 缓存不存在或已被清理。'
    chunk_count = int(meta.chunk_count or 0)
    if chunk_count <= 0:
        return "", f'[读取失败] 长文档 "{meta.filename}" 没有可用的窗口数据。'
    if chunk_index < 0 or chunk_index >= chunk_count:
        return (
            "",
            f"[读取失败] 窗口下标 {chunk_index} 超出范围。"
            f'长文档 "{meta.filename}" 共有 {chunk_count} 个窗口，'
            f"合法下标为 0 到 {chunk_count - 1}。",
        )
    try:
        chunks = load_chunks(user_id, project_name, source_id)
    except AttachmentNotFoundError:
        return "", f'[读取失败] 长文档 "{meta.filename}" 缓存已失效。'
    except Exception as exc:
        return "", f'[读取失败] 加载长文档 "{meta.filename}" 时出错：{exc}'
    if chunk_index >= len(chunks):
        return (
            "",
            f'[读取失败] 长文档 "{meta.filename}" 元信息声明 {chunk_count} 个窗口，'
            f"但磁盘上仅找到 {len(chunks)} 个文件。请重新上传。",
        )
    chunk_text = (chunks[chunk_index] or "").strip()
    if not chunk_text:
        return "", f'[读取失败] 长文档 "{meta.filename}" 第 {chunk_index + 1} 部分内容为空。'
    if estimate_tokens(chunk_text) > LONGREAD_MAX_WINDOW_TOKENS:
        return (
            "",
            f'[读取失败] 长文档 "{meta.filename}" 第 {chunk_index + 1} 部分超过单窗口上限 '
            f"（{LONGREAD_MAX_WINDOW_TOKENS} tokens），请调小附件分片后重新上传。",
        )
    try:
        touch_last_referenced(user_id, project_name, source_id)
    except Exception:
        pass
    header = _window_header(
        source_id=source_id,
        chunk_index=chunk_index,
        filename=meta.filename,
        total=chunk_count,
    )
    return chunk_text, ""


class ReadLongreadWindowInput(BaseModel):
    source_id: str = Field(description="长文档 source_id（附件即 attachment_id；世界观为 worldview）")
    chunk_index: int = Field(description="要读取的窗口下标，从 0 开始", ge=0)


@tool(args_schema=ReadLongreadWindowInput)
def read_longread_window(source_id: str, chunk_index: int) -> str:
    """读取长文档的某一个窗口正文（通用滑窗入口）。

    适用场景：附件、超长世界观等已切分长文档的按需读取。
    每次调用后请先用 `note_window_clues` 记录本窗口线索，再决定是否继续。
    """
    user_id, project_name = ToolExecutionContext.get_context()
    source_id = (source_id or "").strip()
    if not source_id:
        return "[读取失败] 缺少 source_id。"
    if source_id == "worldview":
        return read_worldview_window.invoke({"chunk_index": chunk_index})
    chunk_text, error = _read_attachment_window_text(user_id, project_name, source_id, chunk_index)
    if error:
        return error
    from agents.attachment import get_attachment_meta

    meta = get_attachment_meta(user_id, project_name, source_id)
    filename = meta.filename if meta else source_id
    total = int(meta.chunk_count) if meta else int(chunk_index + 1)
    header = _window_header(
        source_id=source_id, chunk_index=chunk_index, filename=filename, total=total,
    )
    footer = _window_footer(
        source_id=source_id, chunk_index=chunk_index, total=total,
        tool_name="read_longread_window",
    )
    return f"{header}\n{chunk_text}\n\n{footer}"


class ReadWorldviewWindowInput(BaseModel):
    chunk_index: int = Field(description="要读取的世界观窗口下标，从 0 开始", ge=0)


@tool(args_schema=ReadWorldviewWindowInput)
def read_worldview_window(chunk_index: int) -> str:
    """读取超长世界观的某一个窗口正文。

    世界观未超阈时全文已注入上下文，无需调用本工具；只有上下文里出现
    “世界观地图”时才按窗口号读取。读完先用 `note_window_clues`
    （source_id 固定为 worldview）记录线索。
    """
    from agents.longread import SourceManifest
    from agents.worldview_source import describe_worldview_source

    user_id, project_name = ToolExecutionContext.get_context()
    manifest: SourceManifest | None = describe_worldview_source(user_id, project_name)
    if manifest is None or manifest.chunk_count <= 0:
        return "[读取失败] 当前项目没有可滑窗读取的世界观（可能为空或未超阈）。"
    if chunk_index < 0 or chunk_index >= manifest.chunk_count:
        return (
            f"[读取失败] 窗口下标 {chunk_index} 超出范围。"
            f"世界观共有 {manifest.chunk_count} 个窗口，"
            f"合法下标为 0 到 {manifest.chunk_count - 1}。"
        )
    from agents.worldview_source import read_worldview_window_text

    chunk_text = read_worldview_window_text(user_id, project_name, chunk_index)
    if not (chunk_text or "").strip():
        return f"[读取失败] 世界观第 {chunk_index + 1} 部分内容为空。"
    header = _window_header(
        source_id="worldview",
        chunk_index=chunk_index,
        filename="世界观",
        total=manifest.chunk_count,
    )
    footer = _window_footer(
        source_id="worldview",
        chunk_index=chunk_index,
        total=manifest.chunk_count,
        tool_name="read_worldview_window",
    )
    return f"{header}\n{(chunk_text or '').strip()}\n\n{footer}"


class DescribeLongreadSourceInput(BaseModel):
    source_id: str = Field(description="长文档 source_id（附件即 attachment_id；世界观为 worldview）")


@tool(args_schema=DescribeLongreadSourceInput)
def describe_longread_source(source_id: str) -> str:
    """查看长文档的全局地图（窗口清单），不读取正文。

    开局先看地图再决定读哪几个窗口；禁止无地图线性扫完全部窗口。
    """
    from agents.longread import SourceManifest
    from agents.worldview_source import describe_worldview_source

    user_id, project_name = ToolExecutionContext.get_context()
    source_id = (source_id or "").strip()
    if not source_id:
        return "[读取失败] 缺少 source_id。"
    if source_id == "worldview":
        manifest = describe_worldview_source(user_id, project_name)
        if manifest is None:
            return "[读取失败] 当前项目没有可滑窗读取的世界观。"
        return manifest.render()
    from agents.attachment import get_attachment_meta, load_chunks

    meta = get_attachment_meta(user_id, project_name, source_id)
    if meta is None:
        return f'[读取失败] 长文档 "{source_id}" 缓存不存在或已被清理。'
    try:
        chunks = load_chunks(user_id, project_name, source_id)
    except Exception as exc:
        return f'[读取失败] 加载长文档 "{meta.filename}" 时出错：{exc}'
    entries = tuple(
        (text or "").strip().splitlines()[0][:120] if (text or "").strip() else "(空窗口)"
        for text in chunks
    )
    manifest = SourceManifest(
        source_id=source_id,
        filename=meta.filename,
        chunk_count=int(meta.chunk_count or len(chunks)),
        total_tokens=int(meta.total_tokens or 0),
        entries=entries,
    )
    return manifest.render()


class NoteWindowCluesInput(BaseModel):
    source_id: str = Field(description="长文档 source_id（附件即 attachment_id；世界观为 worldview）")
    chunk_index: int = Field(description="线索所属的窗口下标", ge=0)
    clues: list[str] = Field(description="本窗口的关键线索，每条一句话，须带出处引用")
    clue_type: str = Field(default="note", description="线索类型：人物/伏笔/矛盾/时间/设定/note")
    importance: int = Field(default=3, description="重要度 1-5", ge=1, le=5)


@tool(args_schema=NoteWindowCluesInput)
def note_window_clues(
    source_id: str,
    chunk_index: int,
    clues: list[str],
    clue_type: str = "note",
    importance: int = 3,
) -> str:
    """把刚读完的窗口线索记入账本（只追加，不改写旧行）。

    账本随任务流转、终态落盘，下一轮任务自动恢复；折叠旧窗口时留下的
    占位符会引用这里的线索。读一片记一笔是硬纪律：不记账不得继续滑窗。
    """
    from agents.longread import ClueLedger, WindowClue, ledger_key
    from agents.longread_store import append_ledger_entries, load_task_ledger

    user_id, project_name = ToolExecutionContext.get_context()
    source_id = (source_id or "").strip()
    if not source_id:
        return "[记录失败] 缺少 source_id。"
    items = [str(item or "").strip() for item in (clues or []) if str(item or "").strip()]
    if not items:
        return "[记录失败] clues 为空，至少记录一条线索。"
    ledger = load_task_ledger(user_id, project_name)
    if ledger is None:
        ledger = ClueLedger()
    agent_id = ToolExecutionContext.get_agent_id() or ""
    try:
        for item in items:
            ledger.add(WindowClue(
                source_id=source_id,
                chunk_index=int(chunk_index or 0),
                clue=item,
                evidence=item[:200],
                clue_type=str(clue_type or "note"),
                importance=int(importance or 3),
            ))
    except ValueError as exc:
        return f"[记录失败] {exc}"
    append_ledger_entries(ledger.entries[-len(items):] if items else [])
    return (
        f"已记录 {len(items)} 条线索（{source_id} 窗口{chunk_index}）。"
        f"账本共 {len(ledger.entries)} 条，可继续读取下一窗口或回跳账本中的窗口号。"
        + (f"（agent={agent_id}）" if agent_id else "")
    )
