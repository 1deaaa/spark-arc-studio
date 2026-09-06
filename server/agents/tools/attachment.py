"""聊天附件分片读取工具（兼容入口）

统一收口：实现已迁移至 ``agents.tools.longread.read_longread_window``，
本工具保留参数形状（``attachment_id`` / ``chunk_index``）供历史 prompt、
历史测试与 MCP 白名单引用，内部直接转调 longread 通用窗口读取。
"""

from __future__ import annotations

from langchain.tools import tool
from pydantic import BaseModel, Field

from .common import ToolExecutionContext


class ReadAttachmentChunkInput(BaseModel):
    attachment_id: str = Field(
        description="附件 ID（即上传成功后写入 importedFiles[].attachmentId 的字符串）"
    )
    chunk_index: int = Field(
        description="要读取的分片下标，从 0 开始。0 表示首个分片，1 表示第二个分片，依此类推。",
        ge=0,
    )


@tool(args_schema=ReadAttachmentChunkInput)
def read_attachment_chunk(attachment_id: str, chunk_index: int) -> str:
    """读取指定附件的某一个分片正文（兼容入口，内部转调滑窗底座）。

    适用场景：用户上传的附件被切分成多个分片（partial=True 注入），
    首个分片已注入上下文；当需要继续阅读后续内容时调用本工具。

    每次调用后请先用 `note_window_clues` 记录该分片的关键线索，
    再决定是否继续读取下一片。
    """
    from agents.tools.longread import _read_attachment_window_text

    user_id, project_name = ToolExecutionContext.get_context()

    attachment_id = (attachment_id or "").strip()
    if not attachment_id:
        return "[读取失败] 缺少 attachment_id。"

    chunk_text, error = _read_attachment_window_text(
        user_id, project_name, attachment_id, chunk_index,
    )
    if error:
        return error

    from agents.attachment import get_attachment_meta

    meta = get_attachment_meta(user_id, project_name, attachment_id)
    filename = meta.filename if meta else attachment_id
    chunk_count = int(meta.chunk_count) if meta else int(chunk_index + 1)
    header = (
        f'【附件 "{filename}" 第 {chunk_index + 1} 部分（共 {chunk_count} 部分）】\n'
        f'[source_id="{attachment_id}" chunk_index={chunk_index}]'
    )
    if chunk_index >= chunk_count - 1:
        footer = "[说明] 这是最后一个分片，附件已完整读取。"
    else:
        next_index = chunk_index + 1
        footer = (
            f"[说明] 这是第 {chunk_index + 1} 部分，剩余 {chunk_count - chunk_index - 1} 部分未读取。\n"
            f"请先调用 `note_window_clues` 记录本分片的关键线索，再决定是否继续："
            f'`read_attachment_chunk(attachment_id="{attachment_id}", chunk_index={next_index})`。'
        )

    return f"{header}\n{chunk_text}\n\n{footer}"
