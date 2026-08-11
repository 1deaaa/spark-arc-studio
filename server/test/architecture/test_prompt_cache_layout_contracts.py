from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from agents.agent_utils import load_prompt
from agents.director_graph import _append_director_runtime_user_message
from agents.context_provider import AgentContextProvider


def _assert_in_order(text: str, *markers: str) -> None:
    positions = [text.index(marker) for marker in markers]
    assert positions == sorted(positions)


def test_scriptwriter_stable_project_blocks_precede_scene_dynamic_blocks() -> None:
    values = {
        "story_tags": "MARK_STORY_TAGS",
        "worldview": "MARK_WORLDVIEW",
        "full_outline": "MARK_OUTLINE",
        "chr_reference": "MARK_SPEAKERS",
        "roles": "MARK_ROLES",
        "style_profile": "MARK_STYLE",
        "narrative_memory": "MARK_MEMORY",
        "context": "MARK_CONTEXT",
        "guidance": "MARK_GUIDANCE",
        "feedback": "MARK_FEEDBACK",
        "length_instruction": "MARK_LENGTH",
        "arc_example": "MARK_ARC",
    }

    arc_user = load_prompt("scriptwriter", **values)["user"]
    novel_user = load_prompt("scriptwriter", "generate_novel", **values)["user"]
    expected = (
        "MARK_STORY_TAGS",
        "MARK_WORLDVIEW",
        "MARK_OUTLINE",
        "MARK_ROLES",
        "MARK_STYLE",
        "MARK_MEMORY",
        "MARK_CONTEXT",
        "MARK_GUIDANCE",
        "MARK_FEEDBACK",
    )
    _assert_in_order(arc_user, *expected)
    _assert_in_order(novel_user, *expected)


def test_critic_stable_project_blocks_precede_review_dynamic_blocks() -> None:
    user_prompt = load_prompt(
        "critic",
        story_tags="MARK_STORY_TAGS",
        worldview="MARK_WORLDVIEW",
        roles="MARK_ROLES",
        style_profile="MARK_STYLE",
        review_target="MARK_TARGET",
        context="MARK_CONTEXT",
        guidance="MARK_GUIDANCE",
        script="MARK_SCRIPT",
    )["user"]

    _assert_in_order(
        user_prompt,
        "MARK_STORY_TAGS",
        "MARK_WORLDVIEW",
        "MARK_ROLES",
        "MARK_STYLE",
        "MARK_TARGET",
        "MARK_CONTEXT",
        "MARK_GUIDANCE",
        "MARK_SCRIPT",
    )


def test_showrunner_specialized_prompts_keep_project_canon_before_dynamic_inputs() -> None:
    common = {
        "story_tags": "MARK_STORY_TAGS",
        "worldview": "MARK_WORLDVIEW",
        "roles": "MARK_ROLES",
        "style_profile": "MARK_STYLE",
        "guidance": "MARK_GUIDANCE",
        "length_hint": "MARK_LENGTH",
        "logline": "MARK_LOGLINE",
        "synopsis": "MARK_SYNOPSIS",
        "context": "MARK_CONTEXT",
        "beat_sheet": "MARK_BEATS",
        "chapter_count": "3",
        "scene_count_per_chapter": "3",
    }
    synopsis_user = load_prompt("showrunner", "generate_synopsis", **common)["user"]
    beats_user = load_prompt("showrunner", "generate_beat_sheet", **common)["user"]
    outline_user = load_prompt("showrunner", "generate_outline", **common)["user"]

    stable = ("MARK_STORY_TAGS", "MARK_WORLDVIEW", "MARK_ROLES", "MARK_STYLE")
    _assert_in_order(synopsis_user, *stable, "MARK_LOGLINE", "MARK_GUIDANCE")
    _assert_in_order(beats_user, *stable, "MARK_SYNOPSIS", "MARK_GUIDANCE")
    _assert_in_order(outline_user, *stable, "MARK_CONTEXT", "MARK_BEATS", "MARK_GUIDANCE")


def test_director_runtime_context_is_appended_without_rewriting_history_prefix() -> None:
    original_messages = [
        SystemMessage(content="STABLE_SYSTEM"),
        HumanMessage(content="ORIGINAL_USER"),
        AIMessage(content="DELEGATION_RESULT"),
    ]

    updated = _append_director_runtime_user_message(
        original_messages,
        current_user_message="ORIGINAL_USER",
        active_context="PROJECT_STATE_V2",
        runtime_tail="WORK_TRACKER_V2",
    )

    assert [message.content for message in updated[:3]] == [
        "STABLE_SYSTEM",
        "ORIGINAL_USER",
        "DELEGATION_RESULT",
    ]
    assert isinstance(updated[-1], HumanMessage)
    assert "PROJECT_STATE_V2" in updated[-1].content
    assert "WORK_TRACKER_V2" in updated[-1].content
    assert original_messages[1].content == "ORIGINAL_USER"


def test_showrunner_full_outline_precedes_scene_varying_narrative_memory(monkeypatch) -> None:
    provider = AgentContextProvider("cache-user", "cache-project")
    provider._bundle_cache = {
        "worldview": "MARK_WORLDVIEW",
        "roles": "MARK_ROLES",
        "full_outline": "MARK_OUTLINE",
        "narrative_memory": "MARK_MEMORY",
        "structure_state": {"status": "stale"},
    }
    monkeypatch.setattr("agents.context_provider.get_project_story_tags", lambda *_args: {})
    monkeypatch.setattr("agents.context_provider.build_story_tags_hint", lambda _tags: "")
    monkeypatch.setattr(
        "agents.structure_state.format_structure_state_warning",
        lambda _state: "MARK_STRUCTURE_WARNING",
    )
    monkeypatch.setattr(provider, "get_scene_list", lambda: "")

    context = provider.build_context_for_agent(
        "agent_showrunner",
        extra_context="MARK_CURRENT_EDITOR",
    )
    _assert_in_order(
        context,
        "MARK_WORLDVIEW",
        "MARK_ROLES",
        "MARK_OUTLINE",
        "MARK_MEMORY",
        "MARK_STRUCTURE_WARNING",
        "MARK_CURRENT_EDITOR",
    )
