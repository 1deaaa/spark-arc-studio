from __future__ import annotations

import os
import asyncio
from pathlib import Path

from fastapi.responses import JSONResponse


def test_project_character_directory_initializes_system_characters(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("core.utils.USERDATA_ROOT", str(tmp_path))

    from core.utils import ensure_project_characters_directory

    chr_dir = ensure_project_characters_directory("7", "demo")
    from core.character_store import read_character_records

    records = read_character_records("7", "demo")
    assert records["-1"]["name"] == "旁白"
    assert records["-2"]["name"] == "?"
    assert os.listdir(chr_dir) == ["characters.json"]


def test_character_api_hides_and_protects_system_characters(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("core.utils.USERDATA_ROOT", str(tmp_path))

    async def run_case() -> None:
        from agents.routes.characters import (
            create_character,
            delete_character,
            get_characters,
            rename_character,
            save_character,
        )
        from agents.routes.schemas import (
            CharacterSettingsCreate,
            CharacterSettingsRename,
            CharacterSettingsSave,
        )

        user = {"user_id": 7}
        await create_character(CharacterSettingsCreate(projectName="demo", name="沈棠"), user=user)

        visible = await get_characters(projectName="demo", includeContent=False, includeSystem=False, user=user)
        assert [item["id"] for item in visible] == [0]

        with_system = await get_characters(projectName="demo", includeContent=False, includeSystem=True, user=user)
        assert {item["id"]: item["name"] for item in with_system} == {-1: "旁白", -2: "?", 0: "沈棠"}

        save_result = await save_character(
            CharacterSettingsSave(projectName="demo", id=-2, content="不能改"),
            user=user,
        )
        assert isinstance(save_result, JSONResponse)
        assert save_result.status_code == 403

        rename_result = await rename_character(
            CharacterSettingsRename(projectName="demo", id=-2, newName="神秘人"),
            user=user,
        )
        assert isinstance(rename_result, JSONResponse)
        assert rename_result.status_code == 403

        delete_result = await delete_character(id=-2, projectName="demo", user=user)
        assert isinstance(delete_result, JSONResponse)
        assert delete_result.status_code == 403

    asyncio.run(run_case())


def test_character_name_map_understands_unknown_system_character(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("core.utils.USERDATA_ROOT", str(tmp_path))

    from core.utils import ensure_project_characters_directory
    from story.project_files import load_character_id_name_map

    ensure_project_characters_directory("7", "demo")

    assert load_character_id_name_map("7", "demo")["-2"] == "?"
    assert "-2" not in load_character_id_name_map("7", "demo", include_system=False)


def test_character_crud_keeps_a_single_physical_file(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("core.utils.USERDATA_ROOT", str(tmp_path))

    from core.character_store import (
        delete_character_record,
        read_character_records,
        upsert_character,
    )
    from core.utils import ensure_project_characters_directory

    chr_dir = ensure_project_characters_directory("8", "demo")
    upsert_character("8", "demo", 0, name="沈棠", content="# 沈棠\n\n档案管理员")
    upsert_character("8", "demo", 1, name="林烬", content="# 林烬\n\n调查员")
    delete_character_record("8", "demo", 0)

    records = read_character_records("8", "demo")
    assert records["1"]["name"] == "林烬"
    assert "0" not in records
    assert os.listdir(chr_dir) == ["characters.json"]


def test_character_batch_upsert_keeps_previous_batches_and_updates_by_name(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("core.utils.USERDATA_ROOT", str(tmp_path))

    from core.character_store import (
        read_character_records,
        replace_regular_characters,
        upsert_regular_characters,
    )

    replace_regular_characters("8", "batch-demo", [("沈棠", "旧档案"), ("林烬", "调查员")])
    created, updated = upsert_regular_characters(
        "8",
        "batch-demo",
        [("沈棠", "新档案"), ("周遥", "记者")],
    )

    records = read_character_records("8", "batch-demo")
    regular = {record["name"]: record["content"] for cid, record in records.items() if int(cid) >= 0}
    assert (created, updated) == (1, 1)
    assert regular == {"沈棠": "新档案", "林烬": "调查员", "周遥": "记者"}


def test_semantic_collection_expands_character_records(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("core.utils.USERDATA_ROOT", str(tmp_path))

    from core.character_store import write_character_records
    from story.project_files import collect_project_files
    from story.semantic_chunker import SemanticChunker

    write_character_records(
        "9",
        "demo",
        {
            "0": {"name": "沈棠", "content": "职业：档案管理员"},
            "1": {"name": "林烬", "content": "别名：阿烬\n职业：调查员"},
        },
    )

    project_files = collect_project_files("9", "demo")
    character_files = [item for item in project_files if item.format_key == "character"]
    assert [item.metadata["character_name"] for item in character_files] == ["沈棠", "林烬"]
    assert len({item.abs_path for item in character_files}) == 1
    assert all("characters.json#character=" in item.rel_path for item in character_files)

    chunker = SemanticChunker()
    chunks = [chunker.chunk_file(item, {"nodes": []})[0] for item in character_files]
    assert [chunk.metadata["character_id"] for chunk in chunks] == ["0", "1"]
    assert [chunk.metadata["character_name"] for chunk in chunks] == ["沈棠", "林烬"]
