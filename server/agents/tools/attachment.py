"""聊天附件分片读取工具

提供导演 Agent "按需滑窗读取附件分片"的能力。

设计动机
--------
聊天附件上传时已经按 64K token 切分并落盘到
``{project}/.attachments/{attachment_id}/chunks/``。
为避免一次性把大附件全部灌进上下文，导演只在需要时通过本工具
按 chunk_index 主动读取下一片。

工具行为
--------
- 命中：返回该 chunk 的文本 + 元信息（第 K / 共 N、是否最后一块）。
- 越界 / 缓存缺失：返回明确的错误说明文本，不抛异常（让模型自然降级）。
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
    """读取指定附件的某一个分片正文。

    适用场景：用户上传的附件被切分成多个分片（partial=True 注入），
    首个分片已注入上下文；当需要继续阅读后续内容时调用本工具。

    每次调用后请先在回复中提炼该分片的关键信息，再决定是否继续读取下一片。
    """
    user_id, project_name = ToolExecutionContext.get_context()

    attachment_id = (attachment_id or "").strip()
    if not attachment_id:
        return "[读取失败] 缺少 attachment_id。"

    try:
        from agents.attachment import (
            AttachmentNotFoundError,
            get_attachment_meta,
            load_chunks,
            touch_last_referenced,
        )
    except Exception as exc:  # 极端情况下 import 失败
        return f"[读取失败] 附件模块加载异常：{exc}"

    meta = get_attachment_meta(user_id, project_name, attachment_id)
    if meta is None:
        return f'[读取失败] 附件 "{attachment_id}" 缓存不存在或已被清理。'

    chunk_count = int(meta.chunk_count or 0)
    if chunk_count <= 0:
        return f'[读取失败] 附件 "{meta.filename}" 没有可用的分片数据。'

    if chunk_index < 0 or chunk_index >= chunk_count:
        return (
            f'[读取失败] 分片下标 {chunk_index} 超出范围。'
            f'附件 "{meta.filename}" 共有 {chunk_count} 个分片，'
            f"合法下标为 0 到 {chunk_count - 1}。"
        )

    try:
        chunks = load_chunks(user_id, project_name, attachment_id)
    except AttachmentNotFoundError:
        return f'[读取失败] 附件 "{meta.filename}" 缓存已失效。'
    except Exception as exc:
        return f'[读取失败] 加载附件 "{meta.filename}" 时出错：{exc}'

    if chunk_index >= len(chunks):
        return (
            f'[读取失败] 附件 "{meta.filename}" 元信息声明 {chunk_count} 个分片，'
            f"但磁盘上仅找到 {len(chunks)} 个文件。请重新上传附件。"
        )

    chunk_text = (chunks[chunk_index] or "").strip()
    if not chunk_text:
        return (
            f'[读取失败] 附件 "{meta.filename}" 第 {chunk_index + 1} 部分内容为空。'
        )

    try:
        touch_last_referenced(user_id, project_name, attachment_id)
    except Exception:
        pass

    is_last = chunk_index == chunk_count - 1
    header = f'【附件 "{meta.filename}" 第 {chunk_index + 1} 部分（共 {chunk_count} 部分）】'
    if is_last:
        footer = "[说明] 这是最后一个分片，附件已完整读取。"
    else:
        next_index = chunk_index + 1
        footer = (
            f"[说明] 这是第 {chunk_index + 1} 部分，剩余 {chunk_count - chunk_index - 1} 部分未读取。"
            f"\n如需继续，请先提炼本分片的关键信息再调用 "
            f'`read_attachment_chunk(attachment_id="{attachment_id}", chunk_index={next_index})`。'
        )

    return f"{header}\n{chunk_text}\n\n{footer}"
