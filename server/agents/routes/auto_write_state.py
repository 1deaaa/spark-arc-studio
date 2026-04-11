from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

from core.utils import get_project_path, get_project_stories_path
from story.file_naming import build_scene_story_filename, strip_story_filename_meta


AUTO_WRITE_STATE_FILENAME = "auto_write_state.json"


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
    safe_scene = sanitize_scene_title(scene_title)
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
        "lastCompletedChapterIndex": None,
        "lastCompletedChapterTitle": "",
        "nextChapterIndex": 0,
        "availableResumeChapterIndex": None,
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
        # 用户是否已确认该状态（关闭遮罩 / 手动中断后标记为 True，下次不再弹出）
        "acknowledged": False,
    }


def load_auto_write_state(user_id: str, project_name: str) -> Dict[str, Any]:
    state_path = get_auto_write_state_path(user_id, project_name)
    if not os.path.exists(state_path):
        return default_auto_write_state()

    try:
        with open(state_path, "r", encoding="utf-8") as f:
            data = json.load(f) or {}
        state = default_auto_write_state()
        state.update(data)
        return state
    except Exception:
        return default_auto_write_state()


def save_auto_write_state(user_id: str, project_name: str, state: Dict[str, Any]) -> Dict[str, Any]:
    state_path = get_auto_write_state_path(user_id, project_name)
    os.makedirs(os.path.dirname(state_path), exist_ok=True)

    normalized_state = default_auto_write_state()
    normalized_state.update(state or {})
    normalized_state["updatedAt"] = _utc_now_iso()

    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(normalized_state, f, ensure_ascii=False, indent=2)

    return normalized_state


def patch_auto_write_state(user_id: str, project_name: str, **fields: Any) -> Dict[str, Any]:
    state = load_auto_write_state(user_id, project_name)
    state.update(fields)
    return save_auto_write_state(user_id, project_name, state)


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
            "currentChapterIndex": None,
            "currentChapterTitle": "",
            "currentSceneIndex": None,
            "currentSceneTitle": "",
            "lastCompletedChapterIndex": None,
            "lastCompletedChapterTitle": "",
            "nextChapterIndex": start_chapter_index,
            "availableResumeChapterIndex": start_chapter_index,
            "availableRestartChapterIndex": start_chapter_index,
            "lastSavedFilename": "",
            "generatedFiles": [],
            "lastError": "",
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
    """章节级 plan（保留向下兼容，供 ScriptGenerationModal 使用）。"""
    stories_path = get_project_stories_path(user_id, project_name)
    chapter_nodes = [node for node in (outline.get("nodes") or []) if node.get("type") == "chapter"]
    plan: List[Dict[str, Any]] = []

    for index, chapter in enumerate(chapter_nodes):
        chapter_num = chapter.get("chapter", index + 1)
        chapter_title = chapter.get("title", f"Chapter {chapter_num}")
        # 判断是否存在该章任意一个场景文件
        scenes = chapter.get("children", [])
        any_exists = False
        for s_idx, scene in enumerate(scenes):
            scene_title = scene.get("title", f"Scene {s_idx + 1}")
            fn = build_scene_output_filename(chapter_num, chapter_title, s_idx, scene_title, export_format)
            if os.path.exists(os.path.join(stories_path, fn)):
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
        chapter_title = chapter.get("title", f"Chapter {chapter_num}")
        scenes = chapter.get("children", [])
        for s_idx, scene in enumerate(scenes):
            scene_title = scene.get("title", f"Scene {s_idx + 1}")
            filename = build_scene_output_filename(chapter_num, chapter_title, s_idx, scene_title, export_format)
            file_path = os.path.join(stories_path, filename)
            plan.append(
                {
                    "chapterIndex": ch_idx,
                    "chapterNumber": chapter_num,
                    "chapterTitle": chapter_title,
                    "sceneIndex": s_idx,
                    "sceneTitle": scene_title,
                    "filename": strip_story_filename_meta(filename),
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
    return {
        **state,
        # 前端期望字段（直接在 state 顶层）
        "totalChapters": total_chapters,
        "totalScenes": total_scenes,
        "completedScenes": sum(1 for s in scene_plan if s.get("exists")),
        # 向下兼容字段
        "chapterFiles": chapter_plan,
        "chapterCount": len(chapter_plan),
        "sceneFiles": scene_plan,
        "resumable": resumable,
    }
