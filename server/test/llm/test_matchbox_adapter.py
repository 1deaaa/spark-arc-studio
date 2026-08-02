"""SparkArc 对 Agent Matchbox 的兼容适配测试。"""

from __future__ import annotations

import sys
from types import SimpleNamespace

from llm import matchbox_adapter
from llm.agen_matchbox import env_utils


def test_legacy_env_file_values_are_mapped(monkeypatch) -> None:
    legacy_value = "LegacySparkArc/2.0"

    def fake_env_file_var(name: str, default=None):
        if name == "SPARKARC_OPENAI_COMPAT_USER_AGENT":
            return legacy_value
        return default

    monkeypatch.setattr(env_utils, "get_env_file_var", fake_env_file_var)
    monkeypatch.setenv("AGENT_MATCHBOX_OPENAI_COMPAT_USER_AGENT", "SparkArc/1.0")
    monkeypatch.setattr(
        matchbox_adapter,
        "_adapter_defaulted_env_names",
        {"AGENT_MATCHBOX_OPENAI_COMPAT_USER_AGENT"},
    )

    matchbox_adapter._apply_legacy_env_file_aliases()

    assert (
        matchbox_adapter.os.environ["AGENT_MATCHBOX_OPENAI_COMPAT_USER_AGENT"]
        == legacy_value
    )


def test_sparkarc_migration_commands_disable_matchbox(monkeypatch) -> None:
    isolated_os = SimpleNamespace(environ={})
    monkeypatch.setattr(matchbox_adapter, "os", isolated_os)
    monkeypatch.setattr(sys, "argv", ["gen_migration.py"])

    matchbox_adapter.configure_sparkarc_matchbox_environment()

    assert isolated_os.environ["AGENT_MATCHBOX_DISABLED"] == "1"
