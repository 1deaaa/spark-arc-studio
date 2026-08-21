from __future__ import annotations

from pathlib import Path

from agents.routes.context_builder import (
    build_scriptwriter_handoff_context,
    format_outline_scene_contract,
    resolve_outline_scene_contract,
    resolve_outline_scene_contract_for_task,
    get_current_beat,
)
from agents.communication import normalize_handoff_payload
from story.outline_parser import (
    parse_beat_sheet_markup,
    parse_outline_markup,
    serialize_beat_sheet_to_markup,
    serialize_outline_to_markup,
)


def test_outline_scene_contract_resolves_scene_metadata() -> None:
    outline = {
        "nodes": [
            {
                "title": "一 · 开端",
                "description": "建立秘密交易与档案室谜团。",
                "children": [
                    {
                        "title": "1-1 钟楼交易",
                        "description": "沈棠交出旧钥匙，林烬决定查档案室。",
                        "guide": "对白必须像互相试探，不要完整解释。",
                        "characters": ["沈棠", "林烬"],
                        "mood": "压抑",
                        "tension": "高",
                        "key_dialogues": ["你真的相信档案室的记录吗？"],
                    }
                ],
            }
        ]
    }

    contract = resolve_outline_scene_contract(
        outline,
        scene_name="钟楼交易",
        file_path="一 · 开端/1-1 钟楼交易.arc",
    )
    text = format_outline_scene_contract(contract)

    assert contract["chapter_title"] == "一 · 开端"
    assert contract["scene_title"] == "1-1 钟楼交易"
    assert contract["characters"] == ["沈棠", "林烬"]
    assert "场景功能：沈棠交出旧钥匙" in text
    assert "关键对话/剧情方向" in text


def test_outline_markup_preserves_scene_contract_fields() -> None:
    raw = "\n".join(
        [
            "## 一 · 开端",
            "建立秘密交易与档案室谜团。",
            "### 1-1 钟楼交易",
            "> 情绪：压抑 | 张力：High | 登场：沈棠, 林烬 | 对应节拍：1, 2 | 指引：对白必须像互相试探",
            "沈棠交出旧钥匙，林烬决定查档案室。",
            "@key_dialogue 你真的相信档案室的记录吗？",
        ]
    )

    outline = parse_outline_markup(raw)
    scene = outline["nodes"][0]["children"][0]
    assert scene["mood"] == "压抑"
    assert scene["tension"] == "High"
    assert scene["characters"] == ["沈棠", "林烬"]
    assert scene["beat_refs"] == ["1", "2"]
    assert scene["guide"] == "对白必须像互相试探"

    serialized = serialize_outline_to_markup(outline)
    assert "对应节拍：1, 2" in serialized
    assert "指引：对白必须像互相试探" in serialized

    contract = resolve_outline_scene_contract(
        outline,
        scene_name="钟楼交易",
    )
    text = format_outline_scene_contract(contract)
    assert contract["beat_refs"] == ["1", "2"]
    assert "对应节拍：1, 2" in text
    assert "导演指引：对白必须像互相试探" in text


def test_outline_markup_keeps_labeled_beat_reference_as_one_value() -> None:
    outline = parse_outline_markup(
        "## 一 · 开端\n### 1-1 起航\n> 对应节拍：[beat 1, beat 2] | 登场：周岑"
    )

    scene = outline["nodes"][0]["children"][0]
    assert scene["beat_refs"] == ["Beat 1", "Beat 2"]
    serialized = serialize_outline_to_markup(outline)
    assert "对应节拍：Beat 1, Beat 2" in serialized


def test_outline_markup_repairs_legacy_split_beat_reference() -> None:
    outline = parse_outline_markup(
        "## 一 · 开端\n### 1-1 起航\n> 对应节拍：[beat, 1] | 登场：周岑"
    )

    scene = outline["nodes"][0]["children"][0]
    assert scene["beat_refs"] == ["Beat 1"]
    serialized = serialize_outline_to_markup(outline)
    assert "对应节拍：Beat 1" in serialized


def test_outline_markup_preserves_continuity_contract_fields() -> None:
    raw = "\n".join(
        [
            "## 一 · 归来",
            "保护返家惊喜成立。",
            "### 1-1 门外",
            "> 情绪：期待 | 张力：Medium | 登场：哥哥 | 对应节拍：2 | 指引：保护信息差",
            "> 地点：弟弟家门外 | 时间：傍晚",
            "> 前置状态：弟弟不知道哥哥已经返程",
            "> 目标：哥哥完成突然返家的惊喜 | 冲突：不能提前暴露行程",
            "> 转折：弟弟开门看见哥哥 | 后置状态：弟弟确认哥哥已经回来",
            "> 知情前：只有哥哥知道返程计划",
            "> 知情后：兄弟二人都知道哥哥已经返家",
            "> 禁止铺垫：哥哥不得提前询问礼物或透露返程",
            "> 因果依赖：Beat 1 | 设置引用：无 | 兑现引用：哥哥返家惊喜",
            "哥哥按响门铃。",
        ]
    )

    outline = parse_outline_markup(raw)
    scene = outline["nodes"][0]["children"][0]
    assert scene["location"] == "弟弟家门外"
    assert scene["pre_state"] == "弟弟不知道哥哥已经返程"
    assert scene["forbidden_setup"] == "哥哥不得提前询问礼物或透露返程"
    assert scene["causal_dependencies"] == ["Beat 1"]

    serialized = serialize_outline_to_markup(outline)
    reparsed = parse_outline_markup(serialized)
    reparsed_scene = reparsed["nodes"][0]["children"][0]
    assert reparsed_scene["knowledge_before"] == "只有哥哥知道返程计划"
    assert reparsed_scene["knowledge_after"] == "兄弟二人都知道哥哥已经返家"
    assert reparsed_scene["payoff_refs"] == ["哥哥返家惊喜"]

    contract = resolve_outline_scene_contract(reparsed, chapter_index=0, scene_index=0)
    text = format_outline_scene_contract(contract)
    assert "禁止提前发生：哥哥不得提前询问礼物或透露返程" in text
    assert "地点：弟弟家门外" in text


def test_beat_sheet_fields_round_trip_and_exact_scene_reference() -> None:
    raw = "\n".join(
        [
            "@arc 疏离到重逢",
            "---beat 1",
            "> 类型：铺设距离 | 情感目标：想念 | 张力：Low",
            "> 前置状态：兄弟分隔两地",
            "> 触发：哥哥决定返程",
            "> 选择/行动：哥哥隐瞒行程",
            "> 后置状态：哥哥已经在返程途中，弟弟仍不知情",
            "哥哥开始返程。",
            "---beat 2",
            "> 类型：惊喜揭晓 | 情感目标：惊喜 | 张力：High",
            "> 前置状态：弟弟不知道哥哥已到门外",
            "> 触发：弟弟开门",
            "> 选择/行动：哥哥现身",
            "> 后置状态：兄弟重逢",
            "> 知情变化：弟弟从不知道返程变为确认哥哥归来",
            "> 因果依赖：Beat 1",
            "惊喜在开门时揭晓。",
        ]
    )

    beats = parse_beat_sheet_markup(raw)
    assert beats["beats"][1]["beat_type"] == "惊喜揭晓"
    assert beats["beats"][1]["knowledge_change"].startswith("弟弟从不知道")

    serialized = serialize_beat_sheet_to_markup(beats)
    reparsed = parse_beat_sheet_markup(serialized)
    assert reparsed["beats"][0]["post_state"].startswith("哥哥已经在返程途中")
    assert reparsed["beats"][1]["causal_dependencies"] == ["Beat 1"]

    current = get_current_beat(reparsed, 0, 0, beat_refs=["Beat 2"])
    assert "Beat 2 [惊喜揭晓]" in current
    assert "Beat 1 [铺设距离]" not in current
    assert get_current_beat(reparsed, 0, 0, beat_refs=[]) == ""


def test_production_context_pack_injects_outline_scene_contract(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("core.utils.USERDATA_ROOT", str(tmp_path))
    project_path = tmp_path / "uid_14" / "projects" / "demo"
    project_path.mkdir(parents=True)
    (project_path / "大纲.txt").write_text(
        "\n".join(
            [
                "## 一 · 开端",
                "建立秘密交易与档案室谜团。",
                "### 1-1 钟楼交易",
                "> 情绪：压抑 | 张力：高 | 登场：沈棠, 林烬 | 指引：对白必须像互相试探，不要完整解释。",
                "沈棠交出旧钥匙，林烬决定查档案室。",
                "@key_dialogue 你真的相信档案室的记录吗？",
            ]
        ),
        encoding="utf-8",
    )

    from agents.routes.production import build_scriptwriter_context_pack

    pack = build_scriptwriter_context_pack(
        user_id="14",
        project_name="demo",
        operation="continue",
        file_path="一 · 开端/1-1 钟楼交易.arc",
        scene_name="钟楼交易",
        guidance="加强林烬的迟疑。",
    )

    assert "当前大纲场景契约" in pack["context"]
    assert "场景功能：沈棠交出旧钥匙" in pack["context"]
    assert "你真的相信档案室的记录吗？" in pack["context"]
    assert "对白必须像互相试探" in pack["guidance"]
    assert "加强林烬的迟疑" in pack["guidance"]
    assert pack["outline_scene_contract"]["characters"] == ["沈棠", "林烬"]


def test_handoff_payload_preserves_scriptwriter_scene_fields() -> None:
    payload = normalize_handoff_payload(
        {
            "target_agent": "agent_scriptwriter",
            "task_description": "写钟楼交易。",
            "tracker_item_id": "task_clocktower",
            "export_format": "novel",
            "chapter_name": "一 · 开端",
            "scene_name": "1-1 钟楼交易",
            "scene_file_path": "一 · 开端/1-1 钟楼交易.md",
            "scene_guidance": "对白必须像互相试探。",
            "scene_characters": "沈棠，林烬",
        },
        sender_id="agent_director",
    )

    assert payload["export_format"] == "novel"
    assert payload["chapter_name"] == "一 · 开端"
    assert payload["scene_name"] == "1-1 钟楼交易"
    assert payload["scene_file_path"] == "一 · 开端/1-1 钟楼交易.md"
    assert payload["scene_guidance"] == "对白必须像互相试探。"
    assert payload["scene_characters"] == ["沈棠", "林烬"]
    assert payload["tracker_item_id"] == "task_clocktower"


def test_scriptwriter_handoff_context_resolves_outline_contract_from_task(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("core.utils.USERDATA_ROOT", str(tmp_path))
    project_path = tmp_path / "uid_14" / "projects" / "demo"
    project_path.mkdir(parents=True)
    (project_path / "大纲.txt").write_text(
        "\n".join(
            [
                "## 一 · 开端",
                "建立秘密交易与档案室谜团。",
                "### 1-1 钟楼交易",
                "> 情绪：压抑 | 张力：高 | 登场：沈棠, 林烬 | 指引：对白必须像互相试探，不要完整解释。",
                "沈棠交出旧钥匙，林烬决定查档案室。",
                "@key_dialogue 你真的相信档案室的记录吗？",
            ]
        ),
        encoding="utf-8",
    )

    outline = {
        "nodes": [
            {
                "title": "一 · 开端",
                "description": "建立秘密交易与档案室谜团。",
                "children": [
                    {
                        "title": "1-1 钟楼交易",
                        "description": "沈棠交出旧钥匙，林烬决定查档案室。",
                        "guide": "对白必须像互相试探，不要完整解释。",
                        "characters": ["沈棠", "林烬"],
                    }
                ],
            }
        ]
    }
    contract = resolve_outline_scene_contract_for_task(
        outline,
        task_description="请委派编剧写第一章的钟楼交易，重点加强林烬的迟疑。",
    )
    assert contract["scene_title"] == "1-1 钟楼交易"

    context = build_scriptwriter_handoff_context(
        "14",
        "demo",
        task_description="请写第一章的钟楼交易，重点加强林烬的迟疑。",
        scene_characters=["沈棠"],
    )

    assert "Director→Scriptwriter 场景交接包" in context
    assert "当前大纲场景契约" in context
    assert "场景功能：沈棠交出旧钥匙" in context
    assert "当前场景事实包" in context
    assert "沈棠、林烬" in context
    assert "写作前核对本交接包" in context
