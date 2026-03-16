from pathlib import Path
import sys


SERVER_ROOT = Path(__file__).resolve().parents[1]
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))


from agents.routes.chat import _collect_segment_from_event


def test_collect_segments_upgrades_single_tool_call_without_duplicate_segment():
    segments = []
    invocation_counter = [0]

    _collect_segment_from_event(
        segments,
        invocation_counter,
        {"event": "tool_intent_started", "tool_name": "delegate_task", "source_agent": "agent_director"},
        now_ts=1000.0,
    )
    _collect_segment_from_event(
        segments,
        invocation_counter,
        {"event": "tool_exec_started", "tool_name": "delegate_task", "source_agent": "agent_director"},
        now_ts=1000.2,
    )
    _collect_segment_from_event(
        segments,
        invocation_counter,
        {"event": "tool_exec_finished", "tool_name": "delegate_task", "source_agent": "agent_director"},
        now_ts=1000.8,
    )

    tool_segments = [seg for seg in segments if seg.get("type") == "tool_trace"]
    assert len(tool_segments) == 1
    assert tool_segments[0]["status"] == "finished"
    assert tool_segments[0]["source_agent"] == "agent_director"
    assert tool_segments[0]["duration"] == 0.8


def test_collect_segments_preserves_source_agent_for_reasoning_and_text_boundaries():
    segments = []
    invocation_counter = [0]

    _collect_segment_from_event(
        segments,
        invocation_counter,
        {"event": "reasoning_delta", "text": "导演思考1", "source_agent": "agent_director"},
    )
    _collect_segment_from_event(
        segments,
        invocation_counter,
        {"event": "reasoning_delta", "text": "导演思考2", "source_agent": "agent_director"},
    )
    _collect_segment_from_event(
        segments,
        invocation_counter,
        {"event": "assistant_delta", "text": "导演回复", "source_agent": "agent_director"},
    )
    _collect_segment_from_event(
        segments,
        invocation_counter,
        {"event": "assistant_delta", "text": "专家回复", "source_agent": "agent_muse"},
    )

    assert segments[0] == {
        "type": "reasoning",
        "text": "导演思考1导演思考2",
        "source_agent": "agent_director",
    }
    assert segments[1] == {
        "type": "text",
        "text": "导演回复",
        "source_agent": "agent_director",
    }
    assert segments[2] == {
        "type": "text",
        "text": "专家回复",
        "source_agent": "agent_muse",
    }

