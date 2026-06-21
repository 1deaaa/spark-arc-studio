from __future__ import annotations

import json
import os
import asyncio
from pathlib import Path

from fastapi.responses import JSONResponse


def test_project_character_directory_initializes_system_characters(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("core.utils.USERDATA_ROOT", str(tmp_path))

    from core.utils import ensure_project_characters_directory

    chr_dir = ensure_project_characters_directory("7", "demo")
    bind_path = os.path.join(chr_dir, "chr.bind")
    with open(bind_path, "r", encoding="utf-8") as f:
        mapping = json.load(f)

    assert mapping["-1"] == " "
    assert mapping["-2"] == "?"
    assert os.path.exists(os.path.join(chr_dir, "-1.txt"))
    assert os.path.exists(os.path.join(chr_dir, "-2.txt"))


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
