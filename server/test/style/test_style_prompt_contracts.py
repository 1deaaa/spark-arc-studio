from __future__ import annotations

from agents.agent_critic import CriticAgent
from agents.agent_scriptwriter import ScriptwriterAgent
from agents.agent_showrunner import ShowrunnerAgent
from agents.agent_style.utils import format_style_profile_for_prompt


SAMPLE_STYLE_PROFILE = {
    "verbal_physicality": {
        "sentence_weight_and_breath": "短句断奏与少量绵长复句交替。",
        "modifier_density": "修饰克制，形容词靠后出现。",
        "metaphor_gene": "常把空间感迁移到情绪。",
    },
    "emotional_processing": {
        "emotion_presentation": "强烈情绪不直说，用不相干动作转移焦点。",
        "climax_handling": "高潮处突然收束，保留空白。",
    },
    "sensory_and_attention": {
        "sensory_priority": "视觉与触觉优先。",
        "focus_shifting": "重大时刻转向微小物件。",
    },
    "interpersonal_field": {
        "dialogue_efficiency": "对白低效率，常有误解和回避。",
        "silence_mechanism": "沉默靠动作填充。",
        "narrator_temperature": "叙述距离偏冷。",
    },
    "coordinator": {
        "signature_style": "冷感、留白、断奏。",
        "distinctive_summary": "用物理细节承载情绪，不做解释性总结。",
        "negative_constraints": ["不要段尾升华", "不要完整解释人物动机"],
    },
}


def test_style_profile_formatter_builds_actionable_execution_card() -> None:
    text = format_style_profile_for_prompt(SAMPLE_STYLE_PROFILE)

    assert "风格执行卡" in text
    assert "句子呼吸：短句断奏" in text
    assert "对白效率：对白低效率" in text
    assert "禁止/避开：不要段尾升华；不要完整解释人物动机" in text
    assert "原始风格档案" in text


def test_scriptwriter_main_prompt_receives_style_execution_card(monkeypatch) -> None:
    captured: dict[str, str] = {}

    def fake_load_prompt(*args, **kwargs):
        captured["style_profile"] = kwargs.get("style_profile", "")
        return {"system": "system", "user": "user"}

    class FakeChunk:
        content = "# 场景\n[-1] 风吹过钟楼。"

    class FakeLLM:
        def invoke(self, messages):
            return FakeChunk()

    monkeypatch.setattr("agents.agent_scriptwriter.load_prompt", fake_load_prompt)
    monkeypatch.setattr(ScriptwriterAgent, "_get_arc_example", lambda self: "arc example")
    agent = ScriptwriterAgent.__new__(ScriptwriterAgent)
    agent.llm = FakeLLM()

    agent.write_script(
        context="",
        worldview="",
        roles="",
        style_profile=SAMPLE_STYLE_PROFILE,
    )

    assert "风格执行卡" in captured["style_profile"]
    assert "对白效率：对白低效率" in captured["style_profile"]


def test_scriptwriter_main_prompt_uses_specialized_budget_guard(monkeypatch) -> None:
    called = {"count": 0}

    def fake_budget(*args, **kwargs):
        called["count"] += 1
        return type(
            "R",
            (),
            {"messages": [kwargs["system_prompt"], kwargs["user_prompt"]]},
        )()

    class FakeChunk:
        content = "# 场景\n[-1] 风吹过钟楼。"

    class FakeLLM:
        def invoke(self, messages):
            return FakeChunk()

    monkeypatch.setattr("agents.agent_scriptwriter.prepare_specialized_prompt_messages_with_budget", fake_budget)
    monkeypatch.setattr("agents.agent_scriptwriter.load_prompt", lambda *args, **kwargs: {"system": "system", "user": "user"})
    monkeypatch.setattr(ScriptwriterAgent, "_get_arc_example", lambda self: "arc example")
    agent = ScriptwriterAgent.__new__(ScriptwriterAgent)
    agent.agent_id = "agent_scriptwriter"
    agent.llm = FakeLLM()

    agent.write_script(
        context="",
        worldview="",
        roles="",
        style_profile=SAMPLE_STYLE_PROFILE,
    )

    assert called["count"] == 1


def test_scriptwriter_non_stream_generation_uses_invoke(monkeypatch) -> None:
    calls = {"invoke": 0, "stream": 0}

    class FakeResponse:
        content = "# 场景\n[-1] 风吹过钟楼。"

    class FakeLLM:
        def invoke(self, messages):
            calls["invoke"] += 1
            return FakeResponse()

        def stream(self, messages):
            calls["stream"] += 1
            yield FakeResponse()

    monkeypatch.setattr("agents.agent_scriptwriter.load_prompt", lambda *args, **kwargs: {"system": "system", "user": "user"})
    monkeypatch.setattr(ScriptwriterAgent, "_get_arc_example", lambda self: "arc example")
    agent = ScriptwriterAgent.__new__(ScriptwriterAgent)
    agent.agent_id = "agent_scriptwriter"
    agent.llm = FakeLLM()

    agent.write_script(context="", worldview="", roles="")

    assert calls == {"invoke": 1, "stream": 0}


def test_showrunner_planning_prompt_receives_style_execution_card(monkeypatch) -> None:
    captured: dict[str, str] = {}

    def fake_load_prompt(*args, **kwargs):
        captured["style_profile"] = kwargs.get("style_profile", "")
        return {"system": "system", "user": "user"}

    class FakeChunk:
        content = "# 标题\n一句梗概。"

    class FakeLLM:
        def invoke(self, messages):
            return FakeChunk()

    monkeypatch.setattr("agents.agent_showrunner.load_prompt", fake_load_prompt)
    agent = ShowrunnerAgent.__new__(ShowrunnerAgent)
    agent.llm = FakeLLM()

    agent.generate_synopsis(
        logline="旧钥匙引出档案室谜团。",
        worldview="",
        roles="",
        guidance="",
        style_profile=SAMPLE_STYLE_PROFILE,
    )

    assert "风格执行卡" in captured["style_profile"]
    assert "句子呼吸：短句断奏" in captured["style_profile"]


def test_showrunner_non_stream_generation_uses_invoke(monkeypatch) -> None:
    calls = {"invoke": 0, "stream": 0}

    class FakeResponse:
        content = "# 标题\n一句梗概。"

    class FakeLLM:
        def invoke(self, messages):
            calls["invoke"] += 1
            return FakeResponse()

        def stream(self, messages):
            calls["stream"] += 1
            yield FakeResponse()

    monkeypatch.setattr("agents.agent_showrunner.load_prompt", lambda *args, **kwargs: {"system": "system", "user": "user"})
    agent = ShowrunnerAgent.__new__(ShowrunnerAgent)
    agent.llm = FakeLLM()

    agent.generate_synopsis(
        logline="旧钥匙引出档案室谜团。",
        worldview="",
        roles="",
        guidance="",
        style_profile=SAMPLE_STYLE_PROFILE,
    )

    assert calls == {"invoke": 1, "stream": 0}


def test_critic_uses_same_style_execution_card() -> None:
    agent = CriticAgent.__new__(CriticAgent)
    text = agent._stringify_style_profile(SAMPLE_STYLE_PROFILE)

    assert "风格执行卡" in text
    assert "禁止/避开" in text


def test_critic_review_uses_budget_guard_and_invoke(monkeypatch) -> None:
    calls = {"budget": 0, "invoke": 0, "stream": 0}

    def fake_budget(*args, **kwargs):
        calls["budget"] += 1
        return type("R", (), {"messages": [kwargs["system_prompt"], kwargs["user_prompt"]]})()

    class FakeResponse:
        content = '{"decision":"PASS","overall_grade":"A","overall_summary":"自然","dimension_grades":{},"hits":[],"fix_tickets":[],"rewrite_required":false,"rewrite_brief":"","status":"APPROVE","critique":"自然","specific_feedback":""}'

    class FakeLLM:
        def invoke(self, messages):
            calls["invoke"] += 1
            return FakeResponse()

        def stream(self, messages):
            calls["stream"] += 1
            yield FakeResponse()

    monkeypatch.setattr("agents.agent_critic.prepare_specialized_prompt_messages_with_budget", fake_budget)
    monkeypatch.setattr("agents.agent_critic.load_prompt", lambda *args, **kwargs: {"system": "system", "user": "user"})
    agent = CriticAgent.__new__(CriticAgent)
    agent.agent_id = "agent_critic"
    agent.llm = FakeLLM()

    result = agent.evaluate(script_text="[-1] 风吹过钟楼。", style_profile=SAMPLE_STYLE_PROFILE)

    assert result["decision"] == "PASS"
    assert calls == {"budget": 1, "invoke": 1, "stream": 0}
