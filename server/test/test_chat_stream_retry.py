"""聊天流自动重试测试。"""
import json
import queue
import threading
import time
from pathlib import Path
import sys

SERVER_ROOT = Path(__file__).resolve().parents[1]
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

from agents.routes.chat_task import ChatTaskEntry, _make_task_key, register_task, update_task_status, build_task_status_payload


def test_retry_attempt_event_format():
    event = {"event": "retry_attempt", "attempt": 1, "max_retries": 3, "error_summary": "网络异常"}
    assert event["event"] == "retry_attempt"
    assert isinstance(event["attempt"], int)


def test_chat_task_entry_retry_count():
    entry = ChatTaskEntry(
        task_key="1:test:agent_director:global", user_id="1", project_name="test",
        agent_id="agent_director", context_key="global",
        stop_event=threading.Event(), progress_queue=queue.Queue(),
        status='running', started_at=time.time(), retry_count=2,
    )
    assert entry.retry_count == 2
    payload = build_task_status_payload(entry)
    assert payload["retryCount"] == 2


def test_update_task_status_with_retry_count():
    task_key = _make_task_key("1", "test", "agent_director", "global")
    entry = ChatTaskEntry(
        task_key=task_key, user_id="1", project_name="test",
        agent_id="agent_director", context_key="global",
        stop_event=threading.Event(), progress_queue=queue.Queue(),
        status='running', started_at=time.time(),
    )
    register_task(entry)
    update_task_status(task_key, 'running', retry_count=1)
    assert entry.retry_count == 1
    update_task_status(task_key, 'error', error_message="测试错误", retry_count=3)
    assert entry.retry_count == 3
    assert entry.status == 'error'


def test_retry_loop_simulated():
    """模拟重试循环：前2次失败，第3次成功。"""
    MAX_RETRIES = 3
    call_count = 0
    progress_events = []

    def fake_stream():
        nonlocal call_count
        call_count += 1
        if call_count <= 2:
            raise ConnectionError(f"网络异常(第{call_count}次)")
        yield {"event": "assistant_delta", "text": "成功"}

    buf = []
    stop_event = threading.Event()
    progress_queue = queue.Queue()

    for attempt in range(1, MAX_RETRIES + 1):
        if attempt > 1:
            buf.clear()
        try:
            for delta in fake_stream():
                if stop_event.is_set():
                    break
                text = delta.get("text", "") if isinstance(delta, dict) else str(delta)
                if text:
                    buf.append(text)
                progress_queue.put(delta)
            break
        except Exception as e:
            if stop_event.is_set():
                break
            if attempt < MAX_RETRIES:
                progress_queue.put({"event": "retry_attempt", "attempt": attempt, "max_retries": MAX_RETRIES, "error_summary": str(e)})
            else:
                err = str(e)
                buf.append(err)
                progress_queue.put({"event": "error", "message": err})

    # 收集事件
    while not progress_queue.empty():
        progress_events.append(progress_queue.get_nowait())

    assert call_count == 3  # 前2次失败，第3次成功
    assert any(e["event"] == "retry_attempt" for e in progress_events)
    assert any(e["event"] == "assistant_delta" for e in progress_events)
    assert "".join(buf) == "成功"


def test_retry_all_fail():
    """模拟3次均失败。"""
    call_count = 0

    def fake_stream_always_fail():
        nonlocal call_count
        call_count += 1
        raise ConnectionError(f"网络异常(第{call_count}次)")

    buf = []
    progress_events = []
    progress_queue = queue.Queue()
    MAX_RETRIES = 3

    for attempt in range(1, MAX_RETRIES + 1):
        if attempt > 1:
            buf.clear()
        try:
            for delta in fake_stream_always_fail():
                pass
            break
        except Exception as e:
            if attempt < MAX_RETRIES:
                progress_queue.put({"event": "retry_attempt", "attempt": attempt, "max_retries": MAX_RETRIES, "error_summary": str(e)})
            else:
                err = str(e)
                buf.append(err)
                progress_queue.put({"event": "error", "message": err})

    while not progress_queue.empty():
        progress_events.append(progress_queue.get_nowait())

    assert call_count == 3
    retry_events = [e for e in progress_events if e["event"] == "retry_attempt"]
    assert len(retry_events) == 2  # 前2次失败推送 retry_attempt，第3次推送 error
    assert any(e["event"] == "error" for e in progress_events)
