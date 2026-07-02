"""
项目文件收集与叙事定位

从 GraphRAG 服务抽离的通用项目文件收集功能，
供语义分块、正则搜索、向量检索等场景共用。
"""

import json
import os
import re
from dataclasses import dataclass
from typing import Optional

from core.utils import (
    SYSTEM_CHARACTER_NAMES,
    get_project_path,
    get_project_stories_path,
    get_project_characters_path,
    is_system_character_id,
)
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
        if filename.endswith(".txt"):
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


# ==================== 角色卡隐藏绑定表（项目级资源绑定真相源） ====================
#
# 设计原则：创作层与 ARC 正文以角色名为真相；chr.bind 只服务角色卡、
# 资源绑定、SQLite/Unity 导出等运行时边界。绑定表解析仍集中在此处，
# 避免其他模块散落实现。
#
# chr.bind 实际结构有两种历史形态，本工具一并兼容：
#   1) {"0": "沈逐流"}                   —— 早期纯字符串
#   2) {"0": {"name": "沈逐流", ...}}    —— 新版含结构化扩展字段
#
# 特殊 ID："-1" 视作"旁白"，仅在 ``include_narrator=True`` 时回填默认名"旁白"。

_CHARACTER_NARRATOR_ID = "-1"
_CHARACTER_NARRATOR_NAME = SYSTEM_CHARACTER_NAMES.get(-1, "旁白")
_CHARACTER_UNKNOWN_ID = "-2"
_CHARACTER_UNKNOWN_NAME = SYSTEM_CHARACTER_NAMES.get(-2, "?")


def _character_bind_path(user_id: str, project_name: str) -> str:
    """计算 chr.bind 的绝对路径。"""
    return os.path.join(get_project_characters_path(user_id, project_name), "chr.bind")


def _coerce_character_name(value) -> str:
    """从 chr.bind 单条记录抽出"角色名"字段，兼容字符串与字典两种形态。"""
    if isinstance(value, dict):
        return str(value.get("name") or "").strip()
    return str(value or "").strip()


def load_character_id_name_map_from_bind_path(
    bind_path: str,
    *,
    include_narrator: bool = True,
    include_system: bool = True,
    include_empty: bool = False,
) -> dict[str, str]:
    """底层版本：直接按 chr.bind 文件绝对路径读取 ID→名字映射。

    专供"没有 user_id/project_name 上下文"的场景使用（例如语义切块器、
    某些只有 ``ProjectFile.abs_path`` 的策略实现）。一般业务层应该用
    :func:`load_character_id_name_map`。
    """
    if not bind_path or not os.path.isfile(bind_path):
        return {}

    try:
        with open(bind_path, "r", encoding="utf-8") as f:
            mapping = json.load(f) or {}
    except Exception:
        return {}

    if not isinstance(mapping, dict):
        return {}

    result: dict[str, str] = {}
    for raw_cid, raw_value in mapping.items():
        cid = str(raw_cid)
        name = _coerce_character_name(raw_value)
        if cid == _CHARACTER_NARRATOR_ID:
            if not include_narrator:
                continue
            # 旁白角色名约定为"旁白"，即便 chr.bind 内是空字符串也补上
            name = name or _CHARACTER_NARRATOR_NAME
        elif cid == _CHARACTER_UNKNOWN_ID:
            if not include_system:
                continue
            name = name or _CHARACTER_UNKNOWN_NAME
        if not name and not include_empty:
            continue
        result[cid] = name
    return result


def load_character_id_name_map(
    user_id: str,
    project_name: str,
    *,
    include_narrator: bool = True,
    include_system: bool = True,
    include_empty: bool = False,
) -> dict[str, str]:
    """读取 chr.bind，返回 ``{character_id: character_name}`` 映射。

    Args:
        user_id: 用户 ID。
        project_name: 项目名。
        include_narrator: 是否把 ID="-1" 的旁白角色纳入映射。默认 True。
            对于"想拿到全部角色名做实体识别"的场景应保持 True；
            对于"列出可写作的角色"的场景可以设 False 把旁白排除。
        include_system: 是否把除旁白外的系统保留角色纳入映射。默认 True。
        include_empty: 是否保留名字为空的条目。默认 False（过滤掉）。

    Returns:
        ``{cid: name}``。即便 chr.bind 不存在或解析失败，也保证返回 ``{}``。
    """
    return load_character_id_name_map_from_bind_path(
        _character_bind_path(user_id, project_name),
        include_narrator=include_narrator,
        include_system=include_system,
        include_empty=include_empty,
    )


def lookup_character_name(
    user_id: str,
    project_name: str,
    character_id: str,
    *,
    include_narrator: bool = True,
) -> str:
    """根据角色 ID 拿到角色名。找不到时返回空字符串。"""
    if not character_id:
        return ""
    name_map = load_character_id_name_map(
        user_id, project_name, include_narrator=include_narrator,
    )
    return name_map.get(str(character_id), "")


def lookup_character_id_by_name(
    user_id: str,
    project_name: str,
    character_name: str,
) -> str:
    """根据角色名反查 ID。找不到时返回空字符串。"""
    target = (character_name or "").strip()
    if not target:
        return ""
    name_map = load_character_id_name_map(user_id, project_name)
    for cid, name in name_map.items():
        if name == target:
            return cid
    return ""


def get_character_file_path(
    user_id: str,
    project_name: str,
    character_id: str,
    *,
    extensions: tuple[str, ...] = (".txt", ".md"),
) -> str:
    """根据角色 ID 找到设定文件的绝对路径。找不到时返回空字符串。"""
    chr_dir = get_project_characters_path(user_id, project_name)
    if not os.path.isdir(chr_dir):
        return ""
    for ext in extensions:
        path = os.path.join(chr_dir, f"{character_id}{ext}")
        if os.path.isfile(path):
            return path
    return ""


def enrich_character_content(
    raw_content: str,
    character_id: str,
    character_name: str,
) -> str:
    """给 character 文件内容补上"角色名"前缀，便于下游 LLM/精确搜索识别。

    设计要点：
    - 这是 ``collect_project_files`` 内部的内容增强器；其结果会作为
      ``ProjectFile.content`` 暴露给 vector_index、GraphRAG、grep 等所有下游。
    - 即便文件本身没有写明角色名（角色 .txt 通常以"职业:xxx 性格:xxx"这种
      字段形式开头），下游也能直接看到"# 角色：沈逐流"这一行。
    - 已有"角色名："前缀（用户手写场景）时不再重复添加。
    """
    text = (raw_content or "").lstrip()
    name = (character_name or "").strip()
    cid = (character_id or "").strip()

    if not name and not cid:
        return raw_content

    # 已经有"角色：xxx"或"角色名：xxx"开头则不重复
    head_lines = text.splitlines()[:3]
    head_text = "\n".join(head_lines)
    if (
        f"角色：{name}" in head_text
        or f"角色名：{name}" in head_text
        or f"# 角色：{name}" in head_text
    ):
        return raw_content

    if name:
        label = f"角色：{name}"
    else:
        label = "角色"

    return f"# {label}\n\n{raw_content}"


def _iter_named_story_characters(character_map: dict) -> list[tuple[str, str]]:
    """返回普通角色的 ID/名字列表，排除旁白、? 等系统角色。"""
    items: list[tuple[str, str]] = []
    if not isinstance(character_map, dict):
        return items
    for raw_cid, raw_name in character_map.items():
        cid = str(raw_cid).strip()
        name = str(raw_name or "").strip()
        if not cid or not name:
            continue
        try:
            if is_system_character_id(int(cid)):
                continue
        except Exception:
            pass
        items.append((cid, name))
    return items


def enrich_arc_content_for_model(
    raw_content: str,
    character_map: dict,
) -> str:
    """给模型/检索使用的 ARC 文本补一段角色索引并渲染可读说话人。

    新 ARC 正文以 ``[角色名]`` 保存；这里仍保留开发期数字标记的只读容错，
    让 GraphRAG、向量检索和 grep 不会把 ``[0]`` 当成无意义符号。
    """
    text = str(raw_content or "")
    if not text.strip():
        return text
    if text.lstrip().startswith(("【角色索引】", "【可用说话人】")):
        return text

    named_characters = _iter_named_story_characters(character_map)
    if not named_characters:
        return text

    name_map = {str(cid): name for cid, name in named_characters}

    text = re.sub(r"^(\s*)\[(-?\d+)\]\s*$", lambda m: f"{m.group(1)}[{name_map.get(m.group(2), m.group(2))}]", text, flags=re.MULTILINE)

    index_lines = ["【可用说话人】"]
    index_lines.extend(f"[{name}]" for _, name in named_characters)
    index_lines.append("【剧本正文】")
    return "\n".join(index_lines) + "\n" + text


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
      chr/chr.bind, chr/*.txt
      stories/**/*.arc, stories/**/*.md

    内容增强：
      对 ``format_key == "character"`` 的文件，会在 ``content`` 头部注入
      "# 角色：xxx" 前缀（参见 :func:`enrich_character_content`）。
      下游（vector_index、GraphRAG、grep）由此可以识别"沈逐流"对应
      ``chr/0.txt``，而不必各自再写一份 ID→名字解析。
      对 ``format_key == "arc"`` 的文件，会在模型可见文本头部注入紧凑
      角色索引（参见 :func:`enrich_arc_content_for_model`），但不修改原始
      ``.arc`` 文件，也不改变运行时解析协议。
    """
    project_path = get_project_path(user_id, project_name)
    if not os.path.isdir(project_path):
        return []

    # 一次性加载角色 ID → 名字映射（chr.bind 可能不存在，结果为空字典）
    character_map = load_character_id_name_map(user_id, project_name)

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
            if name.endswith(".txt") and name != "chr.bind":
                candidate_files.append(os.path.join(chr_dir, name))

    # stories/ 目录
    stories_dir = get_project_stories_path(user_id, project_name)
    if os.path.isdir(stories_dir):
        # 按目录与文件名排序保证章节 / 场景顺序；支持“章节文件夹 > 场景文件”的作品管理器结构。
        for root, dirs, files in os.walk(stories_dir):
            dirs.sort()
            for name in sorted(files):
                if name.endswith((".arc", ".md")):
                    candidate_files.append(os.path.join(root, name))

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

        # 角色文件：从文件名推断隐藏 ID，只把"# 角色：xxx"前缀注入 content。
        # 这一步必须放在字符截断之前，避免前缀被截掉。
        if format_key == "character":
            character_id = os.path.splitext(filename)[0]
            character_name = character_map.get(character_id, "")
            text = enrich_character_content(text, character_id, character_name)
        elif format_key == "arc":
            text = enrich_arc_content_for_model(text, character_map)

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
