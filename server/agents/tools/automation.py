from __future__ import annotations

import json
import os
from typing import Literal

from langchain.tools import tool
from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator, model_validator

from agents.auto_write_service import load_auto_write_status, start_auto_write_background
from core.utils import get_project_path
from core.project_settings import STORY_TAG_VALUE_UNSET, get_project_story_tags, get_workspace_mode, set_project_story_tags

from .common import ToolExecutionContext


class TriggerAutoWriteInput(BaseModel):
    start_chapter: int = Field(default=1, description="从第几章开始写作（1=第一章）。若要续写未完成的任务，请基于已完成章节向后推算")
    start_scene: int = Field(default=1, description="在起始章内从第几个场景开始写作（1=该章第一个场景）。仅对起始章有效，后续章节总是从第 1 个场景开始")
    mode: str = Field(default="continuous_write", description="写作模式：continuous_write=连续写作全部章节（无人值守直达结束）；chapter_by_chapter=逐章写作（写完一章后暂停断开）")
    auto_review: bool = Field(default=False, description="是否在每个场景保存后自动触发 Critic 轻量审稿，并将修订工单写入 StoryMemory。默认关闭；只有用户明确要求边写边审时才开启，且不会自动改写正文。")


class WorkTrackerItemInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task: str = Field(description="任务描述。稳定任务 ID 由系统自动生成，不要自行提供 ID。")
    status: Literal["pending", "in_progress", "completed", "blocked"] = Field(default="pending", description="任务状态。")
    priority: Literal["high", "medium", "low"] = Field(default="medium", description="任务优先级。")
    notes: str = Field(default="", description="结果、失败原因、重做要求或其他备注。")


class WorkTrackerOperationItemInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task: str | None = Field(default=None, description="任务描述。add/insert 必填；edit 时仅在修改描述时传入。")
    status: Literal["pending", "in_progress", "completed", "blocked"] | None = Field(default=None, description="任务状态。通常使用 set_status 操作修改状态。")
    priority: Literal["high", "medium", "low"] | None = Field(default=None, description="任务优先级。")
    notes: str | None = Field(default=None, description="结果、失败原因、重做要求或其他备注。")


class WorkTrackerOperationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: Literal["add", "insert", "edit", "delete", "set_status"] = Field(description="条目操作：add=末尾新增；insert=指定位置插入；edit=修改；delete=彻底删除；set_status=标记状态。")
    item_id: str | None = Field(default=None, description="单个目标任务 ID，适用于 edit/delete/set_status。")
    item_ids: list[str] | None = Field(default=None, description="批量目标任务 ID，适用于 delete/set_status。")
    item: WorkTrackerOperationItemInput | None = Field(default=None, description="add/insert 时传任务内容；edit 时只传需要修改的字段，禁止传 ID。")
    position: int | None = Field(default=None, ge=1, description="insert 的 1 基位置。")
    status: Literal["pending", "in_progress", "completed", "blocked"] | None = Field(default=None, description="set_status 的目标状态。标记完成请传 completed；删除任务必须使用 delete。")

    @model_validator(mode="after")
    def _validate_operation_shape(self):
        target_ids = [str(value).strip() for value in (self.item_ids or []) if str(value).strip()]
        if self.item_id and self.item_id.strip():
            target_ids.append(self.item_id.strip())

        if self.operation in {"add", "insert"}:
            if self.item is None or not str(self.item.task or "").strip():
                raise ValueError(f"{self.operation} 操作必须提供包含 task 的 item。")
            if self.operation == "insert" and self.position is None:
                raise ValueError("insert 操作必须提供从 1 开始的 position。")
        elif self.operation == "edit":
            if len(set(target_ids)) != 1 or self.item is None:
                raise ValueError("edit 操作必须提供唯一 item_id 和待修改的 item 字段。")
        elif self.operation == "delete" and not target_ids:
            raise ValueError("delete 操作必须提供 item_id 或 item_ids。")
        elif self.operation == "set_status" and (not target_ids or self.status is None):
            raise ValueError("set_status 操作必须提供目标 ID 和 status。")
        return self


class WorkTrackerInput(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    overwrite: bool = Field(default=False, description="仅在创建全新计划或用户明确要求重建任务板时设为 true；已有任务板的日常推进必须保持 false。")
    items: list[WorkTrackerItemInput] | None = Field(default=None, validation_alias=AliasChoices("items", "tasks", "todo_items"), description="仅 overwrite=true 时有效，用于提供新的完整任务列表。")
    operations: list[WorkTrackerOperationInput] | None = Field(default=None, description="增量操作列表，可在一次调用中批量新增、插入、编辑、删除或标记状态。")
    summary: str | None = Field(default=None, validation_alias=AliasChoices("summary", "goal", "objective"), description="任务板总目标；不传则保持原值。")
    contract: dict | None = Field(default=None, description="结构化创作契约；不传则保持原值。")

    @model_validator(mode="after")
    def _validate_update_mode(self):
        if self.overwrite:
            if self.items is None:
                raise ValueError("overwrite=true 时必须提供完整 items。")
            if self.operations:
                raise ValueError("整板覆盖与增量 operations 不能在同一次调用中混用。")
        elif self.items is not None:
            raise ValueError("增量更新不能直接传 items；创建全新计划时请显式设置 overwrite=true。")
        elif not self.operations and self.summary is None and self.contract is None:
            raise ValueError("增量更新必须提供 operations、summary 或 contract。")
        return self


class CheckScriptwriterStatusInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class UpdateProjectStoryTagsInput(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    workspace_mode: str | None = Field(default=None, validation_alias=AliasChoices("workspace_mode", "workspaceMode", "mode"), description="只读兼容字段：项目创作模式只能在创建项目时决定，创建后不可通过此工具修改。")
    style: str | None = Field(default=None, description="风格，单选字符串，如 '治愈'、'悬疑'。")
    genres: list[str] | None = Field(default=None, description="题材，多选字符串数组，如 ['仙侠', '冒险']；即使只有一个也必须传数组。")
    tones: list[str] | None = Field(default=None, description="基调，多选字符串数组，如 ['暗黑', '治愈']；即使只有一个也必须传数组。")
    worldviews: list[str] | None = Field(default=None, description="世界观，多选字符串数组，如 ['修真']；即使只有一个也必须传数组。")
    pov: str | None = Field(default=None, validation_alias=AliasChoices("pov", "point_of_view", "pointOfView"), description="人称视角，单选字符串，如 '第一人称'、'第三人称全知'。")
    length_hint: str | None = Field(default=None, validation_alias=AliasChoices("length_hint", "lengthHint", "length"), description="篇幅，单选字符串，如 '短篇'、'中篇'、'长篇'。")
    scene_length_hint: str | None = Field(default=None, validation_alias=AliasChoices("scene_length_hint", "sceneLengthHint", "scene_length"), description="单场篇幅软目标：concise=精简、standard=标准、expanded=充实。用户要求今后的场景整体变短或变长时使用。")
    scene_target_chars: int | None = Field(default=None, ge=100, le=100000, validation_alias=AliasChoices("scene_target_chars", "sceneTargetChars", "target_chars"), description="单场目标正文字符数，作为软目标；具体值存在时优先于三档区间。")
    clear_scene_target_chars: bool = Field(default=False, validation_alias=AliasChoices("clear_scene_target_chars", "clearSceneTargetChars"), description="是否清除项目级具体字数目标，恢复仅按三档控制。")
    active_inspiration_id: str | None = Field(default=None, validation_alias=AliasChoices("active_inspiration_id", "activeInspirationId"), description="当前生效的灵感 ID，可选字符串，用于追溯来源。")

    @model_validator(mode="before")
    @classmethod
    def _normalize_wrapped_story_tags(cls, value):
        if not isinstance(value, dict):
            return value
        data = dict(value)
        for wrapper_key in ("story_tags", "storyTags", "tags", "data", "payload"):
            wrapped = data.get(wrapper_key)
            if isinstance(wrapped, dict):
                data.pop(wrapper_key, None)
                data = {**wrapped, **data}
                break
        return data

    @field_validator("genres", "tones", "worldviews", mode="before")
    @classmethod
    def _normalize_tag_list(cls, value):
        if value is None or isinstance(value, list):
            return value
        if isinstance(value, str):
            import re

            return [item.strip() for item in re.split(r"[,，、\n]", value) if item.strip()]
        return value


@tool(args_schema=TriggerAutoWriteInput)
def trigger_auto_write(
    start_chapter: int = 1,
    start_scene: int = 1,
    mode: str = "continuous_write",
    auto_review: bool = False,
) -> str:
    """在后台启动自动写作任务。"""
    start_chapter_index = max(0, start_chapter - 1)
    start_scene_index = max(0, start_scene - 1)

    user_id, project_name = ToolExecutionContext.get_context()
    workspace_mode = get_workspace_mode(str(user_id), project_name)
    export_format = "novel" if workspace_mode == "novel" else "arc"
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

    total_scenes = sum(len(ch.get("children") or []) for ch in chapter_nodes[start_chapter_index:])

    start_result = start_auto_write_background(
        user_id=str(user_id),
        project_name=project_name,
        outline=outline,
        mode=mode,
        start_chapter_index=start_chapter_index,
        start_scene_index=start_scene_index,
        export_format=export_format,
        context_strategy="accumulate",
        auto_review=auto_review,
        from_director=True,
    )
    if not start_result.started:
        return f"触发写作失败：{start_result.error or '当前项目已有自动写作任务正在运行。'}"

    remaining_chapters = total_chapters - start_chapter_index

    side_band_meta = json.dumps(
        {
            "project_name": project_name,
            "start_chapter_index": start_chapter_index,
            "start_scene_index": start_scene_index,
            "mode": mode,
            "export_format": export_format,
            "auto_review": auto_review,
            "total_chapters": remaining_chapters,
            "total_scenes": total_scenes,
        },
        ensure_ascii=False,
    )

    return (
        f"__director_auto_write_started__:{side_band_meta}\n"
        f"自动写作任务已在后台启动。\n"
        f"- 项目：{project_name}\n"
        f"- 从第 {start_chapter_index + 1} 章第 {start_scene_index + 1} 场景开始，共 {remaining_chapters} 章，{total_scenes} 个场景\n"
        f"- 输出格式：{export_format}（由项目 story tags 创作模式决定）\n"
        f"- 模式：{mode}\n"
        f"- 自动审稿：{'开启' if auto_review else '关闭'}\n"
        f"写作已在后台进行，前端顶部状态条将实时显示进度，你可以在进度面板中随时中断任务。"
    )


@tool(args_schema=CheckScriptwriterStatusInput)
def check_scriptwriter_status() -> str:
    """查询自动写作状态与编剧任务板。"""
    user_id, project_name = ToolExecutionContext.get_context()

    try:
        aw_state = load_auto_write_status(user_id, project_name)
    except Exception as e:
        aw_state = {"status": "unknown", "lastError": str(e)}

    status = aw_state.get("status", "idle")
    status_labels = {
        "idle": "待机（尚未启动任何写作任务）",
        "running": "✅ 正在写作中",
        "chapter_paused": "⏸️  章节暂停（写完一章后暂停，等待指令）",
        "interrupted": "⚠️  被中断（客户端断开连接或手动停止）",
        "error": "❌ 写作异常（发生错误）",
        "complete": "🎉 已全部完成",
        "unknown": "状态未知",
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
            contract = tracker.get("contract") or {}
            updated = tracker.get("updated_at", "")

            if summary:
                lines.append(f"目标：{summary}")
            if contract:
                lines.append("创作契约：")
                for key, value in contract.items():
                    if isinstance(value, (dict, list)):
                        value_text = json.dumps(value, ensure_ascii=False)
                    else:
                        value_text = str(value)
                    lines.append(f"- {key}：{value_text}")
            if updated:
                lines.append(f"最后更新：{updated}")

            if not items:
                lines.append("任务板为空")
            else:
                lines.append(f"共 {len(items)} 个任务：")
                for idx, item in enumerate(items, 1):
                    status_icon = {
                        "completed": "✅",
                        "in_progress": "🔄",
                        "blocked": "🚫",
                    }.get(item.get("status", ""), "⬜")
                    priority = item.get("priority", "")
                    priority_tag = f"[{priority}] " if priority else ""
                    notes = f"  → {item['notes']}" if item.get("notes") else ""
                    lines.append(f"{idx}. {status_icon} {priority_tag}{item.get('task', '（无描述）')}{notes}")
    except Exception as e:
        lines.append(f"读取任务板失败：{e}")

    return "\n".join(lines)


@tool(args_schema=WorkTrackerInput)
def work_tracker(
    overwrite: bool = False,
    items: list[dict] | None = None,
    operations: list[dict] | None = None,
    summary: str | None = None,
    contract: dict | None = None,
) -> str:
    """更新当前 Agent 的持久任务板；当前板面已由系统自动注入消息尾部。"""
    from agents.work_tracker import update_work_tracker

    user_id, project_name = ToolExecutionContext.get_context()
    agent_id = ToolExecutionContext.get_agent_id() or "unknown"

    effective_contract = contract
    if effective_contract is None and overwrite:
        try:
            story_tags = get_project_story_tags(user_id, project_name)
            if story_tags:
                effective_contract = {
                    "workspace_mode": story_tags.get("workspace_mode", "script"),
                    "style": story_tags.get("style"),
                    "genres": story_tags.get("genres", []),
                    "tones": story_tags.get("tones", []),
                    "worldviews": story_tags.get("worldviews", []),
                    "pov": story_tags.get("pov"),
                    "length_hint": story_tags.get("length_hint"),
                    "scene_length_hint": story_tags.get("scene_length_hint", "standard"),
                }
        except Exception:
            effective_contract = None
    try:
        data = update_work_tracker(
            user_id,
            project_name,
            agent_id,
            overwrite=overwrite,
            items=items,
            operations=operations,
            summary=summary,
            contract=effective_contract,
        )
    except ValueError as exc:
        return f"任务板更新失败：{exc}"
    return json.dumps(data, ensure_ascii=False)


@tool
def read_project_story_tags() -> str:
    """读取当前项目的故事主题参数（风格/题材/基调/世界观/人称/篇幅/单场篇幅）。
    
    这些参数是"项目宪法"，贯穿整个创作周期，所有 Agent 通过 context_provider 统一读取。
    返回格式化的文本，若某项未设置则标注"未设置"。
    """
    user_id, project_name = ToolExecutionContext.get_context()
    
    try:
        tags = get_project_story_tags(user_id, project_name)
    except Exception as e:
        return f"读取项目故事主题参数失败：{e}"
    
    lines = ["══ 项目故事主题参数 ══"]

    workspace_mode = tags.get("workspace_mode", "script")
    mode_label = "小说模式（novel）" if workspace_mode == "novel" else "剧本模式（script）"
    lines.append(f"创作模式：{mode_label}（创建项目时锁定，不可通过 story tags 修改）")
    
    # POV 醒目展示
    pov = tags.get("pov")
    if pov:
        lines.append(f"⚠️ 人称视角：{pov}（已锁定）")
    else:
        lines.append("人称视角：未设置")
    
    # 其他参数
    style = tags.get("style")
    lines.append(f"风格：{style or '未设置'}")
    
    genres = tags.get("genres", [])
    lines.append(f"题材：{'、'.join(genres) if genres else '未设置'}")
    
    tones = tags.get("tones", [])
    lines.append(f"基调：{'、'.join(tones) if tones else '未设置'}")
    
    worldviews = tags.get("worldviews", [])
    lines.append(f"世界观：{'、'.join(worldviews) if worldviews else '未设置'}")
    
    length_hint = tags.get("length_hint")
    lines.append(f"篇幅：{length_hint or '未设置'}")

    scene_length_labels = {"concise": "精简", "standard": "标准", "expanded": "充实"}
    scene_length_hint = tags.get("scene_length_hint", "standard")
    lines.append(f"单场篇幅：{scene_length_labels.get(scene_length_hint, '标准')}（软目标）")
    scene_target_chars = tags.get("scene_target_chars")
    lines.append(
        f"单场目标字数：约 {scene_target_chars} 个可见正文字符（软目标，优先于档位区间）"
        if scene_target_chars
        else "单场目标字数：自动（使用档位区间）"
    )
    
    return "\n".join(lines)


@tool(args_schema=UpdateProjectStoryTagsInput)
def update_project_story_tags(
    workspace_mode: str | None = None,
    style: str | None = None,
    genres: list[str] | None = None,
    tones: list[str] | None = None,
    worldviews: list[str] | None = None,
    pov: str | None = None,
    length_hint: str | None = None,
    scene_length_hint: str | None = None,
    scene_target_chars: int | None = None,
    clear_scene_target_chars: bool = False,
    active_inspiration_id: str | None = None,
) -> str:
    """更新当前项目的故事主题参数（部分更新，仅覆盖传入的字段）。
    
    这些参数是"项目宪法"，贯穿整个创作周期，所有 Agent 通过 context_provider 统一读取。
    Director 在"从头创作"流程中应调用此工具固化用户确认的创作参数。
    """
    user_id, project_name = ToolExecutionContext.get_context()
    
    try:
        tags = set_project_story_tags(
            user_id=user_id,
            project_name=project_name,
            style=style,
            genres=genres,
            tones=tones,
            worldviews=worldviews,
            pov=pov,
            length_hint=length_hint,
            scene_length_hint=scene_length_hint,
            scene_target_chars=(
                None if clear_scene_target_chars
                else scene_target_chars if scene_target_chars is not None else STORY_TAG_VALUE_UNSET
            ),
            active_inspiration_id=active_inspiration_id,
        )
    except Exception as e:
        return f"更新项目故事主题参数失败：{e}"
    
    # 构建更新摘要
    updated_fields = []
    if workspace_mode is not None:
        locked_mode = tags.get("workspace_mode", get_workspace_mode(str(user_id), project_name))
        locked_label = "novel" if locked_mode == "novel" else "script"
        updated_fields.append(f"创作模式已锁定为 {locked_label}，忽略修改请求")
    if style is not None:
        updated_fields.append(f"风格={style}")
    if genres is not None:
        updated_fields.append(f"题材={genres}")
    if tones is not None:
        updated_fields.append(f"基调={tones}")
    if worldviews is not None:
        updated_fields.append(f"世界观={worldviews}")
    if pov is not None:
        updated_fields.append(f"人称视角={pov}")
    if length_hint is not None:
        updated_fields.append(f"篇幅={length_hint}")
    if scene_length_hint is not None:
        scene_length_labels = {"concise": "精简", "standard": "标准", "expanded": "充实"}
        normalized_scene_length = tags.get("scene_length_hint", "standard")
        updated_fields.append(f"单场篇幅={scene_length_labels.get(normalized_scene_length, '标准')}")
    if clear_scene_target_chars:
        updated_fields.append("单场目标字数=自动")
    elif scene_target_chars is not None:
        updated_fields.append(f"单场目标字数≈{tags.get('scene_target_chars')}字")
    if active_inspiration_id is not None:
        updated_fields.append(f"灵感ID={active_inspiration_id}")
    
    summary = "、".join(updated_fields) if updated_fields else "无变更"
    
    return f"项目故事主题参数已更新：{summary}\n所有 Agent 将在下次对话时自动读取新参数。"
