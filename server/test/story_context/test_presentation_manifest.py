from __future__ import annotations

import os
from pathlib import Path

import pytest

from story import presentation_manifest as pm


PNG_BYTES = b"\x89PNG\r\n\x1a\npresentation-test"


def test_background_asset_manifest_snapshot_and_path_guard(monkeypatch, tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    monkeypatch.setattr(pm, "get_project_path", lambda user_id, project_name: str(project_root))

    asset = pm.upload_background_asset(
        user_id="u1",
        project_name="p1",
        data=PNG_BYTES,
        filename="classroom.png",
        content_type="image/png",
        title="教室黄昏",
    )

    manifest = pm.load_project_manifest("u1", "p1")
    assert asset["id"].startswith("bg_")
    assert manifest["assets"][asset["id"]]["title"] == "教室黄昏"
    assert manifest["ignore"]["unity"]["actKeys"] == ["bg", "sprite"]
    assert pm.get_ignored_node_keys(manifest, "unity") == {"presentation"}
    assert manifest["runtime"]["web"]["actBindings"]["sprite"]["type"] == "character_sprite"
    assert pm.filter_act_for_target(
        {"bg": asset["id"], "sprite": "sprite_demo", "shake": "light"},
        manifest,
        "unity",
    ) == {"shake": "light"}
    assert pm.filter_act_for_target({"bg": asset["id"], "shake": "light"}, manifest, "web") == {
        "bg": asset["id"],
        "shake": "light",
    }

    asset_path = pm.get_project_asset_path("u1", "p1", asset["path"])
    assert os.path.isfile(asset_path)
    assert Path(asset_path).read_bytes() == PNG_BYTES

    sprite = pm.upload_character_sprite_asset(
        user_id="u1",
        project_name="p1",
        data=PNG_BYTES,
        filename="hero.png",
        content_type="image/png",
        title="主角默认立绘",
        character_id="1",
    )
    manifest = pm.load_project_manifest("u1", "p1")
    assert sprite["id"].startswith("sprite_")
    assert manifest["assets"][sprite["id"]]["type"] == "character_sprite"
    assert manifest["assets"][sprite["id"]]["characterId"] == "1"

    with pytest.raises(pm.PresentationAssetError):
        pm.get_project_asset_path("u1", "p1", "../escape.png")

    snapshot_path = tmp_path / "story_snapshot.sqlite"
    snapshot_path.write_bytes(b"sqlite-placeholder")
    sidecar = pm.copy_presentation_snapshot("u1", "p1", str(snapshot_path))

    assert sidecar == str(tmp_path / "story_snapshot_presentation")
    snapshot_manifest = pm.load_snapshot_manifest(str(snapshot_path))
    assert snapshot_manifest["assets"][asset["id"]]["path"] == asset["path"]
    assert snapshot_manifest["assets"][sprite["id"]]["path"] == sprite["path"]
    snapshot_asset_path = pm.get_snapshot_asset_path(str(snapshot_path), asset["path"])
    assert os.path.isfile(snapshot_asset_path)
    assert Path(snapshot_asset_path).read_bytes() == PNG_BYTES
    assert os.path.isfile(pm.get_snapshot_asset_path(str(snapshot_path), sprite["path"]))

    pm.remove_presentation_snapshot(str(snapshot_path))
    assert not Path(sidecar).exists()
