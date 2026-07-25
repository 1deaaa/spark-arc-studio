from __future__ import annotations

import pytest

from agents.agent_critic import CriticAgent
from agents.agent_lorebook import WorldviewAgent
from agents.agent_scriptwriter import ScriptwriterAgent
from agents.agent_showrunner import ShowrunnerAgent
from agents.agent_utils import load_prompt
from agents.setup_agents import MuseAgent
from agents.tools.registry import get_tools_for_agent


CORE_AGENT_PROMPTS = [
    "director",
    "muse",
    "lorebook",
    "showrunner",
    "scriptwriter",
    "critic",
]

AGENTS_WITH_PERSIST_TOOLS = [
    ("agent_muse", MuseAgent),
    ("agent_lorebook", WorldviewAgent),
    ("agent_showrunner", ShowrunnerAgent),
    ("agent_scriptwriter", ScriptwriterAgent),
]


@pytest.mark.parametrize("prompt_name", CORE_AGENT_PROMPTS)
def test_core_agent_prompts_keep_three_runtime_modes(prompt_name: str) -> None:
    prompts = load_prompt(prompt_name)

    assert isinstance(prompts.get("system"), str) and prompts["system"].strip()
    assert isinstance(prompts.get("chat_system"), str) and prompts["chat_system"].strip()
    assert isinstance(prompts.get("pipeline_system"), str) and prompts["pipeline_system"].strip()

    pipeline = prompts["pipeline_system"]
    assert "不是用户" in pipeline or "不是用户" in load_prompt(prompt_name).get("tool_rules", "")
    if prompt_name != "director":
        assert "导演" in pipeline
    else:
        assert "总监" in pipeline or "协调中枢" in pipeline
    forbidden_refs = ("同 system", "同正常生成", "参照默认模板", "格式同 system")
    assert not any(token in pipeline for token in forbidden_refs)


@pytest.mark.parametrize("prompt_name", CORE_AGENT_PROMPTS)
def test_core_agent_prompts_use_base_for_shared_material(prompt_name: str) -> None:
    prompts = load_prompt(prompt_name)
    assert "base" in prompts
    assert isinstance(prompts["base"], dict)
    assert prompts["base"]


@pytest.mark.parametrize(("agent_id", "agent_cls"), AGENTS_WITH_PERSIST_TOOLS)
def test_persisting_agents_bind_generation_specs_to_write_tools(agent_id: str, agent_cls: type) -> None:
    method = getattr(agent_cls, "_get_tool_prompt_references", None)
    assert method is not None

    # 直接以轻量 self 调用，避免实例化时绑定真实 LLM。
    refs = method(object()) if not isinstance(method, staticmethod) else method()
    assert isinstance(refs, dict)
    assert refs

    tool_names = {tool.name for tool in get_tools_for_agent(agent_id)}
    assert set(refs).issubset(tool_names)

    for tool_name, items in refs.items():
        assert tool_name in tool_names
        assert isinstance(items, list) and items
        for item in items:
            assert item.get("field", "system") == "system"


def test_critic_keeps_schema_in_pipeline_because_it_has_no_write_tool_reference() -> None:
    assert CriticAgent._get_tool_prompt_references(CriticAgent) == {}

    pipeline = load_prompt("critic")["pipeline_system"]
    for token in ("JSON", "PASS", "REVISE", "REJECT"):
        assert token in pipeline


def test_only_director_overrides_dynamic_tool_system_prompt() -> None:
    import inspect

    from agents.communication import SparkBaseAgent
    from agents.agent_director import DirectorAgent

    assert DirectorAgent._build_tool_system_prompt is not SparkBaseAgent._build_tool_system_prompt

    for cls in (WorldviewAgent, ShowrunnerAgent, ScriptwriterAgent, MuseAgent, CriticAgent):
        if "_build_tool_system_prompt" in cls.__dict__:
            source = inspect.getsource(cls.__dict__["_build_tool_system_prompt"])
            assert "super()._build_tool_system_prompt" in source
