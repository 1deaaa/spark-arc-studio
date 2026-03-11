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


def run_stream_test() -> None:
    LLM_Manager.initialize_defaults()
    app.dependency_overrides[get_current_user] = _fake_get_current_user
    client = TestClient(app)

    payload_1 = {
        "projectName": "默认项目",
        "agentId": "agent_lorebook",
        "contextKey": "global",
        "message": (
            "请调用 rewrite_worldview 工具，并把 overwrite_content 设置为完整文本：\\n"
            "【世界观】\\n"
            "这是一个测试世界，名为火种城。科技与魔法共存，主冲突是记忆污染。\\n"
            "你只需要执行工具，不要额外解释。"
        ),
    }
    payload_2 = {
        "projectName": "默认项目",
        "agentId": "agent_lorebook",
        "contextKey": "global",
        "message": "确认，继续执行工具调用。",
    }

    def _stream_once(path: str, payload: dict, title: str):
        print(f"\n=== {title} ===")
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        print("=== Stream events ===")

        t0 = time.perf_counter()
        first_event_ms = None
        first_tool_ms = None
        with client.stream("POST", path, json=payload) as resp:
            print(
                f"status={resp.status_code}, content-type={resp.headers.get('content-type')}"
            )
            if resp.status_code != 200:
                print(resp.text)
                return

            for line in resp.iter_lines():
                if not line:
                    continue

                if isinstance(line, bytes):
                    line = line.decode("utf-8", errors="ignore")

                dt_ms = int((time.perf_counter() - t0) * 1000)
                try:
                    evt = json.loads(line)
                    if first_event_ms is None:
                        first_event_ms = dt_ms
                    event_type = evt.get("event")
                    if first_tool_ms is None and event_type in {
                        "tool_intent_started",
                        "tool_exec_started",
                    }:
                        first_tool_ms = dt_ms
                    if event_type == "assistant_delta":
                        text = (evt.get("text") or "").strip().replace("\n", " ")
                        if text:
                            print(f"[{dt_ms:6d}ms] assistant_delta: {text[:120]}")
                    else:
                        print(f"[{dt_ms:6d}ms] {json.dumps(evt, ensure_ascii=False)}")
                except Exception:
                    print(f"[{dt_ms:6d}ms] raw: {line[:200]}")

        print(
            f"--- timing summary: first_event={first_event_ms}ms, first_tool_event={first_tool_ms}ms"
        )

    _stream_once("/api/chat/send/stream", payload_1, "POST /api/chat/send/stream #1")
    _stream_once("/api/chat/send/stream", payload_2, "POST /api/chat/send/stream #2")

    history_resp = client.get(
        "/api/chat/history",
        params={
            "projectName": "默认项目",
            "agentId": "agent_lorebook",
            "contextKey": "global",
            "limit": 50,
        },
    )
    history = (history_resp.json() or {}).get("history") or []
    target_user_msg = None
    for msg in reversed(history):
        if msg.get("role") == "user":
            target_user_msg = msg
            break

    if target_user_msg and target_user_msg.get("id"):
        edit_payload = {
            "projectName": "默认项目",
            "agentId": "agent_lorebook",
            "contextKey": "global",
            "messageId": int(target_user_msg["id"]),
            "content": (
                "请调用 rewrite_worldview 工具，overwrite_content 直接给完整覆盖文本：\\n"
                "【世界观（编辑触发）】\\n"
                "这是 edit/stream 时序测试文本，目标是尽快看到 tool_intent_started 事件。"
            ),
            "activeContext": None,
        }
        _stream_once(
            "/api/chat/edit/stream", edit_payload, "POST /api/chat/edit/stream #edit"
        )
    else:
        print("\n[WARN] 未找到可编辑的用户消息，跳过 /api/chat/edit/stream 测试。")

    app.dependency_overrides.clear()


if __name__ == "__main__":
    run_stream_test()


def test_placeholder_pytest_entrypoint():
    """占位测试，供 pytest 收集。真实链路验证请运行 run_stream_test()."""
    assert True
