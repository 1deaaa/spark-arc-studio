"""自动写作持久化状态、恢复游标与输出计划。"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

from core.utils import get_project_path, get_project_stories_path
from core.json_state import json_state_lock, load_json_file, save_json_file_atomic
from story.file_naming import (
    build_scene_story_filename,
    canonical_chapter_display_name,
    canonical_scene_display_name,
    find_scene_file_by_identity,
    strip_story_filename_meta,
)


AUTO_WRITE_STATE_FILENAME = "auto_write_state.json"
STALE_AUTO_WRITE_STATUSES = {"running", "chapter_paused"}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sanitize_name(name: str, fallback: str = "未命名") -> str:
    """通用文件名安全处理：去除特殊字符。"""
    safe = str(name or "").strip() or fallback
    return (
        safe.replace(":", "")
        .replace("：", "")
        .replace("/", "_")
        .replace("\\", "_")
        .replace("|", "_")
    )


def sanitize_chapter_title(title: str) -> str:
    return _sanitize_name(title, "未命名章节")


def sanitize_scene_title(title: str) -> str:
    return _sanitize_name(title, "未命名场景")


def normalize_planned_scene_title(chapter_num: int, scene_idx: int, scene_title: str) -> str:
    """状态预览保持可用；命名错误由生成链路正式阻断。"""
    try:
        chapter = int(chapter_num)
        scene = int(scene_idx) + 1
    except (TypeError, ValueError):
        return "?-? 命名无效"
    try:
        return canonical_scene_display_name(scene_title, chapter, scene)
    except (TypeError, ValueError):
        return f"{chapter}-{scene} 命名无效"


def normalize_planned_chapter_title(chapter_num: int, chapter_title: str) -> str:
    """按大纲索引生成稳定章节显示名。"""
    try:
        return canonical_chapter_display_name(chapter_title, int(chapter_num))
    except (TypeError, ValueError):
        return "? · 命名无效"


def build_chapter_output_filename(chapter_title: str, export_format: str = "arc") -> str:
    """章节级别文件命名（兜底用，正常情况使用 build_scene_output_filename）。"""
    safe_title = sanitize_chapter_title(chapter_title)
    extension = ".arc" if export_format == "arc" else ".md"
    return f"{safe_title}{extension}"


def build_scene_output_filename(
    chapter_num: int,
    chapter_title: str,
    scene_idx: int,
    scene_title: str,
    export_format: str = "arc",
) -> str:
    """场景级别物理文件命名：显示名 + 隐形排序元数据。"""
    safe_scene = normalize_planned_scene_title(
        int(chapter_num), scene_idx, sanitize_scene_title(scene_title)
    )
    return build_scene_story_filename(
        int(chapter_num),
        int(scene_idx) + 1,
        safe_scene,
        file_format=export_format,
    )


def get_auto_write_state_path(user_id: str, project_name: str) -> str:
    return os.path.join(
        get_project_path(user_id, project_name),
        AUTO_WRITE_STATE_FILENAME,
    )


def default_auto_write_state() -> Dict[str, Any]:
    return {
        "runId": "",
        "status": "idle",
        "mode": "chapter_by_chapter",
        "exportFormat": "arc",
        "requestedStartChapterIndex": 0,
        "requestedStartSceneIndex": 0,
        "totalChapters": 0,
        "totalScenes": 0,
        "currentChapterIndex": None,
        "currentChapterTitle": "",
        "currentSceneIndex": None,
        "currentSceneTitle": "",
        "phase": "",
        "phaseMessage": "",
        "phaseToolName": "",
        "phaseEvent": "",
        "phaseError": "",
        "phaseResult": "",
        "phaseAttempt": 0,
        "phaseMaxAttempts": 0,
        # 调研 / 落盘语义（write_started 置位前一切都是调研）与机器可读失败原因。
        # write_started=True 仅代表“落盘工具已被调用”，落盘本身仍是单次原子写入。
        "writeStarted": False,
        "backendReason": "",
        "backendCode": "",
        # 本场落盘完成后的统计（落盘瞬间计算，非流式测速）：
        # lastSceneChars=本场可见正文字数，lastSceneElapsed=本场耗时秒，
        # lastSceneSpeed=字数/耗时。工具调用是非流式的，不存在逐字测速。
        "lastSceneChars": 0,
        "lastSceneElapsed": 0,
        "lastSceneSpeed": 0,
        "lastScenePreview": "",
        "lastCompletedChapterIndex": None,
        "lastCompletedChapterTitle": "",
        "nextChapterIndex": 0,
        "availableResumeChapterIndex": None,
        "availableResumeSceneIndex": None,
        "availableRestartChapterIndex": None,
        "lastSavedFilename": "",
        "generatedFiles": [],         # 保留兼容（章节级）
        "generatedSceneFiles": [],     # 场景级文件列表
        "lastError": "",
        "startedAt": "",
        "updatedAt": "",
        "completedAt": "",
        # 实时流式统计（SSE 观察者模式下由前端从 progress-stream 获取，
        # 轮询模式下此处提供最近一次更新的快照）
        "streamingPreview": "",
        "streamingSpeed": 0,
        "streamingChars": 0,
        "streamingElapsed": 0,
        # 自动写作后的轻量质量回流信息；不阻断写作，只为后续修订与排查提供状态。
        "autoReviewEnabled": False,
        "fromDirector": False,
        "lastReviewDecision": "",
        "lastReviewGrade": "",
        "lastReviewTarget": "",
        "lastReviewTicketCount": 0,
        "lastReviewError": "",
        # 用户是否已确认该状态（关闭遮罩 / 手动中断后标记为 True，下次不再弹出）
        "acknowledged": False,
    }


def _normalize_state_display_filename(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    directory, filename = os.path.split(raw.replace("\\", "/"))
    visible = strip_story_filename_meta(filename)
    return f"{directory}/{visible}" if directory else visible


def _sanitize_state_display_names(state: Dict[str, Any]) -> Dict[str, Any]:
    state["lastSavedFilename"] = _normalize_state_display_filename(state.get("lastSavedFilename"))
    for key in ("generatedFiles", "generatedSceneFiles"):
        values = state.get(key)
        if isinstance(values, list):
            state[key] = list(dict.fromkeys(
                _normalize_state_display_filename(item) for item in values if str(item or "").strip()
            ))
    return state


def load_auto_write_state(user_id: str, project_name: str) -> Dict[str, Any]:
    state_path = get_auto_write_state_path(user_id, project_name)
    data = load_json_file(state_path, default_auto_write_state) or {}
    state = default_auto_write_state()
    state.update(data)
    return _sanitize_state_display_names(state)


def save_auto_write_state(user_id: str, project_name: str, state: Dict[str, Any]) -> Dict[str, Any]:
    state_path = get_auto_write_state_path(user_id, project_name)
    os.makedirs(os.path.dirname(state_path), exist_ok=True)

    normalized_state = default_auto_write_state()
    normalized_state.update(state or {})
    _sanitize_state_display_names(normalized_state)
    normalized_state["updatedAt"] = _utc_now_iso()

    save_json_file_atomic(state_path, normalized_state)

    return normalized_state


def patch_auto_write_state(user_id: str, project_name: str, **fields: Any) -> Dict[str, Any]:
    state_path = get_auto_write_state_path(user_id, project_name)
    with json_state_lock(state_path):
        state = load_auto_write_state(user_id, project_name)
        state.update(fields)
        return save_auto_write_state(user_id, project_name, state)


def repair_stale_auto_write_states(userdata_root: str | None = None) -> int:
    """把进程退出遗留的活跃状态原子修正为可恢复的中断状态。"""
    if userdata_root is None:
        from core import utils as core_utils

        userdata_root = core_utils.USERDATA_ROOT

    root = os.path.abspath(userdata_root)
    if not os.path.isdir(root):
        return 0

    repaired = 0
    for directory, _, filenames in os.walk(root):
        if AUTO_WRITE_STATE_FILENAME not in filenames:
            continue
        state_path = os.path.join(directory, AUTO_WRITE_STATE_FILENAME)
        with json_state_lock(state_path):
            state = load_json_file(state_path, default_auto_write_state)
            if not isinstance(state, dict) or state.get("status") not in STALE_AUTO_WRITE_STATUSES:
                continue
            state["status"] = "interrupted"
            state["lastError"] = "服务进程已退出，原自动写作线程无法继续；可从已保存进度恢复。"
            state["updatedAt"] = _utc_now_iso()
            save_json_file_atomic(state_path, state)
            repaired += 1
    return repaired


def begin_auto_write_run(
    user_id: str,
    project_name: str,
    *,
    mode: str,
    export_format: str,
    start_chapter_index: int,
    start_scene_index: int = 0,
    total_chapters: int = 0,
    total_scenes: int = 0,
    from_director: bool = False,
) -> Dict[str, Any]:
    run_id = str(uuid.uuid4())
    return save_auto_write_state(
        user_id,
        project_name,
        {
            "runId": run_id,
            "status": "running",
            "mode": mode,
            "exportFormat": export_format,
            "requestedStartChapterIndex": start_chapter_index,
            "requestedStartSceneIndex": start_scene_index,
            "totalChapters": total_chapters,
            "totalScenes": total_scenes,
            "fromDirector": from_director,
            "currentChapterIndex": None,
            "currentChapterTitle": "",
            "currentSceneIndex": None,
            "currentSceneTitle": "",
            "phase": "",
            "phaseMessage": "",
            "phaseToolName": "",
            "lastCompletedChapterIndex": None,
            "lastCompletedChapterTitle": "",
            "nextChapterIndex": start_chapter_index,
            "availableResumeChapterIndex": start_chapter_index,
            "availableResumeSceneIndex": start_scene_index,
            "availableRestartChapterIndex": start_chapter_index,
            "lastSavedFilename": "",
            "generatedFiles": [],
            "lastError": "",
            "lastReviewDecision": "",
            "lastReviewGrade": "",
            "lastReviewTarget": "",
            "lastReviewTicketCount": 0,
            "lastReviewError": "",
            "startedAt": _utc_now_iso(),
            "completedAt": "",
            "acknowledged": False,
        },
    )


def build_auto_write_chapter_plan(
    user_id: str,
    project_name: str,
    outline: Dict[str, Any],
    export_format: str = "arc",
) -> List[Dict[str, Any]]:
    """构建章节级状态计划，供恢复操作与覆盖预览使用。"""
    stories_path = get_project_stories_path(user_id, project_name)
    chapter_nodes = [node for node in (outline.get("nodes") or []) if node.get("type") == "chapter"]
    plan: List[Dict[str, Any]] = []

    for index, chapter in enumerate(chapter_nodes):
        chapter_num = chapter.get("chapter", index + 1)
        chapter_title = normalize_planned_chapter_title(
            chapter_num, chapter.get("title", f"Chapter {chapter_num}")
        )
        # 判断是否存在该章任意一个场景文件
        scenes = chapter.get("children", [])
        any_exists = False
        from agents.tools.scriptwriter import _ensure_chapter_dir
        chapter_dir = _ensure_chapter_dir(stories_path, chapter_title)
        for s_idx, scene in enumerate(scenes):
            scene_title = normalize_planned_scene_title(
                int(chapter_num), s_idx, scene.get("title", f"场景 {s_idx + 1}")
            )
            fn = build_scene_output_filename(chapter_num, chapter_title, s_idx, scene_title, export_format)
            existing_path, _ = find_scene_file_by_identity(
                stories_path,
                int(chapter_num),
                int(s_idx) + 1,
                file_format=export_format,
            )
            if existing_path or os.path.exists(os.path.join(chapter_dir, fn)):
                any_exists = True
                break
        plan.append(
            {
                "chapterIndex": index,
                "chapterNumber": chapter_num,
                "chapterTitle": chapter_title,
                "filename": (
                    strip_story_filename_meta(
                        build_scene_output_filename(
                            chapter_num,
                            chapter_title,
                            0,
                            scenes[0].get("title", "场景1") if scenes else "场景1",
                            export_format,
                        )
                    )
                    if scenes
                    else build_chapter_output_filename(chapter_title, export_format)
                ),
                "exists": any_exists,
            }
        )

    return plan


def build_auto_write_scene_plan(
    user_id: str,
    project_name: str,
    outline: Dict[str, Any],
    export_format: str = "arc",
) -> List[Dict[str, Any]]:
    """场景级 plan，返回所有章节下每个场景的独立文件信息。"""
    stories_path = get_project_stories_path(user_id, project_name)
    chapter_nodes = [node for node in (outline.get("nodes") or []) if node.get("type") == "chapter"]
    plan: List[Dict[str, Any]] = []

    for ch_idx, chapter in enumerate(chapter_nodes):
        chapter_num = chapter.get("chapter", ch_idx + 1)
        chapter_title = normalize_planned_chapter_title(
            chapter_num, chapter.get("title", f"Chapter {chapter_num}")
        )
        scenes = chapter.get("children", [])
        for s_idx, scene in enumerate(scenes):
            scene_title = normalize_planned_scene_title(
                int(chapter_num), s_idx, scene.get("title", f"场景 {s_idx + 1}")
            )
            from agents.tools.scriptwriter import _ensure_chapter_dir
            chapter_dir = _ensure_chapter_dir(stories_path, chapter_title)
            filename = build_scene_output_filename(chapter_num, chapter_title, s_idx, scene_title, export_format)
            existing_path, _ = find_scene_file_by_identity(
                stories_path,
                int(chapter_num),
                int(s_idx) + 1,
                file_format=export_format,
            )
            file_path = existing_path or os.path.join(chapter_dir, filename)
            plan.append(
                {
                    "chapterIndex": ch_idx,
                    "chapterNumber": chapter_num,
                    "chapterTitle": chapter_title,
                    "sceneIndex": s_idx,
                    "sceneTitle": scene_title,
                    "filename": strip_story_filename_meta(os.path.basename(file_path)),
                    "exists": os.path.exists(file_path),
                }
            )

    return plan


def build_auto_write_state_payload(
    user_id: str,
    project_name: str,
    outline: Dict[str, Any],
    export_format: str = "arc",
) -> Dict[str, Any]:
    state = load_auto_write_state(user_id, project_name)
    effective_format = export_format or state.get("exportFormat") or "arc"
    chapter_plan = build_auto_write_chapter_plan(
        user_id, project_name, outline, export_format=effective_format,
    )
    scene_plan = build_auto_write_scene_plan(
        user_id, project_name, outline, export_format=effective_format,
    )
    resumable = state.get("status") in {"running", "chapter_paused", "interrupted", "error"}
    total_chapters = state.get("totalChapters") or len(chapter_plan)
    total_scenes = state.get("totalScenes") or sum(
        len(ch.get("children") or [])
        for ch in (outline.get("nodes") or [])
        if ch.get("type") == "chapter"
    )
    # ── completedScenes 计算策略 ──
    # 活跃轮次（running / chapter_paused）：使用 generatedSceneFiles 计数，
    # 避免磁盘上旧文件导致进度条提前到 100%。
    # complete：强制等于 totalScenes，保证前端进度条精确到顶。
    # 其他状态（idle / interrupted / error）：回退到磁盘文件存在性。
    status = state.get("status", "idle")
    if status == "complete":
        completed_scenes = total_scenes
    elif status in ("running", "chapter_paused"):
        completed_scenes = len(state.get("generatedSceneFiles") or [])
    else:
        completed_scenes = sum(1 for s in scene_plan if s.get("exists"))

    return {
        **state,
        # 前端期望字段（直接在 state 顶层）
        "totalChapters": total_chapters,
        "totalScenes": total_scenes,
        "completedScenes": completed_scenes,
        # 向下兼容字段
        "chapterFiles": chapter_plan,
        "chapterCount": len(chapter_plan),
        "sceneFiles": scene_plan,
        "resumable": resumable,
    }
