"""
守护对象：
- 用户可编辑提示词偏好只覆盖质量层
- 格式协议、工具协议和三模态结构不被用户覆盖破坏

本测试禁止：
- 调用真实 LLM
- 连接真实外部服务
- 依赖具体生成文案
"""

from __future__ import annotations

import json
from pathlib import Path

from core.request_context import current_user_id
from agents.agent_utils import load_prompt
from agents.prompt_preferences import (
    QUALITY_GUARDRAIL,
    build_quality_placeholder_values,
    get_agent_prompt_preferences,
    get_quality_default_preference,
    reset_agent_prompt_preference,
    save_agent_prompt_preference,
)


def test_quality_placeholders_merge_default_and_override(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("agents.prompt_preferences.USERDATA_ROOT", str(tmp_path))

    pref_path = Path(tmp_path) / "uid_7" / ".sparkarc" / "agent_prompt_overrides.json"
    pref_path.parent.mkdir(parents=True, exist_ok=True)
    pref_path.write_text(
        json.dumps(
            {
                "version": 2,
                "agents": {
                    "agent_muse": {
                        "enabled": True,
                        "content": "只保留极具视觉冲击力的意象，不写空泛抽象句。",
                    }
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    token = current_user_id.set("7")
    try:
        values = build_quality_placeholder_values("muse", user_id="7")
        assert values["quality.guard"] == QUALITY_GUARDRAIL
        assert "只保留极具视觉冲击力的意象" in values["quality.preference"]

        prompts = load_prompt("muse")
        assert "只保留极具视觉冲击力的意象" in prompts["system"]
        assert "1. 输出必须是**纯文本**" in prompts["system"]
    finally:
        current_user_id.reset(token)


def test_prompt_preference_save_and_reset(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("agents.prompt_preferences.USERDATA_ROOT", str(tmp_path))

    before = get_agent_prompt_preferences("11", "agent_scriptwriter")
    assert before["default_content"]
    assert before["customized"] is False

    saved = save_agent_prompt_preference(
        user_id="11",
        agent_id="agent_scriptwriter",
        content="把对白写得更短，更像人真的在说话。",
    )
    assert "更像人真的在说话" in saved["effective_content"]
    assert saved["customized"] is True

    reset = reset_agent_prompt_preference("11", "agent_scriptwriter")
    assert reset["customized"] is False
    assert reset["effective_content"] == get_quality_default_preference("agent_scriptwriter")


def test_legacy_slot_preferences_are_merged(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("agents.prompt_preferences.USERDATA_ROOT", str(tmp_path))

    pref_path = Path(tmp_path) / "uid_9" / ".sparkarc" / "agent_prompt_overrides.json"
    pref_path.parent.mkdir(parents=True, exist_ok=True)
    pref_path.write_text(
        json.dumps(
            {
                "version": 1,
                "agents": {
                    "agent_lorebook": {
                        "root": {"enabled": True, "content": "世界设定更冷峻。"},
                        "characters": {"enabled": True, "content": "角色动机必须更隐秘。"},
                    }
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    state = get_agent_prompt_preferences("9", "agent_lorebook")
    assert "世界设定更冷峻" in state["effective_content"]
    assert "角色动机必须更隐秘" in state["effective_content"]
    assert state["customized"] is True
