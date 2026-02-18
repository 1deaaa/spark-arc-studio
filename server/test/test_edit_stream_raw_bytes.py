import json
import time
from pathlib import Path
import sys

SERVER_ROOT = Path(__file__).resolve().parents[1]
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

from fastapi import Request
from fastapi.testclient import TestClient

from app import app
from core.auth import get_current_user
from core.request_context import set_current_context
from llm.llm_mgr import LLM_Manager


async def _fake_get_current_user(request: Request):
    user_id = "1"
    project_name = "默认项目"
    set_current_context(user_id, project_name)
    request.state.user = {"user_id": int(user_id), "username": "test_user"}
    return request.state.user


def _ensure_edit_target_message_id(client: TestClient) -> int:
    send_payload = {
        "projectName": "默认项目",
        "agentId": "agent_lorebook",
        "contextKey": "global",
        "message": "这是 edit/stream 原始字节流测试的种子消息，请正常回复。",
    }
    send_resp = client.post("/api/chat/send", json=send_payload)
    if send_resp.status_code != 200:
        raise RuntimeError(f"种子消息发送失败: {send_resp.status_code} {send_resp.text}")

    history_resp = client.get(
        "/api/chat/history",
        params={
            "projectName": "默认项目",
            "agentId": "agent_lorebook",
            "contextKey": "global",
            "limit": 80,
        },
    )
    if history_resp.status_code != 200:
        raise RuntimeError(f"获取历史失败: {history_resp.status_code} {history_resp.text}")

    history = (history_resp.json() or {}).get("history") or []
    for msg in reversed(history):
        if msg.get("role") == "user" and msg.get("id"):
            return int(msg["id"])

    raise RuntimeError("未找到可用于编辑的用户消息")


def _probe_once(client: TestClient, payload: dict, title: str) -> None:
    print(f"\n=== {title} ===")
    print(json.dumps(payload, ensure_ascii=False, indent=2))

    markers = {
        b'\"event\": \"stream_started\"': "stream_started",
        b'\"event\": \"tool_intent_started\"': "tool_intent_started",
        b'\"event\": \"tool_exec_started\"': "tool_exec_started",
        b'\"event\": \"tool_exec_finished\"': "tool_exec_finished",
    }
    marker_first_seen_ms = {name: None for name in markers.values()}

    t0 = time.perf_counter()
    first_chunk_ms = None
    chunk_count = 0
    total_bytes = 0
    all_bytes = bytearray()
    line_buffer = b""

    with client.stream("POST", "/api/chat/edit/stream", json=payload) as resp:
        print(f"status={resp.status_code}")
        print(f"content-type={resp.headers.get('content-type')}")
        if resp.status_code != 200:
            print(resp.text)
            return

        for chunk in resp.iter_raw():
            if not chunk:
                continue

            dt_ms = int((time.perf_counter() - t0) * 1000)
            if first_chunk_ms is None:
                first_chunk_ms = dt_ms

            chunk_count += 1
            total_bytes += len(chunk)
            all_bytes.extend(chunk)

            preview = chunk[:180].decode("utf-8", errors="replace").replace("\n", "\\n")
            print(f"[chunk#{chunk_count:03d} @ {dt_ms:6d}ms] bytes={len(chunk):4d} preview={preview}")

            for raw_marker, marker_name in markers.items():
                if marker_first_seen_ms[marker_name] is None and raw_marker in all_bytes:
                    marker_first_seen_ms[marker_name] = dt_ms
                    print(f"  -> marker first seen: {marker_name} at {dt_ms}ms")

            line_buffer += chunk
            while b"\n" in line_buffer:
                line, line_buffer = line_buffer.split(b"\n", 1)
                line_str = line.decode("utf-8", errors="replace").strip()
                if not line_str:
                    continue
                event_ms = int((time.perf_counter() - t0) * 1000)
                try:
                    evt = json.loads(line_str)
                    etype = evt.get("event")
                    print(f"  [event @ {event_ms:6d}ms] {etype}: {json.dumps(evt, ensure_ascii=False)}")
                except Exception:
                    print(f"  [line  @ {event_ms:6d}ms] raw={line_str[:200]}")

    if line_buffer.strip():
        tail_ms = int((time.perf_counter() - t0) * 1000)
        tail_str = line_buffer.decode("utf-8", errors="replace").strip()
        print(f"[tail @ {tail_ms}ms] {tail_str[:300]}")

    print("--- Summary ---")
    print(f"first_chunk_ms={first_chunk_ms}")
    print(f"chunk_count={chunk_count}")
    print(f"total_bytes={total_bytes}")
    for marker_name in ["stream_started", "tool_intent_started", "tool_exec_started", "tool_exec_finished"]:
        print(f"marker_{marker_name}_ms={marker_first_seen_ms[marker_name]}")


def run_raw_edit_stream_probe() -> None:
    LLM_Manager.initialize_defaults()
    app.dependency_overrides[get_current_user] = _fake_get_current_user
    client = TestClient(app)

    message_id = _ensure_edit_target_message_id(client)

    planning_payload = {
        "projectName": "默认项目",
        "agentId": "agent_lorebook",
        "contextKey": "global",
        "messageId": message_id,
        "content": (
            "请修改世界观。先给我一个简短修改计划，等我确认后再执行工具。"
            "如果执行工具，必须使用 rewrite_worldview 且 overwrite_content 给完整文本。"
        ),
        "activeContext": None,
    }
    _probe_once(client, planning_payload, "Round#1: 方案阶段（应无工具事件）")

    execute_payload = {
        "projectName": "默认项目",
        "agentId": "agent_lorebook",
        "contextKey": "global",
        "messageId": message_id,
        "content": (
            "确认，按刚才方案执行。请立即调用 rewrite_worldview，overwrite_content 使用以下完整覆盖文本：\\n"
            "### 世界观设定\\n"
            "火种城位于旧大陆断裂带边缘，城市依赖记忆蒸馏塔运行。"
            "科技与魔法共存，但所有法术都需要以真实记忆作为燃料。"
            "主冲突是记忆污染：伪造记忆会在群体中扩散并改写现实感知。"
        ),
        "activeContext": None,
    }
    _probe_once(client, execute_payload, "Round#2: 确认执行阶段（观察工具事件）")

    app.dependency_overrides.clear()


if __name__ == "__main__":
    run_raw_edit_stream_probe()
