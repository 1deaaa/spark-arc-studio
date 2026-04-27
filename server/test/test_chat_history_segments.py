from pathlib import Path
import sys
import threading


SERVER_ROOT = Path(__file__).resolve().parents[1]
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))


from agents.routes.chat_persistence import _collect_segment_from_event
from agents.routes.chat_task import ChatTaskEntry


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


def test_collect_segments_coalesces_streamed_tool_chunks_with_changing_keys():
    segments = []
    invocation_counter = [0]

    _collect_segment_from_event(
        segments,
        invocation_counter,
        {"event": "tool_intent_started", "tool_name": "patch_outline", "source_agent": "agent_showrunner", "tool_call_key": "chunk-name"},
        now_ts=1000.0,
    )
    _collect_segment_from_event(
        segments,
        invocation_counter,
        {"event": "tool_intent_started", "tool_name": "patch_outline", "source_agent": "agent_showrunner", "tool_call_key": "chunk-args"},
        now_ts=1000.1,
    )
    _collect_segment_from_event(
        segments,
        invocation_counter,
        {"event": "tool_exec_started", "tool_name": "patch_outline", "source_agent": "agent_showrunner", "tool_call_key": "agent_showrunner:patch_outline:0"},
        now_ts=1000.2,
    )
    _collect_segment_from_event(
        segments,
        invocation_counter,
        {"event": "tool_exec_finished", "tool_name": "patch_outline", "source_agent": "agent_showrunner", "tool_call_key": "agent_showrunner:patch_outline:0"},
        now_ts=1001.0,
    )

    tool_segments = [seg for seg in segments if seg.get("type") == "tool_trace"]
    assert len(tool_segments) == 1
    assert tool_segments[0]["status"] == "finished"
    assert tool_segments[0]["tool_name"] == "patch_outline"
    assert tool_segments[0]["duration"] == 1.0


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


def test_chat_task_metadata_includes_llm_usage():
    entry = ChatTaskEntry(
        task_key="u:p:agent_director:global",
        user_id="u",
        project_name="p",
        agent_id="agent_director",
        context_key="global",
        stop_event=threading.Event(),
        status="completed",
        started_at=1.0,
    )
    entry.append_event({"event": "assistant_delta", "text": "完成"})
    entry.llm_usage = {
        "prompt_tokens": 100,
        "completion_tokens": 20,
        "total_tokens": 120,
        "requests": 1,
        "errors": 0,
        "source": "usage_log",
    }

    metadata = entry.build_metadata(stream_status="completed")
    snapshot = entry.build_snapshot()

    assert metadata["llm_usage"]["total_tokens"] == 120
    assert snapshot["metadata"]["llm_usage"]["total_tokens"] == 120

