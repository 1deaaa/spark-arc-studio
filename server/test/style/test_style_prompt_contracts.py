from __future__ import annotations

from agents.agent_critic import CriticAgent
from agents.agent_scriptwriter import ScriptwriterAgent
from agents.agent_showrunner import ShowrunnerAgent
from agents.agent_style.utils import format_style_profile_for_prompt


SAMPLE_STYLE_MARKDOWN = """## 思维与认知指纹

- 联想跳跃路径:实体→记忆,如「某物的颜色让某人想起某段对话」
- 叙述者姿态:限知第一人称,带轻度不可靠性

## 语言体感

- 句子呼吸:主谓宾完整的短句占七成,偶尔出现 30+ 字复句
- 标点指纹:大量逗号链,极少使用感叹号

## 风格执行卡

- 主谓宾完整的短句占七成,偶尔出现 30+ 字的复句作为情绪重音
- 心理直白严禁出现,所有情绪必须翻译成"看得到的动作"
- 严禁使用"然而、因此、值得一提的是"等 AI 体连接词
"""


def test_style_profile_formatter_passes_through_markdown_string() -> None:
    """markdown 字符串应被直接透传,不再做二次拼装。"""
    text = format_style_profile_for_prompt(SAMPLE_STYLE_MARKDOWN)

    assert "## 风格执行卡" in text
    assert "主谓宾完整的短句占七成" in text


def test_style_profile_formatter_handles_empty_inputs() -> None:
    """None / 空字符串 / 非字符串类型都走 fallback。"""
    fallback = "DEFAULT_FALLBACK"
    assert format_style_profile_for_prompt(None, fallback=fallback) == fallback
    assert format_style_profile_for_prompt("", fallback=fallback) == fallback
    assert format_style_profile_for_prompt("   \n  ", fallback=fallback) == fallback
    # 非字符串(防御性兜底)
    assert format_style_profile_for_prompt({"any": "dict"}, fallback=fallback) == fallback
    assert format_style_profile_for_prompt(123, fallback=fallback) == fallback


def test_scriptwriter_main_prompt_receives_style_markdown(monkeypatch) -> None:
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
        style_profile=SAMPLE_STYLE_MARKDOWN,
    )

    assert "## 风格执行卡" in captured["style_profile"]
    assert "主谓宾完整的短句占七成" in captured["style_profile"]


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
        style_profile=SAMPLE_STYLE_MARKDOWN,
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


def test_showrunner_planning_prompt_receives_style_markdown(monkeypatch) -> None:
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
        style_profile=SAMPLE_STYLE_MARKDOWN,
    )

    assert "## 风格执行卡" in captured["style_profile"]
    assert "主谓宾完整的短句占七成" in captured["style_profile"]


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
        style_profile=SAMPLE_STYLE_MARKDOWN,
    )

    assert calls == {"invoke": 1, "stream": 0}


def test_critic_receives_style_markdown() -> None:
    agent = CriticAgent.__new__(CriticAgent)
    text = agent._stringify_style_profile(SAMPLE_STYLE_MARKDOWN)

    assert "## 风格执行卡" in text
    assert "主谓宾完整的短句占七成" in text


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

    result = agent.evaluate(script_text="[-1] 风吹过钟楼。", style_profile=SAMPLE_STYLE_MARKDOWN)

    assert result["decision"] == "PASS"
    assert calls == {"budget": 1, "invoke": 1, "stream": 0}
