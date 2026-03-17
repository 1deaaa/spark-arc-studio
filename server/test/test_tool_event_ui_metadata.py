from agents.communication import build_tool_stream_event, get_tool_ui_binding


def test_get_tool_ui_binding_matches_worldview_rewrite_panel():
    binding = get_tool_ui_binding("rewrite_worldview")

    assert binding == {
        "scope": "world",
        "target": "worldview",
        "refresh_events": ["lorebook-refresh-worldview", "lorebook-refresh"],
    }


def test_build_tool_stream_event_includes_ui_metadata_and_call_key():
    evt = build_tool_stream_event(
        "tool_exec_started",
        "rewrite_worldview",
        source_agent="agent_lorebook",
        message="正在重写世界观设定...",
        tool_call_key="call_worldview_1",
    )

    assert evt["event"] == "tool_exec_started"
    assert evt["tool_name"] == "rewrite_worldview"
    assert evt["source_agent"] == "agent_lorebook"
    assert evt["message"] == "正在重写世界观设定..."
    assert evt["tool_call_key"] == "call_worldview_1"
    assert evt["ui_scope"] == "world"
    assert evt["ui_target"] == "worldview"
    assert evt["ui_refresh_events"] == ["lorebook-refresh-worldview", "lorebook-refresh"]
