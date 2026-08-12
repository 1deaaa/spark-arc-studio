from __future__ import annotations

import os

from langchain.tools import tool
from pydantic import BaseModel, Field, field_validator

from core.utils import get_project_path
from core.character_relations import read_character_relation_lines
from agents.project_content import load_worldview

from .common import ToolExecutionContext, _apply_patch


_INVALID_STORY_TARGET_NAMES = {"null", "none", "undefined", "nil"}


def _validate_story_target_name(value: object, *, field_name: str) -> str:
    if value is None:
        raise ValueError(f"{field_name} 必须传入真实字符串，不能为 null。")
    if not isinstance(value, str):
        raise ValueError(f"{field_name} 必须传入真实字符串。")
    normalized = value.strip()
    if not normalized or normalized.casefold() in _INVALID_STORY_TARGET_NAMES:
        raise ValueError(f"{field_name} 必须传入真实名称，不能使用空值或 null 占位符。")
    return normalized


class CreateOrRewriteScriptInput(BaseModel):
    overwrite_content: str = Field(description="完整的剧本/小说正文。若目标场景文件尚不存在，系统将自动创建；若已存在则覆盖。必须只包含最终可保存的正文，不得混入解释、确认话术或元话语。")
    chapter_name: str = Field(min_length=1, description="目标章节/分卷的可读标题（即文件夹名称）。编号由 PreWrite metadata 统一生成。【CRITICAL】剧本/小说将保存到该目录下。写作前必须先调用 create_chapter，并在此传入一致的标题。严禁传入 null、字符串 null 或省略此字段。")
    work_name: str = Field(min_length=1, description="场景/章节的可读标题（不含扩展名）。不要自行编造或修改章节号-场景号；唯一身份由 PreWrite 签发的文件元数据决定。必须与 PreWrite 的 scene_name 完全一致，严禁传入 null、字符串 null 或省略此字段。")
    target_chars: int | None = Field(default=None, ge=100, le=100000, description="本轮用户或导演明确要求的目标正文字符数。仅作为软目标和落盘回执的统计基准；未传时使用项目默认目标。")

    @field_validator("chapter_name", "work_name", mode="before")
    @classmethod
    def validate_target_names(cls, value: object, info) -> str:
        return _validate_story_target_name(value, field_name=info.field_name)


class PrepareScriptCreationInput(BaseModel):
    task_description: str = Field(description="本次完整场景创作任务，包含目标、冲突、衔接要求与用户意图。")
    chapter_name: str = Field(min_length=1, description="目标章节/分卷的可读标题，必须与随后 create_chapter 和 create_or_rewrite_script 使用的 chapter_name 完全一致。编号由系统 metadata 决定。严禁传入 null、字符串 null 或其他占位符。")
    scene_name: str = Field(min_length=1, description="目标场景的可读标题，必须与随后 create_or_rewrite_script 使用的 work_name 完全一致；不要把编号当作身份来源。严禁传入 null、字符串 null 或其他占位符。")
    scene_guidance: str = Field(default="", description="大纲中对当前场景的具体指导、关键事件或落点。")
    scene_characters: list[str] = Field(default_factory=list, description="预计在本场出现或必须核对的角色名。")

    @field_validator("chapter_name", "scene_name", mode="before")
    @classmethod
    def validate_target_names(cls, value: object, info) -> str:
        return _validate_story_target_name(value, field_name=info.field_name)


class CreateChapterInput(BaseModel):
    chapter_name: str = Field(description="章节/分卷的可读标题，将作为 stories 目录下的子文件夹名称；系统会按 metadata 补充稳定编号。")


class PatchScriptInput(BaseModel):
    search_text: str = Field(description="需要被替换的剧本片段。必须逐字复制 read_chapter_scene 返回的‘已落盘剧本’代码块内部连续原文，不得包含代码围栏、文件标题或解释文字；优先选择可唯一定位的 1-3 句。传入空字符串可将 replace_text 追加到文件末尾")
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
    name = (chapter_name or "").strip()
    if not name:
        return stories_path
    from story.file_naming import parse_chapter_identity_from_title, resolve_chapter_directory

    chapter_dir = resolve_chapter_directory(
        stories_path,
        name,
        chapter_num=parse_chapter_identity_from_title(name),
    )
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

    content = load_character_content(user_id, project_name, char_id)
    relation_lines = read_character_relation_lines(user_id, project_name, char_id)
    if relation_lines:
        content = f"{content}\n\n【作者确认关系】\n{chr(10).join(relation_lines)}"
    return content


@tool
def read_synopsis() -> str:
    """读取故事梗概。"""
    user_id, project_name = ToolExecutionContext.get_context()
    synopsis_path = os.path.join(get_project_path(user_id, project_name), "梗概.txt")
    if not os.path.exists(synopsis_path):
        return "未找到故事梗概。"
    with open(synopsis_path, "r", encoding="utf-8") as f:
        content = f.read().strip()
    return content or "故事梗概文件为空。"


@tool
def read_beat_sheet() -> str:
    """读取节拍表。"""
    user_id, project_name = ToolExecutionContext.get_context()
    beats_path = os.path.join(get_project_path(user_id, project_name), "节拍表.txt")
    if not os.path.exists(beats_path):
        return "未找到节拍表。"
    with open(beats_path, "r", encoding="utf-8") as f:
        content = f.read().strip()
    return content or "节拍表文件为空。"


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
    target_chars: int | None = None,
) -> str:
    """创建或覆盖剧本文件。"""
    import json

    from core.utils import get_project_stories_path
    from story.file_naming import (
        DuplicateSceneIdentityError,
        build_story_filename,
        canonical_chapter_display_name,
        next_story_order,
        parse_scene_identity_from_title,
        canonical_scene_display_name,
        resolve_planned_scene_file_path,
        sanitize_story_display_name,
    )

    from core.request_context import (
        clear_scriptwriter_prewrite_receipt,
        get_current_export_format,
        get_scriptwriter_prewrite_receipt,
    )
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
    submitted_content = content
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
    else:
        from story.novel_parser import parse_novel_document, serialize_novel_document

        novel_document = parse_novel_document(content)
        content = serialize_novel_document(
            novel_document["body"],
            novel_document["conception"],
        )
    if not content:
        return "创建/重写剧本失败：overwrite_content 为空。"

    stories_path = get_project_stories_path(user_id, project_name)
    os.makedirs(stories_path, exist_ok=True)

    target_dir = stories_path
    relative_dir = ""

    raw_display = sanitize_story_display_name(work_name.strip() if work_name and work_name.strip() else "")
    if not raw_display:
        return "创建/重写剧本失败：work_name 不能为空。"
    receipt = get_scriptwriter_prewrite_receipt()
    if ToolExecutionContext.get_agent_id() == "agent_scriptwriter":
        try:
            chapter_num = int(receipt.get("chapter_num")) if receipt else 0
            scene_num = int(receipt.get("scene_num")) if receipt else 0
        except (TypeError, ValueError):
            chapter_num = scene_num = 0
        if chapter_num <= 0 or scene_num <= 0:
            # 兼容旧版请求凭证；新版 PreWrite 始终会写入元数据身份。
            chapter_num, scene_num = parse_scene_identity_from_title(raw_display)
            if chapter_num is None or scene_num is None or chapter_num <= 0 or scene_num <= 0:
                return "创建/重写剧本失败：PreWrite 未签发有效的场景元数据身份。"
    else:
        chapter_num, scene_num = parse_scene_identity_from_title(raw_display)
        if chapter_num is not None or scene_num is not None:
            if chapter_num is None or scene_num is None or chapter_num <= 0 or scene_num <= 0:
                return "创建/重写剧本失败：场景编号必须是大于 0 的‘章节号-场景号’，例如 3-4。"
        else:
            chapter_num = scene_num = None
    if chapter_num is not None and scene_num is not None:
        try:
            display = canonical_scene_display_name(raw_display, chapter_num, scene_num)
            chapter_display = canonical_chapter_display_name(chapter_name, chapter_num)
        except ValueError as exc:
            return f"创建/重写剧本失败：{exc}"
    else:
        display = raw_display
        chapter_display = str(chapter_name or "").strip()
        if chapter_display:
            target_dir = _ensure_chapter_dir(stories_path, chapter_display)
            relative_dir = os.path.relpath(target_dir, stories_path)
    if chapter_num is not None and scene_num is not None:
        try:
            file_path, existed, _ = resolve_planned_scene_file_path(
                stories_path,
                chapter_num,
                scene_num,
                display,
                chapter_dir_name=chapter_display,
                file_format=effective_format,
            )
        except DuplicateSceneIdentityError as exc:
            return f"创建/重写剧本失败：{exc}。请先在作品管理器中确认并整理重复文件。"
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
        chapter_index=(chapter_num - 1) if chapter_num is not None else None,
        scene_index=(scene_num - 1) if scene_num is not None else None,
        chapter_title=chapter_display,
        scene_title=display,
        source_path=rel,
        export_format=effective_format,
        scene_characters=[],
    )
    if ToolExecutionContext.get_agent_id() == "agent_scriptwriter":
        clear_scriptwriter_prewrite_receipt()

    format_label = "小说" if effective_format == "novel" else "剧本"
    action_label = "已覆盖" if existed else "已保存"
    from core.project_settings import get_project_story_tags
    from story.text_metrics import count_story_body_chars

    written_chars = count_story_body_chars(content, effective_format)
    project_target_chars = get_project_story_tags(user_id, project_name).get("scene_target_chars")
    effective_target_chars = target_chars if isinstance(target_chars, int) else project_target_chars
    deviation = written_chars - effective_target_chars if isinstance(effective_target_chars, int) else None
    return json.dumps(
        {
            "status": "saved",
            "message": f"{format_label}{action_label}：{rel}",
            "format": effective_format,
            "path": rel,
            "written_chars": written_chars,
            "target_chars": effective_target_chars,
            "target_source": "current_task" if isinstance(target_chars, int) else "project" if isinstance(project_target_chars, int) else None,
            "deviation_chars": deviation,
            "length_policy": (
                "具体字数仅为软目标。请根据场景完整性自行判断是否需要调整，"
                "不要因少量偏差整场重写，也不要为凑字数注水。"
            ),
            "content_changed_by_sanitizer": content != submitted_content,
        },
        ensure_ascii=False,
    )


@tool(args_schema=CreateChapterInput)
def create_chapter(chapter_name: str) -> str:
    """创建章节目录。"""
    from core.utils import get_project_stories_path

    name = (chapter_name or "").strip()
    if not name:
        return "创建章节失败：chapter_name 不能为空。"
    user_id, project_name = ToolExecutionContext.get_context()
    if ToolExecutionContext.get_agent_id() == "agent_scriptwriter":
        from core.request_context import get_scriptwriter_prewrite_receipt
        from story.file_naming import canonical_chapter_display_name

        receipt = get_scriptwriter_prewrite_receipt() or {}
        try:
            chapter_num = int(receipt.get("chapter_num"))
            name = canonical_chapter_display_name(name, chapter_num)
        except (TypeError, ValueError):
            return "创建章节失败：PreWrite 未签发有效的章节元数据身份。"
    stories_path = get_project_stories_path(user_id, project_name)
    chapter_dir = _ensure_chapter_dir(stories_path, name)
    return f"章节已创建：{name}（路径：{chapter_dir}）"


@tool(args_schema=PatchScriptInput)
def patch_script(search_text: str, replace_text: str) -> str:
    """局部修改剧本内容；匹配失败时应重新读取原文并缩短定位片段，不要直接完整重写。"""
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
        "恢复步骤：调用 read_chapter_scene 重新读取目标场景，从‘已落盘剧本’代码块内部逐字复制一段"
        "可唯一定位的连续原文（建议 1-3 句），缩短 search_text 后重试；不要包含代码围栏、文件标题或解释文字，"
        "也不要重复提交同一个失败片段。仅因局部匹配失败时，不得改用完整重写。"
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
