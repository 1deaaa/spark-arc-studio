from __future__ import annotations

import json
from pathlib import Path


def test_legacy_character_repository_is_read_without_mutating_project_files(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """历史角色仓库在读取时兼容，新仓库同 ID 记录优先且不改写旧文件。"""
    monkeypatch.setattr("core.utils.USERDATA_ROOT", str(tmp_path / "userdata"))

    from core.character_store import read_character_records
    from core.utils import get_project_path

    project_path = Path(get_project_path("1", "legacy"))
    character_path = project_path / "chr"
    character_path.mkdir(parents=True)
    bind_path = character_path / "chr.bind"
    bind_path.write_text(
        json.dumps({"-1": " ", "-2": "?", "0": "林小满", "1": {"name": "沈砚"}}, ensure_ascii=False),
        encoding="utf-8",
    )
    (character_path / "0.txt").write_text("林小满\n\n安静的观察者。\n", encoding="utf-8")
    (character_path / "1.txt").write_text("沈砚\n\n复读生。\n", encoding="utf-8")

    canonical_path = character_path / "characters.json"
    canonical_content = json.dumps(
        {
            "-1": {"name": "旁白", "content": "旁白正文"},
            "-2": {"name": "?", "content": "未知角色正文"},
            "1": {"name": "沈砚（新）", "content": "新仓库正文"},
        },
        ensure_ascii=False,
        indent=2,
    )
    canonical_path.write_text(canonical_content, encoding="utf-8")

    records = read_character_records("1", "legacy")

    assert records["0"] == {"name": "林小满", "content": "安静的观察者。\n"}
    assert records["1"] == {"name": "沈砚（新）", "content": "新仓库正文"}
    assert canonical_path.read_text(encoding="utf-8") == canonical_content
    assert bind_path.is_file()


def test_legacy_repository_is_materialized_by_existing_character_write_path(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """历史角色在既有写入操作中进入 characters.json，但旧文件保留不删除。"""
    monkeypatch.setattr("core.utils.USERDATA_ROOT", str(tmp_path / "userdata"))

    from core.character_store import read_character_records, upsert_character
    from core.utils import get_project_path

    character_path = Path(get_project_path("2", "legacy")) / "chr"
    character_path.mkdir(parents=True)
    (character_path / "chr.bind").write_text('{"0": "林小满"}', encoding="utf-8")
    (character_path / "0.txt").write_text("林小满\n\n旧正文", encoding="utf-8")
    (character_path / "characters.json").write_text(
        json.dumps(
            {
                "-1": {"name": "旁白", "content": ""},
                "-2": {"name": "?", "content": ""},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    upsert_character("2", "legacy", 1, name="沈砚", content="新角色")

    records = read_character_records("2", "legacy")
    assert records["0"] == {"name": "林小满", "content": "旧正文"}
    assert records["1"] == {"name": "沈砚", "content": "新角色"}
    assert (character_path / "chr.bind").is_file()
    assert (character_path / "0.txt").is_file()


def test_importer_reads_system_characters_from_legacy_repository(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """ARC 导入不能因旧版 chr.bind 缺少可见旁白名而丢失系统角色。"""
    monkeypatch.setattr("core.utils.USERDATA_ROOT", str(tmp_path / "userdata"))

    from story.importer import _load_character_records
    from core.utils import get_project_path

    project_path = Path(get_project_path("3", "legacy"))
    character_path = project_path / "chr"
    character_path.mkdir(parents=True)
    (character_path / "chr.bind").write_text(
        json.dumps({"-1": " ", "-2": "?", "0": "林小满"}, ensure_ascii=False),
        encoding="utf-8",
    )
    (character_path / "0.txt").write_text("林小满\n\n旧角色正文", encoding="utf-8")

    records = _load_character_records(str(project_path))

    assert records["-1"]["name"] == "旁白"
    assert records["-2"]["name"] == "?"
    assert records["0"] == {"name": "林小满", "content": "旧角色正文"}
    assert not (character_path / "characters.json").exists()
