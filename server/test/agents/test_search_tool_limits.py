from __future__ import annotations

from agents.tools.search import search_project
from core.request_context import current_project_name, current_user_id


def test_regex_project_search_stops_at_requested_result_limit(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("core.utils.USERDATA_ROOT", str(tmp_path))
    project_path = tmp_path / "uid_77" / "projects" / "demo"
    story_path = project_path / "stories" / "一 · 开端" / "1.1.arc"
    story_path.parent.mkdir(parents=True)
    story_path.write_text("\n".join(f"第{i}行 命中" for i in range(20)), encoding="utf-8")

    user_token = current_user_id.set("77")
    project_token = current_project_name.set("demo")
    try:
        result = search_project.invoke({
            "pattern": "命中",
            "max_results": 3,
        })
    finally:
        current_project_name.reset(project_token)
        current_user_id.reset(user_token)

    assert "返回前 3 处匹配" in result
    assert "[2]" in result
    assert "[3]" not in result


def test_regex_search_scope_attachment_returns_window_pointer(monkeypatch, tmp_path) -> None:
    """scope=['attachment'] 只搜附件，命中带 chunk_index 回跳指针，不灌全文。"""
    monkeypatch.setattr("core.utils.USERDATA_ROOT", str(tmp_path))
    project_path = tmp_path / "uid_78" / "projects" / "demo"
    project_path.mkdir(parents=True)

    from agents.attachment import save_attachment

    save_attachment("78", "demo", "参考.txt", "txt", "第一窗。目标关键词在第二窗。", ["第一窗。", "目标关键词在第二窗。"], 10)

    user_token = current_user_id.set("78")
    project_token = current_project_name.set("demo")
    try:
        result = search_project.invoke({
            "pattern": "目标关键词",
            "scope": ["attachment"],
        })
    finally:
        current_project_name.reset(project_token)
        current_user_id.reset(user_token)

    assert "[附件]" in result
    assert "chunk_index=1" in result
    assert "read_attachment_chunk" in result


def test_regex_search_default_scope_excludes_attachments(monkeypatch, tmp_path) -> None:
    """不传 scope 时附件默认不进项目正文扫描，保持旧行为。"""
    monkeypatch.setattr("core.utils.USERDATA_ROOT", str(tmp_path))
    project_path = tmp_path / "uid_79" / "projects" / "demo"
    project_path.mkdir(parents=True)

    from agents.attachment import save_attachment

    save_attachment("79", "demo", "参考.txt", "txt", "只有附件里有特殊词XYZ", ["只有附件里有特殊词XYZ"], 5)

    user_token = current_user_id.set("79")
    project_token = current_project_name.set("demo")
    try:
        result = search_project.invoke({"pattern": "特殊词XYZ"})
    finally:
        current_project_name.reset(project_token)
        current_user_id.reset(user_token)

    assert "未找到匹配" in result
