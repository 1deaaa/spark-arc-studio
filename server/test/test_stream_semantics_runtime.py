from pathlib import Path
import sys

SERVER_ROOT = Path(__file__).resolve().parents[1]
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

from agents.routes.execution_core import (
    build_started_payload,
    task_cancelled_event,
    task_done_event,
    task_error_event,
)
from agents.routes.stream_semantics import on_cancelled


def test_on_cancelled_semantics_payload():
    payload = on_cancelled("任务已取消", reason="user_cancelled")
    assert payload == {
        "onCancelled": {
            "message": "任务已取消",
            "reason": "user_cancelled",
        }
    }


def test_task_cancelled_event_contains_cancelled_status():
    event = task_cancelled_event("用户已取消", scope="production")
    assert event["event"] == "cancelled"
    assert event["data"]["status"] == "cancelled"
    assert event["data"]["onCancelled"]["message"] == "用户已取消"
    assert event["data"]["onCancelled"]["scope"] == "production"


def test_task_done_and_error_events_expose_terminal_statuses():
    done = task_done_event("完成", result="ok")
    error = task_error_event("失败", code="E_FAIL")

    assert done["event"] == "done"
    assert done["data"]["status"] == "complete"
    assert done["data"]["onDone"]["message"] == "完成"
    assert done["data"]["result"] == "ok"

    assert error["event"] == "error"
    assert error["data"]["status"] == "error"
    assert error["data"]["error"] == "失败"
    assert error["data"]["onError"]["message"] == "失败"
    assert error["data"]["code"] == "E_FAIL"


def test_build_started_payload_contains_on_start():
    started = build_started_payload("任务启动", scope="outline")
    assert started["status"] == "started"
    assert started["onStart"]["message"] == "任务启动"
    assert started["onStart"]["scope"] == "outline"
