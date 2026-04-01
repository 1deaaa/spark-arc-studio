"""
Agent Tools - 统一的工具定义模块

使用 LangChain @tool 装饰器定义所有 Agent 可调用的工具。
工具通过 model.bind_tools() 绑定到 LLM，让模型自主决策何时调用。
"""

from __future__ import annotations

import json
import os
import uuid
from typing import Any, Literal

from langchain.tools import tool
from pydantic import BaseModel, Field

from core.request_context import (
    current_user_id,
    current_project_name,
    current_inspiration_id,
    get_current_agent_id,
    get_current_project_name,
)
from core.utils import ensure_project_characters_directory, get_project_path
from agents.communication import (
    HANDOFF_COMPLETION_REPORT_TO_USER,
    HANDOFF_CONFIRMATION_PENDING,
    HANDOFF_DELIVERY_DIRECT_TO_USER,
    normalize_handoff_payload,
)
from story.outline_parser import parse_beat_sheet_markup, parse_outline_markup


# ==================== Tool Input Schemas ====================


class RewriteWorldviewInput(BaseModel):
    """重写世界观的输入参数"""

    overwrite_content: str = Field(
        description="完整的世界观覆盖文本。调用后将直接写入并覆盖世界观文件"
    )


class RewriteAllCharactersInput(BaseModel):
    """重写所有角色的输入参数"""

    overwrite_content: str = Field(
        description='完整的角色覆盖文本。推荐 XML: <character><name>角色名</name><content>角色设定</content></character>；也支持 JSON: {"characters":[{"name":"角色名","content":"角色设定"}]}；或兼容旧的纯文本格式：角色名+空行+角色内容，多个角色用 --- 分隔'
    )


class UpdateCharacterInput(BaseModel):
    """修改单个角色的输入参数"""

    character_name: str = Field(description="要修改的角色名称")
    overwrite_content: str = Field(
        description="该角色的完整覆盖文本。调用后将直接覆盖该角色内容"
    )


class RewriteSynopsisInput(BaseModel):
    """重写梗概的输入参数"""

    overwrite_content: str = Field(description="完整梗概覆盖文本。支持 JSON 或纯文本")


class RewriteBeatSheetInput(BaseModel):
    """重写节拍表的输入参数"""

    overwrite_content: str = Field(description="完整节拍表覆盖文本。支持 JSON 或纯文本")


class RewriteOutlineInput(BaseModel):
    """重写大纲的输入参数"""

    overwrite_content: str = Field(
        description="完整大纲覆盖文本。优先使用 Outline Markup（@title/@summary/##/###）。必须只包含最终可保存的大纲正文，不得混入解释、确认话术、提示词、代码围栏或系统指令"
    )


class CreateOrRewriteScriptInput(BaseModel):
    """新建或重写剧本的输入参数"""

    overwrite_content: str = Field(description="完整的剧本正文（.arc 格式）。若目标场景文件尚不存在，系统将自动创建；若已存在则覆盖。必须只包含最终可保存的剧本正文，不得混入解释、确认话术或元话语。")


class CaptureInspirationInput(BaseModel):
    """捕获并扩写灵感的输入参数"""

    raw_input: str = Field(description="需要扩写并保存的灵感种子")
    style: str | None = Field(default=None, description="可选风格，如治愈、悬疑")
    genres: list[str] | None = Field(default=None, description="可选题材标签列表")
    tones: list[str] | None = Field(default=None, description="可选基调标签列表")
    worldviews: list[str] | None = Field(default=None, description="可选世界观标签列表")
    length_hint: str | None = Field(
        default=None, description="可选篇幅建议，如短篇、中篇、长篇"
    )


class RewriteInspirationInput(BaseModel):
    """重写当前灵感的输入参数"""

    overwrite_content: str = Field(
        description="完整的灵感正文。调用后将直接覆盖当前已选中的灵感条目内容"
    )


class PatchWorldviewInput(BaseModel):
    """局部修改世界观的输入参数"""

    search_text: str = Field(
        description="需要被替换的原文片段（必须精确匹配原文中的连续文字，建议提取完整的1~3句话，不要太短以免误替换）"
    )
    replace_text: str = Field(description="修改后的新文本片段")


class PatchSynopsisInput(BaseModel):
    """局部修改梗概的输入参数"""

    search_text: str = Field(description="需要被替换的原文片段（必须精确匹配原文）")
    replace_text: str = Field(description="修改后的新文本片段")


class PatchBeatSheetInput(BaseModel):
    """局部修改节拍表的输入参数"""

    search_text: str = Field(description="需要被替换的原文片段（必须精确匹配原文）")
    replace_text: str = Field(description="修改后的新文本片段")


class PatchScriptInput(BaseModel):
    """局部修改剧本的输入参数"""

    search_text: str = Field(description="需要被替换的剧本片段（必须精确匹配原文）")
    replace_text: str = Field(description="修改后的新文本片段")


class ReadChapterSceneInput(BaseModel):
    """读取指定章节场景内容的输入参数"""

    chapter_index: int = Field(description="章节索引（从 0 开始）")
    scene_index: int | None = Field(
        default=None,
        description="场景索引（从 0 开始）。不提供则读取整个章节下所有场景",
    )


class ReadCharacterInput(BaseModel):
    character_name: str = Field(description="要查阅的角色名字，例如'张三'")



class DelegateTaskInput(BaseModel):
    """委派任务给专家 Agent 的输入参数"""

    target_agent: str = Field(
        description="目标专家 Agent 的 ID，可选值: agent_scriptwriter, agent_showrunner, agent_lorebook, agent_muse, agent_critic"
    )
    task_description: str = Field(
        description="需要委派给该专家的具体任务描述，应包含足够的上下文信息"
    )
    delivery_mode: str = Field(
        default=HANDOFF_DELIVERY_DIRECT_TO_USER,
        description="交付模式。direct_to_user=专家结果直接交付用户；return_to_director=专家结果回到导演继续复核/汇总"
    )
    completion_mode: str = Field(
        default=HANDOFF_COMPLETION_REPORT_TO_USER,
        description="子任务完成后的即时行为。report_to_user=当前子任务完成后可直接面向用户交付；return_to_director=完成后回导演等待复核/汇总；silent_continue=完成后静默回导演并继续后续流水线，不单独向用户汇报"
    )
    return_to: str = Field(
        default="agent_director",
        description="当需要复核或汇总时，结果应返回给哪个 Agent。默认 agent_director"
    )
    grant_baton_to: str = Field(
        default="",
        description="本次委派后由哪个 Agent 接过旗帜（接力棒）。留空时默认授予 target_agent"
    )
    requires_review: bool = Field(
        default=False,
        description="是否要求专家完成后必须回到导演复核。为 true 时会强制采用 return_to_director"
    )
    user_confirmation_state: str = Field(
        default=HANDOFF_CONFIRMATION_PENDING,
        description="用户确认状态。already_confirmed=上游已确认可直接执行；needs_confirmation=仍需确认；not_required=本任务无需确认"
    )


class GraphRagToolInput(BaseModel):
    """GraphRAG 工具统一输入参数。"""

    action: Literal["build", "query", "status", "reset"] = Field(
        description="操作类型：build=构建索引，query=问答检索，status=查看状态，reset=清空索引"
    )
    question: str | None = Field(
        default=None,
        description="当 action=query 时必填。要询问的自然语言问题。",
    )
    query_mode: Literal["local", "global", "drift"] = Field(
        default="drift",
        description="检索模式：local=实体邻域，global=全局摘要，drift=local+global 混合",
    )
    force_rebuild: bool = Field(
        default=False,
        description="仅 build 时生效。true 表示强制重建。",
    )
    max_hops: int = Field(
        default=2,
        ge=1,
        le=4,
        description="仅 query 时生效。local/drift 模式下的图遍历跳数。",
    )
    max_edges: int = Field(
        default=56,
        ge=12,
        le=120,
        description="仅 query 时生效。返回的最大关系条数。",
    )
    response_mode: Literal["answer", "writing_guardrails"] = Field(
        default="answer",
        description="query 输出模式。answer=普通问答；writing_guardrails=返回写作约束清单",
    )


# ==================== Tool Execution Context ====================


class ToolExecutionContext:
    """
    工具执行上下文，封装 user_id 和 project_name。
    工具函数通过 current_user_id / current_project_name 获取上下文。
    """

    @staticmethod
    def get_context() -> tuple[str, str]:
        """获取当前用户ID和项目名"""
        user_id = current_user_id.get()
        project_name = get_current_project_name()
        if not user_id or not project_name:
            raise RuntimeError("缺少用户或项目上下文，无法执行工具")
        return str(user_id), project_name

    @staticmethod
    def get_agent_id() -> str | None:
        """获取当前触发工具调用的 agent_id。"""
        return get_current_agent_id()


def _parse_json_or_text(content: str) -> Any:
    text = (content or "").strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except Exception:
        return {"content": text}


def _strip_markdown_fence(content: str) -> str:
    text = (content or "").strip()
    if not text.startswith("```"):
        return text

    lines = text.splitlines()
    if len(lines) >= 2 and lines[0].startswith("```") and lines[-1].strip() == "```":
        return "\n".join(lines[1:-1]).strip()
    return text


def _coerce_synopsis_payload(content: str) -> dict | None:
    clean_content = _strip_markdown_fence(content)
    parsed = _parse_json_or_text(clean_content)
    if parsed is None:
        return None
    if isinstance(parsed, dict) and any(
        key in parsed
        for key in ("synopsis_text", "title", "themes", "pacing_guide", "logline")
    ):
        return parsed
    return {
        "synopsis_text": clean_content,
    }


def _coerce_beat_sheet_payload(content: str) -> dict | None:
    clean_content = _strip_markdown_fence(content)
    parsed = _parse_json_or_text(clean_content)
    if parsed is None:
        return None
    if isinstance(parsed, dict) and (
        "beats" in parsed or "global_emotional_arc" in parsed
    ):
        return parsed
    return parse_beat_sheet_markup(clean_content)


def _coerce_outline_payload(content: str) -> dict | None:
    clean_content = _strip_markdown_fence(content)
    parsed = _parse_json_or_text(clean_content)
    if parsed is None:
        return None

    if isinstance(parsed, dict) and (
        "nodes" in parsed or "summary" in parsed or "mainTheme" in parsed
    ):
        outline = parsed
    else:
        source_text = (
            parsed.get("content", clean_content)
            if isinstance(parsed, dict)
            else clean_content
        )
        outline = parse_outline_markup(source_text)

    outline.setdefault("title", "未命名大纲")
    outline.setdefault("summary", "")
    outline.setdefault("mainTheme", "")
    outline.setdefault("nodes", [])
    outline["totalChapters"] = len(outline.get("nodes", []))
    outline["estimatedScenes"] = sum(
        len(ch.get("children", [])) for ch in outline.get("nodes", [])
    )
    return outline


def _normalize_ws(text: str) -> str:
    """将多个连续空白字符（空格/制表符）压缩为单个空格，去除每行行尾空格，统一换行符。
    用于 `_apply_patch` 的模糊空白匹配，使大模型因缩进/行尾空格造成的微小差异不导致匹配失败。
    """
    import re
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # 去除每行行尾空格
    lines = [line.rstrip() for line in text.split("\n")]
    # 压缩行内连续空白
    lines = [re.sub(r"[ \t]+", " ", line) for line in lines]
    # 压缩连续空行（多个空行 -> 最多两个空行）
    result = re.sub(r"\n{3,}", "\n\n", "\n".join(lines))
    return result


def _apply_patch(
    file_path: str,
    search_text: str,
    replace_text: str,
    *,
    validate_json: bool = False,
    file_label: str | None = None,
) -> str:
    """
    通用差异化补丁函数（所有 patch_* 工具的唯一底层实现）。

    匹配策略（优先级从高到低）：
    1. 精确字符串匹配：search_text 原样在文件内容中精确查找，命中则直接替换（性能最好，零损耗）。
    2. 空白容错模糊匹配：若精确匹配失败，对文件内容和 search_text 均先做 _normalize_ws，
       在规范化后的文本中定位，再将原始的等量字节区间替换为 replace_text（容忍大模型的缩进/行尾空格误差）。

    validate_json=True 时，替换完成后校验结果是否仍为合法 JSON，如已损坏则回滚并返回错误信息。

    Returns:
        成功时返回成功提示字符串；失败时返回以 "局部修改失败" 开头的错误字符串（工具规范）。
    """
    import re

    label = file_label or os.path.basename(file_path)

    if not os.path.exists(file_path):
        return f"局部修改失败：文件 '{label}' 不存在。"

    with open(file_path, "r", encoding="utf-8") as f:
        original = f.read()

    # ── 策略 1：精确匹配 ──────────────────────────────────────────────────
    if search_text in original:
        new_content = original.replace(search_text, replace_text, 1)
    else:
        # ── 策略 2：空白容错模糊匹配 ────────────────────────────────────────
        norm_original = _normalize_ws(original)
        norm_search = _normalize_ws(search_text)

        if norm_search not in norm_original:
            return (
                f"局部修改失败：在 '{label}' 中未找到与 search_text 匹配的内容。\n"
                "提示：请确保 search_text 取自原文的完整连续片段（建议 1‑3 句，避免过短导致误替换），"
                "且不包含额外的解释性文字。"
            )

        # 找到规范化文本中的匹配位置，映射回原始文本中的对应位置
        norm_start = norm_original.index(norm_search)
        norm_end = norm_start + len(norm_search)

        # 重新逐字符映射：规范化后的字符位置 -> 原始字符位置
        # 建立 norm_pos -> orig_pos 的映射表
        orig_idx = 0
        norm_idx = 0
        norm_to_orig: dict[int, int] = {}
        norm_text_list = list(norm_original)
        orig_text_list = list(original.replace("\r\n", "\n").replace("\r", "\n"))

        # 逐字符对齐（规范化操作是确定性的，可以同步推进双指针）
        orig_clean = original.replace("\r\n", "\n").replace("\r", "\n")
        # 简化策略：逐行对齐而非逐字符，足够应对行尾空白差异
        orig_lines = orig_clean.split("\n")
        norm_lines = norm_original.split("\n")
        # 建立规范化行号 -> 原始字符偏移量的映射
        orig_line_offsets: list[int] = []
        offset = 0
        for line in orig_lines:
            orig_line_offsets.append(offset)
            offset += len(line) + 1  # +1 for \n

        # 找到 norm_search 在 norm_original 中对应的起止行
        norm_lines_before = norm_original[:norm_start].count("\n")
        norm_lines_in = norm_search.count("\n")
        start_line_idx = norm_lines_before
        end_line_idx = norm_lines_before + norm_lines_in

        if start_line_idx >= len(orig_line_offsets):
            return "局部修改失败：行映射计算超出范围，请缩短 search_text 后重试。"

        orig_char_start = orig_line_offsets[start_line_idx]
        if end_line_idx < len(orig_line_offsets):
            # end_line_idx 行的末尾
            orig_char_end = orig_line_offsets[end_line_idx] + len(orig_lines[end_line_idx])
        else:
            orig_char_end = len(orig_clean)

        new_content = orig_clean[:orig_char_start] + replace_text + orig_clean[orig_char_end:]

    # ── JSON 格式校验（可选）────────────────────────────────────────────────
    if validate_json:
        try:
            json.loads(new_content)
        except Exception as e:
            return (
                f"局部修改失败：替换后破坏了原有的 JSON 格式（{e}）。"
                "请检查 replace_text 的引号、括号和逗号是否完整闭合。"
            )

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(new_content)

    return f"已成功局部更新 '{label}'。"


def _build_muse_tags(
    style: str | None,
    genres: list[str] | None,
    tones: list[str] | None,
    worldviews: list[str] | None,
    length_hint: str | None = None,
) -> dict:
    tags = {
        "styles": [style] if style else [],
        "genres": genres or [],
        "tones": tones or [],
        "worldviews": worldviews or [],
        "lengthHint": [length_hint] if length_hint else [],
    }
    return tags


# ==================== Lorebook Tools ====================


@tool(args_schema=CaptureInspirationInput)
def capture_inspiration(
    raw_input: str,
    style: str | None = None,
    genres: list[str] | None = None,
    tones: list[str] | None = None,
    worldviews: list[str] | None = None,
    length_hint: str | None = None,
) -> str:
    """
    扩写灵感并保存到灵感工坊。
    """
    from agents.setup_agents import MuseAgent
    from agents.agent_utils import collect_text_output

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

    save_result = agent.write_result(
        result,
        user_id=user_id,
        source=raw_input,
        tags=_build_muse_tags(style, genres, tones, worldviews, length_hint),
        origin="ui",
    )
    if isinstance(save_result, dict) and not save_result.get("success", False):
        return f"捕获灵感失败：{save_result.get('error') or save_result}"
    return f"已成功捕获并扩写灵感。\n\n{result}"


@tool(args_schema=RewriteInspirationInput)
def rewrite_inspiration(overwrite_content: str) -> str:
    """
    直接覆盖当前已选中的灵感条目内容。
    """
    from mcp_server.spark_inspiration.logic import update_inspiration

    user_id = current_user_id.get()
    inspiration_id = current_inspiration_id.get()
    content = (overwrite_content or "").strip()

    if not user_id:
        return "重写灵感失败：缺少用户上下文。"
    if not inspiration_id:
        return "重写灵感失败：当前未选中灵感条目，请先在灵感工坊中选择或创建一条灵感。"
    if not content:
        return "重写灵感失败：overwrite_content 为空。"

    success = update_inspiration(
        str(user_id), str(inspiration_id), {"content": content}
    )
    if not success:
        return "重写灵感失败：目标灵感不存在或更新失败。"
    return "已成功重写当前灵感条目。"


@tool(args_schema=RewriteWorldviewInput)
def rewrite_worldview(overwrite_content: str) -> str:
    """
    使用 overwrite_content 中的完整文本覆盖世界观设定。
    """
    import logging

    logger = logging.getLogger("agent_tools")
    logger.info(
        f"[TOOL CALL] rewrite_worldview 被调用, overwrite_content={overwrite_content[:100]}..."
    )

    from agents.agent_lorebook import WorldviewAgent

    user_id, project_name = ToolExecutionContext.get_context()
    agent = WorldviewAgent(int(user_id))
    agent.write_result(
        overwrite_content,
        operation="overwrite_worldview",
        user_id=user_id,
        project_name=project_name,
    )
    return "已使用工具参数中的完整文本覆盖世界观。"


@tool(args_schema=RewriteAllCharactersInput)
def rewrite_all_characters(overwrite_content: str) -> str:
    """
    使用 overwrite_content 中的完整文本覆盖所有角色设定。
    """
    from agents.agent_lorebook import WorldviewAgent

    user_id, project_name = ToolExecutionContext.get_context()
    agent = WorldviewAgent(int(user_id))
    return agent.write_result(
        overwrite_content,
        operation="overwrite_characters",
        user_id=user_id,
        project_name=project_name,
        overwrite_content=overwrite_content,
    )


@tool(args_schema=UpdateCharacterInput)
def update_character(character_name: str, overwrite_content: str) -> str:
    """
    使用 overwrite_content 直接覆盖特定角色设定，不影响其他角色。
    """
    user_id, project_name = ToolExecutionContext.get_context()

    characters_path = ensure_project_characters_directory(user_id, project_name)
    bind_path = os.path.join(characters_path, "chr.bind")

    if not os.path.exists(bind_path):
        return f"未找到角色绑定文件，无法修改角色 '{character_name}'。"

    with open(bind_path, "r", encoding="utf-8") as f:
        mapping = json.load(f) or {}

    char_id = None
    for cid, name in mapping.items():
        if name == character_name:
            char_id = cid
            break

    if char_id is None:
        return f"未找到名为 '{character_name}' 的角色。"

    content = (overwrite_content or "").strip()
    if not content:
        return f"修改角色 '{character_name}' 失败：overwrite_content 为空。"

    char_file = os.path.join(characters_path, f"{char_id}.txt")
    with open(char_file, "w", encoding="utf-8") as f:
        f.write(f"{character_name}\n\n{content}")

    return f"已成功修改角色 '{character_name}' 的设定。"


@tool(args_schema=PatchWorldviewInput)
def patch_worldview(search_text: str, replace_text: str) -> str:
    """通过提供原文片段和新文本片段进行局部修改（不会重写全文），适用于对世界观的小规模调整或纠错。"""
    user_id, project_name = ToolExecutionContext.get_context()
    worldview_path = os.path.join(get_project_path(user_id, project_name), "世界观.txt")
    return _apply_patch(worldview_path, search_text, replace_text, file_label="世界观.txt")


# ==================== Showrunner Tools ====================


@tool(args_schema=RewriteSynopsisInput)
def rewrite_synopsis(overwrite_content: str) -> str:
    """
    直接使用 overwrite_content 覆盖故事梗概。
    """
    from agents.agent_showrunner import ShowrunnerAgent

    user_id, project_name = ToolExecutionContext.get_context()

    content = (overwrite_content or "").strip()
    if not content:
        return "重写梗概失败：overwrite_content 为空。"

    data = _coerce_synopsis_payload(content)
    if data is None:
        return "重写梗概失败：overwrite_content 为空。"

    synopsis_path = os.path.join(get_project_path(user_id, project_name), "synopsis.json")
    existing_data: dict = {}
    if os.path.exists(synopsis_path):
        try:
            with open(synopsis_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                if isinstance(loaded, dict):
                    existing_data = loaded
        except Exception:
            existing_data = {}

    merged_data = dict(existing_data)
    if isinstance(data, dict):
        merged_data.update(data)
    else:
        merged_data["synopsis_text"] = content

    if "synopsis_text" not in merged_data:
        merged_data["synopsis_text"] = content

    agent = ShowrunnerAgent(user_id)
    agent.write_result(
        merged_data,
        operation="synopsis",
        user_id=user_id,
        project_name=project_name,
    )

    return "已成功重写并保存故事梗概。"


@tool(args_schema=RewriteBeatSheetInput)
def rewrite_beat_sheet(overwrite_content: str) -> str:
    """
    直接使用 overwrite_content 覆盖节拍表。
    """
    from agents.agent_showrunner import ShowrunnerAgent

    user_id, project_name = ToolExecutionContext.get_context()

    content = (overwrite_content or "").strip()
    if not content:
        return "重写节拍表失败：overwrite_content 为空。"

    data = _coerce_beat_sheet_payload(content)
    if data is None:
        return "重写节拍表失败：overwrite_content 为空。"

    agent = ShowrunnerAgent(user_id)
    agent.write_result(
        data, operation="beat_sheet", user_id=user_id, project_name=project_name
    )

    return "已成功重写并保存节拍表。"


@tool(args_schema=RewriteOutlineInput)
def rewrite_outline(overwrite_content: str) -> str:
    """
    直接使用 overwrite_content 覆盖故事大纲，内容必须是最终可保存的大纲正文。
    """
    from agents.agent_showrunner import ShowrunnerAgent

    user_id, project_name = ToolExecutionContext.get_context()

    content = (overwrite_content or "").strip()
    if not content:
        return "重写大纲失败：overwrite_content 为空。"

    outline = _coerce_outline_payload(content)
    if outline is None:
        return "重写大纲失败：overwrite_content 为空。"

    agent = ShowrunnerAgent(user_id)
    agent.write_result(
        outline,
        operation="outline",
        user_id=user_id,
        project_name=project_name,
        save_to_project=True,
        save_to_history=False,
    )
    return "已成功重写并保存故事大纲。"


@tool(args_schema=PatchSynopsisInput)
def patch_synopsis(search_text: str, replace_text: str) -> str:
    """通过提供原文片段和新文本片段对梗概进行局部修改，适用于对大纲设定文件的部分语句进行增删改。"""
    user_id, project_name = ToolExecutionContext.get_context()
    synopsis_path = os.path.join(get_project_path(user_id, project_name), "synopsis.json")
    return _apply_patch(synopsis_path, search_text, replace_text, validate_json=True, file_label="synopsis.json")


@tool(args_schema=PatchBeatSheetInput)
def patch_beat_sheet(search_text: str, replace_text: str) -> str:
    """通过提供原文片段和新文本片段对节拍表进行局部修改。"""
    user_id, project_name = ToolExecutionContext.get_context()
    beats_path = os.path.join(get_project_path(user_id, project_name), "beats.json")
    return _apply_patch(beats_path, search_text, replace_text, validate_json=True, file_label="beats.json")


# ==================== Scriptwriter Tools ====================


@tool
def read_worldview() -> str:
    """读取当前项目的完整世界观设定。"""
    user_id, project_name = ToolExecutionContext.get_context()
    from agents.routes.context_builder import load_worldview
    content = load_worldview(user_id, project_name)
    return content if content else "未找到世界观设定。"


@tool(args_schema=ReadCharacterInput)
def read_character(character_name: str) -> str:
    """根据角色名字，读取该角色的完整详细设定档案。"""
    user_id, project_name = ToolExecutionContext.get_context()
    from core.utils import get_project_characters_path
    chars_path = get_project_characters_path(user_id, project_name)
    if not os.path.exists(chars_path):
        return f"未找到角色 {character_name} 的设定档案。"
    for file in os.listdir(chars_path):
        if file.endswith('.txt') and character_name in file:
            with open(os.path.join(chars_path, file), 'r', encoding='utf-8') as f:
                return f.read()
    return f"未找到名字包含 {character_name} 的角色档案。"


@tool
def read_synopsis() -> str:
    """读取当前项目的全局故事梗概（synopsis）。"""
    user_id, project_name = ToolExecutionContext.get_context()
    from core.utils import get_project_stories_path
    synopsis_path = os.path.join(get_project_stories_path(user_id, project_name), "synopsis.json")
    if not os.path.exists(synopsis_path):
        return "未找到故事梗概。"
    with open(synopsis_path, "r", encoding="utf-8") as f:
        return f.read()


@tool
def read_beat_sheet() -> str:
    """读取当前项目的全局情感节拍表（beats）。"""
    user_id, project_name = ToolExecutionContext.get_context()
    from core.utils import get_project_path
    beats_path = os.path.join(get_project_path(user_id, project_name), "beats.json")
    if not os.path.exists(beats_path):
        return "未找到节拍表。"
    with open(beats_path, "r", encoding="utf-8") as f:
        return f.read()

@tool(args_schema=CreateOrRewriteScriptInput)
def create_or_rewrite_script(overwrite_content: str) -> str:
    """
    新建或重写当前场景的剧本文件（.arc 格式）。
    若该场景文件尚不存在，系统将自动创建；若已存在则完全覆盖。
    overwrite_content 必须是最终可直接保存的剧本正文，不得混入任何元话语或解释。
    """
    content = (overwrite_content or "").strip()
    if not content:
        return "创建/重写剧本失败：overwrite_content 为空。"
    return content


@tool(args_schema=PatchScriptInput)
def patch_script(search_text: str, replace_text: str) -> str:
    """找出剧本中的 search_text 并替换为 replace_text。由于剧本分散在多个文件中，该工具将遍历所有 .arc 文件，
    优先精确匹配，其次进行空白容错模糊匹配。"""
    user_id, project_name = ToolExecutionContext.get_context()
    from core.utils import get_project_stories_path

    stories_path = get_project_stories_path(user_id, project_name)
    if not os.path.exists(stories_path):
        return "局部修改剧本失败：stories 目录不存在。"

    # 两轮扫描：第一轮精确匹配，第二轮启用空白容错模糊匹配
    # 优先精确匹配，避免模糊匹配误伤其他文件中的相似片段
    arc_files = sorted(f for f in os.listdir(stories_path) if f.endswith(".arc"))

    for filename in arc_files:
        file_path = os.path.join(stories_path, filename)
        with open(file_path, "r", encoding="utf-8") as f:
            arc_content = f.read()
        if search_text in arc_content:
            # 精确命中：直接调用底层函数（内部会再次精确匹配，保持一致性）
            return _apply_patch(file_path, search_text, replace_text, file_label=filename)

    # 精确匹配全部失败，启用空白容错模糊匹配
    for filename in arc_files:
        file_path = os.path.join(stories_path, filename)
        result = _apply_patch(file_path, search_text, replace_text, file_label=filename)
        if not result.startswith("局部修改失败"):
            return result

    return (
        "局部修改剧本失败：在当前项目所有剧本文件中均未找到与 search_text 匹配的片段。\n"
        "提示：请确保 search_text 取自原文的完整连续片段（建议 1‑3 句），不要包含额外解释性文字。"
    )


# ==================== Shared Tools (Director / Scriptwriter / Critic) ====================


@tool
def list_chapters() -> str:
    """
    列出当前项目的所有章节和场景结构。返回每个章节的索引、标题、场景数量和场景名称列表。
    在读取具体章节内容之前，应先调用此工具了解全局结构。
    """
    user_id, project_name = ToolExecutionContext.get_context()

    outline_path = os.path.join(get_project_path(user_id, project_name), "outline.json")
    if not os.path.exists(outline_path):
        return "当前项目尚无大纲数据（outline.json 不存在）。"

    try:
        with open(outline_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        return f"读取大纲失败: {e}"

    nodes = data.get("nodes", [])
    if not nodes:
        return "大纲中没有章节数据。"

    lines = [f"## 项目大纲：{data.get('title', '未命名')}"]
    summary = data.get("summary", "")
    if summary:
        lines.append(f"概述: {summary}")
    lines.append(f"共 {len(nodes)} 个章节\n")

    for i, node in enumerate(nodes):
        title = node.get("title") or node.get("name") or f"章节{i+1}"
        children = node.get("children", [])
        desc_preview = (node.get("description") or "")[:120]
        lines.append(f"### [{i}] {title}  ({len(children)} 个场景)")
        if desc_preview:
            lines.append(f"  摘要: {desc_preview}...")
        for j, scene in enumerate(children):
            scene_title = scene.get("title") or scene.get("name") or f"场景{j+1}"
            lines.append(f"  - [{i}-{j}] {scene_title}")

    return "\n".join(lines)


@tool(args_schema=ReadChapterSceneInput)
def read_chapter_scene(chapter_index: int, scene_index: int | None = None) -> str:
    """
    读取指定章节（和可选场景）的详细内容，包括大纲描述和已生成的剧本脚本（.arc 文件）。
    chapter_index 从 0 开始。scene_index 从 0 开始，不提供则读取整章所有场景。
    """
    user_id, project_name = ToolExecutionContext.get_context()
    project_path = get_project_path(user_id, project_name)

    # 1. 读取大纲中的章节信息
    outline_path = os.path.join(project_path, "outline.json")
    outline_info = ""
    chapter_node = None
    try:
        if os.path.exists(outline_path):
            with open(outline_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            nodes = data.get("nodes", [])
            if 0 <= chapter_index < len(nodes):
                chapter_node = nodes[chapter_index]
            else:
                return f"章节索引 {chapter_index} 超出范围（共 {len(nodes)} 章）。"
    except Exception as e:
        return f"读取大纲失败: {e}"

    if chapter_node:
        title = chapter_node.get("title") or chapter_node.get("name") or f"章节{chapter_index+1}"
        desc = chapter_node.get("description") or ""
        children = chapter_node.get("children", [])

        parts = [f"## 大纲 - 章节 {chapter_index}: {title}"]
        if desc:
            parts.append(f"章节描述:\n{desc}")

        if scene_index is not None:
            if 0 <= scene_index < len(children):
                scene = children[scene_index]
                scene_title = scene.get("title") or scene.get("name") or f"场景{scene_index+1}"
                scene_desc = scene.get("description") or ""
                parts.append(f"\n### 场景 {chapter_index}-{scene_index}: {scene_title}")
                if scene_desc:
                    parts.append(scene_desc)
            else:
                parts.append(f"\n场景索引 {scene_index} 超出范围（本章共 {len(children)} 个场景）。")
        else:
            for j, scene in enumerate(children):
                scene_title = scene.get("title") or scene.get("name") or f"场景{j+1}"
                scene_desc = scene.get("description") or ""
                parts.append(f"\n### 场景 {chapter_index}-{j}: {scene_title}")
                if scene_desc:
                    parts.append(scene_desc)

        outline_info = "\n".join(parts)

    # 2. 读取对应的 .arc 剧本文件
    from core.utils import get_project_stories_path

    stories_path = get_project_stories_path(user_id, project_name)
    script_info = ""
    if os.path.exists(stories_path):
        arc_files = sorted(
            [f for f in os.listdir(stories_path) if f.endswith(".arc")],
        )
        if 0 <= chapter_index < len(arc_files):
            arc_path = os.path.join(stories_path, arc_files[chapter_index])
            try:
                with open(arc_path, "r", encoding="utf-8") as f:
                    content = f.read()
                if len(content) > 15000:
                    content = content[:15000] + "\n...(内容过长已截断)"
                script_info = f"\n\n## 剧本文件: {arc_files[chapter_index]}\n```arc\n{content}\n```"
            except Exception as e:
                script_info = f"\n\n读取剧本文件失败: {e}"
        else:
            script_info = f"\n\n（该章节尚无对应的 .arc 剧本文件）"

    result = outline_info + script_info
    return result if result.strip() else f"章节 {chapter_index} 没有找到任何内容。"


@tool(args_schema=DelegateTaskInput)
def delegate_task(
    target_agent: str,
    task_description: str,
    delivery_mode: str = HANDOFF_DELIVERY_DIRECT_TO_USER,
    completion_mode: str = HANDOFF_COMPLETION_REPORT_TO_USER,
    return_to: str = "agent_director",
    grant_baton_to: str = "",
    requires_review: bool = False,
    user_confirmation_state: str = HANDOFF_CONFIRMATION_PENDING,
) -> str:
    """
    将一个具体任务委派给指定的专家 Agent 执行。
    导演使用此工具来协调其他 Agent 完成创作任务。
    专家会根据任务描述执行工作并返回结果。
    """
    from agents.communication import get_global_context
    from agents.registry import AGENT_REGISTRY

    user_id = current_user_id.get()
    project_name = get_current_project_name()
    if not user_id:
        return "委派任务失败：缺少用户上下文。"

    # 验证目标 agent 是否存在
    valid_agents = {a["key"] for a in AGENT_REGISTRY if a["key"] != "agent_director"}
    if target_agent not in valid_agents:
        return f"委派任务失败：未知的 Agent '{target_agent}'。可选: {', '.join(sorted(valid_agents))}"

    # 通过信标总线发送任务
    context = get_global_context()

    # 确保目标 agent 已注册并开启信标
    from agents.routes.chat import _create_agent_instance
    target_inst = _create_agent_instance(target_agent, user_id, project_name or "")

    # 注册到通信总线，并确保目标专家在协作视野内可见
    context.register(target_inst)
    target_inst.open_beacon()

    # 构建任务载荷并通过总线分发
    handoff_payload = normalize_handoff_payload(
        {
            "task_id": uuid.uuid4().hex,
            "target_agent": target_agent,
            "task_description": task_description,
            "delivery_mode": delivery_mode,
            "completion_mode": completion_mode,
            "return_to": return_to,
            "grant_baton_to": grant_baton_to,
            "requires_review": requires_review,
            "user_confirmation_state": user_confirmation_state,
            "delegated_by": "agent_director",
            "project_name": project_name,
        },
        sender_id="agent_director",
    )

    try:
        # 改动：在 LangGraph 调度模型中，delegate_task 不再真正调用目标 agent 的 chat()，
        # 因为这会导致目标 agent 的推理流和工具调用被隐藏在“同步黑洞”中。
        # 而是返回一个 Sentinel 字符串，交给外层的 DirectorGraph 拦截，
        # 并路由到 sub_agent_node 去执行 chat_stream()，以暴露完整的内层状态流。

        import json
        payload_str = json.dumps(handoff_payload, ensure_ascii=False)
        return f"__DELEGATE__:{payload_str}"
    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"委派任务给 {target_agent} 失败: {e}"


@tool(args_schema=GraphRagToolInput)
def graph_rag_tool(
    action: Literal["build", "query", "status", "reset"],
    question: str | None = None,
    query_mode: Literal["local", "global", "drift"] = "drift",
    force_rebuild: bool = False,
    max_hops: int = 2,
    max_edges: int = 56,
    response_mode: Literal["answer", "writing_guardrails"] = "answer",
) -> str:
    """
    项目级 GraphRAG 工具：
    - build: 从当前项目文本构建知识图谱索引
    - query: 基于图谱进行 local/global/drift 检索问答
    - status: 查看索引与产物状态
    - reset: 清理当前项目的 GraphRAG 产物

    说明：
    1) 该工具已实现生产化能力，但默认不分配给任何 Agent。
    2) 若要启用，只需把 graph_rag_tool 加入目标 Agent 的工具列表。
    """
    from agents.graphrag import GraphRAGService

    user_id, project_name = ToolExecutionContext.get_context()
    caller_agent_id = ToolExecutionContext.get_agent_id()
    service = GraphRAGService(user_id=user_id, project_name=project_name)

    try:
        if action == "status":
            status = service.get_status()
            meta = status.get("metadata") or {}
            return (
                "GraphRAG 状态\n"
                f"- graph_ready: {status.get('graph_ready')}\n"
                f"- metadata_ready: {status.get('metadata_ready')}\n"
                f"- artifacts_dir: {status.get('artifacts_dir')}\n"
                f"- build_usage_key: {status.get('build_usage_key')}\n"
                f"- query_agent_policy: {status.get('query_agent_policy')}\n"
                f"- nodes: {meta.get('nodes', 0)}\n"
                f"- edges: {meta.get('edges', 0)}\n"
                f"- chunks: {meta.get('chunks', 0)}\n"
                f"- triplets: {meta.get('triplets', 0)}\n"
                f"- built_at: {meta.get('built_at', '-') }"
            )

        if action == "build":
            info = service.build_index(force_rebuild=force_rebuild)
            return (
                "GraphRAG 构建完成\n"
                f"- reused: {info.get('reused')}\n"
                f"- nodes: {info.get('nodes', 0)}\n"
                f"- edges: {info.get('edges', 0)}\n"
                f"- chunks: {info.get('chunks', 0)}\n"
                f"- triplets: {info.get('triplets', 0)}\n"
                f"- build_usage_key: {info.get('build_usage_key', '-') }\n"
                f"- query_agent_policy: {info.get('query_agent_policy', '-') }\n"
                f"- built_at: {info.get('built_at', '-') }"
            )

        if action == "reset":
            result = service.reset()
            return (
                "GraphRAG 已清理\n"
                f"- removed: {result.get('removed')}\n"
                f"- artifacts_dir: {result.get('artifacts_dir')}"
            )

        if not question or not question.strip():
            return "GraphRAG 查询失败：action=query 时 question 不能为空。"

        payload = service.query(
            question=question,
            query_agent_name=caller_agent_id,
            query_mode=query_mode,
            max_hops=max_hops,
            max_edges=max_edges,
        )
        matched = payload.get("matched_entities") or []
        entities_line = ", ".join(matched) if matched else "(无)"

        if response_mode == "writing_guardrails":
            constraints = payload.get("fact_constraints") or {}
            must_keep = constraints.get("must_keep") or []
            avoid_conflicts = constraints.get("avoid_conflicts") or []
            unresolved = constraints.get("unresolved") or []

            lines = [
                "GraphRAG 写作约束",
                f"- mode: {payload.get('mode')}",
                f"- matched_entities: {entities_line}",
                "",
                "[必须保持事实]",
            ]
            if must_keep:
                lines.extend([f"- {item}" for item in must_keep])
            else:
                lines.append("- (暂无)")

            lines.append("\n[避免冲突]")
            if avoid_conflicts:
                lines.extend([f"- {item}" for item in avoid_conflicts])
            else:
                lines.append("- (暂无)")

            lines.append("\n[待补充信息]")
            if unresolved:
                lines.extend([f"- {item}" for item in unresolved])
            else:
                lines.append("- (暂无)")

            return "\n".join(lines)

        return (
            "GraphRAG 查询结果\n"
            f"- mode: {payload.get('mode')}\n"
            f"- matched_entities: {entities_line}\n\n"
            f"{payload.get('answer') or '未生成回答。'}"
        )
    except Exception as e:
        return f"GraphRAG 工具执行失败：{e}"


# ==================== Tool Registry ====================

MCP_ONLY_TOOLS = [capture_inspiration]
MUSE_TOOLS = [rewrite_inspiration]
LOREBOOK_TOOLS = [
    rewrite_worldview,
    rewrite_all_characters,
    update_character,
    patch_worldview,
]
SHOWRUNNER_TOOLS = [
    rewrite_synopsis,
    rewrite_beat_sheet,
    rewrite_outline,
    patch_synopsis,
    patch_beat_sheet,
]
SCRIPTWRITER_TOOLS = [create_or_rewrite_script, patch_script, read_worldview, read_character, read_synopsis, read_beat_sheet]
# SHARED_READ_TOOLS 中的 list_chapters / read_chapter_scene 由三种模式差异化授权：
# - 模式一（手动 Compose）：无工具，纯生成调用。
# - 模式二（Auto-Write Pre-flight）：仅授予 SHARED_READ_TOOLS（list_chapters + read_chapter_scene）。
#   注意：全量世界观、角色档案、梗概、节拍表在循环启动前已全量注入 Prompt，无需再配读取工具；
#   但远端任意章节的具体场景原文无法预先全量载入（会导致上下文爆炸），因此仅开放这两个工具供按需懒加载。
# - 模式三（Chat / 导演委派）：SCRIPTWRITER_TOOLS + SHARED_READ_TOOLS 全部开放。
SHARED_READ_TOOLS = [list_chapters, read_chapter_scene]

DIRECTOR_TOOLS = SHARED_READ_TOOLS + [delegate_task]

# 已生产化但默认不挂载到任何 Agent，便于按需灰度启用。
OPTIONAL_RESEARCH_TOOLS = [graph_rag_tool]

ALL_TOOLS = MUSE_TOOLS + LOREBOOK_TOOLS + SHOWRUNNER_TOOLS + SCRIPTWRITER_TOOLS + SHARED_READ_TOOLS + [delegate_task] + OPTIONAL_RESEARCH_TOOLS
TOOLS_BY_NAME = {tool.name: tool for tool in ALL_TOOLS}


def get_tools_for_agent(agent_id: str) -> list:
    """根据 Agent ID 返回对应的工具列表"""
    tool_map = {
        "agent_muse": MUSE_TOOLS,
        "agent_lorebook": LOREBOOK_TOOLS,
        "agent_showrunner": SHOWRUNNER_TOOLS,
        "agent_scriptwriter": SCRIPTWRITER_TOOLS + SHARED_READ_TOOLS,
        "agent_director": DIRECTOR_TOOLS,
        "agent_critic": SHARED_READ_TOOLS,
    }
    return tool_map.get(agent_id, [])
