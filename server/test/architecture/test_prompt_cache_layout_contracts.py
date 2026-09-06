from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from agents.agent_utils import load_prompt
from agents.director_graph import _append_director_runtime_user_message
from agents.context_provider import AgentContextProvider
from agents.agent_director import DirectorAgent
from agents.communication import SparkBaseAgent
from agents.prompt_layout import BoundedPromptTranscript, CompletedPromptTurn
from agents.registry import AGENT_REGISTRY
from agents.tools.registry import SHOWRUNNER_BASE_TOOLS, _showrunner_runtime_tools


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


def test_director_runtime_context_does_not_duplicate_unchanged_tail() -> None:
    original_messages = [
        SystemMessage(content="STABLE_SYSTEM"),
        HumanMessage(content="ORIGINAL_USER"),
    ]
    first = _append_director_runtime_user_message(
        original_messages,
        current_user_message="ORIGINAL_USER",
        active_context="PROJECT_STATE_V1",
        runtime_tail="WORK_TRACKER_V1",
    )
    unchanged = _append_director_runtime_user_message(
        first,
        current_user_message="ORIGINAL_USER",
        active_context="PROJECT_STATE_V1",
        runtime_tail="WORK_TRACKER_V1",
        previous_runtime_message=first[-1].content,
    )
    changed = _append_director_runtime_user_message(
        unchanged,
        current_user_message="ORIGINAL_USER",
        active_context="PROJECT_STATE_V2",
        runtime_tail="WORK_TRACKER_V2",
        previous_runtime_message=first[-1].content,
    )

    assert unchanged == first
    assert changed[:-1] == first
    assert "PROJECT_STATE_V2" in changed[-1].content


def test_dynamic_date_is_in_runtime_tail_not_system_prefix() -> None:
    from agents.tools.registry import TOOLS_BY_NAME

    agent = SparkBaseAgent("agent_director", user_id="cache-user", project_name="demo")
    tools = [TOOLS_BY_NAME["web_search"]]
    system = agent._build_tool_system_prompt("STABLE_SYSTEM", tools_override=tools)
    runtime_tail = agent._build_runtime_tail(tools_override=tools)

    assert "当前真实日期（UTC+8）：" not in system
    assert "当前真实日期（UTC+8）：" in runtime_tail


def test_context_compaction_facade_does_not_expose_a_dedicated_model_binding() -> None:
    utility_entry = next(item for item in AGENT_REGISTRY if item["key"] == "agent_utility")

    assert utility_entry["visibleInModelBinding"] is False
    assert "所属 Agent" in utility_entry["description"]["zh-CN"]


def test_director_team_block_does_not_depend_on_runtime_tool_sets(monkeypatch) -> None:
    monkeypatch.setattr(
        "agents.tools.registry.get_tools_for_agent",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("不应读取动态工具集")),
    )
    block = DirectorAgent(user_id="cache-user", project_name="demo")._build_team_capability_block()

    assert "团队成员能力概览" in block
    assert "agent_lorebook" in block
    assert "rewrite_worldview" not in block


def test_showrunner_tool_schema_does_not_change_after_story_is_written() -> None:
    assert [tool.name for tool in _showrunner_runtime_tools("cache-user")] == [
        tool.name for tool in SHOWRUNNER_BASE_TOOLS
    ]


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


def test_bounded_prompt_transcript_drops_only_hot_history_and_resets_rewrites() -> None:
    transcript = BoundedPromptTranscript(max_turns=2, max_streams=2)
    for index in range(3):
        transcript.append(
            "project-a",
            turn_id=f"scene-{index}",
            turn=CompletedPromptTurn(
                user_prompt=f"user-{index}",
                assistant_receipt=f"assistant-{index}",
            ),
        )

    retained = transcript.load("project-a", current_turn_id="scene-new")
    assert [turn.user_prompt for turn in retained] == ["user-1", "user-2"]
    assert transcript.load("project-a", current_turn_id="scene-2") == ()


def test_append_only_task_messages_preserve_bounded_tool_exchange_before_receipt() -> None:
    from agents.prompt_layout import build_append_only_task_messages

    messages = build_append_only_task_messages(
        system_prompt="STABLE_SYSTEM",
        completed_turns=(CompletedPromptTurn(
            user_prompt="SCENE_ONE",
            preserved_messages=(
                AIMessage(content="", tool_calls=[{
                    "name": "create_chapter",
                    "args": {"chapter_name": "一 · 开端"},
                    "id": "chapter-1",
                    "type": "tool_call",
                }]),
                ToolMessage(
                    content="已存在",
                    tool_call_id="chapter-1",
                    name="create_chapter",
                ),
            ),
            assistant_receipt="SCENE_ONE_RECEIPT",
        ),),
        current_user_prompt="SCENE_TWO",
    )

    assert [message.type for message in messages] == [
        "system", "human", "ai", "tool", "ai", "human"
    ]
    assert messages[2].tool_calls[0]["name"] == "create_chapter"
    assert messages[4].content == "SCENE_ONE_RECEIPT"
    assert messages[-1].content == "SCENE_TWO"


def test_longread_collapse_only_touches_stale_windows() -> None:
    """滑窗折叠只折旧 user 轮次窗口：前缀稳定不断裂。"""
    from agents.longread import collapse_longread_tool_history

    messages = [
        SystemMessage(content="STABLE_SYSTEM"),
        HumanMessage(content="OLD_QUESTION"),
        ToolMessage(
            content='[source_id="att-1" chunk_index=0]\n旧窗口原文',
            tool_call_id="old-window",
            name="read_longread_window",
        ),
        HumanMessage(content="NEW_QUESTION"),
        ToolMessage(
            content='[source_id="att-1" chunk_index=1]\n本轮窗口原文',
            tool_call_id="fresh-window",
            name="read_longread_window",
        ),
    ]

    collapsed = collapse_longread_tool_history(messages, fresh_call_ids={"fresh-window"})

    assert collapsed == 1
    assert messages[0].content == "STABLE_SYSTEM"
    assert messages[1].content == "OLD_QUESTION"
    assert "本轮窗口原文" in messages[4].content
