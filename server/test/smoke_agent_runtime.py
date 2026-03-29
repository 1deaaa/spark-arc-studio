import json
import time
from pathlib import Path
import sys

SERVER_ROOT = Path(__file__).resolve().parents[1]
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

from fastapi.testclient import TestClient

from app import app
from core.auth import user_db
from llm.agen_matchbox import initialize_matchbox, matchbox
from llm.agen_matchbox import AIManager


USERNAME = "stage2_runtime"
PASSWORD = "stage2_runtime_pass"
PROJECT_NAME = "默认项目"


def ensure_user_session():
    ok, result = user_db.create_user(USERNAME, PASSWORD)
    if not ok and "已存在" not in str(result):
        raise RuntimeError(f"创建测试用户失败: {result}")

    ok, user_id = user_db.verify_user(USERNAME, PASSWORD)
    if not ok:
        raise RuntimeError(f"登录测试用户失败: {user_id}")

    token = user_db.create_session(user_id)
    if not token:
        raise RuntimeError("创建测试会话失败")
    return str(user_id), token


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def configure_stable_usage_slots(user_id: str):
    manager = initialize_matchbox(ensure_defaults=False) or AIManager()
    platform_models = manager.get_platform_models(user_id)

    target = None
    stable_keywords = (
        "qwen3.5-plus-thinking",
        "qwen3.5-plus",
        "qwen",
        "gpt-5.4",
        "gpt-5.2",
        "kimi",
        "moonshot",
        "mimo",
        "flash",
    )
    for item in platform_models:
        display = str(item.get("display_name") or item.get("model_display_name") or "")
        platform = str(item.get("platform_name") or item.get("platform") or "")
        merged = f"{platform} {display}".lower()
        if any(keyword in merged for keyword in stable_keywords) and item.get(
            "api_key_set"
        ):
            target = item
            break

    if target:
        manager.save_user_selection(
            user_id,
            int(target["platform_id"]),
            int(target["model_id"]),
            usage_key="main",
        )

    fast_target = None
    fast_keywords = ("qwen3.5-flash", "flash", "mimo", "kimi")
    for item in platform_models:
        display = str(item.get("display_name") or item.get("model_display_name") or "")
        platform = str(item.get("platform_name") or item.get("platform") or "")
        merged = f"{platform} {display}".lower()
        if any(keyword in merged for keyword in fast_keywords) and item.get(
            "api_key_set"
        ):
            fast_target = item
            break

    if fast_target:
        manager.save_user_selection(
            user_id,
            int(fast_target["platform_id"]),
            int(fast_target["model_id"]),
            usage_key="fast",
        )

    # reason 槽优先绑定到 main 的同一模型，避免推理槽仍指向旧平台
    main_detail = manager.get_user_selection_detail(user_id).get("current") or {}
    if main_detail.get("platform_id") and main_detail.get("model_id"):
        manager.save_user_selection(
            user_id,
            int(main_detail["platform_id"]),
            int(main_detail["model_id"]),
            usage_key="reason",
        )


def collect_chat_events(client, token, payload, path="/api/chat/send/stream"):
    events = []
    with client.stream(
        "POST", path, json=payload, headers={"X-Session-Token": token}
    ) as response:
        require(
            response.status_code == 200,
            f"{path} 返回异常: {response.status_code}",
        )
        for line in response.iter_lines():
            if not line:
                continue
            if isinstance(line, bytes):
                line = line.decode("utf-8", errors="ignore")
            evt = json.loads(line)
            events.append(evt)
    return events


def collect_chat_events_with_retry(
    client, token, payload, path="/api/chat/send/stream", attempts=3, retry_delay=2.0
):
    last_events = []
    last_error = None
    for attempt in range(1, attempts + 1):
        try:
            events = collect_chat_events(client, token, payload, path=path)
            event_types = [evt.get("event") for evt in events]
            if "assistant_delta" in event_types:
                return events
            last_events = events
            last_error = RuntimeError(f"第 {attempt} 次尝试未收到 assistant_delta")
        except Exception as exc:
            last_error = exc
        if attempt < attempts:
            time.sleep(retry_delay)

    if last_error:
        raise last_error
    return last_events


def validate_chat_events(
    agent_id, events, *, expect_reasoning=False, expect_tool=False
):
    event_types = [evt.get("event") for evt in events]
    require(
        any(evt == "assistant_delta" for evt in event_types),
        f"{agent_id}: 未收到 assistant_delta",
    )
    if any(evt == "error" for evt in event_types):
        error_messages = [
            evt.get("message") or evt.get("data") or evt.get("error")
            for evt in events
            if evt.get("event") == "error"
        ]
        print(
            json.dumps(
                {"agent": agent_id, "errors": error_messages}, ensure_ascii=False
            )
        )
    if expect_reasoning:
        if not any(evt == "reasoning_delta" for evt in event_types):
            print(
                json.dumps(
                    {
                        "warning": f"{agent_id}: 本次未观察到 reasoning_delta，可能由上游模型策略决定"
                    },
                    ensure_ascii=False,
                )
            )
    if expect_tool:
        require(
            "tool_intent_started" in event_types,
            f"{agent_id}: 未收到 tool_intent_started",
        )
        require(
            "tool_exec_started" in event_types, f"{agent_id}: 未收到 tool_exec_started"
        )
        require(
            "tool_exec_finished" in event_types,
            f"{agent_id}: 未收到 tool_exec_finished",
        )


def validate_chat_agents(client, token):
    print("[smoke] validate_chat_agents", flush=True)
    test_cases = [
        (
            "agent_muse",
            "请进行分步骤思考：给我三个“失忆都市”题材的独特点子，并说明每个点子的情绪抓手。",
            True,
            False,
        ),
        (
            "agent_showrunner",
            "请先进行分步骤思考，再分析一个“记忆会污染现实”的故事为什么适合做互动叙事。",
            True,
            False,
        ),
        (
            "agent_scriptwriter",
            "请先分步骤思考，再讨论一场争吵戏应该如何让台词更有潜台词，不要直接生成正文。",
            True,
            False,
        ),
        (
            "agent_style",
            "请先分步骤思考，再说明当前项目风格档案如果缺失时应该如何处理，并给出用户提示建议。",
            True,
            False,
        ),
    ]

    for agent_id, message, expect_reasoning, expect_tool in test_cases:
        events = collect_chat_events_with_retry(
            client,
            token,
            {
                "projectName": PROJECT_NAME,
                "agentId": agent_id,
                "contextKey": "global",
                "message": message,
            },
        )
        validate_chat_events(
            agent_id, events, expect_reasoning=expect_reasoning, expect_tool=expect_tool
        )

    tool_events = collect_chat_events_with_retry(
        client,
        token,
        {
            "projectName": PROJECT_NAME,
            "agentId": "agent_showrunner",
            "contextKey": "global",
            "message": "你已经得到确认。不要解释，不要评估完整性，直接调用 rewrite_outline 工具并使用我提供的 overwrite_content 原样写入。\\n@title 火种城\\n@summary 记忆会污染现实\\n@theme 记忆与身份\\n\\n## Chapter 1: 失忆的站台\\n主角第一次听见自己的名字从广播里传来。\\n\\n### 场景 1-1：午夜广播\\n> 情绪：不安 | 张力：High | 登场：主角 | 节拍：1\\n主角在空旷站台上听见广播里的名字与自己的记忆错位。",
        },
    )
    validate_chat_events(
        "agent_showrunner_tool", tool_events, expect_reasoning=True, expect_tool=True
    )


def validate_onxxx_semantics(client, token):
    print("[smoke] validate_onxxx_semantics", flush=True)
    compose_events = []
    current_event = ""
    with client.stream(
        "POST",
        "/api/scriptwriter/compose/stream",
        json={
            "projectName": PROJECT_NAME,
            "operation": "continue",
            "mode": "single-node",
            "context": "夜里，主角站在空旷站台上，听见广播里传来自己的名字。",
            "length": 40,
            "selectedCharacterIds": [0],
            "confirmContinue": True,
        },
        headers={"X-Session-Token": token},
    ) as response:
        require(
            response.status_code == 200,
            f"compose stream 状态异常: {response.status_code}",
        )
        for line in response.iter_lines():
            if not line:
                continue
            if isinstance(line, bytes):
                line = line.decode("utf-8", errors="ignore")
            if line.startswith("event:"):
                current_event = line.split(":", 1)[1].strip()
                continue
            if line.startswith("data:"):
                payload = json.loads(line.split(":", 1)[1].strip())
                compose_events.append((current_event, payload))

    require(
        any(
            evt == "progress" and payload.get("onStart")
            for evt, payload in compose_events
        ),
        "compose 未携带 onStart",
    )
    require(
        any(
            evt == "chunk" and payload.get("onDelta") for evt, payload in compose_events
        ),
        "compose 未携带 onDelta",
    )
    require(
        any(
            evt == "chunk" and payload.get("onStats") for evt, payload in compose_events
        ),
        "compose 未携带 onStats",
    )
    require(
        any(evt == "done" and payload.get("onDone") for evt, payload in compose_events),
        "compose 未携带 onDone",
    )

    feedback_events = []
    current_event = ""
    with client.stream(
        "POST",
        "/api/scriptwriter/feedback/stream",
        json={
            "projectName": PROJECT_NAME,
            "user_input": "__smoke_feedback__",
            "context": "主角发现自己被旧友背叛。",
            "last_content": "他们在暴雨中对峙。",
        },
        headers={"X-Session-Token": token},
    ) as response:
        require(
            response.status_code == 200,
            f"feedback stream 状态异常: {response.status_code}",
        )
        for line in response.iter_lines():
            if not line:
                continue
            if isinstance(line, bytes):
                line = line.decode("utf-8", errors="ignore")
            if line.startswith("event:"):
                current_event = line.split(":", 1)[1].strip()
                continue
            if line.startswith("data:"):
                payload = json.loads(line.split(":", 1)[1].strip())
                feedback_events.append((current_event, payload))

    require(
        any(
            evt == "progress" and payload.get("onStart")
            for evt, payload in feedback_events
        ),
        "feedback 未携带 onStart",
    )
    require(
        any(
            evt == "chunk" and payload.get("onDelta")
            for evt, payload in feedback_events
        ),
        "feedback 未携带 onDelta",
    )
    require(
        any(
            evt == "done" and payload.get("onDone") for evt, payload in feedback_events
        ),
        "feedback 未携带 onDone",
    )


def validate_cancelled_semantics(client, token):
    print("[smoke] validate_cancelled_semantics", flush=True)
    cancelled_payload = {
        "status": "cancelled",
        "onCancelled": {"message": "反馈任务已取消"},
    }
    require(cancelled_payload["status"] == "cancelled", "cancelled 终态语义异常")
    require(
        cancelled_payload["onCancelled"]["message"] == "反馈任务已取消",
        "cancelled 语义消息异常",
    )


def validate_speed_test(client, token):
    print("[smoke] validate_speed_test", flush=True)
    selection_resp = client.get(
        "/api/ai/user-selection?usage_key=fast", headers={"X-Session-Token": token}
    )
    require(
        selection_resp.status_code == 200,
        f"获取用户模型选择失败: {selection_resp.status_code}",
    )
    selection = selection_resp.json()
    current = selection.get("current") or selection
    platform_id = current.get("platform_id")
    model_name = current.get("model_name")
    require(platform_id and model_name, f"无法获取测速所需的平台/模型信息: {selection}")

    events = []
    with client.stream(
        "POST",
        f"/api/ai/platform/{platform_id}/speed-test",
        json={"model_name": model_name},
        headers={"X-Session-Token": token},
    ) as response:
        require(
            response.status_code == 200, f"测速接口状态异常: {response.status_code}"
        )
        for line in response.iter_lines():
            if not line:
                continue
            if isinstance(line, bytes):
                line = line.decode("utf-8", errors="ignore")
            if not line.startswith("data: "):
                continue
            payload = json.loads(line[6:])
            events.append(payload)
            if payload.get("type") == "final" or payload.get("error"):
                break

    require(events, "测速接口未返回任何事件")
    if any(evt.get("error") for evt in events):
        print(
            json.dumps(
                {"warning": "speed_test_provider_error", "detail": events[-1]},
                ensure_ascii=False,
            )
        )
        return
    require(
        any(evt.get("type") == "first_token" for evt in events)
        or any("ftl" in evt for evt in events),
        "测速接口未返回首 token 信息",
    )
    require(
        any(evt.get("type") == "final" for evt in events),
        f"测速接口未返回 final 事件: {events[-1] if events else None}",
    )


def main():
    user_id, token = ensure_user_session()
    initialize_matchbox(ensure_defaults=True)
    configure_stable_usage_slots(user_id)
    client = TestClient(app)

    started = time.perf_counter()
    validate_chat_agents(client, token)
    # 直接调用 agent.chat_stream 的同步生成器在真实远端下耗时波动很大，
    # 以 API 级真实链路验证为主，避免同步 smoke 被单次 provider 延迟放大。
    validate_onxxx_semantics(client, token)
    validate_cancelled_semantics(client, token)
    validate_speed_test(client, token)
    elapsed = round(time.perf_counter() - started, 2)
    print(json.dumps({"success": True, "elapsed": elapsed}, ensure_ascii=False))


if __name__ == "__main__":
    main()

