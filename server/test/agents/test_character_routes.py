from __future__ import annotations

import asyncio
from pathlib import Path


def test_character_create_route_accepts_regular_chinese_name(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from agents.routes.characters import create_character
    from agents.routes.schemas import CharacterSettingsCreate
    from core.character_store import read_character_records

    monkeypatch.setattr("core.utils.USERDATA_ROOT", str(tmp_path))
    result = asyncio.run(create_character(
        CharacterSettingsCreate(projectName="demo", name="沈棠"),
        user={"user_id": "18"},
    ))

    assert result == {"success": True, "id": 0, "name": "沈棠"}
    assert read_character_records("18", "demo")["0"]["name"] == "沈棠"


def test_character_create_route_saves_name_and_profile_together(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from agents.routes.characters import create_character
    from agents.routes.schemas import CharacterSettingsCreate
    from core.character_store import read_character_records

    monkeypatch.setattr("core.utils.USERDATA_ROOT", str(tmp_path))
    result = asyncio.run(create_character(
        CharacterSettingsCreate(
            projectName="demo",
            name="周遥",
            content="身份：记者\n动机：查明旧案真相",
        ),
        user={"user_id": "18"},
    ))

    assert result == {"success": True, "id": 0, "name": "周遥"}
    assert read_character_records("18", "demo")["0"] == {
        "name": "周遥",
        "content": "身份：记者\n动机：查明旧案真相",
    }


def test_character_create_route_never_starts_graphrag_build(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from agents.graphrag import GraphRAGService
    from agents.routes.characters import create_character
    from agents.routes.schemas import CharacterSettingsCreate

    monkeypatch.setattr("core.utils.USERDATA_ROOT", str(tmp_path))

    def _unexpected_build(*args, **kwargs):
        raise AssertionError("创建角色不得触发 GraphRAG 构建")

    monkeypatch.setattr(GraphRAGService, "start_background_build", _unexpected_build)
    result = asyncio.run(create_character(
        CharacterSettingsCreate(projectName="demo", name="周遥", content="身份：记者"),
        user={"user_id": "18"},
    ))

    assert result["success"] is True
    assert result["id"] == 0


def test_character_relations_are_manual_and_persist_without_graphrag(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from agents.routes.characters import (
        create_character,
        get_character_relations,
        post_character_relation,
        put_character_relation,
        remove_character_relation,
    )
    from agents.routes.schemas import CharacterRelationCreate, CharacterSettingsCreate

    monkeypatch.setattr("core.utils.USERDATA_ROOT", str(tmp_path))
    user = {"user_id": "18"}
    asyncio.run(create_character(CharacterSettingsCreate(projectName="demo", name="甲"), user=user))
    asyncio.run(create_character(CharacterSettingsCreate(projectName="demo", name="乙"), user=user))

    created = asyncio.run(post_character_relation(
        CharacterRelationCreate(projectName="demo", source=0, target=1, relation="盟友", note="共同调查"),
        user=user,
    ))
    assert created["success"] is True
    relation = created["relation"]
    assert relation["relation"] == "盟友"
    assert asyncio.run(get_character_relations(projectName="demo", user=user)) == [relation]

    updated = asyncio.run(put_character_relation(
        relation["id"],
        CharacterRelationCreate(projectName="demo", source=0, target=1, relation="旧识", note="关系改变"),
        user=user,
    ))
    assert updated["relation"]["relation"] == "旧识"
    second = asyncio.run(post_character_relation(
        CharacterRelationCreate(projectName="demo", source=0, target=1, relation="竞争者", note="立场冲突"),
        user=user,
    ))["relation"]
    assert len(asyncio.run(get_character_relations(projectName="demo", user=user))) == 2
    assert asyncio.run(remove_character_relation(relation["id"], projectName="demo", user=user)) == {"success": True}
    assert asyncio.run(get_character_relations(projectName="demo", user=user)) == [second]
    assert asyncio.run(remove_character_relation(second["id"], projectName="demo", user=user)) == {"success": True}
    assert asyncio.run(get_character_relations(projectName="demo", user=user)) == []
