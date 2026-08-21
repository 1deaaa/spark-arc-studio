from __future__ import annotations

import json

from agents.auto_write_state import (
    AUTO_WRITE_STATE_FILENAME,
    repair_stale_auto_write_states,
)
from agents.routes import auto_write_state as legacy_auto_write_state


def _write_state(project_dir, status: str, marker: str) -> None:
    project_dir.mkdir(parents=True)
    (project_dir / AUTO_WRITE_STATE_FILENAME).write_text(
        json.dumps({"status": status, "marker": marker}, ensure_ascii=False),
        encoding="utf-8",
    )


def test_startup_repair_uses_configured_root_and_preserves_resume_fields(tmp_path) -> None:
    running_dir = tmp_path / "uid_1" / "projects" / "运行项目"
    paused_dir = tmp_path / "uid_2" / "projects" / "暂停项目"
    complete_dir = tmp_path / "uid_3" / "projects" / "完成项目"
    _write_state(running_dir, "running", "running-cursor")
    _write_state(paused_dir, "chapter_paused", "paused-cursor")
    _write_state(complete_dir, "complete", "complete-result")

    repaired = repair_stale_auto_write_states(str(tmp_path))

    assert repaired == 2
    running = json.loads((running_dir / AUTO_WRITE_STATE_FILENAME).read_text(encoding="utf-8"))
    paused = json.loads((paused_dir / AUTO_WRITE_STATE_FILENAME).read_text(encoding="utf-8"))
    complete = json.loads((complete_dir / AUTO_WRITE_STATE_FILENAME).read_text(encoding="utf-8"))
    assert running["status"] == "interrupted"
    assert paused["status"] == "interrupted"
    assert running["marker"] == "running-cursor"
    assert paused["marker"] == "paused-cursor"
    assert "可从已保存进度恢复" in running["lastError"]
    assert complete == {"status": "complete", "marker": "complete-result"}


def test_startup_repair_is_idempotent(tmp_path) -> None:
    project_dir = tmp_path / "uid_1" / "projects" / "项目"
    _write_state(project_dir, "running", "cursor")

    assert repair_stale_auto_write_states(str(tmp_path)) == 1
    first = (project_dir / AUTO_WRITE_STATE_FILENAME).read_text(encoding="utf-8")
    assert repair_stale_auto_write_states(str(tmp_path)) == 0
    assert (project_dir / AUTO_WRITE_STATE_FILENAME).read_text(encoding="utf-8") == first


def test_route_auto_write_state_is_only_a_compatibility_export() -> None:
    assert legacy_auto_write_state.repair_stale_auto_write_states is repair_stale_auto_write_states
