"""兼容入口：项目上下文能力已下沉到 ``agents.project_context``。"""

from agents.project_context import (
    build_scene_context,
    build_scriptwriter_context,
    build_scriptwriter_handoff_context,
    build_story_tags_hint,
    format_outline_scene_contract,
    get_current_beat,
    load_all_roles,
    load_beats_data,
    load_character_bundle,
    load_full_outline,
    load_narrative_memory,
    load_outline_data,
    load_project_context_bundle,
    load_synopsis_data,
    load_worldview,
    resolve_outline_scene_contract,
    resolve_outline_scene_contract_for_task,
)


__all__ = [
    "build_scene_context",
    "build_scriptwriter_context",
    "build_scriptwriter_handoff_context",
    "build_story_tags_hint",
    "format_outline_scene_contract",
    "get_current_beat",
    "load_all_roles",
    "load_beats_data",
    "load_character_bundle",
    "load_full_outline",
    "load_narrative_memory",
    "load_outline_data",
    "load_project_context_bundle",
    "load_synopsis_data",
    "load_worldview",
    "resolve_outline_scene_contract",
    "resolve_outline_scene_contract_for_task",
]
