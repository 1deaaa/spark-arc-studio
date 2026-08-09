from pathlib import Path

from story import novel_parser
from story.file_naming import build_scene_story_filename


def test_novel_visible_text_hides_tagged_field_and_structured_conception() -> None:
    assert novel_parser.clean_novel_visible_text(
        '<conception>隐藏构思</conception>正文里的构思一词。'
    ) == '正文里的构思一词。'
    assert novel_parser.clean_novel_visible_text(
        '"conception": "隐藏构思"\n\n正文。'
    ) == '正文。'
    assert novel_parser.clean_novel_visible_text(
        '{"conception":"隐藏构思","content":"正文。"}'
    ) == '正文。'
    assert novel_parser.clean_novel_visible_text(
        'conception:\n  隐藏构思\n\n正文。'
    ) == '正文。'


def test_aggregate_novel_treats_md_as_novel_format(monkeypatch, tmp_path: Path) -> None:
    stories_path = tmp_path / "stories"
    stories_path.mkdir()
    filename = build_scene_story_filename(1, 1, "相遇", file_format="novel")
    (stories_path / filename).write_text("# 相遇\n\n这是小说正文。", encoding="utf-8")

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
                    "children": [{"title": "相遇"}],
                }
            ]
        },
    )

    result = novel_parser.aggregate_novel("1", "演出测试", export_format="md")

    assert "## 第1章 开端" in result
    assert "这是小说正文。" in result
    assert result.count("这是小说正文。") == 1


def test_aggregate_novel_includes_unplanned_markdown_files(monkeypatch, tmp_path: Path) -> None:
    stories_path = tmp_path / "stories"
    stories_path.mkdir()
    (stories_path / "自由章节.md").write_text("# 自由章节\n\n没有大纲也必须进入演出。", encoding="utf-8")

    monkeypatch.setattr(novel_parser, "get_project_stories_path", lambda *_: str(stories_path))
    monkeypatch.setattr(novel_parser, "_load_project_outline", lambda *_: {"nodes": []})

    result = novel_parser.aggregate_novel("1", "演出测试", export_format="md")

    assert result.startswith("# 演出测试")
    assert "没有大纲也必须进入演出。" in result
    assert result.count("没有大纲也必须进入演出。") == 1
