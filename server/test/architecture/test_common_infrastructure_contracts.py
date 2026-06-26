from __future__ import annotations

import json
from pathlib import Path

import pytest

from agents.tools.common import _apply_patch
from agents.routes.context_builder import build_story_tags_hint
from core.file_ingest.chunking import TokenTextSplitter
from core.migration_specs import get_db_path, get_db_spec, get_version_dir, iter_db_names, sqlite_url
from llm.agen_matchbox.models import DEFAULT_MAX_CONTEXT_TOKENS, DEFAULT_MAX_OUTPUT_TOKENS


def test_apply_patch_exact_append_whitespace_and_json_validation(tmp_path: Path) -> None:
    target = tmp_path / "story.json"
    target.write_text('{"name": "旧名", "items": [1]}\n', encoding="utf-8")

    result = _apply_patch(str(target), "旧名", "新名", validate_json=True, file_label="story.json")
    assert "已成功局部更新" in result
    assert json.loads(target.read_text(encoding="utf-8"))["name"] == "新名"

    bad_result = _apply_patch(str(target), '"items": [1]', '"items": [', validate_json=True, file_label="story.json")
    assert bad_result.startswith("局部修改失败")
    assert json.loads(target.read_text(encoding="utf-8"))["items"] == [1]

    loose = tmp_path / "loose.txt"
    loose.write_text("第一行   很多空格\n\n\n第二行\n", encoding="utf-8")
    loose_result = _apply_patch(str(loose), "第一行 很多空格\n\n第二行", "替换后", file_label="loose.txt")
    assert "已成功局部更新" in loose_result
    assert loose.read_text(encoding="utf-8") == "替换后\n第二行\n"

    append_result = _apply_patch(str(loose), "", "追加", file_label="loose.txt")
    assert "末尾追加" in append_result
    assert loose.read_text(encoding="utf-8").endswith("\n追加")


def test_token_text_splitter_keeps_stable_chunk_metadata(monkeypatch) -> None:
    monkeypatch.setattr("core.file_ingest.chunking.estimate_tokens", lambda text, model=None: len(text))

    text = "甲" * 8 + "。" + "乙" * 8 + "。" + "丙" * 3 + "。"
    splitter = TokenTextSplitter(
        chunk_tokens=10,
        min_tokens=1,
        tail_merge_threshold_ratio=0.5,
        tail_merge_cap_ratio=1.4,
    )
    chunks = splitter.split(text)

    assert len(chunks) == 2
    assert [chunk.index for chunk in chunks] == [0, 1]
    assert all(chunk.total == 2 for chunk in chunks)
    assert chunks[1].previous_tail == chunks[0].text[-splitter.TAIL_CHARS:]

    _chunks, info = splitter.split_with_info(text)
    assert info["chunk_count"] == 2
    assert info["chunk_tokens_target"] == 10


def test_migration_specs_keep_known_database_branches(monkeypatch, tmp_path: Path) -> None:
    users_db = tmp_path / "users.sqlite"
    monkeypatch.setenv("SPARKARC_ALEMBIC_USERS_DB", str(users_db))

    assert set(iter_db_names()) == {"users", "llm"}
    assert get_db_spec("users").version_subdir == "users"
    assert get_db_path("users") == users_db.resolve()
    assert get_version_dir("users", base_dir=tmp_path) == tmp_path.resolve() / "alembic" / "versions" / "users"
    assert sqlite_url(users_db).startswith("sqlite:///")


def test_auto_migrate_stamps_head_when_duplicate_object_matches_model(monkeypatch, tmp_path: Path) -> None:
    from core import auto_migrate

    db_path = tmp_path / "llm.sqlite"
    stamped = []

    monkeypatch.setattr(auto_migrate, "get_database_url", lambda db_name: "sqlite:///fake")
    monkeypatch.setattr(auto_migrate, "_get_db_path", lambda db_name: str(db_path))
    monkeypatch.setattr(auto_migrate, "_get_current_db_revision", lambda path: "old")
    monkeypatch.setattr(auto_migrate, "_get_head_revision", lambda base_dir, db_name: "head")
    monkeypatch.setattr(auto_migrate, "_build_alembic_config", lambda base_dir, db_name: object())
    monkeypatch.setattr(
        auto_migrate.command,
        "upgrade",
        lambda cfg, target: (_ for _ in ()).throw(
            RuntimeError("(sqlite3.OperationalError) duplicate column name: recharge_url")
        ),
    )
    monkeypatch.setattr(
        auto_migrate,
        "_describe_schema_drift",
        lambda db_name, db_path: {
            "missing_tables": [],
            "missing_columns": [],
            "extra_tables": [],
            "extra_columns": [],
        },
    )
    monkeypatch.setattr(auto_migrate, "_stamp_head", lambda db_name, db_path, base_dir: stamped.append((db_name, db_path, base_dir)))
    monkeypatch.setattr(
        auto_migrate,
        "_heal_orphan_revision",
        lambda db_name, db_path, base_dir: pytest.fail("结构一致时不应触发结构自愈"),
    )

    auto_migrate.run_db_upgrade("llm", str(tmp_path))

    assert stamped == [("llm", str(db_path), str(tmp_path))]


def test_auto_migrate_self_heals_duplicate_object_when_model_objects_missing(monkeypatch, tmp_path: Path) -> None:
    from core import auto_migrate

    db_path = tmp_path / "llm.sqlite"
    healed = []

    monkeypatch.setattr(auto_migrate, "get_database_url", lambda db_name: "sqlite:///fake")
    monkeypatch.setattr(auto_migrate, "_get_db_path", lambda db_name: str(db_path))
    monkeypatch.setattr(auto_migrate, "_get_current_db_revision", lambda path: "old")
    monkeypatch.setattr(auto_migrate, "_get_head_revision", lambda base_dir, db_name: "head")
    monkeypatch.setattr(auto_migrate, "_build_alembic_config", lambda base_dir, db_name: object())
    monkeypatch.setattr(
        auto_migrate.command,
        "upgrade",
        lambda cfg, target: (_ for _ in ()).throw(
            RuntimeError("(sqlite3.OperationalError) duplicate column name: recharge_url")
        ),
    )
    monkeypatch.setattr(
        auto_migrate,
        "_describe_schema_drift",
        lambda db_name, db_path: {
            "missing_tables": [],
            "missing_columns": ["llm_platforms.recharge_url"],
            "extra_tables": [],
            "extra_columns": [],
        },
    )
    monkeypatch.setattr(
        auto_migrate,
        "_stamp_head",
        lambda db_name, db_path, base_dir: pytest.fail("仍缺模型对象时不应直接 stamp"),
    )
    monkeypatch.setattr(auto_migrate, "_heal_orphan_revision", lambda db_name, db_path, base_dir: healed.append((db_name, db_path, base_dir)))

    auto_migrate.run_db_upgrade("llm", str(tmp_path))

    assert healed == [("llm", str(db_path), str(tmp_path))]


def test_default_llm_context_baseline_matches_modern_long_context() -> None:
    assert DEFAULT_MAX_CONTEXT_TOKENS == 256_000
    assert DEFAULT_MAX_OUTPUT_TOKENS == 64_000


def test_story_tags_hint_includes_global_workspace_mode() -> None:
    script_hint = build_story_tags_hint({"workspace_mode": "script"})
    novel_hint = build_story_tags_hint({"workspace_mode": "novel"})

    assert "【创作格式】剧本模式" in script_hint
    assert ".arc" in script_hint
    assert "【创作格式】小说模式" in novel_hint
    assert "Markdown 小说正文" in novel_hint


def test_project_story_tags_are_workspace_mode_truth_source(monkeypatch, tmp_path: Path) -> None:
    from core import project_settings

    monkeypatch.setattr(project_settings, "get_project_path", lambda user_id, project_name: str(tmp_path))

    settings_dir = tmp_path / ".sparkarc"
    settings_dir.mkdir()
    (settings_dir / "settings.json").write_text(
        json.dumps({"workspace_mode": "novel", "story_tags": {"genres": ["悬疑"]}}, ensure_ascii=False),
        encoding="utf-8",
    )

    assert project_settings.get_workspace_mode("u1", "p1") == "novel"
    tags = project_settings.get_project_story_tags("u1", "p1")
    assert tags["workspace_mode"] == "novel"
    assert tags["genres"] == ["悬疑"]

    project_settings.set_project_story_tags("u1", "p1", workspace_mode="script", genres=["冒险"])
    saved = json.loads((settings_dir / "settings.json").read_text(encoding="utf-8"))
    assert "workspace_mode" not in saved
    assert saved["story_tags"]["workspace_mode"] == "novel"
    assert saved["story_tags"]["genres"] == ["冒险"]

    initialized = project_settings.initialize_project_workspace_mode("u1", "p1", "script")
    assert initialized["workspace_mode"] == "script"
    assert project_settings.get_workspace_mode("u1", "p1") == "script"


def test_workspace_mode_route_is_folded_into_story_tags() -> None:
    from core.routes_tags import tags_router

    paths = {getattr(route, "path", "") for route in tags_router.routes}
    assert "/api/project/workspace-mode" not in paths
    assert "/api/project/story-tags" in paths


def test_update_story_tags_tool_accepts_common_model_aliases() -> None:
    from agents.tools.automation import UpdateProjectStoryTagsInput

    parsed = UpdateProjectStoryTagsInput.model_validate({
        "tags": {
            "workspaceMode": "novel",
            "genres": "悬疑,冒险",
            "tones": ["冷峻"],
            "length": "中篇",
            "pointOfView": "第三人称有限视角",
        },
    })

    assert parsed.workspace_mode == "novel"
    assert parsed.genres == ["悬疑", "冒险"]
    assert parsed.length_hint == "中篇"
    assert parsed.pov == "第三人称有限视角"


def test_update_story_tags_tool_ignores_workspace_mode_after_creation(monkeypatch, tmp_path: Path) -> None:
    from agents.tools.automation import update_project_story_tags
    from core import project_settings
    from core.request_context import current_project_name, current_user_id

    monkeypatch.setattr(project_settings, "get_project_path", lambda user_id, project_name: str(tmp_path))
    project_settings.initialize_project_workspace_mode("u1", "p1", "script")

    user_token = current_user_id.set("u1")
    project_token = current_project_name.set("p1")
    try:
        result = update_project_story_tags.invoke({"workspaceMode": "novel", "genres": ["冒险"]})
    finally:
        current_project_name.reset(project_token)
        current_user_id.reset(user_token)

    tags = project_settings.get_project_story_tags("u1", "p1")
    assert tags["workspace_mode"] == "script"
    assert tags["genres"] == ["冒险"]
    assert "忽略修改请求" in result
