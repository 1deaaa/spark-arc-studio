"""
项目文件收集与叙事定位

从 GraphRAG 服务抽离的通用项目文件收集功能，
供语义分块、正则搜索、向量检索等场景共用。
"""

import json
import os
import re
from dataclasses import dataclass, field
from typing import Optional

from core.character_store import (
    CHARACTER_STORE_FILENAME,
    get_character_store_path,
    load_character_id_name_map as _load_character_id_name_map,
    read_character_records,
)
from core.utils import (
    get_project_path,
    get_project_stories_path,
    is_system_character_id,
)
from story.arc_safety import sanitize_arc_for_ai_context
from story.file_naming import list_story_files
from story.outline_parser import parse_outline_markup


# ==================== 数据类 ====================

@dataclass
class ProjectFile:
    """项目文件描述"""
    abs_path: str           # 绝对路径
    rel_path: str           # 相对路径（/ 分隔）
    filename: str           # 文件名
    format_key: str         # 格式分类：outline / synopsis / beats / worldview / character / arc / novel
    content: str            # 文件文本内容
    metadata: dict = field(default_factory=dict)


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

    parts = rel_path.replace("\\", "/").split("/")
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


def load_character_id_name_map(
    user_id: str,
    project_name: str,
    *,
    include_narrator: bool = True,
    include_system: bool = True,
) -> dict[str, str]:
    """从单文件角色仓库读取 ID→姓名映射。"""
    return _load_character_id_name_map(
        user_id,
        project_name,
        include_narrator=include_narrator,
        include_system=include_system,
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


def load_character_content(user_id: str, project_name: str, character_id: str) -> str:
    """读取单个角色正文。"""
    record = read_character_records(user_id, project_name).get(str(character_id))
    return record["content"] if record else ""


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
    *,
    allow_visual_illustration: bool = False,
) -> str:
    """给模型/检索使用的 ARC 文本补一段可用说话人清单并渲染可读说话人。

    新 ARC 正文以 ``[角色名]`` 保存；角色 ID 只属于 ``stories.db`` 等运行时结构。
    这里仍保留历史数字标记的只读容错，但不会把角色 ID 注入给 AI。
    """
    text = sanitize_arc_for_ai_context(
        str(raw_content or ""),
        allow_visual_illustration=allow_visual_illustration,
    )
    if not text.strip():
        return text
    if text.lstrip().startswith(("【可用说话人】", "【角色索引】")):
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
    *,
    include_attachments: bool = False,
) -> list[ProjectFile]:
    """
    收集项目下所有文本文件，按叙事顺序排列。

    扫描范围：
      项目根/世界观.txt, 梗概.txt, 节拍表.txt, 大纲.txt
      chr/characters.json（按角色展开为虚拟文件）
      stories/**/*.arc, stories/**/*.md
      include_attachments=True 时追加 .attachments/*/full.txt（全文，不切分）

    附件默认不进项目文件流：附件是“外来长文档”，走 longread 滑窗底座
    （地图 + 按需读窗 + 线索账本），而不是混入项目正文全量扫描。
    只有正则检索的“附件限定”场景才显式打开本开关，且返回的命中必须带
    attachment_id/chunk_index 回跳指针，Agent 直接读窗，不灌全文。

    内容增强：
      对 ``format_key == "character"`` 的虚拟文件，会在 ``content`` 头部注入
      "# 角色：xxx" 前缀（参见 :func:`enrich_character_content`）。
      下游（vector_index、GraphRAG、grep）由此可以识别"沈逐流"对应
      对应角色，而不必各自再写一份 ID→名字解析。
      对 ``format_key == "arc"`` 的文件，会在模型可见文本头部注入紧凑
      可用说话人清单（参见 :func:`enrich_arc_content_for_model`），但不修改原始
      ``.arc`` 文件，也不改变运行时解析协议。
    """
    project_path = get_project_path(user_id, project_name)
    if not os.path.isdir(project_path):
        return []

    character_records = read_character_records(user_id, project_name)
    character_map = {
        character_id: record["name"]
        for character_id, record in character_records.items()
    }
    from core.project_settings import is_visual_illustration_enabled
    allow_visual_illustration = is_visual_illustration_enabled(user_id, project_name)

    results: list[ProjectFile] = []
    total_chars = 0

    def append_physical_file(file_path: str) -> None:
        nonlocal total_chars
        if not os.path.isfile(file_path) or total_chars >= max_source_chars:
            return
        rel_path = os.path.relpath(file_path, project_path).replace("\\", "/")
        filename = os.path.basename(file_path)
        format_key = classify_file(rel_path, filename)
        if format_key is None:
            return

        try:
            text = _read_file_text(file_path)
        except Exception:
            return

        text = (text or "").strip()
        if not text:
            return

        if format_key == "arc":
            text = enrich_arc_content_for_model(
                text,
                character_map,
                allow_visual_illustration=allow_visual_illustration,
            )

        remaining = max_source_chars - total_chars
        if remaining <= 0:
            return
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

    # 固定叙事顺序：项目设定 → 角色 → 故事正文。
    for name in ("世界观.txt", "梗概.txt", "节拍表.txt", "大纲.txt"):
        append_physical_file(os.path.join(project_path, name))

    store_path = get_character_store_path(user_id, project_name)
    for character_id, record in character_records.items():
        if is_system_character_id(character_id) or total_chars >= max_source_chars:
            continue
        text = enrich_character_content(
            record["content"], character_id, record["name"]
        ).strip()
        if not text:
            continue
        remaining = max_source_chars - total_chars
        text = text[:remaining]
        total_chars += len(text)
        results.append(ProjectFile(
            abs_path=store_path,
            rel_path=f"chr/{CHARACTER_STORE_FILENAME}#character={character_id}",
            filename=CHARACTER_STORE_FILENAME,
            format_key="character",
            content=text,
            metadata={
                "character_id": character_id,
                "character_name": record["name"],
            },
        ))

    stories_dir = get_project_stories_path(user_id, project_name)
    if os.path.isdir(stories_dir):
        # 所有故事正文统一复用文件名元数据排序，不能退回目录/文件名字符串排序。
        for _, file_path, _ in list_story_files(stories_dir):
            append_physical_file(file_path)

    if include_attachments:
        _append_attachment_files(
            user_id, project_name, results,
            get_total_chars=lambda: total_chars,
            add_chars=lambda n: _bump_total(n),
        )
        total_chars = _current_total(results)

    return results


def _current_total(files: list[ProjectFile]) -> int:
    return sum(len(pf.content or "") for pf in files)


def _bump_total(n: int) -> None:
    # 占位：实际累计在 _append_attachment_files 内直接操作 results；
    # 保留本函数仅为语义锚点，避免后续维护者误以为附件不计预算。
    _ = n


def _append_attachment_files(
    user_id: str,
    project_name: str,
    results: list[ProjectFile],
    *,
    get_total_chars,
    add_chars,
) -> None:
    """把附件全文作为虚拟 ProjectFile 追加到收集结果。

    每附件一项：rel_path=.attachments/{id}/full.txt、format_key=attachment、
    metadata 带 attachment_id/filename/chunk_count。调用方（正则附件检索）
    必须再按 chunk 边界把命中映射回窗口号，不得把全文灌给模型。
    """
    try:
        from agents.attachment.storage import (
            ATTACHMENTS_DIR_NAME,
            get_attachment_meta,
            load_attachment_text,
        )
        from core.utils import get_project_path as _get_project_path
    except Exception:
        return
    try:
        project_path = _get_project_path(user_id, project_name)
        attachments_root = os.path.join(project_path, ATTACHMENTS_DIR_NAME)
        if not os.path.isdir(attachments_root):
            return
        for attachment_id in sorted(os.listdir(attachments_root)):
            attachment_dir = os.path.join(attachments_root, attachment_id)
            if not os.path.isdir(attachment_dir):
                continue
            meta = get_attachment_meta(user_id, project_name, attachment_id)
            if meta is None:
                continue
            try:
                text = (load_attachment_text(user_id, project_name, attachment_id) or "").strip()
            except Exception:
                continue
            if not text:
                continue
            results.append(ProjectFile(
                abs_path=os.path.join(attachment_dir, "full.txt"),
                rel_path=f"{ATTACHMENTS_DIR_NAME}/{attachment_id}/full.txt".replace("\\", "/"),
                filename=meta.filename,
                format_key="attachment",
                content=text,
                metadata={
                    "attachment_id": attachment_id,
                    "attachment_filename": meta.filename,
                    "chunk_count": int(meta.chunk_count or 0),
                },
            ))
    except Exception:
        return


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

    # 回退：使用文件名
    return rel_path


def _lookup_chapter_title(outline_data: dict, chapter_idx: int) -> str:
    """从大纲数据中查找章节标题"""
    nodes = outline_data.get("nodes", [])
    if 0 <= chapter_idx < len(nodes):
        node = nodes[chapter_idx]
        return node.get("title") or node.get("name") or f"第{chapter_idx + 1}章"
    return f"第{chapter_idx + 1}章"
