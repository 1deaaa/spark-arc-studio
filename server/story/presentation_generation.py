"""视觉演出图片的统一上下文与提示词构建服务。"""

from __future__ import annotations

import os
from typing import Any, Iterable

from agents.project_content import load_worldview
from core.project_settings import (
    get_visual_illustration_settings,
    get_visual_style_settings,
)
from story.project_files import load_character_content, load_character_id_name_map


REFERENCE_ROLES = {"style", "scene", "character", "continuity"}

_ASSET_PURPOSES = {
    "style_reference": "项目级风格种子候选图",
    "scene_reference": "可复用的场景空间参考图",
    "background": "视觉小说舞台背景图",
    "character_sprite": "可复用的角色基础立绘",
    "scene_illustration": "包含环境与必要角色的完整叙事插图",
}

_REFERENCE_ROLE_RULES = {
    "style": "只继承画风、色彩、材质、光照与镜头语言，不复制其中的人物身份或具体构图。",
    "scene": "保持地点结构、时代陈设与空间关系，不把参考图中的临时人物当成目标角色。",
    "character": "严格保持对应角色的脸部、发型、体型、服装识别点与年龄感，不继承其纯色背景。",
    "continuity": "保持相邻已生成画面的时间、天气、服装、光向与空间连续性，同时按本次描述改变动作和镜头。",
}


def _compact(value: Any, limit: int) -> str:
    text = " ".join(str(value or "").split()).strip()
    if len(text) <= limit:
        return text
    return f"{text[:limit].rstrip()}..."


def _unique_strings(values: Iterable[Any], *, limit: int = 16) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for raw in values:
        value = str(raw or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
        if len(result) >= limit:
            break
    return result


def _load_character_contexts(
    user_id: str,
    project_name: str,
    character_ids: Iterable[Any],
) -> list[dict[str, str]]:
    name_map = load_character_id_name_map(
        user_id,
        project_name,
        include_narrator=False,
        include_system=False,
    )
    result: list[dict[str, str]] = []
    for character_id in _unique_strings(character_ids, limit=8):
        name = name_map.get(character_id, "")
        content = load_character_content(user_id, project_name, character_id)
        result.append({
            "id": character_id,
            "name": name,
            "profile": _compact(content, 1800),
        })
    return result


def infer_reference_role(asset: dict[str, Any]) -> str:
    """按资产类型推断参考职责，显式职责仍应由调用方优先提供。"""
    asset_type = str(asset.get("type") or "").strip()
    if asset_type == "style_reference":
        return "style"
    if asset_type in {"background", "scene_reference"}:
        return "scene"
    if asset_type == "character_sprite":
        return "character"
    return "continuity"


def normalize_reference_descriptors(
    references: Iterable[dict[str, Any]],
) -> list[dict[str, str]]:
    """规范化参考图 ID、职责和标题，最多保留十张。"""
    result: list[dict[str, str]] = []
    seen: set[str] = set()
    for raw in references:
        if not isinstance(raw, dict):
            continue
        asset_id = str(raw.get("assetId") or raw.get("id") or "").strip()
        if not asset_id or asset_id in seen:
            continue
        role = str(raw.get("role") or "").strip().lower()
        if role not in REFERENCE_ROLES:
            role = "continuity"
        seen.add(asset_id)
        result.append({
            "assetId": asset_id,
            "role": role,
            "title": _compact(raw.get("title"), 120),
            "characterId": str(raw.get("characterId") or "").strip(),
            "characterName": _compact(raw.get("characterName"), 120),
        })
        if len(result) >= 10:
            break
    return result


def build_visual_generation_prompt(
    *,
    user_id: str,
    project_name: str,
    asset_type: str,
    creative_prompt: str,
    context: dict[str, Any] | None = None,
    references: Iterable[dict[str, Any]] = (),
) -> tuple[str, dict[str, Any]]:
    """从项目真相源与结构化现场生成最终自然语言提示及可追溯快照。"""
    kind = str(asset_type or "").strip()
    if kind not in _ASSET_PURPOSES:
        raise ValueError(f"不支持的视觉资产类型: {asset_type}")

    source = context if isinstance(context, dict) else {}
    style = get_visual_style_settings(user_id, project_name)
    illustration = get_visual_illustration_settings(user_id, project_name)
    worldview = _compact(load_worldview(user_id, project_name), 5000)
    character_ids = _unique_strings(source.get("characterIds") or [], limit=8)
    characters = _load_character_contexts(user_id, project_name, character_ids)
    nearby_dialogue = [
        _compact(item, 500)
        for item in (source.get("nearbyDialogue") or [])
        if _compact(item, 500)
    ][:8]
    normalized_references = normalize_reference_descriptors(references)

    lines = [
        f"你正在为 SparkArc 视觉小说项目生成{_ASSET_PURPOSES[kind]}。",
        "请把以下资料理解为同一个叙事世界中的导演上下文，不要逐段机械拼贴。",
        "优先级：本次画面要求 > 角色身份与场景事实 > 项目风格种子 > 连续性参考 > 一般美学补全。",
    ]

    if style["seed_prompt"]:
        lines.append(f"项目风格种子文本：{_compact(style['seed_prompt'], 2400)}")
    if worldview:
        lines.append(f"世界观、时代与地点规则：{worldview}")

    scene_name = _compact(source.get("sceneName"), 200)
    scene_intro = _compact(source.get("sceneIntro"), 1600)
    scene_conception = _compact(source.get("sceneConception"), 1600)
    node_text = _compact(source.get("nodeText"), 1000)
    if scene_name:
        lines.append(f"当前场景：{scene_name}")
    if scene_intro:
        lines.append(f"场景引言：{scene_intro}")
    if scene_conception:
        lines.append(f"导演构思：{scene_conception}")
    if nearby_dialogue:
        lines.append("邻近叙事节拍：\n" + "\n".join(f"- {item}" for item in nearby_dialogue))
    if node_text:
        lines.append(f"当前节点：{node_text}")

    if characters:
        character_lines = []
        for item in characters:
            label = item["name"] or "未命名角色"
            character_lines.append(f"- {label}：{item['profile'] or '无额外档案'}")
        lines.append("本画面涉及的角色档案：\n" + "\n".join(character_lines))

    if normalized_references:
        reference_lines = []
        for index, item in enumerate(normalized_references, start=1):
            title = f"，{item['title']}" if item["title"] else ""
            character = f"，对应角色 {item.get('characterName')}" if item.get("characterName") else ""
            reference_lines.append(
                f"- 参考图 {index}（资产 {item['assetId']}{title}，职责 {item['role']}{character}）："
                f"{_REFERENCE_ROLE_RULES[item['role']]}"
            )
        lines.append("参考图职责：\n" + "\n".join(reference_lines))

    lines.append(f"本次具体要求：{_compact(creative_prompt, 4000)}")

    if kind == "character_sprite":
        chroma_key = illustration["sprite_chroma_key"]
        lines.extend([
            "输出单个角色的高质量全身基础立绘，完整保留头顶、手、服装下摆和脚部，不裁切肢体。",
            f"背景必须是完全均匀、无纹理、无阴影、无渐变的纯色 {chroma_key}；角色边缘不得反射该背景色。",
            "不要加入地面、道具背景、文字、边框或其他人物。角色姿态自然，优先正面或轻微三分之二侧身，便于后续表情与姿态重绘。",
        ])
    elif kind == "background":
        lines.extend([
            "输出 3:2 横版环境背景，不出现可识别的主要角色；如需要人群，只能作为不可辨识的远景环境元素。",
            "关键建筑、出入口和叙事焦点放在中央安全区，两侧保留可延展环境，兼容桌面覆盖与手机竖屏模糊扩展。",
        ])
    elif kind == "scene_illustration":
        lines.extend([
            "输出 3:2 横版完整叙事画面；角色可以直接融入场景，不要求像独立立绘那样正面站立。",
            "严格保持角色参考图的身份识别点与场景参考图的空间事实，通过动作、视线、景别和光线讲清当前叙事瞬间。",
            "关键角色面部、动作与叙事焦点必须位于中央安全区，避免手机竖屏演出时被裁掉；外围应适合模糊扩展。",
        ])
    elif kind == "style_reference":
        lines.append("重点确立色彩、线条或摄影质感、材质、光照、时代感和镜头语言；它是后续图生图锚点，不是正式剧情截图。")
    elif kind == "scene_reference":
        lines.append("重点确立可复用地点的空间布局、材质、时代陈设、天气与光照基准，避免加入抢占叙事的主要角色。")

    lines.extend([
        "禁止生成 UI、对话框、字幕、标题、说明文字、水印、品牌标志或画中画边框。",
        "若资料之间存在冲突，遵循上述优先级，并保持角色身份和世界观事实不被风格参考覆盖。",
    ])

    snapshot = {
        "schema": "sparkarc.visual-context.v1",
        "assetType": kind,
        "styleSeedPrompt": style["seed_prompt"],
        "styleReferenceAssetIds": style["reference_asset_ids"],
        "sceneName": scene_name,
        "sceneIntro": scene_intro,
        "sceneConception": scene_conception,
        "nodeText": node_text,
        "nearbyDialogue": nearby_dialogue,
        "characterIds": character_ids,
        "characters": characters,
        "references": normalized_references,
        "creativePrompt": _compact(creative_prompt, 4000),
    }
    return "\n\n".join(line for line in lines if line), snapshot
