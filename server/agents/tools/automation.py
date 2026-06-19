from __future__ import annotations

import json
import os

from langchain.tools import tool
from pydantic import BaseModel, Field

from agents.auto_write_service import load_auto_write_status, start_auto_write_background
from core.utils import get_project_path
from core.project_settings import get_project_story_tags, set_project_story_tags

from .common import ToolExecutionContext


class TriggerAutoWriteInput(BaseModel):
    start_chapter: int = Field(default=1, description="从第几章开始写作（1=第一章）。若要续写未完成的任务，请基于已完成章节向后推算")
    start_scene: int = Field(default=1, description="在起始章内从第几个场景开始写作（1=该章第一个场景）。仅对起始章有效，后续章节总是从第 1 个场景开始")
    export_format: str = Field(default="arc", description="输出格式：arc=互动小说剧本格式；novel=普通小说纯文本格式")
    mode: str = Field(default="continuous_write", description="写作模式：continuous_write=连续写作全部章节（无人值守直达结束）；chapter_by_chapter=逐章写作（写完一章后暂停断开）")
    auto_review: bool = Field(default=False, description="是否在每个场景保存后自动触发 Critic 轻量审稿，并将修订工单写入 StoryMemory。默认关闭；只有用户明确要求边写边审时才开启，且不会自动改写正文。")


class WorkTrackerInput(BaseModel):
    action: str = Field(description="操作类型：read=读取当前任务列表；update=覆盖更新任务列表（可同时更新 summary 与 contract）；clear=清空所有任务（全部完成时使用）")
    items: list[dict] | None = Field(default=None, description="任务条目列表，仅 update 时有效。每项格式：{\"task\": \"任务描述\", \"status\": \"pending|in_progress|completed|blocked\", \"priority\": \"high|medium|low\", \"notes\": \"备注（可选）\"}")
    summary: str | None = Field(default=None, description="全局目标/备注描述，仅 update 时有效。不传则保持原有 summary 不变")
    contract: dict | None = Field(default=None, description="结构化创作契约，仅 update 时有效。不传则保持原有 contract 不变。建议记录章节/场景/篇幅/角色数量范围/题材/风格/目标受众/阶段性完成度等可核查参数")


class CheckScriptwriterStatusInput(BaseModel):
    export_format: str = Field(default="arc", description="导出格式（arc / novel），用于读取匹配的自动写作状态")


class UpdateProjectStoryTagsInput(BaseModel):
    style: str | None = Field(default=None, description="风格（单选，如'治愈'、'悬疑'）")
    genres: list[str] | None = Field(default=None, description="题材（多选，如['仙侠', '冒险']）")
    tones: list[str] | None = Field(default=None, description="基调（多选，如['暗黑', '治愈']）")
    worldviews: list[str] | None = Field(default=None, description="世界观（多选，如['修真']）")
    pov: str | None = Field(default=None, description="人称视角（单选，如'第一人称'、'第三人称全知'）")
    length_hint: str | None = Field(default=None, description="篇幅（单选，如'短篇'、'中篇'、'长篇'）")
    active_inspiration_id: str | None = Field(default=None, description="当前生效的灵感 ID（可选，用于追溯来源）")


@tool(args_schema=TriggerAutoWriteInput)
def trigger_auto_write(
    start_chapter: int = 1,
    start_scene: int = 1,
    export_format: str = "arc",
    mode: str = "continuous_write",
    auto_review: bool = False,
) -> str:
    """在后台启动自动写作任务。"""
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

    total_scenes = sum(len(ch.get("children") or []) for ch in chapter_nodes[start_chapter_index:])

    start_auto_write_background(
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
        f"- 输出格式：{export_format}\n"
        f"- 模式：{mode}\n"
        f"- 自动审稿：{'开启' if auto_review else '关闭'}\n"
        f"写作已在后台进行，前端顶部状态条将实时显示进度，你可以在进度面板中随时中断任务。"
    )


@tool(args_schema=CheckScriptwriterStatusInput)
def check_scriptwriter_status(export_format: str = "arc") -> str:
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
    action: str,
    items: list[dict] | None = None,
    summary: str | None = None,
    contract: dict | None = None,
) -> str:
    """读取、更新或清空当前 Agent 的工作追踪。update 时可通过 contract 字段写入结构化创作契约（章节数、角色数量范围、题材风格等可核查参数）。"""
    user_id, project_name = ToolExecutionContext.get_context()
    agent_id = ToolExecutionContext.get_agent_id() or "unknown"
    project_path = get_project_path(user_id, project_name)
    tracker_path = os.path.join(project_path, f"work_tracker_{agent_id}.json")

    def _format_tracker_text(data: dict) -> str:
        item_count = len(data.get("items") or [])
        contract_data = data.get("contract") or {}
        contract_lines = []
        if contract_data:
            contract_lines.append("创作契约：")
            for key, value in contract_data.items():
                if isinstance(value, (dict, list)):
                    value_text = json.dumps(value, ensure_ascii=False)
                else:
                    value_text = str(value)
                contract_lines.append(f"- {key}：{value_text}")
        if item_count == 0:
            msg = "当前工作追踪列表为空。"
            if data.get("summary"):
                msg += f"\n全局备注：{data['summary']}"
            if contract_lines:
                msg += "\n" + "\n".join(contract_lines)
            return msg
        lines = []
        if data.get("summary"):
            lines.append(f"目标：{data['summary']}")
        lines.extend(contract_lines)
        lines.append(f"共 {item_count} 个任务：")
        for idx, item in enumerate(data["items"], 1):
            status_icon = {"completed": "✅", "in_progress": "🔄", "blocked": "🚫"}.get(item.get("status", ""), "⬜")
            priority = item.get("priority", "")
            priority_tag = f"[{priority}] " if priority else ""
            notes = f"  → {item['notes']}" if item.get("notes") else ""
            lines.append(f"{idx}. {status_icon} {priority_tag}{item.get('task', '（无描述）')}{notes}")
        if data.get("updated_at"):
            lines.append(f"\n最后更新：{data['updated_at']}")
        return "\n".join(lines)

    def _load() -> dict:
        if not os.path.exists(tracker_path):
            return {"summary": "", "contract": {}, "items": [], "updated_at": ""}
        try:
            with open(tracker_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"summary": "", "contract": {}, "items": [], "updated_at": ""}

    def _save(data: dict) -> None:
        import datetime

        data["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        os.makedirs(project_path, exist_ok=True)
        with open(tracker_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    if action == "read":
        data = _load()
        return _format_tracker_text(data)
    if action == "update":
        data = _load()
        if items is not None:
            data["items"] = items
        if summary is not None:
            data["summary"] = summary
        if contract is not None:
            data["contract"] = contract
        else:
            # 自动从 story_tags 填充 contract（如果未显式传入）
            try:
                story_tags = get_project_story_tags(user_id, project_name)
                if story_tags:
                    auto_contract = {
                        "style": story_tags.get("style"),
                        "genres": story_tags.get("genres", []),
                        "tones": story_tags.get("tones", []),
                        "worldviews": story_tags.get("worldviews", []),
                        "pov": story_tags.get("pov"),
                        "length_hint": story_tags.get("length_hint"),
                    }
                    # 仅当至少有一个字段非空时才写入
                    if any(v for v in auto_contract.values() if v not in (None, [], "")):
                        data["contract"] = auto_contract
            except Exception:
                pass  # 读取失败时保持原有 contract
        _save(data)
        return _format_tracker_text(data)
    if action == "clear":
        _save({"summary": "", "contract": {}, "items": [], "updated_at": ""})
        return "工作追踪已清空。"

    return f"未知操作类型：{action}。支持的操作：read / update / clear。"


@tool
def read_project_story_tags() -> str:
    """读取当前项目的故事主题参数（风格/题材/基调/世界观/人称/篇幅）。
    
    这些参数是"项目宪法"，贯穿整个创作周期，所有 Agent 通过 context_provider 统一读取。
    返回格式化的文本，若某项未设置则标注"未设置"。
    """
    user_id, project_name = ToolExecutionContext.get_context()
    
    try:
        tags = get_project_story_tags(user_id, project_name)
    except Exception as e:
        return f"读取项目故事主题参数失败：{e}"
    
    lines = ["══ 项目故事主题参数 ══"]
    
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
    
    return "\n".join(lines)


@tool(args_schema=UpdateProjectStoryTagsInput)
def update_project_story_tags(
    style: str | None = None,
    genres: list[str] | None = None,
    tones: list[str] | None = None,
    worldviews: list[str] | None = None,
    pov: str | None = None,
    length_hint: str | None = None,
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
            active_inspiration_id=active_inspiration_id,
        )
    except Exception as e:
        return f"更新项目故事主题参数失败：{e}"
    
    # 构建更新摘要
    updated_fields = []
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
    if active_inspiration_id is not None:
        updated_fields.append(f"灵感ID={active_inspiration_id}")
    
    summary = "、".join(updated_fields) if updated_fields else "无变更"
    
    return f"项目故事主题参数已更新：{summary}\n所有 Agent 将在下次对话时自动读取新参数。"
