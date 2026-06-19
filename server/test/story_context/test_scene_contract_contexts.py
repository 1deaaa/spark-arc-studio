from __future__ import annotations

from pathlib import Path

from agents.routes.context_builder import (
    build_scriptwriter_handoff_context,
    format_outline_scene_contract,
    resolve_outline_scene_contract,
    resolve_outline_scene_contract_for_task,
)
from agents.communication import normalize_handoff_payload
from story.outline_parser import parse_outline_markup, serialize_outline_to_markup


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
    assert "当前场景任务包" in context
    assert "沈棠、林烬" in context
    assert "写作前优先服从本交接包" in context
