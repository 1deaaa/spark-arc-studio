from __future__ import annotations

import json
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from story import presentation_manifest as pm


PNG_BYTES = b"\x89PNG\r\n\x1a\npresentation-test"


def test_legacy_manifest_recursively_restores_defaults(monkeypatch, tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    monkeypatch.setattr(pm, "get_project_path", lambda user_id, project_name: str(project_root))

    legacy_manifest = {
        "schema": "sparkarc.presentation.v2",
        "version": 2,
        "targets": ["web"],
        "ignore": {
            "unity": {
                "actKeys": ["bg", "sprite"],
                "assetTargets": ["web"],
                "customRule": "keep",
            }
        },
        "assets": {
            "bg_legacy": {
                "id": "bg_legacy",
                "type": "background",
            }
        },
        "runtime": {
            "web": {
                "actBindings": {"legacy": True},
                "customSetting": "keep",
                "cueBindings": {
                    "bg": {"fallback": "custom"},
                    "customCue": {"type": "custom"},
                },
            }
        },
    }
    (project_root / pm.MANIFEST_FILENAME).write_text(
        json.dumps(legacy_manifest, ensure_ascii=False),
        encoding="utf-8",
    )

    manifest = pm.load_project_manifest("u1", "p1")

    assert manifest["ignore"]["unity"]["actKeys"] == ["bg", "sprite"]
    assert manifest["ignore"]["unity"]["nodeKeys"] == ["presentation"]
    assert manifest["ignore"]["unity"]["assetTargets"] == ["web"]
    assert manifest["ignore"]["unity"]["customRule"] == "keep"
    assert pm.get_ignored_node_keys(manifest, "unity") == {"presentation"}
    assert manifest["assets"]["bg_legacy"]["type"] == "background"
    assert manifest["runtime"]["web"]["customSetting"] == "keep"
    assert "actBindings" not in manifest["runtime"]["web"]
    assert manifest["runtime"]["web"]["cueBindings"]["bg"] == {
        "type": "background",
        "fallback": "custom",
    }
    assert manifest["runtime"]["web"]["cueBindings"]["sprite"]["type"] == "character_sprite"
    assert manifest["runtime"]["web"]["cueBindings"]["illustration"]["fallback"] == "background_and_sprite"
    assert manifest["runtime"]["web"]["cueBindings"]["customCue"] == {"type": "custom"}


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
    assert manifest["ignore"]["unity"]["actKeys"] == []
    assert pm.get_ignored_node_keys(manifest, "unity") == {"presentation"}
    assert manifest["runtime"]["web"]["cueBindings"]["sprite"]["type"] == "character_sprite"
    assert manifest["schema"] == "sparkarc.presentation.v2"
    assert manifest["runtime"]["web"]["cueBindings"]["illustration"]["type"] == "scene_illustration"
    assert pm.filter_act_for_target(
        {"shake": "light"},
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

    illustration = pm.upload_scene_illustration_asset(
        user_id="u1",
        project_name="p1",
        data=PNG_BYTES,
        filename="rainy-moment.png",
        content_type="image/png",
        title="雨夜回望",
        scene_name="1-1 初遇",
        node_id="7",
    )
    manifest = pm.load_project_manifest("u1", "p1")
    assert illustration["id"].startswith("ill_")
    assert manifest["assets"][illustration["id"]]["type"] == "scene_illustration"
    assert manifest["assets"][illustration["id"]]["sceneName"] == "1-1 初遇"
    assert manifest["assets"][illustration["id"]]["nodeId"] == "7"

    with pytest.raises(pm.PresentationAssetError):
        pm.get_project_asset_path("u1", "p1", "../escape.png")

    snapshot_path = tmp_path / "story_snapshot.sqlite"
    snapshot_path.write_bytes(b"sqlite-placeholder")
    sidecar = pm.copy_presentation_snapshot("u1", "p1", str(snapshot_path))

    assert sidecar == str(tmp_path / "story_snapshot_presentation")
    snapshot_manifest = pm.load_snapshot_manifest(str(snapshot_path))
    assert snapshot_manifest["assets"][asset["id"]]["path"] == asset["path"]
    assert snapshot_manifest["assets"][sprite["id"]]["path"] == sprite["path"]
    assert snapshot_manifest["assets"][illustration["id"]]["path"] == illustration["path"]
    snapshot_asset_path = pm.get_snapshot_asset_path(str(snapshot_path), asset["path"])
    assert os.path.isfile(snapshot_asset_path)
    assert Path(snapshot_asset_path).read_bytes() == PNG_BYTES
    assert os.path.isfile(pm.get_snapshot_asset_path(str(snapshot_path), sprite["path"]))

    pm.remove_presentation_snapshot(str(snapshot_path))
    assert not Path(sidecar).exists()


def test_presentation_snapshot_restore_replaces_current_manifest_and_assets(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    monkeypatch.setattr(pm, "get_project_path", lambda user_id, project_name: str(project_root))

    original = pm.upload_background_asset(
        user_id="u1",
        project_name="p1",
        data=PNG_BYTES,
        filename="original.png",
        title="快照背景",
    )
    snapshot_path = tmp_path / "story_snapshot.sqlite"
    snapshot_path.write_bytes(b"sqlite-placeholder")
    pm.copy_presentation_snapshot("u1", "p1", str(snapshot_path))

    current = pm.upload_background_asset(
        user_id="u1",
        project_name="p1",
        data=PNG_BYTES + b"-current",
        filename="current.png",
        title="当前背景",
    )
    assert current["id"] != original["id"]
    assert current["id"] in pm.load_project_manifest("u1", "p1")["assets"]

    assert pm.restore_presentation_snapshot("u1", "p1", str(snapshot_path)) is True

    restored_manifest = pm.load_project_manifest("u1", "p1")
    assert set(restored_manifest["assets"]) == {original["id"]}
    assert Path(pm.get_project_asset_path("u1", "p1", original["path"])).is_file()
    assert not Path(pm.get_project_asset_path("u1", "p1", current["path"])).exists()
    assert not list(project_root.glob(".presentation-*-*"))


def test_legacy_presentation_snapshot_without_sidecar_keeps_current_assets(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    monkeypatch.setattr(pm, "get_project_path", lambda user_id, project_name: str(project_root))

    current = pm.upload_background_asset(
        user_id="u1",
        project_name="p1",
        data=PNG_BYTES,
        filename="current.png",
        title="当前背景",
    )
    snapshot_path = tmp_path / "legacy_snapshot.sqlite"
    snapshot_path.write_bytes(b"sqlite-placeholder")

    assert pm.restore_presentation_snapshot("u1", "p1", str(snapshot_path)) is False
    manifest = pm.load_project_manifest("u1", "p1")
    assert current["id"] in manifest["assets"]


def test_manifest_concurrent_asset_updates_are_atomic(monkeypatch, tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    monkeypatch.setattr(pm, "get_project_path", lambda user_id, project_name: str(project_root))

    def upload(index: int) -> dict:
        return pm.upload_background_asset(
            user_id="u1",
            project_name="p1",
            data=PNG_BYTES + str(index).encode("ascii"),
            filename=f"background-{index}.png",
            content_type="image/png",
            title=f"背景 {index}",
        )

    with ThreadPoolExecutor(max_workers=4) as executor:
        assets = list(executor.map(upload, range(12)))

    manifest = pm.load_project_manifest("u1", "p1")
    assert set(manifest["assets"]) == {asset["id"] for asset in assets}
    assert not list(project_root.rglob("*.tmp"))

    updated, persisted = pm.update_presentation_asset_metadata(
        "u1",
        "p1",
        assets[0]["id"],
        {"generation": {"provider": "offline-test"}},
    )
    assert updated["generation"]["provider"] == "offline-test"
    assert persisted["assets"][assets[0]["id"]]["generation"]["provider"] == "offline-test"


def test_remove_presentation_asset_keeps_manifest_and_file_in_sync(monkeypatch, tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    monkeypatch.setattr(pm, "get_project_path", lambda user_id, project_name: str(project_root))

    asset = pm.upload_background_asset(
        user_id="u1",
        project_name="p1",
        data=PNG_BYTES,
        filename="generated.png",
        title="待提交背景",
        source="ai",
    )
    asset_path = Path(pm.get_project_asset_path("u1", "p1", asset["path"]))
    assert asset_path.is_file()

    assert pm.remove_presentation_asset("u1", "p1", asset["id"], expected_source="ai") is True
    assert asset["id"] not in pm.load_project_manifest("u1", "p1")["assets"]
    assert not asset_path.exists()
    assert pm.remove_presentation_asset("u1", "p1", asset["id"], expected_source="ai") is False


def test_background_catalog_only_contains_explicit_library_assets(monkeypatch, tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    monkeypatch.setattr(pm, "get_project_path", lambda user_id, project_name: str(project_root))

    ordinary = pm.upload_background_asset(
        user_id="u1",
        project_name="p1",
        data=PNG_BYTES,
        filename="node-background.png",
        title="节点临时背景",
    )
    library = pm.upload_background_asset(
        user_id="u1",
        project_name="p1",
        data=PNG_BYTES + b"-library",
        filename="library-background.png",
        title="项目常用教室",
        library=True,
    )

    manifest = pm.load_project_manifest("u1", "p1")
    assert manifest["assets"][ordinary["id"]].get("library") is not True
    assert manifest["assets"][library["id"]]["library"] is True
    assert pm.get_project_background_catalog("u1", "p1") == [
        {"id": library["id"], "title": "项目常用教室"},
    ]


def test_presentation_project_guard_requires_existing_script_project(monkeypatch, tmp_path: Path) -> None:
    from story import routes_presentation as routes

    project_root = tmp_path / "project"
    monkeypatch.setattr(routes, "get_project_path", lambda user_id, project_name: str(project_root))

    missing = routes._presentation_project_error("u1", "missing")
    assert missing is not None and missing.status_code == 404

    project_root.mkdir()
    monkeypatch.setattr(routes, "get_workspace_mode", lambda user_id, project_name: "novel")
    novel = routes._presentation_project_error("u1", "novel")
    assert novel is not None and novel.status_code == 409

    monkeypatch.setattr(routes, "get_workspace_mode", lambda user_id, project_name: "script")
    assert routes._presentation_project_error("u1", "script") is None
