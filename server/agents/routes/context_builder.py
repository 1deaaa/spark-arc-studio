"""
ScriptWriter Context Builder - 执笔编剧统一上下文组装器

════════════════════════════════════════════════════════════════════════
【设计目标】
本模块是 ScriptwriterAgent 正式写作链路的统一上下文数据源：
  1. 用户手动生产流 (production.py / compose)
  2. 全自动批处理 (auto_write.py)
  3. 导演委派写作 (director_graph.py)
  4. 编剧聊天落盘工具 (tools/scriptwriter.py，经 tool_rules 约束读取 StoryMemory/GraphRAG)
  5. 用户显式吸收故事文件 (story/routes_files.py，普通保存不隐式写 StoryMemory)

其中 1/2/3 共享本模块的写前上下文组装；4 走聊天工具管线，但复用同一套
StoryMemory / GraphRAG / 风格执行卡 / 工具规则；5 只在用户明确触发时提交后台状态吸收。

【核心改进】
  - StoryMemory 场景事实包：在三圈记忆前注入当前场景相关的角色动态状态、
    关系记录、开放线索和最近场景摘要；该状态由场景保存后后台吸收生成。
  - 世界观 / 角色真相源：统一从项目文件加载；正式写作阶段再由上下文预算
    按模型窗口裁剪，避免把“窗口放得下”误当成“模型能稳定利用”。
  - 三圈记忆策略（Scene Context）：
      ① 当前章最近场景全文 ← 最近戏剧连续性
      ② 最近前序章章末尾声 ← 跨章情感锚点
      ③ 梗概+节拍表  ← 全局叙事线
  - 统一大纲注入：直接读取 大纲.txt 原文，
    让编剧始终知道全局故事蓝图。
════════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple

from core.character_relations import read_character_relations
from core.character_store import read_character_records
from core.project_settings import normalize_scene_length_hint
from core.utils import (
    get_project_path,
    get_project_stories_path,
)
from story.file_naming import list_story_files


MAX_CURRENT_CHAPTER_FULL_SCENES = 3
MAX_CROSS_CHAPTER_TAILS = 2


# ─────────────────────── Story Tags 共享构建器 ───────────────────────


def build_story_tags_hint(story_tags: dict) -> str:
    """从 story_tags 字典构建注入 LLM 上下文的提示文本块。

    这是 story tags 注入 LLM 上下文的唯一格式化入口。
    包含 POV 醒目优化（三层锚定策略）。

    Args:
        story_tags: 从 get_project_story_tags 返回的字典

    Returns:
        格式化后的 story tags 文本块，若所有字段均为空则返回空字符串
    """
    if not story_tags:
        return ""

    parts = []

    workspace_mode = story_tags.get("workspace_mode")
    if workspace_mode == "novel":
        parts.append("【创作格式】小说模式（纯文学小说，输出 Markdown 小说正文，避免使用 ARC 剧本语法）。")
    else:
        parts.append("【创作格式】剧本模式（ARC 互动剧本，输出 .arc 剧本正文，遵守 ARC 语法规范）。")

    scene_length_hint = normalize_scene_length_hint(story_tags.get("scene_length_hint"))
    if workspace_mode == "novel":
        scene_targets = {
            "concise": ("精简", "约 600-1000 个中文字符"),
            "standard": ("标准", "约 1000-1800 个中文字符"),
            "expanded": ("充实", "约 1800-3000 个中文字符"),
        }
    else:
        scene_targets = {
            "concise": ("精简", "约 12-20 个有效叙事单元"),
            "standard": ("标准", "约 20-35 个有效叙事单元"),
            "expanded": ("充实", "约 35-55 个有效叙事单元"),
        }
    scene_label, scene_target = scene_targets[scene_length_hint]
    scene_target_chars = story_tags.get("scene_target_chars")
    if isinstance(scene_target_chars, int) and scene_target_chars > 0:
        parts.append(
            f"【单场篇幅软目标】目标约 {scene_target_chars} 个可见正文字符。"
            f"{scene_label}档仅用于表达内容密度与节奏倾向，不再提供竞争性的字数区间。"
            "具体字数不是硬性验收条件；优先保证场景任务、情绪转折和叙事完整性，"
            "由你根据成稿质量自行判断是否需要补写或压缩，严禁为凑字数注水或机械截断。"
            "若本轮用户或导演明确给出不同的目标字数，以本轮要求为准。"
        )
    else:
        parts.append(
            f"【单场篇幅软目标】{scene_label}档，{scene_target}。"
            "剧本中的有效叙事单元包括对白、动作、旁白和明确转折，不只计算对白句。"
            "可按过场、高潮、纯动作等实际节奏在目标附近约 ±30% 浮动；"
            "不得为凑数量注水，也不得在必要的动作或情绪转折中途硬截断。"
            "若本轮用户或导演明确给出具体目标字数，以本轮要求为准。"
        )

    pov = story_tags.get("pov")
    if pov:
        parts.append(
            f"⚠️⚠️⚠️ 【叙事人称锁定】本文严格使用「{pov}」叙事。"
            f"所有描写、对话、心理活动必须符合此人称视角，禁止切换。⚠️⚠️⚠️"
        )

    tag_lines = []
    style = story_tags.get("style")
    if style:
        tag_lines.append(f"风格：{style}")
    genres = story_tags.get("genres", [])
    if genres:
        tag_lines.append(f"题材：{'、'.join(genres)}")
    tones = story_tags.get("tones", [])
    if tones:
        tag_lines.append(f"基调：{'、'.join(tones)}")
    worldviews = story_tags.get("worldviews", [])
    if worldviews:
        tag_lines.append(f"世界观：{'、'.join(worldviews)}")
    length_hint = story_tags.get("length_hint")
    if length_hint:
        tag_lines.append(f"篇幅：{length_hint}")

    if tag_lines:
        parts.append("【创作参数】" + " | ".join(tag_lines))

    return "\n".join(parts)


# ─────────────────────────── 原子加载函数 ───────────────────────────


def load_worldview(user_id: str, project_name: str) -> str:
    """读取世界观全文，不存在则返回空字符串。"""
    from agents.project_content import load_worldview as load_worldview_content

    return load_worldview_content(user_id, project_name)


def load_character_bundle(user_id: str, project_name: str) -> Dict[str, Any]:
    """
    统一读取角色仓库并构建 prompt 用文本。

    返回字段：
      - characters: [{id, name, desc, content}]
      - chr_map: {int(id): name}
      - roles_text: prompt 注入用全量角色文本
      - relations_text: 作者确认的角色关系文本
      - summary_text: 简要列表文本
      - detailed_summary_text: 详细摘要文本
    """
    records = read_character_records(user_id, project_name)

    characters: List[Dict[str, Any]] = []
    chr_map: Dict[int, str] = {}
    role_blocks: List[str] = []
    summary_lines: List[str] = ["### 角色列表"]
    detailed_lines: List[str] = ["### 已有角色设定"]
    relation_lines_by_character: Dict[str, List[str]] = {}
    all_relation_lines: List[str] = []

    for item in read_character_relations(user_id, project_name):
        source_id = str(item.get("source") or "")
        target_id = str(item.get("target") or "")
        source_name = str(records.get(source_id, {}).get("name") or "").strip()
        target_name = str(records.get(target_id, {}).get("name") or "").strip()
        relation = str(item.get("relation") or "").strip()
        if not source_name or not target_name or not relation:
            continue
        note = f"；备注：{item['note']}" if item.get("note") else ""
        line = f"- {source_name} → {target_name}：{relation}{note}"
        all_relation_lines.append(line)
        relation_lines_by_character.setdefault(source_id, []).append(line)
        relation_lines_by_character.setdefault(target_id, []).append(line)

    for cid_str, record in records.items():
        cid = int(cid_str)
        display_name = record["name"]
        chr_map[cid] = display_name
        if cid in (-1, -2):
            continue

        content = record["content"].strip()

        desc = content.replace("\n", " ") if content else ""
        characters.append(
            {
                "id": cid,
                "name": display_name,
                "desc": desc,
                "content": content,
            }
        )

        role_block = f"--- 角色: {display_name} ---\n{content or '(暂无详细设定)'}"
        character_relation_lines = relation_lines_by_character.get(cid_str) or []
        if character_relation_lines:
            role_block += "\n【作者确认关系】\n" + "\n".join(character_relation_lines)
        role_blocks.append(role_block)

        summary_entry = f"- {display_name}"
        if desc:
            summary_entry += f": {desc}"
        summary_lines.append(summary_entry)

        detailed_lines.append(f"\n#### {display_name}")
        detailed_lines.append(content if content else "(尚无详细设定)")
        if character_relation_lines:
            detailed_lines.append("【作者确认关系】")
            detailed_lines.extend(character_relation_lines)

    summary_text = "\n".join(summary_lines) if len(summary_lines) > 1 else ""
    detailed_summary_text = "\n".join(detailed_lines) if len(detailed_lines) > 1 else ""
    return {
        "characters": characters,
        "chr_map": chr_map,
        "roles_text": "\n\n".join(role_blocks),
        "relations_text": "\n".join(all_relation_lines),
        "summary_text": summary_text,
        "detailed_summary_text": detailed_summary_text,
    }


def load_all_roles(user_id: str, project_name: str) -> Tuple[str, Dict[int, str]]:
    """
    读取项目下所有角色的完整设定文本，并返回 chr_map (id -> name)。

    返回: (roles_text, chr_map)
      roles_text: 用于注入 Prompt 的全量角色文本
      chr_map:    {int(id): "角色名"} 的映射，供 .arc 格式约束使用
    """
    bundle = load_character_bundle(user_id, project_name)
    return bundle.get("roles_text", ""), bundle.get("chr_map", {})


def load_synopsis_data(user_id: str, project_name: str) -> Dict[str, Any]:
    """统一读取梗概 Markup，不存在或解析失败时返回空 dict。"""
    from story.outline_parser import parse_synopsis_markup
    synopsis_path = os.path.join(get_project_path(user_id, project_name), "梗概.txt")
    if not os.path.exists(synopsis_path):
        return {}
    try:
        with open(synopsis_path, "r", encoding="utf-8") as f:
            text = f.read()
        return parse_synopsis_markup(text) if text.strip() else {}
    except Exception:
        return {}


def load_beats_data(user_id: str, project_name: str) -> Dict[str, Any]:
    """统一读取节拍表 Markup，不存在或解析失败时返回空 dict。"""
    from story.outline_parser import parse_beat_sheet_markup
    beats_path = os.path.join(get_project_path(user_id, project_name), "节拍表.txt")
    if not os.path.exists(beats_path):
        return {}
    try:
        with open(beats_path, "r", encoding="utf-8") as f:
            text = f.read()
        return parse_beat_sheet_markup(text) if text.strip() else {}
    except Exception:
        return {}


def load_outline_data(user_id: str, project_name: str) -> Dict[str, Any]:
    """统一读取大纲 Markup，不存在或解析失败时返回空 dict。"""
    from story.outline_parser import parse_outline_markup
    outline_path = os.path.join(get_project_path(user_id, project_name), "大纲.txt")
    if not os.path.exists(outline_path):
        return {}
    try:
        with open(outline_path, "r", encoding="utf-8") as f:
            text = f.read()
        return parse_outline_markup(text) if text.strip() else {}
    except Exception:
        return {}


def load_project_context_bundle(user_id: str, project_name: str) -> Dict[str, Any]:
    """
    统一读取项目核心上下文。

    返回字段覆盖对话链路和正式创作链路的公共需求，避免多处重复 IO。
    """
    worldview = load_worldview(user_id, project_name)
    character_bundle = load_character_bundle(user_id, project_name)
    synopsis_data = load_synopsis_data(user_id, project_name)
    beats_data = load_beats_data(user_id, project_name)
    outline_data = load_outline_data(user_id, project_name)
    full_outline = load_full_outline(user_id, project_name)
    narrative_memory, beats_summary = load_narrative_memory(user_id, project_name)
    from agents.structure_state import load_structure_state
    structure_state = load_structure_state(user_id, project_name)

    return {
        "worldview": worldview,
        "character_bundle": character_bundle,
        "roles": character_bundle.get("roles_text", ""),
        "chr_map": character_bundle.get("chr_map", {}),
        "characters": character_bundle.get("characters", []),
        "characters_summary": character_bundle.get("summary_text", ""),
        "characters_detailed_summary": character_bundle.get("detailed_summary_text", ""),
        "relations_text": character_bundle.get("relations_text", ""),
        "synopsis_data": synopsis_data,
        "beats_data": beats_data,
        "outline_data": outline_data,
        "full_outline": full_outline,
        "narrative_memory": narrative_memory,
        "beats_summary": beats_summary,
        "structure_state": structure_state,
    }


def _normalize_outline_title(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    text = text.replace("\\", "/").split("/")[-1]
    text = os.path.splitext(text)[0]
    text = text.split(".__spark__", 1)[0]
    text = re.sub(r"^\s*\d+\s*[-_.·]\s*\d+\s*", "", text)
    text = re.sub(r"^\s*(?:第)?\s*\d+\s*(?:场|幕|节)\s*[:：.\-_ ]*", "", text)
    text = re.sub(r"\s+", "", text)
    return text.lower()


def _outline_text_match_score(candidate: str, targets: set[str]) -> int:
    normalized = _normalize_outline_title(candidate)
    if not normalized:
        return 0
    if normalized in targets:
        return 6
    if any(normalized in target or target in normalized for target in targets if target):
        return 3
    return 0


def _outline_scene_contract_payload(
    ci: int,
    si: int,
    chapter: Dict[str, Any],
    scene: Dict[str, Any],
) -> Dict[str, Any]:
    """把大纲节点转成统一场景契约 payload。"""
    key_dialogues = scene.get("key_dialogues") if isinstance(scene.get("key_dialogues"), list) else []
    characters = scene.get("characters") if isinstance(scene.get("characters"), list) else []
    beat_refs = scene.get("beat_refs") if isinstance(scene.get("beat_refs"), list) else []
    return {
        "chapter_index": ci,
        "scene_index": si,
        "chapter_title": str(chapter.get("title") or chapter.get("name") or "").strip(),
        "chapter_description": str(chapter.get("description") or "").strip(),
        "scene_title": str(scene.get("title") or scene.get("name") or "").strip(),
        "scene_description": str(scene.get("description") or "").strip(),
        "guidance": str(scene.get("guide") or "").strip(),
        "characters": [str(item).strip() for item in characters if str(item).strip()],
        "mood": str(scene.get("mood") or "").strip(),
        "tension": str(scene.get("tension") or "").strip(),
        "beat_refs": [str(item).strip() for item in beat_refs if str(item).strip()],
        "key_dialogues": [str(item).strip() for item in key_dialogues if str(item).strip()],
        "location": str(scene.get("location") or "").strip(),
        "time": str(scene.get("time") or "").strip(),
        "pre_state": str(scene.get("pre_state") or "").strip(),
        "objective": str(scene.get("objective") or "").strip(),
        "conflict": str(scene.get("conflict") or "").strip(),
        "turn": str(scene.get("turn") or "").strip(),
        "post_state": str(scene.get("post_state") or "").strip(),
        "knowledge_before": str(scene.get("knowledge_before") or "").strip(),
        "knowledge_after": str(scene.get("knowledge_after") or "").strip(),
        "forbidden_setup": str(scene.get("forbidden_setup") or "").strip(),
        "causal_dependencies": [
            str(item).strip()
            for item in (scene.get("causal_dependencies") or [])
            if str(item).strip()
        ],
        "setup_refs": [
            str(item).strip()
            for item in (scene.get("setup_refs") or [])
            if str(item).strip()
        ],
        "payoff_refs": [
            str(item).strip()
            for item in (scene.get("payoff_refs") or [])
            if str(item).strip()
        ],
    }


def resolve_outline_scene_contract(
    outline_data: Dict[str, Any],
    *,
    scene_name: str = "",
    file_path: str = "",
    chapter_title: str = "",
    chapter_index: Optional[int] = None,
    scene_index: Optional[int] = None,
) -> Dict[str, Any]:
    """从结构化大纲中解析当前场景契约，供写作上下文复用。"""
    nodes = outline_data.get("nodes") if isinstance(outline_data, dict) else []
    if not isinstance(nodes, list):
        return {}

    try:
        from story.file_naming import parse_story_filename
    except Exception:
        parse_story_filename = None

    parsed_file = parse_story_filename(os.path.basename(file_path)) if parse_story_filename and file_path else None
    if parsed_file:
        if not scene_name:
            scene_name = str(parsed_file.get("display_name") or "")
        if chapter_index is None and parsed_file.get("chapter_num") is not None:
            chapter_index = int(parsed_file["chapter_num"]) - 1
        if scene_index is None and parsed_file.get("scene_num") is not None:
            scene_index = int(parsed_file["scene_num"]) - 1

    scene_targets = {
        item for item in (
            _normalize_outline_title(scene_name),
            _normalize_outline_title(file_path),
            _normalize_outline_title(os.path.basename(file_path)),
        ) if item
    }
    chapter_targets = {
        item for item in (
            _normalize_outline_title(chapter_title),
            _normalize_outline_title(os.path.dirname(file_path)),
        ) if item
    }

    best: tuple[int, int, int, Dict[str, Any], Dict[str, Any]] | None = None
    for ci, chapter in enumerate(nodes):
        if not isinstance(chapter, dict):
            continue
        children = chapter.get("children") or []
        if not isinstance(children, list):
            continue
        chapter_score = 0
        if chapter_index is not None and ci == chapter_index:
            chapter_score += 8
        chapter_score += _outline_text_match_score(
            str(chapter.get("title") or chapter.get("name") or ""),
            chapter_targets,
        )

        for si, scene in enumerate(children):
            if not isinstance(scene, dict):
                continue
            score = chapter_score
            if scene_index is not None and si == scene_index:
                score += 8
            score += _outline_text_match_score(
                str(scene.get("title") or scene.get("name") or ""),
                scene_targets,
            )
            if score <= 0:
                continue
            candidate = (score, ci, si, chapter, scene)
            if best is None or candidate[:3] > best[:3]:
                best = candidate

    if best is None or best[0] < 3:
        return {}

    _, ci, si, chapter, scene = best
    return _outline_scene_contract_payload(ci, si, chapter, scene)


def resolve_outline_scene_contract_for_task(
    outline_data: Dict[str, Any],
    *,
    task_description: str = "",
    chapter_title: str = "",
    scene_name: str = "",
    file_path: str = "",
) -> Dict[str, Any]:
    """从导演委派任务中尽力解析当前大纲场景契约。"""
    explicit = resolve_outline_scene_contract(
        outline_data,
        scene_name=scene_name,
        file_path=file_path,
        chapter_title=chapter_title,
    )
    if explicit:
        return explicit

    nodes = outline_data.get("nodes") if isinstance(outline_data, dict) else []
    if not isinstance(nodes, list):
        return {}

    task_text = _normalize_outline_title(
        "\n".join([task_description, chapter_title, scene_name, file_path])
    )
    if not task_text:
        return {}

    def _contains_score(value: Any, score: int) -> int:
        normalized = _normalize_outline_title(value)
        if len(normalized) < 2:
            return 0
        return score if normalized in task_text else 0

    best: tuple[int, int, int, Dict[str, Any], Dict[str, Any]] | None = None
    for ci, chapter in enumerate(nodes):
        if not isinstance(chapter, dict):
            continue
        chapter_score = _contains_score(chapter.get("title") or chapter.get("name"), 4)
        children = chapter.get("children") or []
        if not isinstance(children, list):
            continue
        for si, scene in enumerate(children):
            if not isinstance(scene, dict):
                continue
            score = chapter_score
            score += _contains_score(scene.get("title") or scene.get("name"), 9)
            score += _contains_score(scene.get("guide"), 2)
            for dialogue in scene.get("key_dialogues") or []:
                score += _contains_score(dialogue, 2)
            description = _normalize_outline_title(scene.get("description"))
            if len(description) >= 8 and description[:24] in task_text:
                score += 2
            if score <= 0:
                continue
            candidate = (score, ci, si, chapter, scene)
            if best is None or candidate[:3] > best[:3]:
                best = candidate

    if best is None or best[0] < 6:
        return {}

    _, ci, si, chapter, scene = best
    return _outline_scene_contract_payload(ci, si, chapter, scene)


def format_outline_scene_contract(contract: Dict[str, Any]) -> str:
    """把当前场景契约转成 prompt 可读文本。"""
    if not contract:
        return ""
    lines = ["【当前大纲场景契约】"]
    if contract.get("chapter_title"):
        lines.append(f"- 章节：{contract.get('chapter_title')}")
    if contract.get("chapter_description"):
        lines.append(f"- 章节目标：{contract.get('chapter_description')}")
    if contract.get("scene_title"):
        lines.append(f"- 场景：{contract.get('scene_title')}")
    if contract.get("scene_description"):
        lines.append(f"- 场景功能：{contract.get('scene_description')}")
    scene_traits: list[str] = []
    if contract.get("mood"):
        scene_traits.append(f"情绪：{contract.get('mood')}")
    if contract.get("tension"):
        scene_traits.append(f"张力：{contract.get('tension')}")
    if contract.get("beat_refs"):
        scene_traits.append(f"对应节拍：{', '.join(contract.get('beat_refs') or [])}")
    if contract.get("characters"):
        scene_traits.append(f"登场：{'、'.join(contract.get('characters') or [])}")
    if scene_traits:
        lines.append("- 场景参数：" + " | ".join(scene_traits))
    for label, key in (
        ("地点", "location"),
        ("时间", "time"),
        ("入场状态", "pre_state"),
        ("本场目标", "objective"),
        ("核心冲突", "conflict"),
        ("本场转折", "turn"),
        ("离场状态", "post_state"),
        ("揭示前知情边界", "knowledge_before"),
        ("揭示后知情边界", "knowledge_after"),
        ("禁止提前发生", "forbidden_setup"),
    ):
        if contract.get(key):
            lines.append(f"- {label}：{contract.get(key)}")
    for label, key in (
        ("因果依赖", "causal_dependencies"),
        ("设置引用", "setup_refs"),
        ("兑现引用", "payoff_refs"),
    ):
        values = contract.get(key) or []
        if values:
            lines.append(f"- {label}：{'、'.join(values)}")
    if contract.get("guidance"):
        lines.append(f"- 导演指引：{contract.get('guidance')}")
    key_dialogues = contract.get("key_dialogues") or []
    if key_dialogues:
        lines.append("- 关键对话/剧情方向：")
        lines.extend(f"  - {item}" for item in key_dialogues[:6])
    lines.append("- 写作时必须服务于这个场景契约；如用户补充要求与契约冲突，优先保留用户明确要求并避免破坏全局结构。")
    return "\n".join(lines)


def _normalize_scene_character_list(value: Any) -> List[str]:
    if isinstance(value, str):
        items = re.split(r"[,，、\n]", value)
    elif isinstance(value, list):
        items = value
    else:
        items = []
    seen: set[str] = set()
    names: List[str] = []
    for item in items:
        name = str(item or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        names.append(name)
    return names


def _compact_prompt_text(value: Any, limit: int = 700) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "..."


def build_scriptwriter_handoff_context(
    user_id: str,
    project_name: str,
    *,
    task_description: str,
    chapter_name: str = "",
    scene_name: str = "",
    scene_file_path: str = "",
    scene_guidance: str = "",
    scene_characters: Any = None,
) -> str:
    """为 Director 委派 Scriptwriter 时生成写前场景交接包。"""
    if not project_name:
        return ""

    bundle = load_project_context_bundle(user_id, project_name)
    outline_data = bundle.get("outline_data") or {}
    chr_map = bundle.get("chr_map") or {}
    outline_contract = resolve_outline_scene_contract_for_task(
        outline_data,
        task_description=task_description,
        chapter_title=chapter_name,
        scene_name=scene_name,
        file_path=scene_file_path,
    )

    effective_chapter = chapter_name or outline_contract.get("chapter_title") or ""
    effective_scene = scene_name or outline_contract.get("scene_title") or ""
    effective_guidance = scene_guidance or outline_contract.get("guidance") or task_description
    characters = _normalize_scene_character_list(scene_characters)
    for name in outline_contract.get("characters") or []:
        if name and name not in characters:
            characters.append(name)

    lines: List[str] = ["### Director→Scriptwriter 场景交接包"]
    if task_description:
        lines.append("【导演委派任务】")
        lines.append(_compact_prompt_text(task_description, 900))

    contract_text = format_outline_scene_contract(outline_contract)
    if contract_text:
        lines.append("")
        lines.append(contract_text)

    try:
        from agents.story_memory import StoryMemoryFacade

        state_pack = StoryMemoryFacade(user_id, project_name).compose_scene_task_pack(
            chapter_index=outline_contract.get("chapter_index"),
            scene_index=outline_contract.get("scene_index"),
            chapter_title=effective_chapter,
            chapter_description=str(outline_contract.get("chapter_description") or ""),
            scene_title=effective_scene,
            scene_description=str(outline_contract.get("scene_description") or ""),
            scene_characters=characters,
            guidance=effective_guidance,
            chr_map=chr_map,
        )
        if state_pack.get("text"):
            lines.append("")
            lines.append(state_pack["text"])
    except Exception as e:
        print(f"[StoryMemory] 委派场景任务包构建失败（已降级）：{e}")

    lines.append("")
    lines.append("【委派核对边界】")
    lines.append("- 写作前核对本交接包中的大纲场景契约、实时人物状态、关系记录、开放线索与修订工单。")
    lines.append("- StoryMemory 只提供已保存正文整理出的事实和证据，不提供剧情方案；具体表达与取舍由执笔编剧根据导演意图完成。")
    lines.append("- 若交接包缺少具体人物或场景状态，正式落盘前应按需调用 story_memory_tool 或项目读取工具核对。")
    return "\n".join(line for line in lines if line is not None).strip()


def load_full_outline(user_id: str, project_name: str) -> str:
    """
    直接读取 大纲.txt 原文，用于注入 {full_outline}。
    不再需要 JSON→文本序列化，存储即 Markup。
    """
    outline_path = os.path.join(get_project_path(user_id, project_name), "大纲.txt")
    if not os.path.exists(outline_path):
        return ""
    try:
        with open(outline_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""


def load_narrative_memory(user_id: str, project_name: str) -> Tuple[str, str]:
    """
    加载叙事记忆：梗概文本 + 节拍表摘要。

    返回: (narrative_memory_text, beats_summary)
      narrative_memory_text: 拼合后供注入 {narrative_memory} 的字符串
      beats_summary: 纯节拍汇总，供调用方获取 current_beat 等字段
    """
    project_path = get_project_path(user_id, project_name)
    synopsis_lines: List[str] = []
    beats_lines: List[str] = []

    # ── 读取梗概 ──
    synopsis = load_synopsis_data(user_id, project_name)
    text = synopsis.get("synopsis_text", "") if isinstance(synopsis, dict) else ""
    if text:
        synopsis_lines.append("【故事梗概】")
        synopsis_lines.append(text)

    # ── 读取节拍表 ──
    beats_data = load_beats_data(user_id, project_name)
    arc = beats_data.get("global_emotional_arc", "") if isinstance(beats_data, dict) else ""
    if arc:
        beats_lines.append("【全局情感弧光】")
        beats_lines.append(arc)

    beats = beats_data.get("beats", []) if isinstance(beats_data, dict) else []
    if beats:
        beats_lines.append("\n【情感节拍表】")
        for b in beats:
            idx = b.get("beat_id", b.get("index", ""))
            btype = b.get("beat_type", b.get("type", ""))
            emotion = b.get("emotional_goal", b.get("emotion", ""))
            desc = (b.get("narrative_action") or b.get("description") or "").strip()
            header = f"Beat {idx}"
            if btype:
                header += f" [{btype}]"
            if emotion:
                header += f" 情感目标: {emotion}"
            beats_lines.append(f"  {header}")
            for label, key in (
                ("前置状态", "pre_state"),
                ("触发", "trigger"),
                ("选择/行动", "choice_or_action"),
                ("后置状态", "post_state"),
                ("揭示", "reveal"),
                ("知情变化", "knowledge_change"),
            ):
                value = str(b.get(key) or "").strip()
                if value:
                    beats_lines.append(f"    {label}: {value}")
            if desc:
                beats_lines.append(f"    {desc}")

    narrative_memory = "\n".join(synopsis_lines + beats_lines)
    beats_summary = "\n".join(beats_lines)
    return narrative_memory, beats_summary


def _get_chapter_story_files(user_id: str, project_name: str) -> Dict[int, List[str]]:
    """按隐藏章节/场景身份分组返回当前正文文件。"""
    stories_path = get_project_stories_path(user_id, project_name)
    chapters: Dict[int, List[str]] = {}
    for _, abs_path, parsed in list_story_files(stories_path):
        if not parsed or parsed.get("chapter_num") is None or parsed.get("scene_num") is None:
            continue
        chapter_index = int(parsed["chapter_num"]) - 1
        chapters.setdefault(chapter_index, []).append(abs_path)
    return chapters


def _read_story_file_safe(filepath: str) -> str:
    """安全读取正文文件，失败返回空字符串。"""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""


def build_scene_context(
    user_id: str,
    project_name: str,
    current_chapter_index: int,
    *,
    current_chapter_arc_text: Optional[str] = None,
    current_scene_index: Optional[int] = None,
    chapter_meta: Optional[Dict[str, Any]] = None,
    scene_meta: Optional[Dict[str, Any]] = None,
    chr_map: Optional[Dict[int, str]] = None,
) -> str:
    """
    三圈记忆策略：为写作当前场景组装前文上下文。

    圈 1（Hard Context）：当前章节内，目标场景之前最近的已完成场景全文。
        如果 current_chapter_arc_text 已知则直接使用；否则从文件加载。
    圈 2（Sliding Window）：最近前序章节的【最后一个场景】全文。
    圈 3（Compressed）：由调用方通过 narrative_memory 注入，此函数不重复处理。
    """
    from story.arc_parser import parse_arc, serialize_to_arc
    from story.arc_safety import sanitize_arc_for_project_ai_context

    def clean_arc(value: str) -> str:
        return sanitize_arc_for_project_ai_context(value, user_id, project_name)

    chapter_files = _get_chapter_story_files(user_id, project_name)
    parts: List[str] = []

    # ── StoryMemory：当前场景事实包（仅供核对）──────────────────────
    try:
        from agents.story_memory import StoryMemoryFacade

        chapter_meta = chapter_meta or {}
        scene_meta = scene_meta or {}
        scene_characters = (
            scene_meta.get("characters")
            or scene_meta.get("roles")
            or scene_meta.get("登场角色")
            or []
        )
        pack = StoryMemoryFacade(user_id, project_name).compose_scene_task_pack(
            chapter_index=current_chapter_index,
            scene_index=current_scene_index,
            chapter_title=str(chapter_meta.get("title") or chapter_meta.get("name") or ""),
            chapter_description=str(chapter_meta.get("description") or chapter_meta.get("summary") or ""),
            scene_title=str(scene_meta.get("title") or scene_meta.get("scene") or ""),
            scene_description=str(scene_meta.get("description") or scene_meta.get("summary") or ""),
            scene_characters=scene_characters,
            guidance=str(scene_meta.get("guidance") or scene_meta.get("goal") or ""),
            chr_map=chr_map,
        )
        if pack.get("text"):
            parts.append(pack["text"])
            parts.append("")
    except Exception as e:
        print(f"[StoryMemory] 构建场景任务包失败（已降级为三圈记忆）：{e}")

    # ── 圈 2：前序章节末尾场景 ──────────────────────────────────────────
    tail_scenes: List[str] = []
    first_tail_chapter = max(0, current_chapter_index - MAX_CROSS_CHAPTER_TAILS)
    for ci in range(first_tail_chapter, current_chapter_index):
        files = chapter_files.get(ci) or []
        if not files:
            continue
        last_file = files[-1]
        raw = _read_story_file_safe(last_file)
        if not raw:
            continue
        if last_file.lower().endswith(".md"):
            tail_scenes.append(f"【第 {ci + 1} 章 尾声】\n{raw}")
            continue
        try:
            parsed = parse_arc(raw, chr_map=chr_map)
            if parsed:
                # 只取最后一个场景作为章末锚点
                last_scene_arc = serialize_to_arc([parsed[-1]], chr_map=chr_map)
                tail_scenes.append(
                    f"【第 {ci + 1} 章 尾声 - {parsed[-1].get('scene', '')}】\n{clean_arc(last_scene_arc)}"
                )
        except Exception:
            continue

    if tail_scenes:
        parts.append("=== 前序各章节末尾场景（跨章连续性锚点）===")
        parts.extend(tail_scenes)
        parts.append("")

    # ── 圈 1：当前章已完成场景 ─────────────────────────────────────────
    if current_chapter_arc_text and current_chapter_arc_text.strip():
        # 调用方可能传入当前章完整 ARC；只保留最近场景全文，旧场景交给 StoryMemory 摘要承载。
        current_text = clean_arc(current_chapter_arc_text)
        try:
            parsed_current = parse_arc(current_text, chr_map=chr_map)
            if len(parsed_current) > MAX_CURRENT_CHAPTER_FULL_SCENES:
                current_text = clean_arc(
                    serialize_to_arc(parsed_current[-MAX_CURRENT_CHAPTER_FULL_SCENES:], chr_map=chr_map)
                )
        except Exception:
            pass
        parts.append("=== 当前章节最近前文 ===")
        parts.append(current_text)
    else:
        completed_files = chapter_files.get(current_chapter_index) or []
        if current_scene_index is not None:
            completed_files = completed_files[: max(0, current_scene_index)]
        completed_files = completed_files[-MAX_CURRENT_CHAPTER_FULL_SCENES:]
        completed_parts: List[str] = []
        for story_file in completed_files:
            raw = _read_story_file_safe(story_file)
            if not raw:
                continue
            completed_parts.append(raw if story_file.lower().endswith(".md") else clean_arc(raw))
        if completed_parts:
            parts.append("=== 当前章节最近前文（已完成场景）===")
            parts.append("\n\n".join(completed_parts))

    return "\n".join(parts)


def _normalize_beat_ref(value: Any) -> str:
    text = str(value or "").strip().casefold()
    match = re.search(r"\d+", text)
    return match.group(0) if match else text


def _format_beat_for_context(beat: Dict[str, Any]) -> str:
    beat_id = beat.get("beat_id", beat.get("index", ""))
    beat_type = str(beat.get("beat_type") or beat.get("type") or "").strip()
    emotion = str(beat.get("emotional_goal") or beat.get("emotion") or "").strip()
    description = str(beat.get("narrative_action") or beat.get("description") or "").strip()
    lines = [f"Beat {beat_id}" + (f" [{beat_type}]" if beat_type else "")]
    if emotion:
        lines[0] += f"（情感目标：{emotion}）"
    for label, key in (
        ("前置状态", "pre_state"),
        ("触发", "trigger"),
        ("选择/行动", "choice_or_action"),
        ("后置状态", "post_state"),
        ("揭示", "reveal"),
        ("知情变化", "knowledge_change"),
    ):
        value = str(beat.get(key) or "").strip()
        if value:
            lines.append(f"- {label}：{value}")
    if description:
        lines.append(f"- 节拍动作：{description}")
    return "\n".join(lines)


def get_current_beat(
    beats_data: Optional[Dict[str, Any]],
    chapter_index: int,
    scene_index: int,
    *,
    beat_refs: Optional[List[Any]] = None,
) -> str:
    """
    根据大纲场景显式标注的 beat_refs 读取当前节拍。

    章节/场景索引只保留调用兼容，不再用位置比例猜测节拍；没有明确引用时
    返回空字符串，避免把伪精确结果作为创作事实注入 Prompt。
    """
    if not beats_data:
        return ""
    beats = beats_data.get("beats", [])
    if not beats:
        return ""

    refs = {_normalize_beat_ref(item) for item in (beat_refs or []) if str(item or "").strip()}
    if not refs:
        return ""
    matched = [
        beat for beat in beats
        if _normalize_beat_ref(beat.get("beat_id", beat.get("index", ""))) in refs
    ]
    return "\n\n".join(_format_beat_for_context(beat) for beat in matched)


# ───────────────────────── 核心组装入口 ─────────────────────────────


def build_scriptwriter_context(
    user_id: str,
    project_name: str,
    *,
    # ── 场景定位 ──
    current_chapter_index: int = 0,
    current_scene_index: Optional[int] = None,
    scene_guidance: str = "",
    # ── 手动模式可传入的已解析前文 ──
    current_chapter_arc_text: Optional[str] = None,
    # ── 用户或 Director 传入的额外补充 ──
    extra_context: str = "",
    # ── 覆盖项（若调用方已自行加载，则不重复 IO）──
    worldview: Optional[str] = None,
    roles: Optional[str] = None,
    chr_map: Optional[Dict[int, str]] = None,
) -> Dict[str, Any]:
    """
    统一组装 ScriptwriterAgent 所需的完整上下文包。

    所有触发链路（手动/自动/导演）均应调用此函数获取上下文，
    然后将返回的字段透传给 `ScriptwriterAgent.write_script()` / `write_script_stream()`。

    返回 dict 包含：
      worldview         - 世界观全文
      roles             - 全量角色设定文本
      chr_map           - 角色卡隐藏绑定表，仅供解析/导出层派生使用
      full_outline      - 完整大纲文本
      narrative_memory  - 梗概 + 节拍表叙事记忆
      context           - 三圈记忆组装的前文剧本文本
      guidance          - 当前场景创作指导
      current_beat      - 当前所处情感节拍（启发式）
      current_chapter_index
      current_scene_index
    """
    # ── 加载核心数据（如未由调用方提供）──
    if worldview is None:
        worldview = load_worldview(user_id, project_name)
    if roles is None or chr_map is None:
        _roles, _chr_map = load_all_roles(user_id, project_name)
        if roles is None:
            roles = _roles
        if chr_map is None:
            chr_map = _chr_map

    bundle = load_project_context_bundle(user_id, project_name)
    full_outline = bundle.get("full_outline", "")
    narrative_memory = bundle.get("narrative_memory", "")
    outline_data = bundle.get("outline_data") or {}
    outline_scene_contract = resolve_outline_scene_contract(
        outline_data,
        chapter_index=current_chapter_index,
        scene_index=current_scene_index,
    ) if current_scene_index is not None else {}

    # 加载节拍表（用于 current_beat 估算）
    beats_data: Optional[Dict[str, Any]] = bundle.get("beats_data") or None

    current_beat = get_current_beat(
        beats_data,
        current_chapter_index,
        current_scene_index or 0,
        beat_refs=outline_scene_contract.get("beat_refs") or [],
    )

    # ── 三圈记忆前文 ──
    context = build_scene_context(
        user_id,
        project_name,
        current_chapter_index,
        current_chapter_arc_text=current_chapter_arc_text,
        current_scene_index=current_scene_index,
        chapter_meta={
            "title": outline_scene_contract.get("chapter_title", ""),
            "description": outline_scene_contract.get("chapter_description", ""),
        },
        scene_meta={
            "title": outline_scene_contract.get("scene_title", ""),
            "description": outline_scene_contract.get("scene_description", ""),
            "characters": outline_scene_contract.get("characters", []),
            "guidance": outline_scene_contract.get("guidance", ""),
        },
        chr_map=chr_map,
    )

    # 拼接用户/Director 额外补充
    if extra_context and extra_context.strip():
        from story.arc_safety import sanitize_arc_for_project_ai_context
        extra_context = sanitize_arc_for_project_ai_context(extra_context, user_id, project_name)
        if context:
            context += f"\n\n# 用户补充上下文\n{extra_context.strip()}"
        else:
            context = extra_context.strip()

    return {
        "worldview": worldview,
        "roles": roles,
        "chr_map": chr_map,
        "full_outline": full_outline,
        "narrative_memory": narrative_memory,
        "context": context,
        "guidance": scene_guidance,
        "current_beat": current_beat,
        "current_chapter_index": current_chapter_index,
        "current_scene_index": current_scene_index,
        "outline_scene_contract": outline_scene_contract,
    }
