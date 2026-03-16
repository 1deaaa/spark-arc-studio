from pathlib import Path
import sys


SERVER_ROOT = Path(__file__).resolve().parents[1]
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))


from agents.communication import (
    HANDOFF_CONFIRMATION_CONFIRMED,
    HANDOFF_CONFIRMATION_PENDING,
    HANDOFF_DELIVERY_DIRECT_TO_USER,
    HANDOFF_DELIVERY_RETURN_TO_DIRECTOR,
    SparkBaseAgent,
    CommunicationContext,
    normalize_handoff_payload,
    transfer_baton,
)
from agents.director_graph import route_after_sub_agent


def test_normalize_handoff_payload_uses_protocol_defaults():
    payload = normalize_handoff_payload(
        {
            "target_agent": "agent_muse",
            "task_description": "重写灵感",
        },
        sender_id="agent_director",
    )

    assert payload["target_agent"] == "agent_muse"
    assert payload["delivery_mode"] == HANDOFF_DELIVERY_DIRECT_TO_USER
    assert payload["grant_baton_to"] == "agent_muse"
    assert payload["return_to"] == "agent_director"
    assert payload["user_confirmation_state"] == HANDOFF_CONFIRMATION_PENDING
    assert payload["skip_tool_confirmation"] is False
    assert payload["task_id"]


def test_normalize_handoff_payload_enables_skip_when_upstream_already_confirmed():
    payload = normalize_handoff_payload(
        {
            "target_agent": "agent_showrunner",
            "task_description": "直接改写梗概",
            "user_confirmation_state": HANDOFF_CONFIRMATION_CONFIRMED,
        },
        sender_id="agent_scriptwriter",
    )

    assert payload["user_confirmation_state"] == HANDOFF_CONFIRMATION_CONFIRMED
    assert payload["skip_tool_confirmation"] is True


def test_transfer_baton_moves_control_to_target_and_opens_beacon():
    ctx = CommunicationContext()
    director = SparkBaseAgent("agent_director", "1")
    muse = SparkBaseAgent("agent_muse", "1")
    director.bind_context(ctx)
    muse.bind_context(ctx)
    director.raise_horn()
    director.take_baton()
    muse.close_beacon()

    result = transfer_baton(ctx, "1", to_agent_id="agent_muse", from_agent_id="agent_director")

    assert result["status"] == "ok"
    assert result["baton_holder"] == "agent_muse"
    assert director.signals.has_baton is False
    assert muse.signals.is_beacon_open is True
    assert muse.signals.has_baton is True


def test_route_after_sub_agent_respects_delivery_mode():
    assert route_after_sub_agent({"pending_delegate": {"delivery_mode": HANDOFF_DELIVERY_DIRECT_TO_USER}}) == "__end__"
    assert route_after_sub_agent({"pending_delegate": {"delivery_mode": HANDOFF_DELIVERY_RETURN_TO_DIRECTOR}}) == "director"
