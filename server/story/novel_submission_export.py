from __future__ import annotations

import io
import re
import zipfile
from dataclasses import dataclass
from html import escape as html_escape
from typing import Any
from xml.sax.saxutils import escape as xml_escape

from story.novel_parser import clean_novel_visible_text


class NovelSubmissionExportError(ValueError):
    """小说投稿包生成失败。"""


@dataclass(frozen=True)
class NovelSubmissionPlatformSpec:
    key: str
    display_name: str
    bundle_suffix: str
    readme_note: str
    material_pack: bool = False
    jinjiang_layout: bool = False


@dataclass(frozen=True)
class NormalizedSubmissionChapter:
    chapter_num: str
    heading: str
    body: str
    filename_stem: str


@dataclass(frozen=True)
class NovelSubmissionPackage:
    filename: str
    content: bytes
    platform: NovelSubmissionPlatformSpec
    chapter_count: int


SUPPORTED_NOVEL_SUBMISSION_PLATFORMS: dict[str, NovelSubmissionPlatformSpec] = {
    "fanqie": NovelSubmissionPlatformSpec(
        key="fanqie",
        display_name="番茄小说",
        bundle_suffix="番茄投稿包",
        readme_note="适合番茄作家助手新建作品后逐章发布：使用逐章文件中的第一行作为章节标题，余下内容粘贴到正文框。",
    ),
    "qidian": NovelSubmissionPlatformSpec(
        key="qidian",
        display_name="阅文/起点",
        bundle_suffix="阅文起点投稿包",
        readme_note="适合阅文作家助手或起点作家后台逐章发布：使用逐章文件中的章节标题和正文，按后台字段复制粘贴。",
    ),
    "qimao": NovelSubmissionPlatformSpec(
        key="qimao",
        display_name="七猫小说",
        bundle_suffix="七猫投稿材料包",
        readme_note="适合七猫作者后台或编辑收稿材料整理：正文已拆成整本与逐章文件，大纲模板需按平台要求补齐作品简介、卖点和分章梗概。",
        material_pack=True,
    ),
    "jinjiang": NovelSubmissionPlatformSpec(
        key="jinjiang",
        display_name="晋江文学城",
        bundle_suffix="晋江投稿包",
        readme_note="适合晋江作者后台逐章粘贴：每章文件按“章节标题 / 内容提要 / 章节正文”三段整理，内容提要留空供发布前补写。",
        jinjiang_layout=True,
    ),
    "zongheng": NovelSubmissionPlatformSpec(
        key="zongheng",
        display_name="纵横中文网",
        bundle_suffix="纵横投稿材料包",
        readme_note="适合纵横作家后台或编辑投稿材料整理：正文已拆成整本与逐章文件，大纲模板需补齐作品简介、核心卖点和分章梗概。",
        material_pack=True,
    ),
}


_INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_MARKDOWN_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+")


def _normalize_newlines(value: Any) -> str:
    return str(value or "").replace("\r\n", "\n").replace("\r", "\n").replace("\u00A0", " ")


def _sanitize_filename_part(value: str, fallback: str = "未命名") -> str:
    cleaned = _INVALID_FILENAME_CHARS.sub("_", _normalize_newlines(value))
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .")
    return (cleaned or fallback)[:80]


def _plain_title(value: Any) -> str:
    title = _normalize_newlines(value).split("\n", 1)[0]
    title = re.sub(r"\s+", " ", title).strip()
    return title


def _format_chapter_heading(chapter: dict[str, Any]) -> str:
    chapter_num = str(chapter.get("chapter_num") or "").strip() or "1"
    title = _plain_title(chapter.get("title")) or f"第{chapter_num}章"
    if re.match(r"^第[0-9零〇一二三四五六七八九十百千万]+[章节回卷部集]", title):
        return title
    return f"第{chapter_num}章 {title}".strip()


def _format_chapter_num_for_filename(value: Any) -> str:
    raw = str(value or "").strip()
    try:
        return f"{int(raw):03d}"
    except ValueError:
        return _sanitize_filename_part(raw, "000")


def _clean_body_text(value: Any) -> str:
    lines: list[str] = []
    visible_text = clean_novel_visible_text(_normalize_newlines(value))
    for raw_line in visible_text.split("\n"):
        line = raw_line.rstrip()
        if _MARKDOWN_HEADING_RE.match(line):
            continue
        line = re.sub(r"^\s{0,3}>\s?", "", line)
        line = re.sub(r"(\*\*|__)(.*?)\1", r"\2", line)
        line = re.sub(r"(\*|_)(.*?)\1", r"\2", line)
        line = re.sub(r"`([^`]+)`", r"\1", line)
        lines.append(line.rstrip())

    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _collect_chapters(toc: list[dict[str, Any]]) -> list[NormalizedSubmissionChapter]:
    chapters: list[NormalizedSubmissionChapter] = []
    for chapter in toc:
        scenes = chapter.get("scenes") if isinstance(chapter, dict) else []
        if not isinstance(scenes, list):
            scenes = []

        scene_blocks: list[str] = []
        for scene in scenes:
            if not isinstance(scene, dict):
                continue
            content = _clean_body_text(scene.get("content"))
            if content:
                scene_blocks.append(content)

        body = "\n\n".join(scene_blocks).strip()
        if not body:
            continue

        heading = _format_chapter_heading(chapter)
        chapter_num = str(chapter.get("chapter_num") or len(chapters) + 1)
        filename_stem = f"{_format_chapter_num_for_filename(chapter_num)}_{_sanitize_filename_part(heading)}"
        chapters.append(
            NormalizedSubmissionChapter(
                chapter_num=chapter_num,
                heading=heading,
                body=body,
                filename_stem=filename_stem,
            )
        )

    return chapters


def _build_plain_chapter(chapter: NormalizedSubmissionChapter) -> str:
    return f"{chapter.heading}\n\n{chapter.body}".strip() + "\n"


def _build_plain_full_text(chapters: list[NormalizedSubmissionChapter]) -> str:
    return "\n\n".join(_build_plain_chapter(chapter).strip() for chapter in chapters).strip() + "\n"


def _build_jinjiang_chapter(chapter: NormalizedSubmissionChapter) -> str:
    return (
        f"章节标题：{chapter.heading}\n"
        "内容提要：\n"
        "章节正文：\n"
        f"{chapter.body}\n"
    )


def _build_jinjiang_full_text(chapters: list[NormalizedSubmissionChapter]) -> str:
    return "\n\n".join(_build_jinjiang_chapter(chapter).strip() for chapter in chapters).strip() + "\n"


def _build_outline_template(project_name: str, chapters: list[NormalizedSubmissionChapter]) -> str:
    lines = [
        f"作品名：{project_name}",
        "一句话简介：",
        "全文简介：",
        "核心卖点：",
        "",
        "分章大纲：",
    ]
    for chapter in chapters:
        lines.append(f"{chapter.heading}：")
    return "\n".join(lines).strip() + "\n"


def _build_readme(
    project_name: str,
    platform: NovelSubmissionPlatformSpec,
    chapters: list[NormalizedSubmissionChapter],
) -> str:
    return (
        f"作品：{project_name}\n"
        f"平台：{platform.display_name}\n"
        f"章节数：{len(chapters)}\n\n"
        f"{platform.readme_note}\n\n"
        "文件说明：\n"
        "- 整本正文.txt：按章节顺序合并的 UTF-8 纯文本正文。\n"
        "- 逐章拆分/：每章一个 txt 文件，便于复制到作者后台。\n"
        "- 大纲模板.txt：仅材料包平台包含，发布或投稿前请补齐简介、大纲、作者资料等后台必填信息。\n"
        "- Word材料/：仅材料包平台包含，提供 Word 可打开的正文与大纲文件，便于编辑邮箱投稿。\n\n"
        "注意：平台后台规则可能调整；发布前请以对应作者后台当前提示为准。\n"
    )


def _build_docx_bytes(title: str, text: str) -> bytes:
    paragraphs = [title, "", *_normalize_newlines(text).split("\n")]
    body = "\n".join(
        f'<w:p><w:r><w:t xml:space="preserve">{xml_escape(paragraph)}</w:t></w:r></w:p>'
        for paragraph in paragraphs
    )
    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{body}<w:sectPr /></w:body>"
        "</w:document>"
    )

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "[Content_Types].xml",
            (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml" />'
                '<Default Extension="xml" ContentType="application/xml" />'
                '<Override PartName="/word/document.xml" '
                'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml" />'
                "</Types>"
            ),
        )
        archive.writestr(
            "_rels/.rels",
            (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rId1" '
                'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
                'Target="word/document.xml" />'
                "</Relationships>"
            ),
        )
        archive.writestr("word/document.xml", document_xml)
    return buffer.getvalue()


def _build_word_html_bytes(title: str, text: str) -> bytes:
    paragraphs = [title, "", *_normalize_newlines(text).split("\n")]
    html_paragraphs = "\n".join(f"<p>{html_escape(paragraph) or '&nbsp;'}</p>" for paragraph in paragraphs)
    html_doc = (
        "<html><head><meta charset=\"utf-8\"></head>"
        f"<body>{html_paragraphs}</body></html>"
    )
    return ("\ufeff" + html_doc).encode("utf-8")


def generate_novel_submission_zip(
    project_name: str,
    toc: list[dict[str, Any]],
    platform_key: str,
) -> NovelSubmissionPackage:
    """根据小说目录生成指定平台投稿 zip 包。"""
    normalized_key = str(platform_key or "").strip().lower()
    platform = SUPPORTED_NOVEL_SUBMISSION_PLATFORMS.get(normalized_key)
    if not platform:
        supported = "、".join(spec.display_name for spec in SUPPORTED_NOVEL_SUBMISSION_PLATFORMS.values())
        raise NovelSubmissionExportError(f"不支持的投稿平台，可选：{supported}")

    chapters = _collect_chapters(toc)
    if not chapters:
        raise NovelSubmissionExportError("暂无可导出的小说正文")

    safe_project_name = _sanitize_filename_part(project_name, "小说")
    buffer = io.BytesIO()

    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("投稿说明.txt", _build_readme(project_name, platform, chapters))

        if platform.jinjiang_layout:
            archive.writestr("整本正文.txt", _build_jinjiang_full_text(chapters))
            for chapter in chapters:
                archive.writestr(
                    f"逐章拆分/{chapter.filename_stem}.txt",
                    _build_jinjiang_chapter(chapter),
                )
        else:
            archive.writestr("整本正文.txt", _build_plain_full_text(chapters))
            for chapter in chapters:
                archive.writestr(
                    f"逐章拆分/{chapter.filename_stem}.txt",
                    _build_plain_chapter(chapter),
                )

        if platform.material_pack:
            outline_template = _build_outline_template(project_name, chapters)
            full_text = _build_plain_full_text(chapters)
            archive.writestr("大纲模板.txt", outline_template)
            archive.writestr("Word材料/投稿正文.docx", _build_docx_bytes("投稿正文", full_text))
            archive.writestr("Word材料/投稿正文.doc", _build_word_html_bytes("投稿正文", full_text))
            archive.writestr("Word材料/大纲模板.docx", _build_docx_bytes("大纲模板", outline_template))
            archive.writestr("Word材料/大纲模板.doc", _build_word_html_bytes("大纲模板", outline_template))

    return NovelSubmissionPackage(
        filename=f"{safe_project_name}_{platform.bundle_suffix}.zip",
        content=buffer.getvalue(),
        platform=platform,
        chapter_count=len(chapters),
    )
