"""剧本与小说正文的统一文本统计。"""

from __future__ import annotations

import re
from typing import Any, Iterable


def _count_letters_and_numbers(text: Any) -> int:
    """与编辑器字数口径一致：只统计 Unicode 字母与数字。"""
    return sum(1 for char in str(text or "") if char.isalnum())


def _iter_dialogue_text(nodes: Iterable[dict[str, Any]]) -> Iterable[str]:
    for node in nodes:
        if not isinstance(node, dict):
            continue
        text = node.get("txt")
        if text:
            yield str(text)
        for option in node.get("opt") or []:
            if not isinstance(option, dict):
                continue
            option_text = option.get("optn")
            if option_text:
                yield str(option_text)
            yield from _iter_dialogue_text(option.get("dia") or [])


def count_story_body_chars(content: str, export_format: str) -> int:
    """统计最终可见正文字符，排除 ARC/Markdown 标记和构思块。"""
    text = str(content or "")
    if str(export_format or "").strip().lower() == "novel":
        from story.novel_parser import clean_novel_visible_text

        text = clean_novel_visible_text(text)
        return _count_letters_and_numbers(text)

    try:
        from story.arc_parser import parse_arc

        parts: list[str] = []
        parsed_scenes = parse_arc(text)
        for scene in parsed_scenes:
            intro = scene.get("intro")
            if intro:
                parts.append(str(intro))
            parts.extend(_iter_dialogue_text(scene.get("dia") or []))
        if parsed_scenes:
            return _count_letters_and_numbers("\n".join(parts))
    except Exception:
        pass

    fallback = re.sub(r"<conception>[\s\S]*?</conception>", "", text)
    fallback = re.sub(r"^\s*(?:#|@\w+|\[[^\]]+\]|</?\w+[^>]*>)\s*", "", fallback, flags=re.MULTILINE)
    return _count_letters_and_numbers(fallback)
