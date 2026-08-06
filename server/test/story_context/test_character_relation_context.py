from pathlib import Path


def test_character_bundle_injects_author_relations_into_role_cards(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from agents.routes.context_builder import load_character_bundle, load_project_context_bundle
    from core.character_relations import create_character_relation
    from core.character_store import write_character_records

    monkeypatch.setattr("core.utils.USERDATA_ROOT", str(tmp_path))
    write_character_records(
        "31",
        "demo",
        {
            "0": {"name": "甲", "content": "身份：调查员"},
            "1": {"name": "乙", "content": "身份：记者"},
        },
    )
    create_character_relation(
        "31",
        "demo",
        source="0",
        target="1",
        relation="盟友",
        note="共同调查旧案",
    )

    bundle = load_character_bundle("31", "demo")
    project_bundle = load_project_context_bundle("31", "demo")

    expected = "甲 → 乙：盟友；备注：共同调查旧案"
    assert expected in bundle["roles_text"]
    assert expected in bundle["detailed_summary_text"]
    assert expected in bundle["relations_text"]
    assert expected in project_bundle["roles"]
    assert expected in project_bundle["relations_text"]
