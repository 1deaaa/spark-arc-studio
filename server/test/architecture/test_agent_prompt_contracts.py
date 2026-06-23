from __future__ import annotations

import inspect

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


def test_showrunner_outline_prompt_requires_scene_contract_fields() -> None:
    prompt = load_prompt("showrunner", "generate_outline")["system"]
    for token in ("情绪", "张力", "登场", "对应节拍", "指引", "@key_dialogue"):
        assert token in prompt
    assert "场景元数据必填" in prompt


def test_showrunner_pipeline_requires_in_task_append_until_complete() -> None:
    prompts = load_prompt("showrunner")
    pipeline = prompts["pipeline_system"]
    outline_system = load_prompt("showrunner", "generate_outline")["system"]

    assert "本次委派内连续完成" in pipeline
    assert "不要把“只完成核心部分”等同于任务完成" in pipeline
    assert "同一次任务中继续追加后续章节" in outline_system


def test_outline_length_guidance_keeps_scene_count_flexible() -> None:
    outline_prompts = load_prompt(
        "showrunner",
        "generate_outline",
        chapter_count=8,
        scene_count_per_chapter=3,
    )
    combined = f"{outline_prompts['system']}\n{outline_prompts['user']}"

    assert "章节数" in combined
    assert "尽量贴合" in combined
    assert "场景密度" in combined
    assert "平均参考" in combined
    assert "每章场景数可以不一样" in combined
    assert "不是每章固定配额" in combined or "不是要求每一章都固定同样场数" in combined


def test_director_contract_uses_scene_density_reference_not_fixed_scene_count() -> None:
    director_prompt = load_prompt("director")["chat_system"]

    assert "章节目标和场景密度参考" in director_prompt
    assert "scene_density_reference" in director_prompt
    assert "按剧情弹性安排" in director_prompt
    assert "scenes_per_chapter" not in director_prompt


def test_only_director_overrides_dynamic_tool_system_prompt() -> None:
    from agents.communication import SparkBaseAgent
    from agents.agent_director import DirectorAgent

    assert DirectorAgent._build_tool_system_prompt is not SparkBaseAgent._build_tool_system_prompt

    for cls in (WorldviewAgent, ShowrunnerAgent, ScriptwriterAgent, MuseAgent, CriticAgent):
        if "_build_tool_system_prompt" in cls.__dict__:
            source = inspect.getsource(cls.__dict__["_build_tool_system_prompt"])
            assert "super()._build_tool_system_prompt" in source
