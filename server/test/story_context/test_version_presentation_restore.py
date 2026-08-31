from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

from story import presentation_manifest as pm
from story import routes_version


PNG_BYTES = b"\x89PNG\r\n\x1a\npresentation-version-test"


def test_restore_version_restores_database_and_presentation_sidecar(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    monkeypatch.setattr(pm, "get_project_path", lambda user_id, project_name: str(project_root))
    monkeypatch.setattr(routes_version, "get_project_path", lambda user_id, project_name: str(project_root))

    snapshot_asset = pm.upload_background_asset(
        user_id="1",
        project_name="demo",
        data=PNG_BYTES,
        filename="snapshot.png",
        title="快照背景",
    )
    snapshot_path = tmp_path / "version.db"
    snapshot_path.write_bytes(b"snapshot-db")
    pm.copy_presentation_snapshot("1", "demo", str(snapshot_path))

    current_asset = pm.upload_background_asset(
        user_id="1",
        project_name="demo",
        data=PNG_BYTES + b"-current",
        filename="current.png",
        title="当前背景",
    )
    (project_root / "stories.db").write_bytes(b"current-db")

    version = SimpleNamespace(
        description="[[format:script]]\n版本测试",
        project_name="demo",
        snapshot_path=str(snapshot_path),
        version_name="测试版本",
    )

    class FakeQuery:
        def filter_by(self, **kwargs):
            return self

        def first(self):
            return version

    class FakeSession:
        def query(self, model):
            return FakeQuery()

        def close(self):
            return None

    monkeypatch.setattr(routes_version, "UserInfoSession", FakeSession)

    result = asyncio.run(routes_version.restore_version("version-id", user={"user_id": "1"}))

    assert result["success"] is True
    assert (project_root / "stories.db").read_bytes() == b"snapshot-db"
    restored_manifest = pm.load_project_manifest("1", "demo")
    assert set(restored_manifest["assets"]) == {snapshot_asset["id"]}
    assert current_asset["id"] not in restored_manifest["assets"]
    assert Path(pm.get_project_asset_path("1", "demo", snapshot_asset["path"])).is_file()
    assert not Path(pm.get_project_asset_path("1", "demo", current_asset["path"])).exists()
