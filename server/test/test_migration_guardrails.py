from pathlib import Path
import sys

import pytest


SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))


def test_llm_migration_path_honors_matchbox_home(tmp_path, monkeypatch):
    monkeypatch.delenv("SPARKARC_ALEMBIC_LLM_DB", raising=False)
    monkeypatch.setenv("AGENT_MATCHBOX_HOME", str(tmp_path / "matchbox_home"))

    from core.migration_specs import get_db_path

    assert get_db_path("llm") == (tmp_path / "matchbox_home" / "llm_config.db").resolve()


def test_explicit_alembic_db_override_wins(tmp_path, monkeypatch):
    override = tmp_path / "override.db"
    monkeypatch.setenv("AGENT_MATCHBOX_HOME", str(tmp_path / "matchbox_home"))
    monkeypatch.setenv("SPARKARC_ALEMBIC_LLM_DB", str(override))

    from core.migration_specs import get_db_path

    assert get_db_path("llm") == override.resolve()


def _patch_head_state(monkeypatch, auto_migrate, drift):
    monkeypatch.setattr(auto_migrate, "_get_db_path", lambda db_name: str(Path("dummy.db")))
    monkeypatch.setattr(auto_migrate, "_get_current_db_revision", lambda db_path: "headrev")
    monkeypatch.setattr(auto_migrate, "_get_head_revision", lambda base_dir, db_name: "headrev")
    monkeypatch.setattr(auto_migrate, "_describe_schema_drift", lambda db_name, db_path: drift)


def test_head_revision_missing_schema_fails_without_repair_flag(monkeypatch):
    from core import auto_migrate

    _patch_head_state(
        monkeypatch,
        auto_migrate,
        {
            "missing_tables": [],
            "missing_columns": ["llm_platforms.sys_credit_balance"],
            "extra_tables": [],
            "extra_columns": [],
        },
    )
    monkeypatch.delenv("SPARKARC_AUTO_MIGRATE_REPAIR_HEAD_DRIFT", raising=False)

    with pytest.raises(RuntimeError, match="gen_migration.py"):
        auto_migrate.run_db_upgrade("llm", str(Path.cwd()))


def test_head_revision_extra_schema_is_non_destructive(monkeypatch):
    from core import auto_migrate

    called = False

    def _unexpected_heal(*args, **kwargs):
        nonlocal called
        called = True

    _patch_head_state(
        monkeypatch,
        auto_migrate,
        {
            "missing_tables": [],
            "missing_columns": [],
            "extra_tables": [],
            "extra_columns": ["llm_platforms.old_column"],
        },
    )
    monkeypatch.setattr(auto_migrate, "_heal_orphan_revision", _unexpected_heal)

    auto_migrate.run_db_upgrade("llm", str(Path.cwd()))

    assert called is False


def test_head_revision_missing_schema_can_be_repaired_with_flag(monkeypatch):
    from core import auto_migrate

    calls = []

    _patch_head_state(
        monkeypatch,
        auto_migrate,
        {
            "missing_tables": ["redeem_codes"],
            "missing_columns": [],
            "extra_tables": [],
            "extra_columns": [],
        },
    )
    monkeypatch.setenv("SPARKARC_AUTO_MIGRATE_REPAIR_HEAD_DRIFT", "1")
    monkeypatch.setattr(
        auto_migrate,
        "_heal_orphan_revision",
        lambda db_name, db_path, base_dir: calls.append((db_name, db_path, base_dir)),
    )

    auto_migrate.run_db_upgrade("llm", str(Path.cwd()))

    assert calls and calls[0][0] == "llm"
