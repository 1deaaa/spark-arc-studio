from __future__ import annotations

from langchain.tools import tool
from pydantic import BaseModel, Field

from core.request_context import current_inspiration_id, current_user_id


class CaptureInspirationInput(BaseModel):
    raw_input: str = Field(default="", description="需要扩写并保存的灵感种子；留空时 AI 将自由创作一个原创灵感")
    style: str | None = Field(default=None, description="可选风格，如治愈、悬疑")
    genres: list[str] | None = Field(default=None, description="可选题材标签列表")
    tones: list[str] | None = Field(default=None, description="可选基调标签列表")
    worldviews: list[str] | None = Field(default=None, description="可选世界观标签列表")
    length_hint: str | None = Field(default=None, description="可选篇幅建议，如短篇、中篇、长篇")


class RewriteInspirationInput(BaseModel):
    overwrite_content: str = Field(description="完整的灵感正文。调用后将直接覆盖当前已选中的灵感条目内容")


def _build_muse_tags(
    style: str | None,
    genres: list[str] | None,
    tones: list[str] | None,
    worldviews: list[str] | None,
    length_hint: str | None = None,
) -> dict:
    return {
        "styles": [style] if style else [],
        "genres": genres or [],
        "tones": tones or [],
        "worldviews": worldviews or [],
        "lengthHint": [length_hint] if length_hint else [],
    }


@tool(args_schema=CaptureInspirationInput)
def capture_inspiration(
    raw_input: str,
    style: str | None = None,
    genres: list[str] | None = None,
    tones: list[str] | None = None,
    worldviews: list[str] | None = None,
    length_hint: str | None = None,
) -> str:
    """扩写并保存灵感内容。"""
    from agents.agent_utils import collect_text_output
    from agents.setup_agents import MuseAgent

    user_id = current_user_id.get()
    if not user_id:
        return "捕获灵感失败：缺少用户上下文。"
    agent = MuseAgent(user_id)
    context = agent.build_context(
        operation="expand_inspiration",
        raw_input=raw_input,
        style=style,
        genres=genres,
        tones=tones,
        worldviews=worldviews,
        length_hint=length_hint,
    )
    result = collect_text_output(agent.execute(context))
    if not result:
        return "捕获灵感失败：生成结果为空。"

    source = raw_input if raw_input.strip() else agent.generate_source_title(result)
    save_result = agent.write_result(
        result,
        user_id=user_id,
        source=source,
        tags=_build_muse_tags(style, genres, tones, worldviews, length_hint),
        origin="ui",
    )
    if isinstance(save_result, dict) and not save_result.get("success", False):
        return f"捕获灵感失败：{save_result.get('error') or save_result}"
    return f"已成功捕获并扩写灵感。\n\n{result}"


@tool(args_schema=RewriteInspirationInput)
def rewrite_inspiration(overwrite_content: str) -> str:
    """覆盖当前灵感条目或创建新的灵感条目。"""
    from mcp_server.spark_inspiration.logic import (
        current_user_id as mcp_uid_var,
        save_inspiration,
        update_inspiration,
    )
    from agents.setup_agents import MuseAgent

    user_id = current_user_id.get()
    inspiration_id = current_inspiration_id.get()
    content = (overwrite_content or "").strip()

    if not user_id:
        return "写入灵感失败：缺少用户上下文。"
    if not content:
        return "写入灵感失败：overwrite_content 为空。"

    if inspiration_id:
        success = update_inspiration(str(user_id), str(inspiration_id), {"content": content})
        if not success:
            return "重写灵感失败：目标灵感不存在或更新失败。"
        return "已成功重写当前灵感条目。"

    source = MuseAgent.generate_source_title(content)
    token = mcp_uid_var.set(str(user_id))
    try:
        result = save_inspiration(source=source, content=content, tags=None, origin="ui")
    finally:
        mcp_uid_var.reset(token)
    if isinstance(result, dict) and result.get("success"):
        return f"已自动创建新灵感条目（source: {source}，ID: {result['id']}）。"
    return f"创建灵感条目失败：{result}"
