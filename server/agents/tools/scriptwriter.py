from __future__ import annotations

import os

from langchain.tools import tool
from pydantic import BaseModel, Field

from core.utils import get_project_path
from agents.project_content import load_worldview

from .common import ToolExecutionContext, _apply_patch


class CreateOrRewriteScriptInput(BaseModel):
    overwrite_content: str = Field(description="完整的剧本/小说正文。若目标场景文件尚不存在，系统将自动创建；若已存在则覆盖。必须只包含最终可保存的正文，不得混入解释、确认话术或元话语。")
    chapter_name: str | None = Field(default=None, description="目标章节名称（即文件夹名称），格式为「中文数字 · 标题」（如「一 · 开端」「二 · 相遇」）。【CRITICAL】剧本将保存到该章节目录下。写剧本/小说前，必须先调用 create_chapter 确保该章节目录存在，并在此传入一致的章节名。严禁在不指定章节的情况下调用此工具往根目录写入孤儿场景文件。")
    work_name: str | None = Field(default=None, description="场景文件的显示名称（不含扩展名），格式为「章节号-场景号 场景名」（如「1-1 初遇」「2-3 决战」）。若不提供，系统将自动根据内容或上下文命名。")


class PrepareScriptCreationInput(BaseModel):
    task_description: str = Field(description="本次完整场景创作任务，包含目标、冲突、衔接要求与用户意图。")
    chapter_name: str = Field(description="目标章节名称，必须与随后 create_chapter 和 create_or_rewrite_script 使用的 chapter_name 完全一致。")
    scene_name: str = Field(description="目标场景名称，必须与随后 create_or_rewrite_script 使用的 work_name 完全一致。")
    scene_guidance: str = Field(default="", description="大纲中对当前场景的具体指导、关键事件或落点。")
    scene_characters: list[str] = Field(default_factory=list, description="预计在本场出现或必须核对的角色名。")


class CreateChapterInput(BaseModel):
    chapter_name: str = Field(description="章节名称，将作为 stories 目录下的子文件夹名称。格式为「中文数字 · 标题」（如「一 · 开端」「二 · 相遇」「十 · 终章」）。")


class PatchScriptInput(BaseModel):
    search_text: str = Field(description="需要被替换的剧本片段（必须精确匹配原文）。传入空字符串可将 replace_text 追加到文件末尾")
    replace_text: str = Field(description="修改后的新文本片段")


class ReadCharacterInput(BaseModel):
    character_name: str = Field(description="要查阅的角色名字，例如'张三'")


class OrganizeScenesToChapterInput(BaseModel):
    scene_paths: list[str] = Field(
        description="要归纳的场景文件相对路径列表（相对于 stories 目录）。"
                    "例如：['旧场景.arc', '一 · 开端/1-1 初遇.arc']。"
                    "可通过 list_chapters 或 search_project 获取现有文件路径。"
    )
    new_chapter_name: str = Field(
        description="目标章节名称（即文件夹名称），格式为「中文数字 · 标题」（如「二 · 发展」「三 · 转折」）。若章节不存在将自动创建。"
    )
    chapter_num: int | None = Field(
        default=None,
        description="章节编号（用于文件名元数据 chap=xxx）。若不指定，将根据现有章节自动推算。"
    )
    preserve_originals: bool = Field(
        default=False,
        description="是否保留原文件。False=移动（删除原文件），True=复制（保留原文件）。"
    )


def _ensure_chapter_dir(stories_path: str, chapter_name: str) -> str:
    safe = (chapter_name or "").strip().replace("\\", "_").replace("/", "_")
    if not safe:
        return stories_path
    chapter_dir = os.path.join(stories_path, safe)
    os.makedirs(chapter_dir, exist_ok=True)
    return chapter_dir


@tool
def read_worldview() -> str:
    """读取世界观全文。"""
    user_id, project_name = ToolExecutionContext.get_context()
    content = load_worldview(user_id, project_name)
    return content if content else "未找到世界观设定。"


@tool(args_schema=ReadCharacterInput)
def read_character(character_name: str) -> str:
    """读取角色设定。

    先按姓名反查稳定 ID，再通过统一门面读取角色正文。
    """
    from story.project_files import (
        load_character_content,
        lookup_character_id_by_name,
    )

    user_id, project_name = ToolExecutionContext.get_context()
    char_id = lookup_character_id_by_name(user_id, project_name, character_name)
    if not char_id:
        return f"未找到名为 '{character_name}' 的角色档案。"

    return load_character_content(user_id, project_name, char_id)


@tool
def read_synopsis() -> str:
    """读取故事梗概。"""
    user_id, project_name = ToolExecutionContext.get_context()
    synopsis_path = os.path.join(get_project_path(user_id, project_name), "梗概.txt")
    if not os.path.exists(synopsis_path):
        return "未找到故事梗概。"
    with open(synopsis_path, "r", encoding="utf-8") as f:
        return f.read()


@tool
def read_beat_sheet() -> str:
    """读取节拍表。"""
    user_id, project_name = ToolExecutionContext.get_context()
    beats_path = os.path.join(get_project_path(user_id, project_name), "节拍表.txt")
    if not os.path.exists(beats_path):
        return "未找到节拍表。"
    with open(beats_path, "r", encoding="utf-8") as f:
        return f.read()


@tool(args_schema=PrepareScriptCreationInput)
def prepare_script_creation(
    task_description: str,
    chapter_name: str,
    scene_name: str,
    scene_guidance: str = "",
    scene_characters: list[str] | None = None,
) -> str:
    """执行完整场景创作前的 PreWrite，核对任务包并签发本次落盘凭证。"""
    import json

    from agents.scriptwriter_prewrite import (
        ScriptwriterPreWriteRequest,
        prepare_interactive_scriptwriter_prewrite,
    )

    user_id, project_name = ToolExecutionContext.get_context()
    chapter = str(chapter_name or "").strip()
    scene = str(scene_name or "").strip()
    if not chapter or not scene:
        return "PreWrite 失败：chapter_name 与 scene_name 均不能为空。"

    result = prepare_interactive_scriptwriter_prewrite(ScriptwriterPreWriteRequest(
        user_id=user_id,
        project_name=project_name,
        task_description=str(task_description or "").strip(),
        chapter_name=chapter,
        scene_name=scene,
        scene_guidance=str(scene_guidance or "").strip(),
        scene_characters=[str(item).strip() for item in (scene_characters or []) if str(item).strip()],
    ))
    return json.dumps({
        "status": "ready",
        "message": "PreWrite 已完成，可以继续补查只读资料，随后创建章节并落盘正文。",
        "task_pack": result.brief,
        "planning_note": result.planning_note,
    }, ensure_ascii=False)


@tool(args_schema=CreateOrRewriteScriptInput)
def create_or_rewrite_script(
    overwrite_content: str,
    chapter_name: str | None = None,
    work_name: str | None = None,
) -> str:
    """创建或覆盖剧本文件。"""
    from core.utils import get_project_stories_path
    from story.file_naming import (
        build_story_filename,
        next_story_order,
        parse_scene_identity_from_title,
        resolve_planned_scene_file_path,
        sanitize_story_display_name,
    )

    from core.request_context import clear_scriptwriter_prewrite_receipt, get_current_export_format
    from agents.scriptwriter_prewrite import has_matching_prewrite_receipt

    effective_format = get_current_export_format()
    user_id, project_name = ToolExecutionContext.get_context()
    if ToolExecutionContext.get_agent_id() == "agent_scriptwriter" and not has_matching_prewrite_receipt(
        user_id=user_id,
        project_name=project_name,
        chapter_name=chapter_name,
        scene_name=work_name,
    ):
        return (
            "创建/重写剧本失败：当前完整场景尚未完成匹配的 PreWrite。"
            "请先调用 prepare_script_creation，并使用完全一致的 chapter_name 与 scene_name。"
        )
    content = (overwrite_content or "").strip()
    if effective_format != "novel":
        from core.project_settings import (
            get_visual_illustration_settings,
            is_visual_illustration_enabled,
        )
        from story.arc_safety import sanitize_arc_ai_output
        from story.presentation_manifest import get_project_background_catalog

        visual_settings = get_visual_illustration_settings(user_id, project_name)
        allowed_background_ids = {
            item["id"] for item in get_project_background_catalog(user_id, project_name)
        }
        content = sanitize_arc_ai_output(
            content,
            allow_visual_illustration=is_visual_illustration_enabled(user_id, project_name),
            max_per_scene=visual_settings["max_per_scene"],
            min_node_gap=visual_settings["min_node_gap"],
            allowed_background_ids=allowed_background_ids,
        )
    if not content:
        return "创建/重写剧本失败：overwrite_content 为空。"

    stories_path = get_project_stories_path(user_id, project_name)
    os.makedirs(stories_path, exist_ok=True)

    if chapter_name and chapter_name.strip():
        target_dir = _ensure_chapter_dir(stories_path, chapter_name.strip())
        relative_dir = chapter_name.strip().replace("\\", "_").replace("/", "_")
    else:
        target_dir = stories_path
        relative_dir = ""

    display = sanitize_story_display_name(work_name.strip() if work_name and work_name.strip() else "新场景")
    chapter_num, scene_num = parse_scene_identity_from_title(display)
    if chapter_num is not None and scene_num is not None:
        file_path, existed, _ = resolve_planned_scene_file_path(
            stories_path,
            chapter_num,
            scene_num,
            display,
            chapter_dir_name=chapter_name.strip() if chapter_name else "",
            file_format=effective_format,
        )
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        relative_dir = os.path.relpath(os.path.dirname(file_path), stories_path)
        if relative_dir == ".":
            relative_dir = ""
        filename = os.path.basename(file_path)
    else:
        existed = False
        order = next_story_order(stories_path, relative_dir)
        filename = build_story_filename(display, file_format=effective_format, order=order)
        file_path = os.path.join(target_dir, filename)

    import re as _re

    if effective_format != "novel" and not _re.search(r'^#\s+\S', content, _re.MULTILINE):
        content = f"# {display}\n{content}"

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

    rel = os.path.join(relative_dir, filename).replace("\\", "/") if relative_dir else filename
    from agents.story_memory import enqueue_scene_memory_write

    enqueue_scene_memory_write(
        user_id=user_id,
        project_name=project_name,
        label="Scriptwriter 工具落盘",
        scene_text=content,
        chapter_title=chapter_name or "",
        scene_title=display,
        source_path=rel,
        export_format=effective_format,
        scene_characters=[],
    )
    if ToolExecutionContext.get_agent_id() == "agent_scriptwriter":
        clear_scriptwriter_prewrite_receipt()

    format_label = "小说" if effective_format == "novel" else "剧本"
    action_label = "已覆盖" if existed else "已保存"
    return f"{format_label}{action_label}：{rel}"


@tool(args_schema=CreateChapterInput)
def create_chapter(chapter_name: str) -> str:
    """创建章节目录。"""
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
    """局部修改剧本内容。search_text 传空字符串可将 replace_text 追加到文件末尾。"""
    from core.utils import get_project_stories_path

    user_id, project_name = ToolExecutionContext.get_context()
    from core.project_settings import (
        get_visual_illustration_settings,
        is_visual_illustration_enabled,
    )
    from story.arc_safety import (
        sanitize_arc_ai_fragment,
        validate_arc_visual_prompt_candidate,
    )
    from story.presentation_manifest import get_project_background_catalog

    visual_settings = get_visual_illustration_settings(user_id, project_name)
    allowed_background_ids = {
        item["id"] for item in get_project_background_catalog(user_id, project_name)
    }
    raw_replace_text = replace_text
    replace_text = sanitize_arc_ai_fragment(
        replace_text,
        allow_visual_illustration=is_visual_illustration_enabled(user_id, project_name),
        allowed_background_ids=allowed_background_ids,
    )
    if str(raw_replace_text or "").strip() and not replace_text:
        return "局部修改剧本失败：replace_text 只包含 AI 无权写入的运行时控制字段。"

    def validate_candidate(original: str, candidate: str) -> None:
        validate_arc_visual_prompt_candidate(
            original,
            candidate,
            max_per_scene=visual_settings["max_per_scene"],
            min_node_gap=visual_settings["min_node_gap"],
        )
    stories_path = get_project_stories_path(user_id, project_name)
    if not os.path.exists(stories_path):
        return "局部修改剧本失败：stories 目录不存在。"

    from story.file_naming import list_story_files

    arc_files = list_story_files(stories_path, file_format="arc")

    for rel_path, file_path, _ in arc_files:
        with open(file_path, "r", encoding="utf-8") as f:
            arc_content = f.read()
        if search_text in arc_content:
            return _apply_patch(
                file_path,
                search_text,
                replace_text,
                validate_content=validate_candidate,
                file_label=rel_path,
            )

    for rel_path, file_path, _ in arc_files:
        result = _apply_patch(
            file_path,
            search_text,
            replace_text,
            validate_content=validate_candidate,
            file_label=rel_path,
        )
        if not result.startswith("局部修改失败"):
            return result

    return (
        "局部修改剧本失败：在当前项目所有剧本文件中均未找到与 search_text 匹配的片段。\n"
        "提示：请确保 search_text 取自原文的完整连续片段（建议 1‑3 句），不要包含额外解释性文字。"
    )


@tool(args_schema=OrganizeScenesToChapterInput)
def organize_scenes_to_chapter(
    scene_paths: list[str],
    new_chapter_name: str,
    chapter_num: int | None = None,
    preserve_originals: bool = False,
) -> str:
    """将指定的场景文件归纳到目标章节目录下。

    适用场景：
    - 整理散落在 stories 根目录的孤儿场景文件
    - 将多个相关场景合并到新章节
    - 重新组织章节结构

    核心操作：
    1. 更新文件名中的元数据（chap=xxx, order=xxx）
    2. 可选：移动文件到章节文件夹（自动创建）
    """
    from core.utils import get_project_stories_path
    from story.file_naming import (
        parse_story_filename,
        rebuild_story_filename,
        next_story_order,
    )
    import shutil

    user_id, project_name = ToolExecutionContext.get_context()
    stories_path = get_project_stories_path(user_id, project_name)

    if not scene_paths:
        return "整理失败：scene_paths 不能为空。"

    # 1. 验证所有源文件存在
    source_files = []
    for rel_path in scene_paths:
        full_path = os.path.join(stories_path, rel_path.replace("/", os.sep))
        if not os.path.exists(full_path):
            return f"整理失败：文件不存在 - {rel_path}"
        parsed = parse_story_filename(os.path.basename(full_path))
        if not parsed:
            return f"整理失败：无法解析文件名元数据 - {rel_path}"
        source_files.append((rel_path, full_path, parsed))

    # 2. 创建目标章节目录
    target_chapter_name = (new_chapter_name or "").strip()
    if not target_chapter_name:
        return "整理失败：new_chapter_name 不能为空。"
    target_dir = _ensure_chapter_dir(stories_path, target_chapter_name)

    # 3. 确定章节编号
    effective_chap = chapter_num
    if effective_chap is None:
        # 自动推算：扫描现有章节目录，取最大编号 +1
        existing_chaps = []
        for root, dirs, files in os.walk(stories_path):
            for f in files:
                p = parse_story_filename(f)
                if p and p["chapter_num"] is not None:
                    existing_chaps.append(p["chapter_num"])
        effective_chap = max(existing_chaps, default=0) + 1

    # 4. 获取目标目录的下一个可用 order
    current_order = next_story_order(stories_path, target_chapter_name)

    # 5. 逐个处理文件
    moved_files = []
    errors = []
    for rel_path, full_path, parsed in source_files:
        try:
            # 构建新文件名（更新 chap 和 order）
            new_filename = rebuild_story_filename(
                os.path.basename(full_path),
                chapter_num=effective_chap,
                order=current_order,
            )
            target_path = os.path.join(target_dir, new_filename)

            # 移动或复制
            if preserve_originals:
                shutil.copy2(full_path, target_path)
            else:
                shutil.move(full_path, target_path)

            moved_files.append(f"{rel_path} → {target_chapter_name}/{new_filename}")
            current_order += 1
        except Exception as e:
            errors.append(f"{rel_path}: {e}")

    # 6. 返回结果
    if errors:
        return f"部分完成：\n成功：{moved_files}\n失败：{errors}"

    action = "复制" if preserve_originals else "移动"
    return f"已成功{action} {len(moved_files)} 个场景到章节「{target_chapter_name}」：\n" + "\n".join(moved_files)
