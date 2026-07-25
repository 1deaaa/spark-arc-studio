"""专有工作模式提示词预算行为回归。"""

from __future__ import annotations

import inspect

from langchain_core.messages import HumanMessage, SystemMessage

from agents.context_budget import (
    DEFAULT_SPECIALIZED_SECTION_BUDGETS,
    _budget_limits,
    prepare_specialized_prompt_messages_with_budget,
)


class FakeLLM:
    max_context_tokens = 200
    max_output_tokens = 32
    model_name = "fake"


class FakeNearLimitLLM:
    max_context_tokens = 256_000
    max_output_tokens = 20_000
    model_name = "fake-near-limit"


def test_specialized_prompt_budget_keeps_high_priority_task_pack(monkeypatch) -> None:
    monkeypatch.setattr("agents.context_budget.estimate_tokens", lambda text, model=None: len(text))

    system_prompt = "S" * 40
    user_prompt = "\n".join(
        [
            "=== 当前场景事实包（StoryMemory 自动整理，高优先级）===",
            "【场景契约】",
            "- 当前章节：一 · 开端",
            "- 当前场景：1-1 钟楼交易",
            "- 登场角色：沈棠、林烬",
            "",
            "### 世界观背景：",
            "W" * 5000,
            "",
            "### 全局大纲（完整章节与场景结构）：",
            "O" * 5000,
            "",
            "### 叙事记忆（梗概 + 节拍表 + 当前情感节拍定位）：",
            "N" * 5000,
            "",
            "### 角色详细档案（全量）：",
            "R" * 5000,
            "",
            "### 前文剧本（当前章全文 + 前序章末尾锚点）：",
            "P" * 5000,
            "",
            "### 当前场景的创作指导/导演意图：",
            "必须先确认关系再推进。",
            "",
            "### 修正意见（如有）：",
            "保持节奏更克制。",
        ]
    )

    result = prepare_specialized_prompt_messages_with_budget(
        agent_id="agent_scriptwriter",
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        llm_client=FakeLLM(),
        section_budgets=DEFAULT_SPECIALIZED_SECTION_BUDGETS,
    )

    assert len(result.messages) == 2
    assert isinstance(result.messages[0], SystemMessage)
    assert isinstance(result.messages[1], HumanMessage)
    assert "当前场景事实包" in result.messages[1].content
    assert "当前场景的创作指导" in result.messages[1].content
    assert "修正意见" in result.messages[1].content
    assert "Worldview" not in result.messages[1].content
    assert len(result.messages[1].content) < len(user_prompt)


def test_specialized_prompt_budget_does_not_trim_before_hard_limit(monkeypatch) -> None:
    monkeypatch.setattr("agents.context_budget.estimate_tokens", lambda text, model=None: len(text))

    events = []
    system_prompt = "S" * 20
    user_prompt = "U" * 220_000

    result = prepare_specialized_prompt_messages_with_budget(
        agent_id="agent_scriptwriter",
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        llm_client=FakeNearLimitLLM(),
        emit_event=events.append,
    )

    assert result.compacted is False
    assert result.messages[1].content == user_prompt
    assert events[-1]["reason"] == "within_hard_budget_high_usage"
    assert events[-1]["usage_ratio"] > 0.85


def test_large_context_budget_reserves_less_than_legacy_quarter() -> None:
    hard_budget, trigger_budget = _budget_limits(1_000_000, 200_000)

    assert hard_budget == 830_000
    assert trigger_budget == 830_000


def test_production_single_node_stream_uses_specialized_budget_guard() -> None:
    from agents.routes import production as production_module

    source = inspect.getsource(production_module.scriptwriter_compose_stream)
    single_node_branch = source[source.index('if mode == "single-node"') :]
    assert "prepare_specialized_prompt_messages_with_budget" in single_node_branch
    assert single_node_branch.index("prepare_specialized_prompt_messages_with_budget") < single_node_branch.index("chat.stream(messages)")
