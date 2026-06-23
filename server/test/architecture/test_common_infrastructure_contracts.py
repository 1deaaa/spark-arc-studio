from __future__ import annotations

import json
from pathlib import Path

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

    project_settings.set_project_story_tags("u1", "p1", workspace_mode="script")
    saved = json.loads((settings_dir / "settings.json").read_text(encoding="utf-8"))
    assert saved["workspace_mode"] == "script"
    assert saved["story_tags"]["workspace_mode"] == "script"


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
