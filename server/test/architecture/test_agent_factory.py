"""
守护对象：
- Agent 工厂对注册 Agent 的构造参数契约保持明确且稳定；
- 显式项目名绑定到 Agent 实例，但不污染调用者的 ContextVar；
- 旧构造器不接收 project_name 时仍能按原签名创建。

本测试禁止：
- 调用真实大模型；
- 连接真实外部服务；
- 依赖具体提示词或生成正文。
"""

from __future__ import annotations

from typing import Any

import pytest

from agents import agent_factory
from agents.registry import AGENT_REGISTRY
from core.request_context import current_project_name, get_current_project_name


REGISTERED_AGENT_IDS = tuple(item["key"] for item in AGENT_REGISTRY)
PROJECT_NAME_ARGUMENT_AGENT_IDS = {"agent_muse", "agent_style"}
LEGACY_USER_ONLY_AGENT_IDS = {
    "agent_showrunner",
    "agent_scriptwriter",
    "agent_critic",
    "agent_lorebook",
}


def _make_user_only_probe(agent_id: str, calls: dict[str, dict[str, Any]]):
    class UserOnlyProbe:
        def __init__(self, user_id: str):
            calls[agent_id] = {"user_id": user_id}
            self.agent_id = agent_id
            self.project_name = "构造器默认项目"

    return UserOnlyProbe


def _make_project_name_probe(agent_id: str, calls: dict[str, dict[str, Any]]):
    class ProjectNameProbe:
        def __init__(self, user_id: str, project_name: str):
            calls[agent_id] = {
                "user_id": user_id,
                "project_name": project_name,
            }
            self.agent_id = agent_id
            self.project_name = project_name

    return ProjectNameProbe


def _make_base_probe(calls: dict[str, dict[str, Any]]):
    class BaseProbe:
        def __init__(self, *, agent_id: str, user_id: str, project_name: str):
            calls[agent_id] = {
                "agent_id": agent_id,
                "user_id": user_id,
                "project_name": project_name,
            }
            self.agent_id = agent_id
            self.project_name = project_name

    return BaseProbe


def _install_probe_classes(monkeypatch, calls: dict[str, dict[str, Any]]) -> None:
    class_map = {
        agent_id: (
            _make_project_name_probe(agent_id, calls)
            if agent_id in PROJECT_NAME_ARGUMENT_AGENT_IDS
            else _make_user_only_probe(agent_id, calls)
        )
        for agent_id in LEGACY_USER_ONLY_AGENT_IDS | PROJECT_NAME_ARGUMENT_AGENT_IDS
    }
    monkeypatch.setattr(agent_factory, "get_agent_class_map", lambda: class_map)
    monkeypatch.setattr(agent_factory, "SparkBaseAgent", _make_base_probe(calls))


@pytest.fixture(autouse=True)
def restore_project_context():
    """每个测试独立保存并恢复项目上下文，避免测试顺序影响结果。"""
    token = current_project_name.set(None)
    try:
        yield
    finally:
        current_project_name.reset(token)


@pytest.mark.parametrize("agent_id", REGISTERED_AGENT_IDS)
def test_registered_agents_bind_explicit_project_without_changing_context(
    monkeypatch,
    agent_id: str,
) -> None:
    calls: dict[str, dict[str, Any]] = {}
    _install_probe_classes(monkeypatch, calls)
    token = current_project_name.set("旧项目")

    try:
        agent = agent_factory.create_agent_instance(agent_id, "user-1", " 项目甲 ")

        assert agent.agent_id == agent_id
        assert agent.project_name == "项目甲"
        assert get_current_project_name() == "旧项目"
    finally:
        current_project_name.reset(token)

    if agent_id in PROJECT_NAME_ARGUMENT_AGENT_IDS:
        assert calls[agent_id] == {
            "user_id": "user-1",
            "project_name": "项目甲",
        }
    elif agent_id in LEGACY_USER_ONLY_AGENT_IDS:
        assert calls[agent_id] == {"user_id": "user-1"}
    elif agent_id == "agent_utility":
        assert calls[agent_id] == {
            "agent_id": "agent_utility",
            "user_id": "user-1",
            "project_name": "项目甲",
        }
    else:
        assert agent_id == "agent_director"


@pytest.mark.parametrize("agent_id", REGISTERED_AGENT_IDS)
def test_registered_agents_bind_empty_project_without_changing_context(
    monkeypatch,
    agent_id: str,
) -> None:
    calls: dict[str, dict[str, Any]] = {}
    _install_probe_classes(monkeypatch, calls)
    token = current_project_name.set("不应继承的旧项目")

    try:
        agent = agent_factory.create_agent_instance(agent_id, "user-1", "")

        assert agent.agent_id == agent_id
        assert agent.project_name == ""
        assert get_current_project_name() == "不应继承的旧项目"
    finally:
        current_project_name.reset(token)

    if agent_id in PROJECT_NAME_ARGUMENT_AGENT_IDS:
        assert calls[agent_id] == {
            "user_id": "user-1",
            "project_name": "",
        }
    elif agent_id in LEGACY_USER_ONLY_AGENT_IDS:
        assert calls[agent_id] == {"user_id": "user-1"}
    elif agent_id == "agent_utility":
        assert calls[agent_id] == {
            "agent_id": "agent_utility",
            "user_id": "user-1",
            "project_name": "",
        }
    else:
        assert agent_id == "agent_director"


@pytest.mark.parametrize("agent_id", sorted(LEGACY_USER_ONLY_AGENT_IDS))
def test_legacy_agent_constructor_does_not_receive_project_name(monkeypatch, agent_id: str) -> None:
    calls: dict[str, dict[str, Any]] = {}
    _install_probe_classes(monkeypatch, calls)

    agent = agent_factory.create_agent_instance(agent_id, "user-2", "项目乙")

    assert calls[agent_id] == {"user_id": "user-2"}
    assert agent.project_name == "项目乙"


@pytest.mark.parametrize("agent_id", sorted(PROJECT_NAME_ARGUMENT_AGENT_IDS))
def test_project_aware_agent_constructor_receives_project_name(monkeypatch, agent_id: str) -> None:
    calls: dict[str, dict[str, Any]] = {}
    _install_probe_classes(monkeypatch, calls)

    agent = agent_factory.create_agent_instance(agent_id, "user-3", "项目丙")

    assert calls[agent_id] == {
        "user_id": "user-3",
        "project_name": "项目丙",
    }
    assert agent.project_name == "项目丙"


def test_unknown_agent_uses_project_aware_base_fallback(monkeypatch) -> None:
    calls: dict[str, dict[str, Any]] = {}
    _install_probe_classes(monkeypatch, calls)

    token = current_project_name.set("外层项目")
    try:
        agent = agent_factory.create_agent_instance("agent_unknown", "user-4", "项目丁")

        assert get_current_project_name() == "外层项目"
    finally:
        current_project_name.reset(token)

    assert calls["agent_unknown"] == {
        "agent_id": "agent_unknown",
        "user_id": "user-4",
        "project_name": "项目丁",
    }
    assert agent.project_name == "项目丁"


def test_constructor_type_error_is_not_retried_with_another_signature(monkeypatch) -> None:
    calls = 0

    class BrokenProbe:
        def __init__(self, user_id: str):
            nonlocal calls
            calls += 1
            raise TypeError("构造器内部错误")

    monkeypatch.setattr(
        agent_factory,
        "get_agent_class_map",
        lambda: {"agent_showrunner": BrokenProbe},
    )

    with pytest.raises(TypeError, match="构造器内部错误"):
        agent_factory.create_agent_instance("agent_showrunner", "user-5", "项目戊")

    assert calls == 1
