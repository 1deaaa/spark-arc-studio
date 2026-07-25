import asyncio
import json
from types import SimpleNamespace

import pytest

from agents.agent_style import utils as style_utils
from agents.routes.schemas import StyleApplyRequest
from agents.routes.style import apply_style, get_style_profile, list_styles, style_router
from core.request_context import current_project_name
from story.routes_project import _build_project_style_snapshot, _restore_project_style_snapshot


@pytest.fixture(autouse=True)
def _isolate_project_context():
    token = current_project_name.set(None)
    try:
        yield
    finally:
        current_project_name.reset(token)


def _use_temporary_userdata(monkeypatch, tmp_path) -> str:
    userdata_root = str(tmp_path / "userdata")
    monkeypatch.setattr("core.utils.USERDATA_ROOT", userdata_root)
    monkeypatch.setattr(style_utils, "USERDATA_ROOT", userdata_root)
    return userdata_root


def test_new_user_has_no_style_and_no_default_api(monkeypatch, tmp_path) -> None:
    _use_temporary_userdata(monkeypatch, tmp_path)

    result = asyncio.run(list_styles(user={"user_id": "new-style-user"}))

    assert result == {"success": True, "styles": []}
    route_paths = {route.path for route in style_router.routes}
    assert "/api/ai/style-default" not in route_paths
    assert "/api/ai/style-set-default" not in route_paths


def test_style_profile_and_project_binding_only_use_style_id(monkeypatch, tmp_path) -> None:
    _use_temporary_userdata(monkeypatch, tmp_path)
    user_id = "style-user"
    project_name = "demo"

    style_utils.save_style_profile_to_file("项目风格", "## 项目风格", user_id=user_id)
    record = style_utils.find_style_profile_by_name("项目风格", user_id=user_id)
    assert record
    assert style_utils.load_style_profile_record("项目风格", user_id=user_id) is None
    assert style_utils.load_style_profile_record(record["style_id"], user_id=user_id) == record
    assert set(style_utils.style_profile_summary(record)) == {"style_id", "style_name"}

    document = record["path"].read_text(encoding="utf-8")
    metadata, body = style_utils.parse_style_profile_document(document)
    assert set(metadata) == {"style_id", "style_name", "created_at", "format_version"}
    assert body == "## 项目风格"

    binding = style_utils.save_project_style_binding(
        user_id,
        project_name,
        record["style_id"],
    )
    assert binding == {"style_id": record["style_id"]}

    binding_path = style_utils.get_project_style_binding_path(user_id, project_name)
    assert json.loads(binding_path.read_text(encoding="utf-8")) == {
        "style_id": record["style_id"]
    }
    assert style_utils.load_project_style_binding_record(user_id, project_name) == {
        "style_id": record["style_id"],
        "style_name": "项目风格",
    }


def test_unbound_project_does_not_resolve_or_inject_style(monkeypatch, tmp_path) -> None:
    _use_temporary_userdata(monkeypatch, tmp_path)
    user_id = "style-user"
    project_name = "demo"
    style_utils.save_style_profile_to_file("未应用风格", "## 不应注入", user_id=user_id)

    assert style_utils.resolve_project_style_binding(user_id, project_name) is None
    assert style_utils.resolve_project_style_id(user_id, project_name) is None
    assert style_utils.load_project_style_profile(user_id, project_name) is None

    response = asyncio.run(
        get_style_profile(
            SimpleNamespace(query_params={"projectName": project_name}),
            user={"user_id": user_id},
        )
    )
    assert response.status_code == 404


def test_apply_and_cancel_are_a_single_project_switch(monkeypatch, tmp_path) -> None:
    _use_temporary_userdata(monkeypatch, tmp_path)
    user_id = "style-user"
    project_name = "demo"
    style_utils.save_style_profile_to_file("项目风格", "## 项目风格", user_id=user_id)
    record = style_utils.find_style_profile_by_name("项目风格", user_id=user_id)
    assert record

    apply_result = asyncio.run(
        apply_style(
            StyleApplyRequest(
                styleId=record["style_id"],
                projectName=project_name,
                applied=True,
            ),
            user={"user_id": user_id},
        )
    )
    assert apply_result == {
        "success": True,
        "project": project_name,
        "applied": True,
        "project_binding": {
            "style_id": record["style_id"],
            "style_name": "项目风格",
        },
    }

    profile_result = asyncio.run(
        get_style_profile(
            SimpleNamespace(query_params={"projectName": project_name}),
            user={"user_id": user_id},
        )
    )
    assert profile_result["style_id"] == record["style_id"]
    assert profile_result["style_name"] == "项目风格"
    assert profile_result["project_binding"] == apply_result["project_binding"]

    cancel_result = asyncio.run(
        apply_style(
            StyleApplyRequest(
                styleId=record["style_id"],
                projectName=project_name,
                applied=False,
            ),
            user={"user_id": user_id},
        )
    )
    assert cancel_result == {
        "success": True,
        "project": project_name,
        "applied": False,
        "project_binding": None,
    }
    assert style_utils.resolve_project_style_binding(user_id, project_name) is None
    assert style_utils.load_project_style_profile(user_id, project_name) is None


def test_applying_another_style_replaces_the_only_binding(monkeypatch, tmp_path) -> None:
    _use_temporary_userdata(monkeypatch, tmp_path)
    user_id = "style-user"
    project_name = "demo"
    style_utils.save_style_profile_to_file("风格一", "## 风格一", user_id=user_id)
    style_utils.save_style_profile_to_file("风格二", "## 风格二", user_id=user_id)
    first = style_utils.find_style_profile_by_name("风格一", user_id=user_id)
    second = style_utils.find_style_profile_by_name("风格二", user_id=user_id)
    assert first and second

    style_utils.save_project_style_binding(user_id, project_name, first["style_id"])
    style_utils.save_project_style_binding(user_id, project_name, second["style_id"])

    binding = style_utils.load_project_style_binding_record(user_id, project_name)
    assert binding == {"style_id": second["style_id"], "style_name": "风格二"}


def test_stale_cancel_cannot_clear_a_new_project_binding(monkeypatch, tmp_path) -> None:
    _use_temporary_userdata(monkeypatch, tmp_path)
    user_id = "style-user"
    project_name = "demo"
    style_utils.save_style_profile_to_file("旧风格", "## 旧风格", user_id=user_id)
    style_utils.save_style_profile_to_file("新风格", "## 新风格", user_id=user_id)
    old_record = style_utils.find_style_profile_by_name("旧风格", user_id=user_id)
    new_record = style_utils.find_style_profile_by_name("新风格", user_id=user_id)
    assert old_record and new_record
    style_utils.save_project_style_binding(user_id, project_name, new_record["style_id"])

    response = asyncio.run(
        apply_style(
            StyleApplyRequest(
                styleId=old_record["style_id"],
                projectName=project_name,
                applied=False,
            ),
            user={"user_id": user_id},
        )
    )
    assert response.status_code == 409
    binding = style_utils.load_project_style_binding_record(user_id, project_name)
    assert binding and binding["style_id"] == new_record["style_id"]


def test_project_export_preserves_only_style_identity(monkeypatch, tmp_path) -> None:
    _use_temporary_userdata(monkeypatch, tmp_path)
    source_user_id = "source-user"
    target_user_id = "target-user"
    source_project = "源项目"
    target_project = "目标项目"
    style_utils.save_style_profile_to_file("项目风格", "## 项目风格", user_id=source_user_id)
    source_record = style_utils.find_style_profile_by_name("项目风格", user_id=source_user_id)
    assert source_record
    style_utils.save_project_style_binding(
        source_user_id,
        source_project,
        source_record["style_id"],
    )

    snapshot = _build_project_style_snapshot(source_user_id, source_project)
    assert snapshot
    assert snapshot["version"] == 2
    assert snapshot["style_id"] == source_record["style_id"]
    assert "author_id" not in snapshot
    assert "binding_source" not in snapshot

    target_project_path = style_utils.get_project_style_binding_path(
        target_user_id,
        target_project,
    ).parent
    snapshot_path = target_project_path / ".sparkarc" / "exported_style_profile.json"
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_path.write_text(json.dumps(snapshot, ensure_ascii=False), encoding="utf-8")

    restored = _restore_project_style_snapshot(
        target_user_id,
        target_project,
        str(target_project_path),
    )
    assert restored
    assert restored["styleId"] == source_record["style_id"]
    assert "authorId" not in restored
    target_binding = style_utils.load_project_style_binding_record(
        target_user_id,
        target_project,
    )
    assert target_binding and target_binding["style_id"] == source_record["style_id"]


def test_duplicate_import_issues_a_new_style_id(monkeypatch, tmp_path) -> None:
    _use_temporary_userdata(monkeypatch, tmp_path)
    user_id = "style-user"
    style_utils.save_style_profile_to_file("原风格", "## 正文", user_id=user_id)
    original = style_utils.find_style_profile_by_name("原风格", user_id=user_id)
    assert original
    exported_document = (
        "---\n"
        f"style_id: {original['style_id']}\n"
        "style_name: 原风格\n"
        "---\n\n"
        "## 正文\n"
    )

    style_utils.save_style_profile_to_file(
        "原风格-2",
        exported_document,
        user_id=user_id,
        use_embedded_identity=False,
    )
    duplicate = style_utils.find_style_profile_by_name("原风格-2", user_id=user_id)
    assert duplicate
    assert duplicate["style_id"] != original["style_id"]
