from typing import Any, Dict


def normalize_tool_name(raw_tool_name: str = "") -> str:
    normalized = str(raw_tool_name or "").strip().lower()
    if not normalized:
        return ""
    key = normalized.replace(" ", "").replace("_", "").replace("-", "")
    aliases = {
        "rewriteworldview": "rewrite_worldview",
        "rewriteallcharacters": "rewrite_all_characters",
        "rewritecharacters": "rewrite_all_characters",
        "rewritecharacter": "update_character",
        "updatecharacter": "update_character",
    }
    return aliases.get(key, normalized)


def get_tool_ui_binding(tool_name: str) -> Dict[str, Any]:
    normalized = normalize_tool_name(tool_name)
    if normalized == "rewrite_inspiration":
        return {
            "scope": "muse",
            "target": "",
            "refresh_events": ["muse-refresh"],
        }

    if normalized in {"rewrite_worldview", "rewrite_all_characters", "update_character"}:
        target = "worldview" if normalized == "rewrite_worldview" else "characters"
        refresh_events = ["lorebook-refresh"]
        if target == "worldview":
            refresh_events.insert(0, "lorebook-refresh-worldview")
        if target == "characters":
            refresh_events.insert(0, "lorebook-refresh-characters")
        return {
            "scope": "world",
            "target": target,
            "refresh_events": refresh_events,
        }

    if normalized in {"rewrite_outline", "patch_outline"}:
        return {
            "scope": "outline",
            "target": "",
            "refresh_events": ["outline-refresh"],
        }

    if normalized == "read_chapter_outline_raw":
        return {
            "scope": "outline",
            "target": "",
            "refresh_events": [],
        }

    if normalized in {"rewrite_synopsis", "patch_synopsis"}:
        return {
            "scope": "synopsis",
            "target": "content",
            "refresh_events": ["synopsis-refresh"],
        }

    if normalized in {"rewrite_beat_sheet", "patch_beat_sheet"}:
        return {
            "scope": "synopsis",
            "target": "beats",
            "refresh_events": ["synopsis-refresh"],
        }

    if normalized in {"search_project", "semantic_search", "web_search"}:
        return {
            "scope": "",
            "target": "",
            "refresh_events": [],
        }

    if normalized == "replace_from_search":
        return {
            "scope": "",
            "target": "",
            "refresh_events": [
                "outline-refresh",
                "synopsis-refresh",
                "lorebook-refresh",
                "lorebook-refresh-worldview",
                "lorebook-refresh-characters",
            ],
        }

    return {
        "scope": "",
        "target": "",
        "refresh_events": [],
    }


def build_tool_stream_event(
    event_name: str,
    tool_name: str,
    *,
    source_agent: str = "",
    message: str = "",
    tool_call_key: str = "",
    **extra: Any,
) -> Dict[str, Any]:
    normalized_tool_name = normalize_tool_name(tool_name)
    payload: Dict[str, Any] = {
        "event": str(event_name or "").strip(),
        "tool_name": normalized_tool_name,
    }
    if source_agent:
        payload["source_agent"] = source_agent
    if message:
        payload["message"] = message
    if tool_call_key:
        payload["tool_call_key"] = tool_call_key

    binding = get_tool_ui_binding(normalized_tool_name)
    if binding.get("scope"):
        payload["ui_scope"] = binding["scope"]
    if binding.get("target"):
        payload["ui_target"] = binding["target"]
    if binding.get("refresh_events"):
        payload["ui_refresh_events"] = list(binding["refresh_events"])

    payload.update(extra)
    return payload
