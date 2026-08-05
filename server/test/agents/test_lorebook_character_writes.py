from __future__ import annotations

from pathlib import Path


def _regular_characters(user_id: str, project_name: str) -> dict[str, str]:
    from core.character_store import read_character_records

    return {
        record["name"]: record["content"]
        for character_id, record in read_character_records(user_id, project_name).items()
        if int(character_id) >= 0
    }


def test_character_agent_defaults_to_incremental_write(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("core.utils.USERDATA_ROOT", str(tmp_path))

    from agents.agent_lorebook import WorldviewAgent
    from core.character_store import replace_regular_characters

    replace_regular_characters("18", "demo", [("沈棠", "旧档案"), ("林烬", "调查员")])
    agent = WorldviewAgent.__new__(WorldviewAgent)

    result = agent._write_characters_overwrite(
        "18",
        "demo",
        "<character><name>周遥</name><content>记者</content></character>",
    )

    assert "增量写入" in result
    assert _regular_characters("18", "demo") == {
        "沈棠": "旧档案",
        "林烬": "调查员",
        "周遥": "记者",
    }


def test_character_agent_replaces_all_only_when_explicit(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("core.utils.USERDATA_ROOT", str(tmp_path))

    from agents.agent_lorebook import WorldviewAgent
    from core.character_store import replace_regular_characters

    replace_regular_characters("18", "demo", [("沈棠", "旧档案"), ("林烬", "调查员")])
    agent = WorldviewAgent.__new__(WorldviewAgent)

    result = agent._write_characters_overwrite(
        "18",
        "demo",
        "<character><name>周遥</name><content>记者</content></character>",
        append=False,
    )

    assert "覆盖角色设定" in result
    assert _regular_characters("18", "demo") == {"周遥": "记者"}
