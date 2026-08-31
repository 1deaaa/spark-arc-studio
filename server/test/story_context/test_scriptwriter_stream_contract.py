from __future__ import annotations

from types import SimpleNamespace

import pytest


def _make_scriptwriter(monkeypatch, chunks):
    from agents import agent_scriptwriter as scriptwriter_module
    from agents.agent_scriptwriter import ScriptwriterAgent

    class FakeLlm:
        def stream(self, _messages):
            yield from chunks

    monkeypatch.setattr(
        scriptwriter_module,
        "load_prompt",
        lambda *_args, **_kwargs: {"system": "system", "user": "user"},
    )

    agent = object.__new__(ScriptwriterAgent)
    agent.llm = FakeLlm()
    agent._get_arc_example = lambda: ""
    agent._build_chr_reference = lambda _chr_map: ""
    agent._build_write_messages = lambda **_kwargs: []
    agent._clean_model_visible_arc_text = lambda value: str(value or "")
    agent._extract_arc_script = lambda value: value.strip()
    return agent


def test_scriptwriter_stream_accepts_string_and_text_blocks(monkeypatch) -> None:
    from agents.agent_scriptwriter import ScriptwriterAgent

    agent = _make_scriptwriter(
        monkeypatch,
        [
            "# 1-2\n",
            SimpleNamespace(content=[{"type": "text", "text": "[程遥]\n"}]),
            SimpleNamespace(
                content=[
                    {"type": "reasoning", "text": "内部推理"},
                    {"type": "text", "text": "天线在响。"},
                ],
                additional_kwargs={"reasoning_content": "内部推理"},
            ),
        ],
    )

    events = list(
        agent.write_script_stream(
            context="",
            worldview="",
            roles="",
            export_format="arc",
        )
    )

    assert "".join(event["content"] for event in events if event["type"] == "chunk") == (
        "# 1-2\n[程遥]\n天线在响。"
    )
    assert events[-1] == {
        "type": "done",
        "arc_script": "# 1-2\n[程遥]\n天线在响。",
        "thought": "",
        "total_chars": len("# 1-2\n[程遥]\n天线在响。"),
    }


def test_scriptwriter_stream_keeps_reasoning_only_output_empty(monkeypatch) -> None:
    agent = _make_scriptwriter(
        monkeypatch,
        [
            SimpleNamespace(
                content=[{"type": "reasoning", "text": "模型正在思考，但没有输出正文"}],
                additional_kwargs={"reasoning_content": "模型正在思考，但没有输出正文"},
            )
        ],
    )

    events = list(
        agent.write_script_stream(
            context="",
            worldview="",
            roles="",
            export_format="arc",
        )
    )

    assert [event for event in events if event["type"] == "chunk"] == []
    assert events[-1]["type"] == "done"
    assert events[-1]["arc_script"] == ""


def test_production_rejects_empty_arc_result_before_persist() -> None:
    from agents.routes.production import _ensure_generated_output_is_persistable

    with pytest.raises(RuntimeError, match="原文件未修改"):
        _ensure_generated_output_is_persistable(
            export_format="arc",
            generated_text="# 1-2\n<conception>只有构思</conception>",
            final_nodes=[],
        )


def test_production_rejects_empty_novel_result_before_persist() -> None:
    from agents.routes.production import _ensure_generated_output_is_persistable

    with pytest.raises(RuntimeError, match="原文件未修改"):
        _ensure_generated_output_is_persistable(
            export_format="novel",
            generated_text="   ",
        )
