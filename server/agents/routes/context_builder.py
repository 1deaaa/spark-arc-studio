"""
ScriptWriter Context Builder - 执笔编剧统一上下文组装器

════════════════════════════════════════════════════════════════════════
【设计目标】
本模块是 ScriptwriterAgent 三条触发链路的唯一上下文数据源：
  1. 手动创作 (production.py / compose)
  2. 全自动批处理 (auto_write.py)
  3. 导演委派 (director_graph.py)

在此之前，各链路分别维护各自的上下文组装代码，导致任何逻辑改动
必须同步修改三处，且 auto_write.py 内的世界观/角色均为硬编码占位符。

【核心改进】
  - 全量世界观 / 全量角色：废弃"只传选中角色"的旧逻辑，所有入口必须
    全量加载，因为大模型上下文窗口（128K+）完全容纳，且遗漏角色设定
    是导致 OOC（角色崩坏）和"吃书"的根本原因。
  - 三圈记忆策略（Scene Context）：
      ① 当前章全文    ← 最近戏剧连续性
      ② 前序章章末尾声 ← 跨章情感锚点
      ③ 梗概+节拍表  ← 全局叙事线
  - 统一大纲注入：直接读取 大纲.txt 原文，
    让编剧始终知道全局故事蓝图。
════════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional, Tuple

from core.utils import (
    ensure_project_characters_directory,
    get_project_path,
    get_project_stories_path,
)
from story.project_files import _coerce_character_name


# ─────────────────────── Story Tags 共享构建器 ───────────────────────


def build_story_tags_hint(story_tags: dict) -> str:
    """从 story_tags 字典构建注入 LLM 上下文的提示文本块。

    与 context_provider._build_story_tags_block 保持一致的格式，
    包含 POV 醒目优化（三层锚定策略）。

    Args:
        story_tags: 从 get_project_story_tags 返回的字典

    Returns:
        格式化后的 story tags 文本块，若所有字段均为空则返回空字符串
    """
    if not story_tags:
        return ""

    parts = []

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
    统一读取角色绑定、详情文本与 prompt 用文本。

    返回字段：
      - characters: [{id, name, desc, content}]
      - chr_map: {int(id): name}
      - roles_text: prompt 注入用全量角色文本
      - summary_text: 简要列表文本
      - detailed_summary_text: 详细摘要文本
    """
    characters_path = ensure_project_characters_directory(user_id, project_name)
    bind_file = os.path.join(characters_path, "chr.bind")
    if not os.path.exists(bind_file):
        return {
            "characters": [],
            "chr_map": {},
            "roles_text": "",
            "summary_text": "",
            "detailed_summary_text": "",
        }

    try:
        with open(bind_file, "r", encoding="utf-8") as f:
            raw_map: Dict[str, Any] = json.load(f) or {}
    except Exception:
        raw_map = {}

    characters: List[Dict[str, Any]] = []
    chr_map: Dict[int, str] = {}
    role_blocks: List[str] = []
    summary_lines: List[str] = ["### 角色列表"]
    detailed_lines: List[str] = ["### 已有角色设定"]

    for cid_str, raw_info in raw_map.items():
        try:
            cid = int(cid_str)
        except Exception:
            continue

        raw_name = _coerce_character_name(raw_info)
        display_name = "旁白" if cid == -1 else raw_name
        chr_map[cid] = display_name

        content = ""
        detail_path = os.path.join(characters_path, f"{cid_str}.txt")
        if os.path.exists(detail_path):
            try:
                with open(detail_path, "r", encoding="utf-8") as f:
                    text = f.read().strip()
                if text:
                    content = text
            except Exception:
                continue

        desc = content.replace("\n", " ") if content else ""
        characters.append(
            {
                "id": cid,
                "name": display_name,
                "desc": desc,
                "content": content,
            }
        )

        role_blocks.append(
            f"--- 角色: {display_name} (ID: {cid}) ---\n{content or '(暂无详细设定)'}"
        )

        if cid != -1:
            summary_entry = f"- {display_name}"
            if desc:
                summary_entry += f": {desc}"
            summary_lines.append(summary_entry)

            detailed_lines.append(f"\n#### {display_name}")
            detailed_lines.append(content if content else "(尚无详细设定)")

    summary_text = "\n".join(summary_lines) if len(summary_lines) > 1 else ""
    detailed_summary_text = "\n".join(detailed_lines) if len(detailed_lines) > 1 else ""
    return {
        "characters": characters,
        "chr_map": chr_map,
        "roles_text": "\n\n".join(role_blocks),
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

    return {
        "worldview": worldview,
        "character_bundle": character_bundle,
        "roles": character_bundle.get("roles_text", ""),
        "chr_map": character_bundle.get("chr_map", {}),
        "characters": character_bundle.get("characters", []),
        "characters_summary": character_bundle.get("summary_text", ""),
        "characters_detailed_summary": character_bundle.get("detailed_summary_text", ""),
        "synopsis_data": synopsis_data,
        "beats_data": beats_data,
        "outline_data": outline_data,
        "full_outline": full_outline,
        "narrative_memory": narrative_memory,
        "beats_summary": beats_summary,
    }


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
            idx = b.get("index", "")
            btype = b.get("type", "")
            emotion = b.get("emotion", "")
            desc = (b.get("description") or "").strip()
            header = f"Beat {idx}"
            if btype:
                header += f" [{btype}]"
            if emotion:
                header += f" 情感目标: {emotion}"
            beats_lines.append(f"  {header}")
            if desc:
                beats_lines.append(f"    {desc}")

    narrative_memory = "\n".join(synopsis_lines + beats_lines)
    beats_summary = "\n".join(beats_lines)
    return narrative_memory, beats_summary


def _get_chapter_arc_files(user_id: str, project_name: str) -> List[str]:
    """返回按名称排序的章节 .arc 文件路径列表。"""
    stories_path = get_project_stories_path(user_id, project_name)
    if not os.path.exists(stories_path):
        return []
    return sorted(
        [
            os.path.join(stories_path, f)
            for f in os.listdir(stories_path)
            if f.endswith(".arc")
        ]
    )


def _read_arc_file_safe(filepath: str) -> str:
    """安全读取 .arc 文件，失败返回空字符串。"""
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
) -> str:
    """
    三圈记忆策略：为写作当前场景组装前文上下文。

    圈 1（Hard Context）：当前章节内，目标场景之前的所有已完成场景全文。
        如果 current_chapter_arc_text 已知则直接使用；否则从文件加载。
    圈 2（Sliding Window）：前序各章节的【最后一个场景】的 .arc 全文。
    圈 3（Compressed）：由调用方通过 narrative_memory 注入，此函数不重复处理。
    """
    from story.arc_parser import parse_arc, serialize_to_arc

    arc_files = _get_chapter_arc_files(user_id, project_name)
    parts: List[str] = []

    # ── 圈 2：前序章节末尾场景 ──────────────────────────────────────────
    tail_scenes: List[str] = []
    for ci in range(current_chapter_index):
        if ci >= len(arc_files):
            break
        raw = _read_arc_file_safe(arc_files[ci])
        if not raw:
            continue
        try:
            parsed = parse_arc(raw)
            if parsed:
                # 只取最后一个场景作为章末锚点
                last_scene_arc = serialize_to_arc([parsed[-1]])
                tail_scenes.append(
                    f"【第 {ci} 章 尾声 - {parsed[-1].get('scene', '')}】\n{last_scene_arc}"
                )
        except Exception:
            continue

    if tail_scenes:
        parts.append("=== 前序各章节末尾场景（跨章连续性锚点）===")
        parts.extend(tail_scenes)
        parts.append("")

    # ── 圈 1：当前章已完成场景 ─────────────────────────────────────────
    if current_chapter_arc_text and current_chapter_arc_text.strip():
        # 调用方已传入当前章的完整 arc 文本（截至 target_scene 之前）
        parts.append("=== 当前章节前文 ===")
        parts.append(current_chapter_arc_text)
    elif current_chapter_index < len(arc_files):
        # 全自动模式下：读取已保存的当前章 arc 文件
        raw = _read_arc_file_safe(arc_files[current_chapter_index])
        if raw:
            if current_scene_index is not None:
                # 截取到 current_scene_index 之前的所有场景
                try:
                    parsed = parse_arc(raw)
                    before_scenes = parsed[:current_scene_index]
                    if before_scenes:
                        parts.append("=== 当前章节前文（已完成场景）===")
                        parts.append(serialize_to_arc(before_scenes))
                except Exception:
                    pass
            else:
                parts.append("=== 当前章节前文 ===")
                parts.append(raw)

    return "\n".join(parts)


def get_current_beat(beats_data: Optional[Dict[str, Any]], chapter_index: int, scene_index: int) -> str:
    """
    根据章节和场景索引，尽力匹配当前最接近的情感节拍名称。
    这是一个启发式估算，供 Prompt 里展示"当前情感节拍"用。
    """
    if not beats_data:
        return ""
    beats = beats_data.get("beats", [])
    if not beats:
        return ""

    # 简单线性映射：按章节总数比例估算节拍位置
    # 更精确的映射需要大纲里做节拍编号标注（outline 节点里的 beat_refs 字段）
    total_beats = len(beats)
    # 从 大纲.txt 推算当前是整本书第几个场景
    # （此处只用 chapter_index 粗略估算，未来可精确到场景级）
    ratio = chapter_index / max(1, chapter_index + 1)
    beat_idx = min(int(ratio * total_beats), total_beats - 1)
    beat = beats[beat_idx]
    btype = beat.get("type", "")
    emotion = beat.get("emotion", "")
    if btype and emotion:
        return f"{btype}（情感目标：{emotion}）"
    return btype or emotion


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
      chr_map           - {int: str} 角色 ID 映射
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

    # 加载节拍表（用于 current_beat 估算）
    beats_data: Optional[Dict[str, Any]] = bundle.get("beats_data") or None

    current_beat = get_current_beat(beats_data, current_chapter_index, current_scene_index or 0)

    # ── 三圈记忆前文 ──
    context = build_scene_context(
        user_id,
        project_name,
        current_chapter_index,
        current_chapter_arc_text=current_chapter_arc_text,
        current_scene_index=current_scene_index,
    )

    # 拼接用户/Director 额外补充
    if extra_context and extra_context.strip():
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
    }
