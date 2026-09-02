import json
import sqlite3
from pathlib import Path


def _decode_row(row):
    """将 sqlite3 返回的 bytes 字段解码为 str，兼容 Python 3.13 BLOB 行为。"""
    return tuple(v.decode("utf-8") if isinstance(v, bytes) else v for v in row)


def test_import_project_stories_keeps_presentation_and_ignores_legacy_visual_directives(tmp_path, monkeypatch):
    """通用 stories.db 保留正式演出字段；旧视觉指令被忽略，Unity 再按 target 过滤。"""
    from core import utils as core_utils
    from story import importer

    userdata_root = tmp_path / "_userdata"
    monkeypatch.setattr(core_utils, "USERDATA_ROOT", str(userdata_root))
    monkeypatch.setattr(importer, "ensure_project_directory", core_utils.ensure_project_directory)
    monkeypatch.setattr(importer, "ensure_project_stories_directory", core_utils.ensure_project_stories_directory)

    user_id = "unity_runtime_export"
    project_name = "demo"
    project_path = Path(core_utils.ensure_project_directory(user_id, project_name))
    stories_dir = Path(core_utils.ensure_project_stories_directory(user_id, project_name))
    chr_dir = Path(core_utils.ensure_project_characters_directory(user_id, project_name))

    from core.character_store import write_character_records

    write_character_records(
        user_id,
        project_name,
        {"1": {"name": "信使", "content": "# 信使"}},
    )
    (stories_dir / "001_测试.arc").write_text(
        "\n".join(
            [
                "# windrise_first_meet",
                "@guide 测试 Unity 行为映射",
                "@intro 欢迎来到 {place}",
                "@meta button_text:按 F 与 {npc_name} 对话",
                "[-1]",
                "系统准备触发行为。",
                "@show bg:bg_school_road",
                "@show sprite:sprite_hero_default",
                "@act bgm:town_theme",
                "[信使]",
                "你好，{player_name}。",
                "@act bg:bg_legacy_alley",
                "@act sprite:sprite_legacy_hero",
                "@web bg:bg_deprecated_alley",
                "@web sprite:sprite_deprecated_hero",
            ]
        ),
        encoding="utf-8",
    )
    (project_path / "action_bindings.json").write_text(
        json.dumps(
            [
                {
                    "id": "bgm",
                    "act_name": "bgm",
                    "func_name": "PlayBGM",
                    "act_type": "audio",
                    "act_description": "播放背景音乐",
                    "act_args": {"musicName": ["town_theme", "battle_theme"]},
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (project_path / "registries.json").write_text(
        json.dumps(
            [
                {"id": "player_name", "name": "player_name", "value": ["艾莉"]},
                {"id": "place", "name": "place", "value": ["风丘"]},
                {"id": "npc_name", "name": "npc_name", "value": ["信使"]},
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    result = importer.import_project_stories_to_db(user_id, project_name)

    with sqlite3.connect(result["db_path"]) as connection:
        action_rows = [
            _decode_row(r)
            for r in connection.execute(
                "select act_name, func_name, act_type, act_args from binding_act"
            ).fetchall()
        ]
        registry_rows = [
            _decode_row(r)
            for r in connection.execute(
                "select name, value from registry order by name"
            ).fetchall()
        ]
        dlg_json = connection.execute("select dlg_json from stories limit 1").fetchone()[0]

    assert action_rows == [
        ("bgm", "PlayBGM", "audio", '{"musicName": ["town_theme", "battle_theme"]}')
    ]
    assert registry_rows == [
        ("npc_name", '["信使"]'),
        ("place", '["风丘"]'),
        ("player_name", '["艾莉"]'),
    ]
    decoded_dlg_json = dlg_json.decode("utf-8") if isinstance(dlg_json, bytes) else dlg_json
    assert ('"show": {"bg": "bg_school_road", "sprite": "sprite_hero_default"}' in decoded_dlg_json or '"presentation": {"bg": "bg_school_road", "sprite": "sprite_hero_default"}' in decoded_dlg_json)
    assert "bg_legacy_alley" not in decoded_dlg_json
    assert "sprite_legacy_hero" not in decoded_dlg_json
    assert "bg_deprecated_alley" not in decoded_dlg_json
    assert "sprite_deprecated_hero" not in decoded_dlg_json
    assert '"bgm": "town_theme"' in decoded_dlg_json

    unity_result = importer.import_project_stories_to_db(user_id, project_name, target="unity")

    with sqlite3.connect(unity_result["db_path"]) as connection:
        unity_dlg_json = connection.execute("select dlg_json from stories limit 1").fetchone()[0]

    decoded_unity_dlg_json = unity_dlg_json.decode("utf-8") if isinstance(unity_dlg_json, bytes) else unity_dlg_json
    assert '"act": {"bgm": "town_theme"}' in decoded_unity_dlg_json
    assert '"presentation":' not in decoded_unity_dlg_json
    assert '"bg":' not in decoded_unity_dlg_json
    assert '"sprite":' not in decoded_unity_dlg_json
