"""
Agent Tools - 统一的工具定义模块

使用 LangChain @tool 装饰器定义所有 Agent 可调用的工具。
工具通过 model.bind_tools() 绑定到 LLM，让模型自主决策何时调用。
"""

from __future__ import annotations

import json
import os
import re
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

    overwrite_content: str = Field(description="完整的剧本/小说正文。若目标场景文件尚不存在，系统将自动创建；若已存在则覆盖。必须只包含最终可保存的正文，不得混入解释、确认话术或元话语。")
    chapter_name: str | None = Field(
        default=None,
        description="目标章节名称（即文件夹名称）。若提供，剧本将保存到该章节目录下；若不提供，则保存到 stories 根目录。创建剧本前应先调用 create_chapter 确保章节存在。"
    )
    work_name: str | None = Field(
        default=None,
        description="剧本文件的显示名称（不含扩展名）。若不提供，系统将自动根据内容或上下文命名。"
    )
    export_format: str | None = Field(
        default=None,
        description="输出格式：'arc' 为互动剧本（默认），'novel' 为纯文学小说。决定文件扩展名与格式规范。"
    )


class CreateChapterInput(BaseModel):
    """创建章节（文件夹）的输入参数"""

    chapter_name: str = Field(description="章节名称，将作为 stories 目录下的子文件夹名称。建议格式如「第一章_开端」或「第01章_相遇」。")


class CaptureInspirationInput(BaseModel):
    """捕获并扩写灵感的输入参数"""

    raw_input: str = Field(default="", description="需要扩写并保存的灵感种子；留空时 AI 将自由创作一个原创灵感")
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


class PatchOutlineInput(BaseModel):
    """局部修改大纲的输入参数"""

    search_text: str = Field(description="需要被替换的原文片段（必须精确匹配原文中的连续文字，建议提取完整的1~3句话）")
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


class ReadChapterOutlineRawInput(BaseModel):
    """读取大纲原始文本的输入参数"""

    chapter_index: int = Field(description="章节索引（从 0 开始），对应大纲.txt中 ## Chapter 的顺序")


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


class TriggerAutoWriteInput(BaseModel):
    """触发自动化批量写作的输入参数"""

    start_chapter: int = Field(
        default=1,
        description="从第几章开始写作（1=第一章）。若要续写未完成的任务，请基于已完成章节向后推算"
    )
    start_scene: int = Field(
        default=1,
        description="在起始章内从第几个场景开始写作（1=该章第一个场景）。仅对起始章有效，后续章节总是从第 1 个场景开始"
    )
    export_format: str = Field(
        default="arc",
        description="输出格式：arc=互动小说剧本格式；novel=普通小说纯文本格式"
    )
    mode: str = Field(
        default="continuous_write",
        description="写作模式：continuous_write=连续写作全部章节（无人值守直达结束）；chapter_by_chapter=逐章写作（写完一章后暂停断开）"
    )


class WorkTrackerInput(BaseModel):
    """工作追踪工具的输入参数"""

    action: Literal["read", "update", "clear"] = Field(
        description="操作类型：read=读取当前任务列表；update=覆盖更新任务列表（可同时更新 summary）；clear=清空所有任务（全部完成时使用）"
    )
    items: list[dict] | None = Field(
        default=None,
        description="任务条目列表，仅 update 时有效。每项格式：{\"task\": \"任务描述\", \"status\": \"pending|in_progress|completed|blocked\", \"priority\": \"high|medium|low\", \"notes\": \"备注（可选）\"}"
    )
    summary: str | None = Field(
        default=None,
        description="全局目标/备注描述，仅 update 时有效。不传则保持原有 summary 不变"
    )


class CheckScriptwriterStatusInput(BaseModel):
    """查询编剧工作状态的输入参数"""

    export_format: str = Field(
        default="arc",
        description="导出格式（arc / novel），用于读取匹配的自动写作状态"
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
    """
    将灵感内容写入灵感工坊。若当前已选中条目则覆盖其内容；若未选中任何条目，则自动创建新条目。
    """
    from mcp_server.spark_inspiration.logic import (
        update_inspiration,
        save_inspiration,
        current_user_id as mcp_uid_var,
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
    直接使用 overwrite_content 覆盖故事梗概。内容应为 Synopsis Markup 格式。
    """
    user_id, project_name = ToolExecutionContext.get_context()

    content = _strip_markdown_fence((overwrite_content or "").strip())
    if not content:
        return "重写梗概失败：overwrite_content 为空。"

    synopsis_path = os.path.join(get_project_path(user_id, project_name), "梗概.txt")
    with open(synopsis_path, "w", encoding="utf-8") as f:
        f.write(content)

    return "已成功重写并保存故事梗概。"


@tool(args_schema=RewriteBeatSheetInput)
def rewrite_beat_sheet(overwrite_content: str) -> str:
    """
    直接使用 overwrite_content 覆盖节拍表。内容应为 Beat Sheet Markup 格式。
    """
    user_id, project_name = ToolExecutionContext.get_context()

    content = _strip_markdown_fence((overwrite_content or "").strip())
    if not content:
        return "重写节拍表失败：overwrite_content 为空。"

    beats_path = os.path.join(get_project_path(user_id, project_name), "节拍表.txt")
    with open(beats_path, "w", encoding="utf-8") as f:
        f.write(content)

    return "已成功重写并保存节拍表。"


@tool(args_schema=RewriteOutlineInput)
def rewrite_outline(overwrite_content: str) -> str:
    """
    直接使用 overwrite_content 覆盖故事大纲，内容必须是最终可保存的 Outline Markup 正文。
    """
    user_id, project_name = ToolExecutionContext.get_context()

    content = _strip_markdown_fence((overwrite_content or "").strip())
    if not content:
        return "重写大纲失败：overwrite_content 为空。"

    outline_path = os.path.join(get_project_path(user_id, project_name), "大纲.txt")
    with open(outline_path, "w", encoding="utf-8") as f:
        f.write(content)

    return "已成功重写并保存故事大纲。"


@tool(args_schema=PatchSynopsisInput)
def patch_synopsis(search_text: str, replace_text: str) -> str:
    """通过提供原文片段和新文本片段对梗概进行局部修改，适用于对梗概的部分语句进行增删改。"""
    user_id, project_name = ToolExecutionContext.get_context()
    synopsis_path = os.path.join(get_project_path(user_id, project_name), "梗概.txt")
    return _apply_patch(synopsis_path, search_text, replace_text, file_label="梗概.txt")


@tool(args_schema=PatchBeatSheetInput)
def patch_beat_sheet(search_text: str, replace_text: str) -> str:
    """通过提供原文片段和新文本片段对节拍表进行局部修改。"""
    user_id, project_name = ToolExecutionContext.get_context()
    beats_path = os.path.join(get_project_path(user_id, project_name), "节拍表.txt")
    return _apply_patch(beats_path, search_text, replace_text, file_label="节拍表.txt")


@tool(args_schema=PatchOutlineInput)
def patch_outline(search_text: str, replace_text: str) -> str:
    """通过提供原文片段和新文本片段对大纲进行局部修改，适用于修改某章描述或增量追加新章节。"""
    user_id, project_name = ToolExecutionContext.get_context()
    outline_path = os.path.join(get_project_path(user_id, project_name), "大纲.txt")
    return _apply_patch(outline_path, search_text, replace_text, file_label="大纲.txt")


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
    """读取当前项目的全局故事梗概（Markup 纯文本）。"""
    user_id, project_name = ToolExecutionContext.get_context()
    synopsis_path = os.path.join(get_project_path(user_id, project_name), "梗概.txt")
    if not os.path.exists(synopsis_path):
        return "未找到故事梗概。"
    with open(synopsis_path, "r", encoding="utf-8") as f:
        return f.read()


@tool
def read_beat_sheet() -> str:
    """读取当前项目的全局情感节拍表（Markup 纯文本）。"""
    user_id, project_name = ToolExecutionContext.get_context()
    beats_path = os.path.join(get_project_path(user_id, project_name), "节拍表.txt")
    if not os.path.exists(beats_path):
        return "未找到节拍表。"
    with open(beats_path, "r", encoding="utf-8") as f:
        return f.read()

def _ensure_chapter_dir(stories_path: str, chapter_name: str) -> str:
    """确保章节目录存在并返回其绝对路径。"""
    safe = (chapter_name or "").strip().replace("\\", "_").replace("/", "_")
    if not safe:
        return stories_path
    chapter_dir = os.path.join(stories_path, safe)
    os.makedirs(chapter_dir, exist_ok=True)
    return chapter_dir


@tool(args_schema=CreateOrRewriteScriptInput)
def create_or_rewrite_script(
    overwrite_content: str,
    chapter_name: str | None = None,
    work_name: str | None = None,
    export_format: str | None = None,
) -> str:
    """
    新建或重写剧本/小说文件并落盘。
    - export_format: 'arc' 为互动剧本（默认），'novel' 为纯文学小说（.md）。
    - chapter_name: 目标章节文件夹名，不提供则保存到 stories 根目录。
    - work_name: 剧本文件显示名（不含扩展名），不提供则自动命名。
    - 调用前请先用 create_chapter 确保章节存在。
    overwrite_content 必须是最终可直接保存的正文，不得混入任何元话语或解释。
    """
    from core.utils import get_project_stories_path
    from story.file_naming import sanitize_story_display_name, next_story_order, build_story_filename

    effective_format = export_format or "arc"

    content = (overwrite_content or "").strip()
    if not content:
        return "创建/重写剧本失败：overwrite_content 为空。"

    user_id, project_name = ToolExecutionContext.get_context()
    stories_path = get_project_stories_path(user_id, project_name)
    os.makedirs(stories_path, exist_ok=True)

    if chapter_name and chapter_name.strip():
        target_dir = _ensure_chapter_dir(stories_path, chapter_name.strip())
        relative_dir = chapter_name.strip().replace("\\", "_").replace("/", "_")
    else:
        target_dir = stories_path
        relative_dir = ""

    display = sanitize_story_display_name(work_name.strip() if work_name and work_name.strip() else "新作品")
    order = next_story_order(stories_path, relative_dir)
    filename = build_story_filename(display, file_format=effective_format, order=order)
    file_path = os.path.join(target_dir, filename)

    import re as _re
    # 小说模式不需要自动加 # 标题行
    if effective_format != "novel" and not _re.search(r'^#\s+\S', content, _re.MULTILINE):
        content = f"# {display}\n{content}"

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

    rel = os.path.join(relative_dir, filename).replace("\\", "/") if relative_dir else filename
    format_label = "小说" if effective_format == "novel" else "剧本"
    return f"{format_label}已保存：{rel}"


@tool(args_schema=CreateChapterInput)
def create_chapter(chapter_name: str) -> str:
    """
    在 stories 目录下创建一个新章节（文件夹）。
    必须在调用 create_or_rewrite_script 之前调用，以确保目标章节存在。
    chapter_name 建议格式如「第一章_开端」或「第01章_相遇」。
    """
    from core.utils import get_project_stories_path

    name = (chapter_name or "").strip()
    if not name:
        return "创建章节失败：chapter_name 不能为空。"

    user_id, project_name = ToolExecutionContext.get_context()
    stories_path = get_project_stories_path(user_id, project_name)
    chapter_dir = _ensure_chapter_dir(stories_path, name)
    return f"章节已创建：{name}（路径：{chapter_dir}）"


@tool(args_schema=PatchScriptInput)
def patch_script(search_text: str, replace_text: str) -> str:
    """对剧本进行局部修改，在所有 .arc 文件中查找原文片段并替换为新文本（优先精确匹配，其次空白容错模糊匹配）。"""
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

    outline_path = os.path.join(get_project_path(user_id, project_name), "大纲.txt")
    if not os.path.exists(outline_path):
        return "当前项目尚无大纲数据（大纲.txt 不存在）。"

    try:
        with open(outline_path, "r", encoding="utf-8") as f:
            data = parse_outline_markup(f.read())
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
        desc = node.get("description") or ""
        lines.append(f"### [{i}] {title}  ({len(children)} 个场景)")
        if desc:
            lines.append(f"  摘要: {desc}")
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
    outline_path = os.path.join(project_path, "大纲.txt")
    outline_info = ""
    chapter_node = None
    try:
        if os.path.exists(outline_path):
            with open(outline_path, "r", encoding="utf-8") as f:
                data = parse_outline_markup(f.read())
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
                script_info = f"\n\n## 剧本文件: {arc_files[chapter_index]}\n```arc\n{content}\n```"
            except Exception as e:
                script_info = f"\n\n读取剧本文件失败: {e}"
        else:
            script_info = f"\n\n（该章节尚无对应的 .arc 剧本文件）"

    result = outline_info + script_info
    return result if result.strip() else f"章节 {chapter_index} 没有找到任何内容。"


@tool(args_schema=ReadChapterOutlineRawInput)
def read_chapter_outline_raw(chapter_index: int) -> str:
    """
    读取大纲.txt中指定章节的原始Markup文本（未经解析的结构化文本）。
    用于在执行 patch_outline 局部修改前，精确获取原文片段以确保 search_text 匹配正确。
    chapter_index 从 0 开始，对应大纲中 ## Chapter 的出现顺序。
    """
    user_id, project_name = ToolExecutionContext.get_context()
    outline_path = os.path.join(get_project_path(user_id, project_name), "大纲.txt")
    if not os.path.exists(outline_path):
        return "当前项目尚无大纲数据（大纲.txt 不存在）。"

    with open(outline_path, "r", encoding="utf-8") as f:
        full_text = f.read()

    # 按 ## Chapter 分割原始文本
    # 匹配所有 ## 开头的章节标题行
    chapter_pattern = re.compile(r'^(##\s+)', re.MULTILINE)
    splits = list(chapter_pattern.finditer(full_text))

    if not splits:
        # 没有任何 ## 标记，返回全文（可能只有全局元数据）
        if chapter_index == 0:
            return full_text
        return f"章节索引 {chapter_index} 超出范围（大纲中没有 ## Chapter 标记）。"

    if chapter_index < 0 or chapter_index >= len(splits):
        return f"章节索引 {chapter_index} 超出范围（共 {len(splits)} 个章节）。"

    # 提取该章节从标题行到下一个章节标题之前的内容
    start = splits[chapter_index].start()
    if chapter_index + 1 < len(splits):
        end = splits[chapter_index + 1].start()
    else:
        end = len(full_text)

    chapter_raw = full_text[start:end].rstrip()
    return chapter_raw


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
    from core.request_context import get_current_export_format
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
            "export_format": get_current_export_format(),
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
    """项目级知识图谱检索工具，支持构建索引、语义问答、状态查询和索引重置。

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


# ==================== Trigger Auto Write ====================


@tool(args_schema=TriggerAutoWriteInput)
def trigger_auto_write(
    start_chapter: int = 1,
    start_scene: int = 1,
    export_format: str = "arc",
    mode: str = "continuous_write",
) -> str:
    """
    触发自动化批量写作管道，根据当前项目的大纲（大纲.txt）自动生成所有章节的剧本文件。

    该工具会在后台启动写作任务并立即返回确认信息，写作过程异步进行。
    写作结束后，生成的文件会自动保存到项目的 stories 目录。

    使用时机：
    - 大纲已完成，用户希望自动生成全部剧本
    - 之前的写作任务中断，需要从指定章节继续
    - 已确认用户同意自动写作（花费时间较长）

    注意：写作过程中用户可以在前端的「自动写作」面板查看实时进度。
    """
    import threading

    start_chapter_index = max(0, start_chapter - 1)
    start_scene_index = max(0, start_scene - 1)

    user_id, project_name = ToolExecutionContext.get_context()
    project_path = get_project_path(user_id, project_name)
    from story.outline_parser import parse_outline_markup
    outline_path = os.path.join(project_path, "大纲.txt")

    if not os.path.exists(outline_path):
        return "触发写作失败：当前项目尚无大纲（大纲.txt 不存在），请先完成大纲规划。"

    try:
        with open(outline_path, "r", encoding="utf-8") as f:
            outline = parse_outline_markup(f.read())
    except Exception as e:
        return f"触发写作失败：读取大纲出错 — {e}"

    chapter_nodes = [n for n in (outline.get("nodes") or []) if n.get("type") == "chapter"]
    total_chapters = len(chapter_nodes)
    if total_chapters == 0:
        return "触发写作失败：大纲中未找到任何章节，请检查大纲.txt格式。"

    if start_chapter_index >= total_chapters:
        return f"触发写作失败：start_chapter_index={start_chapter_index} 超出章节范围（共 {total_chapters} 章）。"

    total_scenes = sum(
        len(ch.get("children") or [])
        for ch in chapter_nodes[start_chapter_index:]
    )

    def _run_auto_write():
        import asyncio
        from agents.routes.auto_write import generate_script_stream
        from core.request_context import current_user_id, current_project_name

        current_user_id.set(str(user_id))
        current_project_name.set(project_name)

        async def _drain():
            async for _ in generate_script_stream(
                user_id=str(user_id),
                project_name=project_name,
                outline=outline,
                request=None,
                mode=mode,
                start_chapter_index=start_chapter_index,
                start_scene_index=start_scene_index,
                context_strategy="accumulate",
                export_format=export_format,
            ):
                pass

        asyncio.run(_drain())

    thread = threading.Thread(target=_run_auto_write, daemon=True, name=f"auto_write_{project_name}")
    thread.start()

    remaining_chapters = total_chapters - start_chapter_index

    # 旁路标记：注入结构化元数据，供 chat.py 流式生成器识别并转发给前端
    # 格式：__director_auto_write_started__:{json}  （在首行，对 LLM 不可见）
    side_band_meta = json.dumps({
        "project_name": project_name,
        "start_chapter_index": start_chapter_index,
        "mode": mode,
        "export_format": export_format,
        "total_chapters": remaining_chapters,
        "total_scenes": total_scenes,
    }, ensure_ascii=False)

    return (
        f"__director_auto_write_started__:{side_band_meta}\n"
        f"自动写作任务已在后台启动。\n"
        f"- 项目：{project_name}\n"
        f"- 从第 {start_chapter_index + 1} 章第 {start_scene_index + 1} 场景开始，共 {remaining_chapters} 章，{total_scenes} 个场景\n"
        f"- 输出格式：{export_format}\n"
        f"- 模式：{mode}\n"
        f"写作已在后台进行，前端顶部状态条将实时显示进度，你可以在进度面板中随时中断任务。"
    )


# ==================== Check Scriptwriter Status ====================


@tool(args_schema=CheckScriptwriterStatusInput)
def check_scriptwriter_status(export_format: str = "arc") -> str:
    """查询编剧自动写作管道的运行状态及任务板进度（包括是否在写、中断原因、待办事项等）。

    适用场景：
    - 想了解上次触发的自动写作是否还在进行。
    - 想知道编剧当前排在任务板上的待办事项。
    - 调试写作管道异常时，查看具体出错原因。
    """
    user_id, project_name = ToolExecutionContext.get_context()

    # ── 1. 读取 Auto-Write 状态 ──────────────────────────────────────────
    try:
        from agents.routes.auto_write_state import load_auto_write_state
        aw_state = load_auto_write_state(user_id, project_name)
    except Exception as e:
        aw_state = {"status": "unknown", "lastError": str(e)}

    status = aw_state.get("status", "idle")
    status_labels = {
        "idle":           "待机（尚未启动任何写作任务）",
        "running":        "✅ 正在写作中",
        "chapter_paused": "⏸️  章节暂停（写完一章后暂停，等待指令）",
        "interrupted":    "⚠️  被中断（客户端断开连接或手动停止）",
        "error":          "❌ 写作异常（发生错误）",
        "complete":       "🎉 已全部完成",
        "unknown":        "状态未知",
    }
    status_label = status_labels.get(status, status)

    lines = ["══ 编剧自动写作状态 ══", f"状态：{status_label}"]

    if status == "running":
        ch_idx = aw_state.get("currentChapterIndex")
        ch_title = aw_state.get("currentChapterTitle", "")
        sc_title = aw_state.get("currentSceneTitle", "")
        if ch_idx is not None:
            lines.append(f"当前章节：第 {ch_idx + 1} 章 · {ch_title}")
        if sc_title:
            lines.append(f"当前场景：{sc_title}")
        started = aw_state.get("startedAt", "")
        if started:
            lines.append(f"启动时间：{started}")

    elif status in ("chapter_paused", "interrupted"):
        next_idx = aw_state.get("nextChapterIndex")
        if next_idx is not None:
            lines.append(f"下一章索引：{next_idx}（可从此处继续）")
        last_error = aw_state.get("lastError", "")
        if last_error:
            lines.append(f"中断原因：{last_error}")

    elif status == "error":
        last_error = aw_state.get("lastError", "（未记录错误原因）")
        lines.append(f"错误详情：{last_error}")
        resume_idx = aw_state.get("availableResumeChapterIndex")
        if resume_idx is not None:
            lines.append(f"可从第 {resume_idx + 1} 章重试（start_chapter_index={resume_idx}）")

    elif status == "complete":
        completed_at = aw_state.get("completedAt", "")
        if completed_at:
            lines.append(f"完成时间：{completed_at}")
        scene_files = aw_state.get("generatedSceneFiles", [])
        lines.append(f"共生成场景文件：{len(scene_files)} 个")

    lines.append("")

    # ── 2. 读取编剧的 work_tracker ────────────────────────────────────────
    project_path = get_project_path(user_id, project_name)
    tracker_path = os.path.join(project_path, "work_tracker_agent_scriptwriter.json")
    lines.append("══ 编剧任务板（Work Tracker）══")

    try:
        if not os.path.exists(tracker_path):
            lines.append("任务板为空（无历史记录）")
        else:
            with open(tracker_path, "r", encoding="utf-8") as f:
                tracker = json.load(f)
            items = tracker.get("items") or []
            summary = tracker.get("summary", "")
            updated = tracker.get("updated_at", "")

            if summary:
                lines.append(f"目标：{summary}")
            if updated:
                lines.append(f"最后更新：{updated}")

            if not items:
                lines.append("任务板为空")
            else:
                lines.append(f"共 {len(items)} 个任务：")
                for idx, item in enumerate(items, 1):
                    status_icon = {
                        "completed":  "✅",
                        "in_progress": "🔄",
                        "blocked":    "🚫",
                    }.get(item.get("status", ""), "⬜")
                    priority = item.get("priority", "")
                    priority_tag = f"[{priority}] " if priority else ""
                    notes = f"  → {item['notes']}" if item.get("notes") else ""
                    lines.append(
                        f"{idx}. {status_icon} {priority_tag}{item.get('task', '（无描述）')}{notes}"
                    )
    except Exception as e:
        lines.append(f"读取任务板失败：{e}")

    return "\n".join(lines)


# ==================== Work Tracker ====================


@tool(args_schema=WorkTrackerInput)
def work_tracker(
    action: str,
    items: list[dict] | None = None,
    summary: str | None = None,
) -> str:
    """
    读取或更新当前 Agent 在当前项目下的工作追踪列表。
    用于多轮任务中持久化进度，支持跨会话恢复。

    - read：返回当前所有任务条目及全局备注。
    - update：覆盖更新任务列表（items）和/或全局备注（summary）。
    - clear：清空所有任务（全部完成后调用）。

    建议使用规范：
    1. 开始多步任务前先 read，检查是否有未完成的历史任务。
    2. 每完成一步后 update 对应条目的 status 为 completed。
    3. 全部完成后调用 clear 或将所有 status 标为 completed。
    4. 被中断后重新开始时，先 read 恢复上次进度。
    """
    user_id, project_name = ToolExecutionContext.get_context()
    agent_id = ToolExecutionContext.get_agent_id() or "unknown"
    project_path = get_project_path(user_id, project_name)
    tracker_path = os.path.join(project_path, f"work_tracker_{agent_id}.json")

    def _format_tracker_text(data: dict) -> str:
        """将 work_tracker 数据格式化为结构化文本（read / update 共用）"""
        item_count = len(data.get("items") or [])
        if item_count == 0:
            msg = "当前工作追踪列表为空。"
            if data.get("summary"):
                msg += f"\n全局备注：{data['summary']}"
            return msg
        lines = []
        if data.get("summary"):
            lines.append(f"目标：{data['summary']}")
        lines.append(f"共 {item_count} 个任务：")
        for idx, item in enumerate(data["items"], 1):
            status_icon = {"completed": "✅", "in_progress": "🔄", "blocked": "🚫"}.get(
                item.get("status", ""), "⬜"
            )
            priority = item.get("priority", "")
            priority_tag = f"[{priority}] " if priority else ""
            notes = f"  → {item['notes']}" if item.get("notes") else ""
            lines.append(f"{idx}. {status_icon} {priority_tag}{item.get('task', '（无描述）')}{notes}")
        if data.get("updated_at"):
            lines.append(f"\n最后更新：{data['updated_at']}")
        return "\n".join(lines)

    def _load() -> dict:
        if not os.path.exists(tracker_path):
            return {"summary": "", "items": [], "updated_at": ""}
        try:
            with open(tracker_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"summary": "", "items": [], "updated_at": ""}

    def _save(data: dict) -> None:
        import datetime
        data["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        os.makedirs(project_path, exist_ok=True)
        with open(tracker_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    if action == "read":
        data = _load()
        return _format_tracker_text(data)

    elif action == "update":
        data = _load()
        if items is not None:
            data["items"] = items
        if summary is not None:
            data["summary"] = summary
        _save(data)
        return _format_tracker_text(data)

    elif action == "clear":
        _save({"summary": "", "items": [], "updated_at": ""})
        return "工作追踪已清空。"

    return f"未知操作类型：{action}。支持的操作：read / update / clear。"


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
    patch_outline,
    read_chapter_outline_raw,
]
SCRIPTWRITER_TOOLS = [create_chapter, create_or_rewrite_script, patch_script, read_worldview, read_character, read_synopsis, read_beat_sheet, work_tracker]
# SHARED_READ_TOOLS 中的 list_chapters / read_chapter_scene / read_chapter_outline_raw 由三种模式差异化授权：
# - 模式一（手动 Compose）：无工具，纯生成调用。
# - 模式二（Auto-Write Pre-flight）：仅授予 SHARED_READ_TOOLS。
#   注意：全量世界观、角色档案、梗概、节拍表在循环启动前已全量注入 Prompt，无需再配读取工具；
#   但远端任意章节的具体场景原文无法预先全量载入（会导致上下文爆炸），因此仅开放这些工具供按需懒加载。
# - 模式三（Chat / 导演委派）：SCRIPTWRITER_TOOLS + SHARED_READ_TOOLS 全部开放。
SHARED_READ_TOOLS = [list_chapters, read_chapter_scene, read_chapter_outline_raw]

DIRECTOR_TOOLS = SHARED_READ_TOOLS + [delegate_task, work_tracker, trigger_auto_write, check_scriptwriter_status]

# 已生产化但默认不挂载到任何 Agent，便于按需灰度启用。
OPTIONAL_RESEARCH_TOOLS = [graph_rag_tool]

ALL_TOOLS = MUSE_TOOLS + LOREBOOK_TOOLS + SHOWRUNNER_TOOLS + SCRIPTWRITER_TOOLS + SHARED_READ_TOOLS + [delegate_task, trigger_auto_write, check_scriptwriter_status] + OPTIONAL_RESEARCH_TOOLS
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
        "agent_style": [],
    }
    return tool_map.get(agent_id, [])
