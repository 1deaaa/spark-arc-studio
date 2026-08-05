from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Callable

from agents.prompt_layout import build_prompt_messages
from core.request_context import (
    current_agent_id,
    current_project_name,
    current_user_id,
    get_scriptwriter_prewrite_receipt,
    set_scriptwriter_prewrite_receipt,
)


PREWRITE_STATUS_MESSAGE = "编剧正在调研规划。"
PREWRITE_TOOL_NAME = "prepare_script_creation"
PREWRITE_MAX_TOOL_ROUNDS = 2
PREWRITE_MAX_TOOL_CALLS = 6
PREWRITE_MAX_TOOL_RESULT_CHARS = 4000
PREWRITE_MAX_RESEARCH_CHARS = 12000


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
            parts.append("### PreWrite 创作规划\n" + self.planning_note.strip())
        return "\n\n".join(parts)


def _normalize_target(value: str) -> str:
    return str(value or "").strip().replace("\\", "/").casefold()


def _issue_receipt(request: ScriptwriterPreWriteRequest, *, persist: bool = True) -> str:
    receipt_id = uuid.uuid4().hex
    if persist:
        set_scriptwriter_prewrite_receipt({
            "receipt_id": receipt_id,
            "user_id": str(request.user_id),
            "project_name": request.project_name,
            "chapter_name": request.chapter_name.strip(),
            "scene_name": request.scene_name.strip(),
            "task_description": request.task_description.strip(),
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
        planning_note="系统已确定性预装目标场景契约与相关 StoryMemory；仅当具体原文证据仍缺失时，再调用只读工具补查后落盘。",
        tools_used=(),
    )


def _prewrite_read_tools() -> list[Any]:
    from agents.tools.research import graph_rag_tool
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
    ]


def run_autonomous_scriptwriter_prewrite(
    request: ScriptwriterPreWriteRequest,
    *,
    llm: Any,
    clean_text: Callable[[Any], str] | None = None,
    max_tool_rounds: int = PREWRITE_MAX_TOOL_ROUNDS,
) -> ScriptwriterPreWriteResult:
    """业务生产流模式：用受限只读工具循环完成写前调查，不承担正文生成。"""
    from agents.language_policy import prepend_prompt_language_policy
    from langchain_core.messages import HumanMessage, ToolMessage
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

信息已经足够时不要为了形式调用工具。调查结束后输出不超过 200 字的创作规划，只写本场目标、冲突推进、必须保持的事实与落点。"""
    )
    context_preview = request.available_context.strip()
    if len(context_preview) > 6000:
        context_preview = context_preview[-6000:]
    outline_preview = request.full_outline.strip()
    if len(outline_preview) > 8000:
        outline_preview = outline_preview[:8000]
    user_prompt = "\n\n".join(part for part in [
        brief,
        f"### 当前已经准备的上下文摘要\n{context_preview}" if context_preview else "",
        f"### 完整大纲\n{outline_preview}" if outline_preview else "",
        "请完成 PreWrite。",
    ] if part)
    messages = build_prompt_messages(system_prompt=system_prompt, user_prompt=user_prompt)

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
            messages.append(response)
            tool_calls = getattr(response, "tool_calls", None) or []
            if not tool_calls:
                planning_note = clean(extract_text_content_from_message(response)).strip()
                break

            for tool_call in tool_calls:
                tool_name = str(tool_call.get("name") or "").strip()
                tool_args = tool_call.get("args") if isinstance(tool_call, dict) else {}
                call_id = str(tool_call.get("id") or uuid.uuid4().hex) if isinstance(tool_call, dict) else uuid.uuid4().hex
                if total_calls >= PREWRITE_MAX_TOOL_CALLS:
                    messages.append(ToolMessage(
                        content="PreWrite 已达到只读工具调用上限，请基于现有证据完成规划。",
                        tool_call_id=call_id,
                        name=tool_name or "unknown_tool",
                    ))
                    continue
                tool = allowed_tools.get(tool_name)
                if tool is None:
                    result = f"PreWrite 拒绝未知或非只读工具：{tool_name}"
                else:
                    try:
                        result = tool.invoke(tool_args or {})
                    except Exception as exc:
                        result = f"工具 {tool_name} 执行失败：{exc}"
                cleaned = clean(result).strip()
                if len(cleaned) > PREWRITE_MAX_TOOL_RESULT_CHARS:
                    cleaned = cleaned[:PREWRITE_MAX_TOOL_RESULT_CHARS] + "\n[结果已按 PreWrite 上下文预算截断]"
                remaining = PREWRITE_MAX_RESEARCH_CHARS - sum(len(item) for item in gathered)
                if remaining <= 0:
                    cleaned = "PreWrite 调研上下文已达到上限，请基于现有证据完成规划。"
                elif len(cleaned) > remaining:
                    cleaned = cleaned[:remaining] + "\n[调研上下文已达到上限]"
                gathered.append(f"[{tool_name}]\n{cleaned}")
                tools_used.append(tool_name)
                total_calls += 1
                messages.append(ToolMessage(content=cleaned, tool_call_id=call_id, name=tool_name))
            if total_calls >= PREWRITE_MAX_TOOL_CALLS:
                break

        if not planning_note:
            messages.append(HumanMessage(content="PreWrite 调研阶段已结束。不得再调用工具；请基于现有证据输出不超过 200 字的创作规划。"))
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
