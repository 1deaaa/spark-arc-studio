from __future__ import annotations

import io
import zipfile

import pytest

from story import novel_parser
from story.file_naming import build_scene_story_filename, build_story_filename
from story.novel_submission_export import (
    NovelSubmissionExportError,
    generate_novel_submission_zip,
)


def _sample_toc():
    return [
        {
            "chapter_num": 1,
            "title": "星火初燃",
            "scenes": [
                {
                    "content": "# 场景一\n\n**她**醒来。\n\n> 风声在窗外。",
                }
            ],
        },
        {
            "chapter_num": 2,
            "title": "第2章 旧城",
            "scenes": [
                {
                    "content": "灯光落在石阶上。\n\n`钥匙`仍在掌心。",
                }
            ],
        },
    ]


def _read_zip(package):
    return zipfile.ZipFile(io.BytesIO(package.content))


def test_submission_zip_exports_plain_chapters():
    package = generate_novel_submission_zip("星火计划", _sample_toc(), "qidian")

    assert package.filename == "星火计划_阅文起点投稿包.zip"
    assert package.chapter_count == 2

    with _read_zip(package) as archive:
        names = set(archive.namelist())
        assert "投稿说明.txt" in names
        assert "整本正文.txt" in names
        assert "逐章拆分/001_第1章 星火初燃.txt" in names

        full_text = archive.read("整本正文.txt").decode("utf-8")
        assert "第1章 星火初燃" in full_text
        assert "第2章 旧城" in full_text
        assert "场景一" not in full_text
        assert "**" not in full_text
        assert "`" not in full_text
        assert "她醒来。" in full_text


def test_submission_zip_exports_jinjiang_layout():
    package = generate_novel_submission_zip("星火计划", _sample_toc(), "jinjiang")

    with _read_zip(package) as archive:
        chapter_text = archive.read("逐章拆分/001_第1章 星火初燃.txt").decode("utf-8")
        assert "章节标题：第1章 星火初燃" in chapter_text
        assert "内容提要：" in chapter_text
        assert "章节正文：" in chapter_text


def test_submission_zip_exports_material_template_for_qimao():
    package = generate_novel_submission_zip("星火计划", _sample_toc(), "qimao")

    with _read_zip(package) as archive:
        names = set(archive.namelist())
        assert "Word材料/投稿正文.docx" in names
        assert "Word材料/投稿正文.doc" in names
        assert "Word材料/大纲模板.docx" in names
        assert "Word材料/大纲模板.doc" in names

        outline = archive.read("大纲模板.txt").decode("utf-8")
        assert "作品名：星火计划" in outline
        assert "第1章 星火初燃：" in outline

        docx_bytes = archive.read("Word材料/投稿正文.docx")
        with zipfile.ZipFile(io.BytesIO(docx_bytes)) as docx:
            document_xml = docx.read("word/document.xml").decode("utf-8")
            assert "第1章 星火初燃" in document_xml


def test_submission_zip_rejects_empty_content():
    with pytest.raises(NovelSubmissionExportError, match="暂无可导出的小说正文"):
        generate_novel_submission_zip("空项目", [{"chapter_num": 1, "title": "空章", "scenes": []}], "fanqie")


def test_submission_zip_keeps_manual_and_outlined_novel_sections(monkeypatch, tmp_path):
    stories_path = tmp_path / "stories"
    stories_path.mkdir()
    (stories_path / build_story_filename("第一小节", file_format="novel", order=1, free=True)).write_text(
        "第一小节正文。",
        encoding="utf-8",
    )
    (stories_path / build_story_filename(
        "第二小节",
        file_format="novel",
        chapter_num=1,
        order=1002,
        free=True,
    )).write_text("第二小节正文。", encoding="utf-8")
    (stories_path / build_story_filename("未编排小节", file_format="novel", order=3, free=True)).write_text(
        "未编排小节正文。",
        encoding="utf-8",
    )

    monkeypatch.setattr(novel_parser, "get_project_stories_path", lambda *_: str(stories_path))
    monkeypatch.setattr(
        novel_parser,
        "_load_project_outline",
        lambda *_: {
            "nodes": [
                {
                    "type": "chapter",
                    "chapter": 1,
                    "title": "开端",
                    "children": [{"title": "第一小节"}, {"title": "第二小节"}],
                }
            ]
        },
    )

    toc = novel_parser.get_novel_chapter_list("1", "投稿测试", export_format="md")
    assert [(scene["title"], scene["exists"]) for scene in toc[0]["scenes"]] == [
        ("第一小节", True),
        ("第二小节", True),
    ]

    package = generate_novel_submission_zip("投稿测试", toc, "fanqie")
    with _read_zip(package) as archive:
        names = set(archive.namelist())
        full_text = archive.read("整本正文.txt").decode("utf-8")
        extra_chapter = archive.read("逐章拆分/002_第2章 未编排小节.txt").decode("utf-8")

    assert package.chapter_count == 2
    assert "逐章拆分/002_第2章 未编排小节.txt" in names
    assert "第一小节正文。" in full_text
    assert "第二小节正文。" in full_text
    assert "未编排小节正文。" in full_text
    assert "未编排小节正文。" in extra_chapter
    assert full_text.count("第一小节正文。") == 1
    assert full_text.count("第二小节正文。") == 1
    assert full_text.count("未编排小节正文。") == 1
