from __future__ import annotations

from agents.agent_tools import TOOLS_BY_NAME as FACADE_TOOLS_BY_NAME
from agents.agent_tools import get_tools_for_agent as facade_get_tools_for_agent
from agents.skill_packs import import_skill_markdown
from agents.tools.registry import ALL_TOOLS, TOOLS_BY_NAME, get_tools_for_agent
from agents.tools.stream_events import build_tool_stream_event, get_tool_ui_binding, normalize_tool_name


CORE_AGENT_IDS = {
    "agent_director",
    "agent_muse",
    "agent_lorebook",
    "agent_showrunner",
    "agent_scriptwriter",
    "agent_critic",
    "agent_style",
}


def tool_names(agent_id: str, user_id: str | None = None) -> set[str]:
    return {tool.name for tool in get_tools_for_agent(agent_id, user_id=user_id)}


def test_tool_registry_has_stable_unique_truth_source() -> None:
    all_names = [tool.name for tool in ALL_TOOLS]
    assert all_names
    assert set(all_names) == set(TOOLS_BY_NAME)
    assert FACADE_TOOLS_BY_NAME is TOOLS_BY_NAME
    assert facade_get_tools_for_agent is get_tools_for_agent


def test_core_agent_tool_boundaries() -> None:
    assert "delegate_task" in tool_names("agent_director")
    assert "rewrite_inspiration" in tool_names("agent_muse")
    assert {"rewrite_worldview", "rewrite_all_characters", "update_character"} <= tool_names("agent_lorebook")
    assert {"rewrite_synopsis", "rewrite_beat_sheet", "rewrite_outline"} <= tool_names("agent_showrunner")
    assert {"create_chapter", "create_or_rewrite_script", "patch_script"} <= tool_names("agent_scriptwriter")
    assert "delegate_task" not in tool_names("agent_scriptwriter")
    assert "delegate_task" not in tool_names("agent_critic")
    assert tool_names("agent_style") == set()


def test_story_format_is_not_exposed_as_tool_switch() -> None:
    from agents.tools.automation import CheckScriptwriterStatusInput, TriggerAutoWriteInput
    from agents.tools.scriptwriter import CreateOrRewriteScriptInput

    assert "export_format" not in TriggerAutoWriteInput.model_fields
    assert "export_format" not in CheckScriptwriterStatusInput.model_fields
    assert "export_format" not in CreateOrRewriteScriptInput.model_fields


def test_skill_tools_are_exposed_only_when_user_has_skills(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("agents.skill_packs.USERDATA_ROOT", str(tmp_path))

    skill_tools = {"search_skills", "read_skill", "read_skill_reference"}
    assert skill_tools.isdisjoint(tool_names("agent_director", user_id="42"))

    import_skill_markdown(
        "42",
        """---
name: Precise Style
description: Helps line-level prose quality.
---
# Precise Style

## Quality
Use specific verbs.
""",
    )

    for agent_id in {"agent_director", "agent_muse", "agent_lorebook", "agent_showrunner", "agent_scriptwriter", "agent_critic"}:
        assert skill_tools <= tool_names(agent_id, user_id="42")


def test_get_tools_for_agent_is_defined_for_every_core_agent() -> None:
    for agent_id in CORE_AGENT_IDS:
        tools = get_tools_for_agent(agent_id)
        assert isinstance(tools, list)
        assert all(getattr(tool, "name", "") for tool in tools)


def test_tool_stream_event_injects_ui_metadata_from_backend_binding() -> None:
    evt = build_tool_stream_event(
        "tool_exec_started",
        "rewrite_worldview",
        source_agent="agent_lorebook",
        tool_call_key="call-1",
    )

    assert evt["tool_name"] == "rewrite_worldview"
    assert evt["ui_scope"] == "world"
    assert evt["ui_target"] == "worldview"
    assert "lorebook-refresh-worldview" in evt["ui_refresh_events"]

    tags_evt = build_tool_stream_event("tool_exec_started", "update story tags")
    assert tags_evt["tool_name"] == "update_project_story_tags"
    assert tags_evt["ui_scope"] == "story-tags"
    assert "story-tags-refresh" in tags_evt["ui_refresh_events"]


def test_tool_name_aliases_match_ui_binding_normalization() -> None:
    assert normalize_tool_name("rewrite-worldview") == "rewrite_worldview"
    assert normalize_tool_name("rewrite characters") == "rewrite_all_characters"
    assert normalize_tool_name("update story tags") == "update_project_story_tags"
    assert get_tool_ui_binding("rewrite characters")["target"] == "characters"
