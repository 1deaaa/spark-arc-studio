"""
项目文件收集与叙事定位

从 GraphRAG 服务抽离的通用项目文件收集功能，
供语义分块、正则搜索、向量检索等场景共用。
"""

import json
import os
from dataclasses import dataclass
from typing import Optional

from core.utils import get_project_path, get_project_stories_path, get_project_characters_path
from story.outline_parser import parse_outline_markup


# ==================== 数据类 ====================

@dataclass
class ProjectFile:
    """项目文件描述"""
    abs_path: str           # 绝对路径
    rel_path: str           # 相对路径（/ 分隔）
    filename: str           # 文件名
    format_key: str         # 格式分类：outline / synopsis / beats / worldview / character / arc / novel / chrbind
    content: str            # 文件文本内容


# ==================== 文件格式分类 ====================

# 根目录下的已知文件名 → format_key 映射
_ROOT_FILE_MAP: dict[str, str] = {
    "大纲.txt": "outline",
    "梗概.txt": "synopsis",
    "节拍表.txt": "beats",
    "世界观.txt": "worldview",
}


def classify_file(rel_path: str, filename: str) -> Optional[str]:
    """
    根据路径和文件名推断 format_key。
    不匹配返回 None（表示不在扫描范围内）。
    """
    # 根目录下的已知文件
    if "/" not in rel_path and "\\" not in rel_path:
        return _ROOT_FILE_MAP.get(filename)

    # chr/ 目录
    parts = rel_path.replace("\\", "/").split("/")
    if len(parts) >= 2 and parts[0] == "chr":
        if filename == "chr.bind":
            return "chrbind"
        if filename.endswith((".txt", ".md")):
            return "character"
        return None

    # stories/ 目录
    if len(parts) >= 2 and parts[0] == "stories":
        if filename.endswith(".arc"):
            return "arc"
        if filename.endswith(".md"):
            return "novel"
        return None

    return None


# ==================== 文件读取 ====================

def _read_file_text(file_path: str) -> str:
    """读取文件文本内容，.json 文件序列化为格式化文本"""
    if file_path.endswith(".json"):
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return json.dumps(data, ensure_ascii=False, indent=2)

    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


# ==================== 项目文件收集 ====================

def collect_project_files(
    user_id: str,
    project_name: str,
    max_source_chars: int = 600_000,
) -> list[ProjectFile]:
    """
    收集项目下所有文本文件，按叙事顺序排列。

    扫描范围：
      项目根/世界观.txt, 梗概.txt, 节拍表.txt, 大纲.txt
      chr/chr.bind, chr/*.txt, chr/*.md
      stories/**/*.arc, stories/**/*.md
    """
    project_path = get_project_path(user_id, project_name)
    if not os.path.isdir(project_path):
        return []

    # 按叙事顺序构建候选文件列表
    candidate_files: list[str] = []

    # 根目录文件（固定顺序：世界观 → 梗概 → 节拍表 → 大纲）
    for name in ("世界观.txt", "梗概.txt", "节拍表.txt", "大纲.txt"):
        candidate_files.append(os.path.join(project_path, name))

    # chr/ 目录
    chr_dir = get_project_characters_path(user_id, project_name)
    if os.path.isdir(chr_dir):
        chr_bind = os.path.join(chr_dir, "chr.bind")
        if os.path.isfile(chr_bind):
            candidate_files.append(chr_bind)
        for name in sorted(os.listdir(chr_dir)):
            if name.endswith((".txt", ".md")) and name != "chr.bind":
                candidate_files.append(os.path.join(chr_dir, name))

    # stories/ 目录
    stories_dir = get_project_stories_path(user_id, project_name)
    if os.path.isdir(stories_dir):
        # 按文件名排序保证章节顺序
        for name in sorted(os.listdir(stories_dir)):
            if name.endswith((".arc", ".md")):
                candidate_files.append(os.path.join(stories_dir, name))

    # 读取文件内容并分类
    results: list[ProjectFile] = []
    total_chars = 0

    for file_path in candidate_files:
        if not os.path.isfile(file_path):
            continue
        if total_chars >= max_source_chars:
            break

        rel_path = os.path.relpath(file_path, project_path).replace("\\", "/")
        filename = os.path.basename(file_path)
        format_key = classify_file(rel_path, filename)
        if format_key is None:
            continue

        try:
            text = _read_file_text(file_path)
        except Exception:
            continue

        text = (text or "").strip()
        if not text:
            continue

        remaining = max_source_chars - total_chars
        if remaining <= 0:
            break
        if len(text) > remaining:
            text = text[:remaining]

        total_chars += len(text)
        results.append(ProjectFile(
            abs_path=file_path,
            rel_path=rel_path,
            filename=filename,
            format_key=format_key,
            content=text,
        ))

    return results


# ==================== 叙事定位 ====================

def load_outline_data(user_id: str, project_name: str) -> dict:
    """读取并解析项目大纲，返回 outline_parser 输出的结构化数据。"""
    outline_path = os.path.join(get_project_path(user_id, project_name), "大纲.txt")
    if not os.path.exists(outline_path):
        return {"nodes": []}
    try:
        with open(outline_path, "r", encoding="utf-8") as f:
            return parse_outline_markup(f.read())
    except Exception:
        return {"nodes": []}


def build_narrative_ref(
    rel_path: str,
    format_key: str,
    outline_data: dict,
    **kwargs,
) -> str:
    """
    将文件路径+元数据转换为叙事定位文本。

    示例输出：
      "大纲 > 第1章 相遇 > 场景2 初遇"
      "剧本 > 第2章 离别 > 场景3 雨夜告白"
      "角色档案 > 张三"
      "世界观 > 魔法体系"
    """
    if format_key == "outline":
        chapter_idx = kwargs.get("chapter_idx")
        scene_idx = kwargs.get("scene_idx")
        chapter_title = kwargs.get("chapter_title", "")
        scene_title = kwargs.get("scene_title", "")
        parts = ["大纲"]
        if chapter_idx is not None:
            parts.append(f"第{chapter_idx + 1}章 {chapter_title}".strip())
        if scene_idx is not None:
            parts.append(f"场景{scene_idx + 1} {scene_title}".strip())
        return " > ".join(parts)

    if format_key == "arc":
        chapter_idx = kwargs.get("chapter_idx")
        scene_idx = kwargs.get("scene_idx")
        scene_title = kwargs.get("scene_title", "")
        parts = ["剧本"]
        if chapter_idx is not None:
            # 从大纲中查找章节标题
            chapter_title = _lookup_chapter_title(outline_data, chapter_idx)
            parts.append(f"第{chapter_idx + 1}章 {chapter_title}".strip())
        if scene_idx is not None:
            parts.append(f"场景{scene_idx + 1} {scene_title}".strip())
        return " > ".join(parts)

    if format_key == "novel":
        chapter_idx = kwargs.get("chapter_idx")
        scene_idx = kwargs.get("scene_idx")
        scene_title = kwargs.get("scene_title", "")
        parts = ["小说"]
        if chapter_idx is not None:
            chapter_title = _lookup_chapter_title(outline_data, chapter_idx)
            parts.append(f"第{chapter_idx + 1}章 {chapter_title}".strip())
        if scene_idx is not None:
            parts.append(f"场景{scene_idx + 1} {scene_title}".strip())
        return " > ".join(parts)

    if format_key == "synopsis":
        return "梗概"

    if format_key == "beats":
        beat_title = kwargs.get("beat_title", "")
        if beat_title:
            return f"节拍表 > {beat_title}"
        return "节拍表"

    if format_key == "worldview":
        section_title = kwargs.get("section_title", "")
        if section_title:
            return f"世界观 > {section_title}"
        return "世界观"

    if format_key == "character":
        char_name = kwargs.get("character_name", "")
        if char_name:
            return f"角色档案 > {char_name}"
        return "角色档案"

    if format_key == "chrbind":
        char_name = kwargs.get("character_name", "")
        if char_name:
            return f"角色绑定 > {char_name}"
        return "角色绑定"

    # 回退：使用文件名
    return rel_path


def _lookup_chapter_title(outline_data: dict, chapter_idx: int) -> str:
    """从大纲数据中查找章节标题"""
    nodes = outline_data.get("nodes", [])
    if 0 <= chapter_idx < len(nodes):
        node = nodes[chapter_idx]
        return node.get("title") or node.get("name") or f"第{chapter_idx + 1}章"
    return f"第{chapter_idx + 1}章"
