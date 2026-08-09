from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Callable

from core.request_context import (
    current_agent_id,
    current_project_name,
    current_user_id,
    get_scriptwriter_prewrite_receipt,
    set_scriptwriter_prewrite_receipt,
)
from llm.agen_matchbox.tool_protocol import (
    build_tool_history_message,
    build_tool_result_messages,
    extract_tool_specs_from_message,
    prepare_tool_specs_for_execution,
)
from agents.tools.stream_events import normalize_tool_name


PREWRITE_STATUS_MESSAGE = "编剧调研"
PREWRITE_TOOL_NAME = "prepare_script_creation"
PREWRITE_MAX_TOOL_ROUNDS = 6
PREWRITE_MAX_TOOL_CALLS = 12


@dataclass(frozen=True)
class ScriptwriterPreWriteRequest:
    user_id: str
    project_name: str
    task_description: str
    chapter_name: str = ""
    scene_name: str = ""
    scene_guidance: str = ""
    scene_characters: list[str] = field(default_factory=list)
    full_outline: str = ""
    available_context: str = ""


@dataclass(frozen=True)
class ScriptwriterPreWriteResult:
    receipt_id: str
    brief: str
    research_context: str
    planning_note: str
    tools_used: tuple[str, ...]

    @property
    def context_addition(self) -> str:
        parts = []
        if self.research_context.strip():
            parts.append("### PreWrite 调研所得\n" + self.research_context.strip())
        if self.planning_note.strip():
            parts.append("### PreWrite 连续性简报\n" + self.planning_note.strip())
        return "\n\n".join(parts)


def _normalize_target(value: str) -> str:
    return str(value or "").strip().replace("\\", "/").casefold()


def _resolve_request_scene_identity(request: ScriptwriterPreWriteRequest) -> tuple[int, int]:
    """由大纲或现有文件元数据签发身份，禁止从模型标题编号推断。"""
    import os

    from agents.routes.context_builder import (
        load_project_context_bundle,
        resolve_outline_scene_contract_for_task,
    )
    from core.utils import get_project_stories_path
    from story.file_naming import list_story_files, sanitize_story_display_name

    bundle = load_project_context_bundle(request.user_id, request.project_name)
    contract = resolve_outline_scene_contract_for_task(
        bundle.get("outline_data") or {},
        task_description=request.task_description,
        chapter_title=request.chapter_name,
        scene_name=request.scene_name,
        file_path="",
    )
    chapter_index = contract.get("chapter_index")
    scene_index = contract.get("scene_index")
    if isinstance(chapter_index, int) and isinstance(scene_index, int):
        return chapter_index + 1, scene_index + 1

    stories_path = get_project_stories_path(request.user_id, request.project_name)
    story_files = list_story_files(stories_path)
    desired_display = sanitize_story_display_name(request.scene_name, "")
    for _, _, parsed in story_files:
        if not parsed or parsed.get("free"):
            continue
        if parsed.get("display_name") != desired_display:
            continue
        if isinstance(parsed.get("chapter_num"), int) and isinstance(parsed.get("scene_num"), int):
            return int(parsed["chapter_num"]), int(parsed["scene_num"])

    safe_chapter = str(request.chapter_name or "").strip().replace("\\", "_").replace("/", "_")
    chapter_dir = os.path.join(stories_path, safe_chapter)
    chapter_numbers: set[int] = set()
    scene_numbers: list[int] = []
    for _, absolute_path, parsed in story_files:
        if not parsed or parsed.get("free"):
            continue
        chapter_num = parsed.get("chapter_num")
        scene_num = parsed.get("scene_num")
        if isinstance(chapter_num, int):
            chapter_numbers.add(chapter_num)
        if os.path.dirname(absolute_path) == chapter_dir and isinstance(chapter_num, int):
            if isinstance(scene_num, int):
                scene_numbers.append(scene_num)

    if scene_numbers:
        target_chapter = next(
            int(parsed["chapter_num"])
            for _, absolute_path, parsed in story_files
            if parsed
            and os.path.dirname(absolute_path) == chapter_dir
            and isinstance(parsed.get("chapter_num"), int)
        )
        return target_chapter, max(scene_numbers) + 1

    return max(chapter_numbers, default=0) + 1, 1


def _issue_receipt(request: ScriptwriterPreWriteRequest, *, persist: bool = True) -> str:
    receipt_id = uuid.uuid4().hex
    if persist:
        chapter_num, scene_num = _resolve_request_scene_identity(request)
        set_scriptwriter_prewrite_receipt({
            "receipt_id": receipt_id,
            "user_id": str(request.user_id),
            "project_name": request.project_name,
            "chapter_name": request.chapter_name.strip(),
            "scene_name": request.scene_name.strip(),
            "task_description": request.task_description.strip(),
            "chapter_num": chapter_num,
            "scene_num": scene_num,
        })
    return receipt_id


def has_matching_prewrite_receipt(
    *,
    user_id: str,
    project_name: str,
    chapter_name: str | None,
    scene_name: str | None,
) -> bool:
    receipt = get_scriptwriter_prewrite_receipt()
    if not receipt:
        return False
    if str(receipt.get("user_id") or "") != str(user_id):
        return False
    if _normalize_target(str(receipt.get("project_name") or "")) != _normalize_target(project_name):
        return False

    expected_chapter = _normalize_target(chapter_name or "")
    actual_chapter = _normalize_target(str(receipt.get("chapter_name") or ""))
    expected_scene = _normalize_target(scene_name or "")
    actual_scene = _normalize_target(str(receipt.get("scene_name") or ""))
    invalid_targets = {"", "null", "none", "undefined", "nil"}
    if expected_chapter in invalid_targets or actual_chapter in invalid_targets:
        return False
    if expected_scene in invalid_targets or actual_scene in invalid_targets:
        return False
    if expected_chapter != actual_chapter or expected_scene != actual_scene:
        return False
    return True


def _build_prewrite_brief(request: ScriptwriterPreWriteRequest) -> str:
    from agents.routes.context_builder import build_scriptwriter_handoff_context

    return build_scriptwriter_handoff_context(
        request.user_id,
        request.project_name,
        task_description=request.task_description,
        chapter_name=request.chapter_name,
        scene_name=request.scene_name,
        scene_guidance=request.scene_guidance,
        scene_characters=request.scene_characters,
    )


def prepare_interactive_scriptwriter_prewrite(
    request: ScriptwriterPreWriteRequest,
) -> ScriptwriterPreWriteResult:
    """聊天/导演委派模式：生成确定性任务包，后续调查继续走当前 Agent 工具循环。"""
    brief = _build_prewrite_brief(request)
    receipt_id = _issue_receipt(request)
    return ScriptwriterPreWriteResult(
        receipt_id=receipt_id,
        brief=brief,
        research_context="",
        planning_note=(
            "系统已预装目标场景契约与相关 StoryMemory。请在当前工具循环中先核对入场状态、"
            "角色目标、知情边界、禁止提前发生事项、离场状态和待查事实；证据不足时继续调用只读工具。"
            "本轮任务或场景指导给出的结束边界比完整大纲中的后续动作更具体；不得把边界后的动作提前到本场。"
        ),
        tools_used=(),
    )


def _prewrite_read_tools() -> list[Any]:
    from agents.tools.research import graph_rag_tool
    from agents.tools.search import search_project, semantic_search
    from agents.tools.scriptwriter import read_beat_sheet, read_character, read_synopsis, read_worldview
    from agents.tools.shared_read import list_chapters, read_chapter_outline_raw, read_chapter_scene
    from agents.tools.story_memory import story_memory_tool

    return [
        story_memory_tool,
        graph_rag_tool,
        list_chapters,
        read_chapter_scene,
        read_chapter_outline_raw,
        read_worldview,
        read_character,
        read_synopsis,
        read_beat_sheet,
        search_project,
        semantic_search,
    ]


def run_autonomous_scriptwriter_prewrite(
    request: ScriptwriterPreWriteRequest,
    *,
    llm: Any,
    clean_text: Callable[[Any], str] | None = None,
    on_tool_progress: Callable[[str], None] | None = None,
    max_tool_rounds: int = PREWRITE_MAX_TOOL_ROUNDS,
) -> ScriptwriterPreWriteResult:
    """业务生产流模式：用受限只读工具循环完成写前调查，不承担正文生成。"""
    from agents.context_budget import (
        prepare_specialized_prompt_messages_with_budget,
        rebudget_existing_messages,
    )
    from agents.language_policy import prepend_prompt_language_policy
    from langchain_core.messages import HumanMessage
    from llm.agen_matchbox.reasoning_compat import extract_text_content_from_message

    brief = _build_prewrite_brief(request)
    tools = _prewrite_read_tools()
    allowed_tools = {str(getattr(tool, "name", "")): tool for tool in tools}
    llm_with_tools = llm.bind_tools(tools)
    clean = clean_text or (lambda value: str(value or ""))

    system_prompt = prepend_prompt_language_policy(
        """你是 Scriptwriter 的 PreWrite 调研规划器。你的职责仅限正式创作前的事实核对与创作规划，不得生成正文、不得调用写入工具。

先阅读系统确定性检索并提供的场景任务包，不要重复查询已经出现的 StoryMemory 条目。只有在任务包仍缺少关键原文证据时才调用只读工具：
- 人物关系、最近状态、秘密知情边界、开放线索：story_memory_tool。
- 跨文件关系与更大范围事实约束：graph_rag_tool。
- 必须核对原始措辞或历史场景细节：章节、场景、世界观、角色、梗概、节拍表读取工具。
- 已知关键词、人物或物品需要定位原文：search_project；只有关键词不足时再使用 semantic_search。

信息已经足够时不要为了形式调用工具。调查结束后输出“连续性简报”，依次写明：
1. 入场状态：人物、地点、物品、关系与开放线索的当前状态；
2. 角色目标：每个关键角色本场想达成什么；
3. 知情边界：谁知道什么、谁仍不知道什么；
4. 冲突与转折：本场如何改变局势，而不是只重复既有信息；
5. 禁止提前：哪些行为、信息或铺垫会破坏后续惊喜、秘密、误会或转折；
6. 离场状态与待查事实：本场结束后必须留下什么，哪些事实仍未核实。

范围优先级：本轮任务描述与场景指导中明确的开始/结束边界，高于完整大纲里更宽泛或属于后续场景的动作。若本轮要求“结束在某动作前”，该动作只能记入“禁止提前/下一场边界”，不得写入本场转折或离场状态。

简报应具体、可执行、有原文依据；不得生成正文，也不得用字数上限压缩掉关键状态。"""
    )
    context_preview = request.available_context.strip()
    outline_preview = request.full_outline.strip()
    if outline_preview:
        system_prompt = (
            system_prompt.rstrip()
            + "\n\n### 本次自动写作的稳定完整大纲\n"
            + outline_preview
        )
    user_prompt = "\n\n".join(part for part in [
        brief,
        f"### 当前已经准备的上下文摘要\n{context_preview}" if context_preview else "",
        "请完成 PreWrite。",
    ] if part)
    messages = prepare_specialized_prompt_messages_with_budget(
        agent_id="agent_scriptwriter",
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        llm_client=llm,
    ).messages

    user_token = current_user_id.set(str(request.user_id))
    project_token = current_project_name.set(request.project_name)
    agent_token = current_agent_id.set("agent_scriptwriter")
    gathered: list[str] = []
    tools_used: list[str] = []
    planning_note = ""
    total_calls = 0

    try:
        tool_rounds = max(0, int(max_tool_rounds))
        for _ in range(tool_rounds):
            response = llm_with_tools.invoke(messages)
            tool_specs = prepare_tool_specs_for_execution(
                extract_tool_specs_from_message(response),
                normalize_name=normalize_tool_name,
            )
            if not tool_specs:
                planning_note = clean(extract_text_content_from_message(response)).strip()
                break

            # 只把规范化后的 assistant 消息写入历史，确保空 ID / 重复 ID
            # 与后续 ToolMessage 使用同一份调用定义。
            messages.append(build_tool_history_message(response, tool_specs))
            tool_results: list[tuple[str, str, Any]] = []
            for tool_call in tool_specs:
                tool_name = str(tool_call.get("name") or "").strip()
                tool_args = tool_call.get("args") or {}
                call_id = str(tool_call["call_id"])
                if total_calls >= PREWRITE_MAX_TOOL_CALLS:
                    result = "PreWrite 已达到只读工具调用上限，请基于现有证据完成规划。"
                    tool_results.append((call_id, tool_name or "unknown_tool", result))
                    continue
                tool = allowed_tools.get(tool_name)
                if tool is None:
                    result = f"PreWrite 拒绝未知或非只读工具：{tool_name}"
                else:
                    try:
                        if on_tool_progress is not None:
                            on_tool_progress(tool_name)
                        result = tool.invoke(tool_args or {})
                    except Exception as exc:
                        result = f"工具 {tool_name} 执行失败：{exc}"
                cleaned = clean(result).strip()
                gathered.append(f"[{tool_name}]\n{cleaned}")
                tools_used.append(tool_name)
                total_calls += 1
                tool_results.append((call_id, tool_name, cleaned))
            messages.extend(build_tool_result_messages(tool_results))
            messages = rebudget_existing_messages(
                user_id=str(request.user_id),
                project_name=request.project_name,
                agent_id="agent_scriptwriter",
                messages=messages,
                llm_client=llm,
                current_user_message=user_prompt,
            ).messages
            if total_calls >= PREWRITE_MAX_TOOL_CALLS:
                break

        if not planning_note:
            messages.append(HumanMessage(content="PreWrite 调研阶段已结束。不得再调用工具；请基于现有证据输出完整的连续性简报，不得省略知情边界、禁止提前事项和离场状态。"))
            messages = rebudget_existing_messages(
                user_id=str(request.user_id),
                project_name=request.project_name,
                agent_id="agent_scriptwriter",
                messages=messages,
                llm_client=llm,
                current_user_message="输出完整的 PreWrite 连续性简报。",
            ).messages
            response = llm.invoke(messages)
            planning_note = clean(extract_text_content_from_message(response)).strip()
    finally:
        current_agent_id.reset(agent_token)
        current_project_name.reset(project_token)
        current_user_id.reset(user_token)

    receipt_id = _issue_receipt(request, persist=False)
    return ScriptwriterPreWriteResult(
        receipt_id=receipt_id,
        brief=brief,
        research_context="\n\n".join(gathered),
        planning_note=planning_note,
        tools_used=tuple(tools_used),
    )
