from __future__ import annotations

import json
import asyncio
import contextvars
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage
from langchain_core.tools import tool
from pydantic import ValidationError

from agents.scriptwriter_prewrite import (
    ScriptwriterPreWriteRequest,
    run_autonomous_scriptwriter_prewrite,
)
from agents.routes.chat import _run_chat_background_context
from core.request_context import (
    clear_scriptwriter_prewrite_receipt,
    current_agent_id,
    current_project_name,
    current_scriptwriter_prewrite_receipt,
    current_user_id,
    get_scriptwriter_prewrite_receipt,
    set_current_export_format,
    set_scriptwriter_prewrite_receipt,
)


@tool
def prewrite_read_probe() -> str:
    """返回只读测试资料。"""
    return "只读事实"


class _FakeBoundLlm:
    def __init__(self, responses: list[AIMessage]) -> None:
        self.responses = list(responses)
        self.invoke_count = 0

    def invoke(self, _messages):
        self.invoke_count += 1
        return self.responses.pop(0)


class _FakeLlm:
    def __init__(self, bound_responses: list[AIMessage]) -> None:
        self.bound = _FakeBoundLlm(bound_responses)
        self.bound_tool_names: list[str] = []
        self.final_invoke_count = 0

    def bind_tools(self, tools):
        self.bound_tool_names = [item.name for item in tools]
        return self.bound

    def invoke(self, _messages):
        self.final_invoke_count += 1
        return AIMessage(content="围绕冲突推进，保持人物知情边界，结尾落到关键选择。")


def _tool_call(call_id: str) -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[{
            "name": "prewrite_read_probe",
            "args": {},
            "id": call_id,
            "type": "tool_call",
        }],
    )


def test_autonomous_prewrite_only_binds_read_tools_and_limits_rounds(monkeypatch) -> None:
    monkeypatch.setattr("agents.scriptwriter_prewrite._build_prewrite_brief", lambda _request: "场景任务包")
    monkeypatch.setattr("agents.scriptwriter_prewrite._prewrite_read_tools", lambda: [prewrite_read_probe])
    llm = _FakeLlm([_tool_call("call-1"), _tool_call("call-2")])

    result = run_autonomous_scriptwriter_prewrite(
        ScriptwriterPreWriteRequest(
            user_id="u1",
            project_name="p1",
            task_description="写第一场",
            chapter_name="一 · 开端",
            scene_name="1-1 初遇",
        ),
        llm=llm,
        max_tool_rounds=2,
    )

    assert llm.bound_tool_names == ["prewrite_read_probe"]
    assert llm.bound.invoke_count == 2
    assert llm.final_invoke_count == 1
    assert result.tools_used == ("prewrite_read_probe", "prewrite_read_probe")
    assert "只读事实" in result.research_context
    assert "关键选择" in result.planning_note


def test_prepare_tool_issues_matching_receipt(monkeypatch) -> None:
    from agents.tools.scriptwriter import prepare_script_creation

    monkeypatch.setattr("agents.scriptwriter_prewrite._build_prewrite_brief", lambda _request: "确定性任务包")
    user_token = current_user_id.set("u2")
    project_token = current_project_name.set("p2")
    agent_token = current_agent_id.set("agent_scriptwriter")
    receipt_token = current_scriptwriter_prewrite_receipt.set({})
    clear_scriptwriter_prewrite_receipt()
    try:
        payload = json.loads(prepare_script_creation.invoke({
            "task_description": "完整创作第一场",
            "chapter_name": "一 · 开端",
            "scene_name": "1-1 初遇",
            "scene_guidance": "建立冲突",
            "scene_characters": ["林舟"],
        }))
        receipt = get_scriptwriter_prewrite_receipt()
        assert payload["status"] == "ready"
        assert payload["task_pack"] == "确定性任务包"
        assert receipt is not None
        assert receipt["chapter_name"] == "一 · 开端"
        assert receipt["scene_name"] == "1-1 初遇"
    finally:
        clear_scriptwriter_prewrite_receipt()
        current_scriptwriter_prewrite_receipt.reset(receipt_token)
        current_agent_id.reset(agent_token)
        current_project_name.reset(project_token)
        current_user_id.reset(user_token)


def test_scriptwriter_tools_reject_null_and_placeholder_target_names() -> None:
    from agents.tools.scriptwriter import (
        CreateOrRewriteScriptInput,
        PrepareScriptCreationInput,
    )

    invalid_values = (None, "", "   ", "null", "NULL", "undefined", "None")
    for invalid in invalid_values:
        with pytest.raises(ValidationError):
            PrepareScriptCreationInput.model_validate({
                "task_description": "写第一场",
                "chapter_name": invalid,
                "scene_name": "1-1 初遇",
            })
        with pytest.raises(ValidationError):
            CreateOrRewriteScriptInput.model_validate({
                "overwrite_content": "正文",
                "chapter_name": "一 · 开端",
                "work_name": invalid,
            })

    with pytest.raises(ValidationError):
        CreateOrRewriteScriptInput.model_validate({"overwrite_content": "正文"})


def test_prewrite_receipt_never_matches_missing_or_placeholder_targets() -> None:
    from agents.scriptwriter_prewrite import has_matching_prewrite_receipt

    receipt_token = current_scriptwriter_prewrite_receipt.set({})
    try:
        set_scriptwriter_prewrite_receipt({
            "receipt_id": "receipt-invalid",
            "user_id": "u-invalid",
            "project_name": "p-invalid",
            "chapter_name": "null",
            "scene_name": "null",
        })
        assert has_matching_prewrite_receipt(
            user_id="u-invalid",
            project_name="p-invalid",
            chapter_name=None,
            scene_name=None,
        ) is False
        assert has_matching_prewrite_receipt(
            user_id="u-invalid",
            project_name="p-invalid",
            chapter_name="null",
            scene_name="null",
        ) is False
    finally:
        clear_scriptwriter_prewrite_receipt()
        current_scriptwriter_prewrite_receipt.reset(receipt_token)


def test_full_script_write_requires_and_consumes_matching_receipt(monkeypatch, tmp_path) -> None:
    from agents.tools.scriptwriter import create_or_rewrite_script

    monkeypatch.setattr("core.utils.USERDATA_ROOT", str(tmp_path))
    monkeypatch.setattr("agents.story_memory.enqueue_scene_memory_write", lambda **_kwargs: None)
    user_token = current_user_id.set("u3")
    project_token = current_project_name.set("p3")
    agent_token = current_agent_id.set("agent_scriptwriter")
    receipt_token = current_scriptwriter_prewrite_receipt.set({})
    set_current_export_format("novel")
    clear_scriptwriter_prewrite_receipt()
    args = {
        "overwrite_content": "雨落在旧站台上。",
        "chapter_name": "一 · 开端",
        "work_name": "1-1 初遇",
        "target_chars": 800,
    }
    try:
        rejected = create_or_rewrite_script.invoke(args)
        assert "尚未完成匹配的 PreWrite" in rejected

        set_scriptwriter_prewrite_receipt({
            "receipt_id": "receipt-1",
            "user_id": "u3",
            "project_name": "p3",
            "chapter_name": "一 · 开端",
            "scene_name": "1-2 错误场景",
        })
        mismatch = create_or_rewrite_script.invoke(args)
        assert "尚未完成匹配的 PreWrite" in mismatch

        set_scriptwriter_prewrite_receipt({
            "receipt_id": "receipt-2",
            "user_id": "u3",
            "project_name": "p3",
            "chapter_name": "一 · 开端",
            "scene_name": "1-1 初遇",
        })
        saved = create_or_rewrite_script.invoke(args)
        saved_payload = json.loads(saved)
        assert saved_payload["status"] == "saved"
        assert "已保存" in saved_payload["message"]
        assert saved_payload["written_chars"] == len("雨落在旧站台上")
        assert saved_payload["target_chars"] == 800
        assert saved_payload["target_source"] == "current_task"
        assert saved_payload["deviation_chars"] == len("雨落在旧站台上") - 800
        assert "自行判断" in saved_payload["length_policy"]
        assert get_scriptwriter_prewrite_receipt() is None
    finally:
        clear_scriptwriter_prewrite_receipt()
        set_current_export_format(None)
        current_scriptwriter_prewrite_receipt.reset(receipt_token)
        current_agent_id.reset(agent_token)
        current_project_name.reset(project_token)
        current_user_id.reset(user_token)


def test_chat_background_preserves_receipt_across_separate_tool_contexts(monkeypatch, tmp_path) -> None:
    from agents.tools.scriptwriter import create_or_rewrite_script, prepare_script_creation

    monkeypatch.setattr("core.utils.USERDATA_ROOT", str(tmp_path))
    monkeypatch.setattr("agents.scriptwriter_prewrite._build_prewrite_brief", lambda _request: "确定性任务包")
    monkeypatch.setattr("agents.story_memory.enqueue_scene_memory_write", lambda **_kwargs: None)

    saved_result = ""

    def callback() -> None:
        nonlocal saved_result
        agent_token = current_agent_id.set("agent_scriptwriter")
        set_current_export_format("novel")
        try:
            prepare_context = contextvars.copy_context()
            prepare_payload = json.loads(prepare_context.run(
                prepare_script_creation.invoke,
                {
                    "task_description": "完整创作第一场",
                    "chapter_name": "一 · 开端",
                    "scene_name": "1-1 初遇",
                },
            ))
            assert prepare_payload["status"] == "ready"

            write_context = contextvars.copy_context()
            saved_result = write_context.run(
                create_or_rewrite_script.invoke,
                {
                    "overwrite_content": "雨落在旧站台上。",
                    "chapter_name": "一 · 开端",
                    "work_name": "1-1 初遇",
                },
            )
        finally:
            set_current_export_format(None)
            current_agent_id.reset(agent_token)

    _run_chat_background_context(
        user_id="u-chat",
        project_name="p-chat",
        is_admin=False,
        locale="zh-CN",
        llm_usage_context="task:prewrite-regression",
        chat_agent_id="agent_director",
        chat_context_key="global",
        callback=callback,
    )

    saved_payload = json.loads(saved_result)
    assert "已保存" in saved_payload["message"]
    from core.utils import get_project_stories_path

    saved_relative_path = saved_payload["path"]
    saved_path = Path(get_project_stories_path("u-chat", "p-chat")) / saved_relative_path
    assert saved_path.read_text(encoding="utf-8") == "雨落在旧站台上。"


def test_auto_write_emits_prewrite_before_writing_scene(monkeypatch, tmp_path: Path) -> None:
    from agents.routes import auto_write
    from agents.scriptwriter_prewrite import ScriptwriterPreWriteResult

    class FakeWriter:
        def __init__(self, _user_id: str) -> None:
            self.llm = object()

        @staticmethod
        def _clean_model_visible_arc_text(value) -> str:
            return str(value or "")

    state_updates: list[dict] = []
    monkeypatch.setattr(auto_write, "ScriptwriterAgent", FakeWriter)
    monkeypatch.setattr(auto_write, "begin_auto_write_run", lambda *_args, **_kwargs: {})

    def fake_patch_state(*_args, **fields):
        state_updates.append(dict(fields))
        return {"updatedAt": "now", **fields}

    monkeypatch.setattr(auto_write, "patch_auto_write_state", fake_patch_state)
    monkeypatch.setattr(auto_write, "get_project_path", lambda *_args: str(tmp_path))
    monkeypatch.setattr(auto_write, "load_worldview", lambda *_args: "世界观")
    monkeypatch.setattr(auto_write, "load_all_roles", lambda *_args: ("角色", {1: "林舟"}))
    monkeypatch.setattr(auto_write, "load_full_outline", lambda *_args: "完整大纲")
    monkeypatch.setattr(auto_write, "load_narrative_memory", lambda *_args: ("叙事记忆", {}))
    monkeypatch.setattr(auto_write, "load_project_style_profile", lambda **_kwargs: None)
    monkeypatch.setattr(auto_write, "get_project_story_tags", lambda *_args: {})
    monkeypatch.setattr(auto_write, "build_story_tags_hint", lambda _tags: "")
    monkeypatch.setattr(auto_write, "build_scene_context", lambda *_args, **_kwargs: "前文上下文")
    scene_path = tmp_path / "stories" / "一 · 开端" / "1-1 初遇.arc"
    monkeypatch.setattr(
        auto_write,
        "resolve_planned_scene_file_path",
        lambda *_args, **_kwargs: (str(scene_path), False, None),
    )
    monkeypatch.setattr(
        auto_write,
        "run_autonomous_scriptwriter_prewrite",
        lambda *_args, **_kwargs: ScriptwriterPreWriteResult(
            receipt_id="autonomous",
            brief="任务包",
            research_context="事实",
            planning_note="规划",
            tools_used=(),
        ),
    )

    outline = {
        "nodes": [{
            "type": "chapter",
            "title": "一 · 开端",
            "chapter": 1,
            "description": "建立悬念",
            "children": [{
                "title": "1-1 初遇",
                "description": "两人在雨夜相遇",
                "characters": ["林舟"],
            }],
        }],
    }
    async def collect_statuses() -> list[str]:
        stream = auto_write.generate_script_stream(
            "u4",
            "p4",
            outline,
            mode="continuous_write",
            export_format="arc",
        )
        statuses: list[str] = []
        try:
            async for raw_event in stream:
                payload = json.loads(raw_event.removeprefix("data: ").strip())
                statuses.append(str(payload.get("status") or ""))
                if payload.get("status") == "writing_scene":
                    break
        finally:
            await stream.aclose()
        return statuses

    statuses = asyncio.run(collect_statuses())

    assert statuses.index("prewrite") < statuses.index("writing_scene")
    phase_sequence = [item.get("phase") for item in state_updates if item.get("phase")]
    assert phase_sequence[:2] == ["prewrite", "writing"]
