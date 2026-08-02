"""Agent Matchbox GUI schema 初始化边界测试。"""

from __future__ import annotations

from llm.agen_matchbox.gui.main_window import LLMConfigGUI


class _Root:
    def __init__(self) -> None:
        self.destroyed = False

    def after(self, _delay, callback) -> None:
        callback()

    def destroy(self) -> None:
        self.destroyed = True


class _Manager:
    def __init__(self) -> None:
        self.schema_calls = 0
        self.default_calls = 0

    def ensure_schema(self) -> None:
        self.schema_calls += 1

    def initialize_defaults(self) -> None:
        self.default_calls += 1


def _build_gui(schema_initializer=None):
    gui = object.__new__(LLMConfigGUI)
    gui.root = _Root()
    gui.ai_manager = _Manager()
    gui._schema_initializer = schema_initializer
    gui._ensure_master_key_ready_on_startup = lambda: True
    gui.load_config_from_db = lambda: None
    return gui


def test_gui_uses_own_schema_initializer_by_default() -> None:
    gui = _build_gui()

    gui._bootstrap_startup()

    assert gui.ai_manager.schema_calls == 1
    assert gui.ai_manager.default_calls == 1


def test_gui_delegates_schema_initialization_to_host() -> None:
    callback_calls = []
    gui = _build_gui(lambda manager: callback_calls.append(manager))

    gui._bootstrap_startup()

    assert callback_calls == [gui.ai_manager]
    assert gui.ai_manager.schema_calls == 0
    assert gui.ai_manager.default_calls == 1
