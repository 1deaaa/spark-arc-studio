"""兼容入口：自动写作状态能力已下沉到 ``agents.auto_write_state``。"""

from agents.auto_write_state import (
    AUTO_WRITE_STATE_FILENAME,
    STALE_AUTO_WRITE_STATUSES,
    begin_auto_write_run,
    build_auto_write_chapter_plan,
    build_auto_write_scene_plan,
    build_auto_write_state_payload,
    build_chapter_output_filename,
    build_scene_output_filename,
    default_auto_write_state,
    get_auto_write_state_path,
    load_auto_write_state,
    normalize_planned_chapter_title,
    normalize_planned_scene_title,
    patch_auto_write_state,
    repair_stale_auto_write_states,
    sanitize_chapter_title,
    sanitize_scene_title,
    save_auto_write_state,
)


__all__ = [
    "AUTO_WRITE_STATE_FILENAME",
    "STALE_AUTO_WRITE_STATUSES",
    "begin_auto_write_run",
    "build_auto_write_chapter_plan",
    "build_auto_write_scene_plan",
    "build_auto_write_state_payload",
    "build_chapter_output_filename",
    "build_scene_output_filename",
    "default_auto_write_state",
    "get_auto_write_state_path",
    "load_auto_write_state",
    "normalize_planned_chapter_title",
    "normalize_planned_scene_title",
    "patch_auto_write_state",
    "repair_stale_auto_write_states",
    "sanitize_chapter_title",
    "sanitize_scene_title",
    "save_auto_write_state",
]
