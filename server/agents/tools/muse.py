from __future__ import annotations

from typing import Literal

from langchain.tools import tool
from pydantic import BaseModel, Field

from core.request_context import (
    current_inspiration_id,
    current_project_name,
    current_user_id,
    get_current_project_name,
)
from core.project_settings import get_project_story_tags


class CaptureInspirationInput(BaseModel):
    raw_input: str = Field(default="", description="需要扩写并保存的灵感种子；留空时 AI 将自由创作一个原创灵感")
    style: str | None = Field(default=None, description="可选风格，如治愈、悬疑")
    genres: list[str] | None = Field(default=None, description="可选题材标签列表")
    tones: list[str] | None = Field(default=None, description="可选基调标签列表")
    worldviews: list[str] | None = Field(default=None, description="可选世界观标签列表")
    length_hint: str | None = Field(default=None, description="可选作品规模，如短篇、中篇、长篇；有项目上下文时按项目的剧本/小说模式解释")


class RewriteInspirationInput(BaseModel):
    overwrite_content: str = Field(description="完整的灵感正文。调用后将直接覆盖当前已选中的灵感条目内容")


class ListInspirationsInput(BaseModel):
    scope: Literal["project", "drafts", "all"] = Field(
        default="project",
        description=(
            "灵感过滤范围："
            "project=仅当前项目已绑定的灵感（默认，最常用）；"
            "drafts=尚未绑定到任何项目的草稿（用户随手记的、跨项目尚未归档的）；"
            "all=用户全部灵感库（仅在用户明确要求查找历史时使用）"
        ),
    )
    limit: int = Field(
        default=20,
        ge=1,
        le=50,
        description="最多返回多少条灵感，默认 20，最大 50",
    )


class ReadInspirationInput(BaseModel):
    inspiration_id: str = Field(description="目标灵感条目的 id")


class BindInspirationInput(BaseModel):
    inspiration_id: str = Field(description="要绑定到当前项目的灵感条目 id")


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
    project_name = get_current_project_name()
    story_tags = get_project_story_tags(str(user_id), project_name) if project_name else {}
    agent = MuseAgent(user_id)
    context = agent.build_context(
        operation="expand_inspiration",
        raw_input=raw_input,
        style=style,
        genres=genres,
        tones=tones,
        worldviews=worldviews,
        length_hint=length_hint,
        workspace_mode=story_tags.get("workspace_mode"),
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
    """覆盖当前灵感条目或创建新条目；有项目上下文时自动设为项目当前灵感。"""
    from mcp_server.spark_inspiration.logic import (
        activate_inspiration_for_project,
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
        project_name = get_current_project_name()
        if project_name:
            activation = activate_inspiration_for_project(str(user_id), str(inspiration_id), project_name)
            if not activation.get("success"):
                return "已重写灵感内容，但设为当前项目灵感失败。"
            return f"已成功重写灵感，并设为项目「{project_name}」的当前灵感。"
        return "已成功重写当前灵感条目；当前没有项目上下文，保留原绑定状态。"

    source = MuseAgent.generate_source_title(content)
    token = current_user_id.set(str(user_id))
    try:
        result = save_inspiration(source=source, content=content, tags=None, origin="ui")
    finally:
        current_user_id.reset(token)
    if isinstance(result, dict) and result.get("success"):
        new_id = str(result["id"])
        project_name = get_current_project_name()
        if project_name:
            activation = activate_inspiration_for_project(str(user_id), new_id, project_name)
            if not activation.get("success"):
                return f"已创建新灵感条目（ID: {new_id}），但设为当前项目灵感失败。"
            return f"已创建新灵感条目（source: {source}，ID: {new_id}），并设为项目「{project_name}」的当前灵感。"
        return f"已自动创建新灵感草稿（source: {source}，ID: {new_id}）。"
    return f"创建灵感条目失败：{result}"


# ──────────────────────────────────────────────────────────────────────
# 主动检索类工具：list / read / bind
#
# 设计动机：
# - 被动注入侧（context_provider）只塞已绑定到当前项目的灵感，避免草稿污染 prompt；
# - 草稿和跨项目灵感对 LLM 默认不可见，需要靠这三个工具按用户语义主动获取。
# - 例：用户说"把那个梦核校园的灵感加到这个项目"→ list_inspirations(scope=drafts)
#   找到候选 → bind_inspiration_to_current_project(id=...)。
# ──────────────────────────────────────────────────────────────────────


def _format_tags_summary(tags: dict | None) -> str:
    """把灵感的多维标签压缩成一行简短描述，供列表展示。"""
    if not isinstance(tags, dict):
        return ""
    parts: list[str] = []
    for key in ("styles", "genres", "tones", "worldviews", "lengthHint"):
        values = tags.get(key) or []
        if isinstance(values, list) and values:
            parts.append("/".join(str(v) for v in values if v))
    return " · ".join(parts)


def _format_project_links(links: list[str] | None) -> str:
    """把 project_links 压成一段易读的状态说明。"""
    if not links:
        return "草稿（未绑定项目）"
    return f"已绑定到 {len(links)} 个项目：{', '.join(links)}"


@tool(args_schema=ListInspirationsInput)
def list_inspirations(scope: str = "project", limit: int = 20) -> str:
    """列出灵感条目。默认仅返回已绑定到当前项目的灵感；
    
    需要查看用户的草稿（未绑定到任何项目的灵感）时，scope 传 'drafts'；
    需要在用户全部灵感库中检索历史时，scope 传 'all'。
    
    返回紧凑文本列表，每行格式：[id] 来源标题 | 标签摘要 | 绑定状态。
    """
    from mcp_server.spark_inspiration.logic import (
        INSPIRATION_SCOPE_DRAFTS,
        INSPIRATION_SCOPE_PROJECT,
        VALID_INSPIRATION_SCOPES,
        get_all_inspirations,
    )

    user_id = current_user_id.get()
    if not user_id:
        return "查询灵感失败：缺少用户上下文。"

    normalized_scope = (scope or INSPIRATION_SCOPE_PROJECT).strip().lower()
    if normalized_scope not in VALID_INSPIRATION_SCOPES:
        normalized_scope = INSPIRATION_SCOPE_PROJECT

    project_name = current_project_name.get() if normalized_scope == INSPIRATION_SCOPE_PROJECT else None
    if normalized_scope == INSPIRATION_SCOPE_PROJECT and not project_name:
        return (
            "查询灵感失败：当前没有激活的项目，无法按项目维度检索。"
            "如需查看用户全部灵感，请改用 scope='all' 或 scope='drafts'。"
        )

    items = get_all_inspirations(
        str(user_id),
        project_name=project_name,
        scope=normalized_scope,
    )
    if not items:
        if normalized_scope == INSPIRATION_SCOPE_PROJECT:
            return f"当前项目「{project_name}」尚未绑定任何灵感。可向用户确认是否需要查看草稿（scope='drafts'）或全部灵感（scope='all'）。"
        if normalized_scope == INSPIRATION_SCOPE_DRAFTS:
            return "用户暂时没有任何未绑定项目的草稿灵感。"
        return "用户的灵感库为空。"

    capped = items[: max(1, min(int(limit or 20), 50))]
    lines: list[str] = []
    if normalized_scope == INSPIRATION_SCOPE_PROJECT:
        header = f"### 项目「{project_name}」已绑定的灵感（共 {len(items)} 条，展示最近 {len(capped)} 条）"
    elif normalized_scope == INSPIRATION_SCOPE_DRAFTS:
        header = f"### 用户的草稿灵感（共 {len(items)} 条，展示最近 {len(capped)} 条）"
    else:
        header = f"### 用户全部灵感（共 {len(items)} 条，展示最近 {len(capped)} 条）"
    lines.append(header)
    for entry in capped:
        entry_id = str(entry.get("id") or "")
        source = (entry.get("source") or "").strip().splitlines()[0] if entry.get("source") else ""
        title = source[:40] if source else "(空标题)"
        if source and len(source) > 40:
            title += "…"
        timestamp = (entry.get("timestamp") or "")[:10]
        tags_str = _format_tags_summary(entry.get("tags"))
        status_str = _format_project_links(entry.get("project_links"))
        line_parts = [f"- [{entry_id}]"]
        if timestamp:
            line_parts.append(f"({timestamp})")
        line_parts.append(title)
        if tags_str:
            line_parts.append(f"｜标签: {tags_str}")
        line_parts.append(f"｜{status_str}")
        lines.append(" ".join(line_parts))
    lines.append("如需查看正文，请调用 read_inspiration(inspiration_id=...)。")
    return "\n".join(lines)


@tool(args_schema=ReadInspirationInput)
def read_inspiration(inspiration_id: str) -> str:
    """读取指定灵感条目的完整正文，包括 source / content / tags / 已绑定项目。
    
    通常配合 list_inspirations 使用：先列表，再按 id 取详情。
    """
    from mcp_server.spark_inspiration.logic import get_all_inspirations

    user_id = current_user_id.get()
    if not user_id:
        return "读取灵感失败：缺少用户上下文。"
    target_id = (inspiration_id or "").strip()
    if not target_id:
        return "读取灵感失败：inspiration_id 为空。"

    # 没有按 id 直查的接口，扫一遍用户灵感库（量级很小，可忽略）
    items = get_all_inspirations(str(user_id))
    target = next((item for item in items if str(item.get("id")) == target_id), None)
    if not target:
        return f"读取灵感失败：未找到 id={target_id} 的灵感条目。"

    source = (target.get("source") or "").strip()
    content = (target.get("content") or "").strip()
    tags_str = _format_tags_summary(target.get("tags"))
    status_str = _format_project_links(target.get("project_links"))
    timestamp = (target.get("timestamp") or "")[:19]

    sections: list[str] = [f"### 灵感 [{target_id}]"]
    if timestamp:
        sections.append(f"创建时间：{timestamp}")
    sections.append(f"绑定状态：{status_str}")
    if tags_str:
        sections.append(f"标签：{tags_str}")
    if source:
        sections.append(f"### 灵感种子（source）\n{source}")
    if content:
        sections.append(f"### 扩展正文（content）\n{content}")
    elif not source:
        sections.append("（该条灵感的 source 与 content 均为空）")
    return "\n\n".join(sections)


@tool(args_schema=BindInspirationInput)
def bind_inspiration_to_current_project(inspiration_id: str) -> str:
    """把指定灵感条目设为当前项目灵感。
    
    常用场景：用户说"把那个灵感加到这个项目"——你可以先用 list_inspirations(scope='drafts')
    找到候选 id，再调用本工具完成绑定。绑定后该灵感会在下一轮对话中自动进入项目上下文。
    """
    from mcp_server.spark_inspiration.logic import activate_inspiration_for_project

    user_id = current_user_id.get()
    if not user_id:
        return "绑定灵感失败：缺少用户上下文。"
    project_name = current_project_name.get()
    if not project_name:
        return "绑定灵感失败：当前没有激活的项目，请用户先选择目标项目。"
    target_id = (inspiration_id or "").strip()
    if not target_id:
        return "绑定灵感失败：inspiration_id 为空。"

    result = activate_inspiration_for_project(str(user_id), target_id, str(project_name))
    if result.get("success"):
        return f"已将灵感 [{target_id}] 设为项目「{project_name}」的当前灵感。下一轮对话中它会自动出现在项目上下文里。"
    return f"绑定灵感失败：未找到 id={target_id} 的灵感，或操作未生效。"
