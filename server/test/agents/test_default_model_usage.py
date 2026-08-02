"""Agent 默认模型用途的统一解析契约测试。"""

from types import SimpleNamespace

import llm.agen_matchbox.builder as builder_module
from llm.agen_matchbox.builder import LLMBuilderMixin
from llm.agen_matchbox.models import AgentModelBinding


class _FakeQuery:
    def __init__(self, binding):
        self._binding = binding

    def filter_by(self, **_filters):
        return self

    def first(self):
        return self._binding


class _FakeSession:
    def __init__(self, binding):
        self._binding = binding

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def query(self, model):
        assert model is AgentModelBinding
        return _FakeQuery(self._binding)

    def commit(self):
        return None


class _FakeCallback:
    def __init__(self, **_kwargs):
        pass


class _FakeChatUniversal:
    def __init__(self, **kwargs):
        self.model_name = kwargs["model_name"]


class _FakeUsage:
    def __init__(self, **_kwargs):
        pass


class _FakeClient:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


def _build_manager(monkeypatch, binding=None):
    manager = LLMBuilderMixin()
    selected_usage = {}
    platform = SimpleNamespace(id=1, name="测试平台", base_url="https://example.test")
    model = SimpleNamespace(
        id=2,
        model_name="test-model",
        max_context_tokens=4096,
        max_output_tokens=1024,
    )
    slots = {
        "main": SimpleNamespace(selected_platform_id=1, selected_model_id=2),
        "reason": SimpleNamespace(selected_platform_id=1, selected_model_id=2),
        "fast": SimpleNamespace(selected_platform_id=1, selected_model_id=2),
    }

    manager.Session = lambda: _FakeSession(binding)
    manager.ensure_user_has_config = lambda *_args: None
    def get_usage_slot(_session, _user_id, key):
        selected_usage["key"] = key
        return slots[key]

    manager._get_usage_slot = get_usage_slot
    manager._normalize_usage_key = lambda key: str(key).strip().lower() or "main"
    manager._resolve_user_choice = lambda *_args, **_kwargs: {
        "platform": platform,
        "model": model,
        "api_key": "test-key",
        "base_url": platform.base_url,
        "quota_scope": None,
    }
    manager.enforce_user_credit = lambda *_args: None
    manager._apply_model_params = lambda _model, kwargs: kwargs
    manager._apply_sdk_request_compat = lambda kwargs: kwargs
    manager.billing_enabled = False

    monkeypatch.setattr(
        builder_module,
        "_load_chat_runtime",
        lambda: (_FakeChatUniversal, _FakeCallback, _FakeUsage, _FakeClient),
    )
    return manager, selected_usage


def test_director_without_binding_uses_reasoning_usage(monkeypatch) -> None:
    manager, selected_usage = _build_manager(monkeypatch)
    manager._default_usage_key_resolver = lambda agent_name: (
        "reason" if agent_name == "agent_director" else "main"
    )

    manager.get_user_llm("user-1", agent_name="agent_director")

    assert selected_usage["key"] == "reason"


def test_matchbox_without_host_resolver_uses_generic_main_usage(monkeypatch) -> None:
    manager, selected_usage = _build_manager(monkeypatch)

    manager.get_user_llm("user-1", agent_name="agent_director")

    assert selected_usage["key"] == "main"


def test_other_agent_without_binding_keeps_main_usage(monkeypatch) -> None:
    manager, selected_usage = _build_manager(monkeypatch)

    manager.get_user_llm("user-1", agent_name="agent_scriptwriter")

    assert selected_usage["key"] == "main"


def test_explicit_agent_binding_wins_over_default(monkeypatch) -> None:
    binding = SimpleNamespace(target_type="usage", usage_key="fast")
    manager, selected_usage = _build_manager(monkeypatch, binding=binding)

    manager.get_user_llm("user-1", agent_name="agent_director")

    assert selected_usage["key"] == "fast"
