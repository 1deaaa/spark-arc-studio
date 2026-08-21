from __future__ import annotations

from agents.structure_artifacts import (
    get_outline_history_dir,
    save_outline_to_history,
    save_project_beat_sheet,
    save_project_outline,
    save_project_synopsis,
)
from agents.routes import schemas
from agents.structure_state import format_structure_state_warning, load_structure_state


def test_structure_state_tracks_sources_and_invalidates_downstream(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("core.utils.USERDATA_ROOT", str(tmp_path))
    project_path = tmp_path / "uid_7" / "projects" / "demo"
    project_path.mkdir(parents=True)

    save_project_synopsis("7", "demo", "第一版梗概")
    save_project_beat_sheet("7", "demo", "第一版节拍")
    save_project_outline("7", "demo", "第一版大纲")

    state = load_structure_state("7", "demo")
    assert state["artifacts"]["beat_sheet"]["derived_from"] == {"synopsis": 1}
    assert state["artifacts"]["outline"]["derived_from"] == {"synopsis": 1, "beat_sheet": 1}
    assert format_structure_state_warning(state) == ""

    save_project_synopsis("7", "demo", "第二版梗概")
    state = load_structure_state("7", "demo")
    assert state["artifacts"]["beat_sheet"]["stale"] is True
    assert state["artifacts"]["outline"]["stale"] is True
    assert "节拍表已过期" in format_structure_state_warning(state)

    save_project_beat_sheet("7", "demo", "第二版节拍")
    state = load_structure_state("7", "demo")
    assert state["artifacts"]["beat_sheet"]["derived_from"] == {"synopsis": 2}
    assert state["artifacts"]["beat_sheet"]["stale"] is False
    assert state["artifacts"]["outline"]["stale"] is True

    save_project_outline("7", "demo", "第二版大纲")
    state = load_structure_state("7", "demo")
    assert state["artifacts"]["outline"]["derived_from"] == {"synopsis": 2, "beat_sheet": 2}
    assert state["artifacts"]["outline"]["stale"] is False


def test_first_tracked_save_hydrates_existing_legacy_artifacts(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("core.utils.USERDATA_ROOT", str(tmp_path))
    project_path = tmp_path / "uid_8" / "projects" / "legacy"
    project_path.mkdir(parents=True)
    (project_path / "梗概.txt").write_text("旧梗概", encoding="utf-8")
    (project_path / "节拍表.txt").write_text("旧节拍", encoding="utf-8")
    (project_path / "大纲.txt").write_text("旧大纲", encoding="utf-8")

    save_project_synopsis("8", "legacy", "新梗概")
    state = load_structure_state("8", "legacy")

    assert state["artifacts"]["synopsis"]["revision"] == 2
    assert state["artifacts"]["beat_sheet"]["revision"] == 1
    assert state["artifacts"]["beat_sheet"]["stale"] is True
    assert state["artifacts"]["outline"]["stale"] is True


def test_new_project_starts_at_revision_one(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("core.utils.USERDATA_ROOT", str(tmp_path))
    project_path = tmp_path / "uid_9" / "projects" / "new-project"
    project_path.mkdir(parents=True)

    save_project_synopsis("9", "new-project", "首版梗概")
    state = load_structure_state("9", "new-project")

    assert state["artifacts"]["synopsis"]["revision"] == 1
    assert state["artifacts"]["beat_sheet"]["revision"] == 0
    assert state["artifacts"]["outline"]["revision"] == 0


def test_loading_missing_structure_state_has_no_filesystem_side_effect(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("core.utils.USERDATA_ROOT", str(tmp_path))
    project_path = tmp_path / "uid_10" / "projects" / "missing-project"

    state = load_structure_state("10", "missing-project")

    assert state["artifacts"]["synopsis"]["revision"] == 0
    assert not project_path.exists()


def test_route_schema_keeps_structure_persistence_as_compatibility_exports() -> None:
    assert schemas._get_history_dir is get_outline_history_dir
    assert schemas._save_outline_to_history is save_outline_to_history
    assert schemas._save_project_synopsis is save_project_synopsis
    assert schemas._save_project_beat_sheet is save_project_beat_sheet
    assert schemas._save_project_outline is save_project_outline
