from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

from core.utils import get_project_path, get_project_stories_path


AUTO_WRITE_STATE_FILENAME = "auto_write_state.json"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def sanitize_chapter_title(title: str) -> str:
    safe_title = str(title or "").strip() or "未命名章节"
    return (
        safe_title.replace(":", "")
        .replace("：", "")
        .replace("/", "_")
        .replace("\\", "_")
    )


def build_chapter_output_filename(chapter_title: str, export_format: str = "arc") -> str:
    safe_title = sanitize_chapter_title(chapter_title)
    extension = ".arc" if export_format == "arc" else ".md"
    return f"{safe_title}{extension}"


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
        "generatedFiles": [],
        "lastError": "",
        "startedAt": "",
        "updatedAt": "",
        "completedAt": "",
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
        },
    )


def build_auto_write_chapter_plan(
    user_id: str,
    project_name: str,
    outline: Dict[str, Any],
    export_format: str = "arc",
) -> List[Dict[str, Any]]:
    stories_path = get_project_stories_path(user_id, project_name)
    chapter_nodes = [node for node in (outline.get("nodes") or []) if node.get("type") == "chapter"]
    plan: List[Dict[str, Any]] = []

    for index, chapter in enumerate(chapter_nodes):
        chapter_num = chapter.get("chapter", index + 1)
        chapter_title = chapter.get("title", f"Chapter {chapter_num}")
        filename = build_chapter_output_filename(chapter_title, export_format)
        file_path = os.path.join(stories_path, filename)
        plan.append(
            {
                "chapterIndex": index,
                "chapterNumber": chapter_num,
                "chapterTitle": chapter_title,
                "filename": filename,
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
    chapter_plan = build_auto_write_chapter_plan(
        user_id,
        project_name,
        outline,
        export_format=export_format or state.get("exportFormat") or "arc",
    )
    resumable = state.get("status") in {"running", "chapter_paused", "interrupted", "error"}
    return {
        **state,
        "chapterFiles": chapter_plan,
        "chapterCount": len(chapter_plan),
        "resumable": resumable,
    }