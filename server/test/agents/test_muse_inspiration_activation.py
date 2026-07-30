"""Muse 灵感写入与项目单当前灵感契约测试。"""

from agents.tools.muse import rewrite_inspiration
from core.request_context import current_inspiration_id, current_project_name, current_user_id
from mcp_server.spark_inspiration import logic as inspiration_logic


def _rewrite(content: str) -> str:
    return rewrite_inspiration.invoke({"overwrite_content": content})


def test_rewrite_creates_and_activates_inspiration_without_breaking_cross_project_reuse(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setattr(inspiration_logic, "USERDATA_ROOT", str(tmp_path))
    user_token = current_user_id.set("user-1")
    project_token = current_project_name.set("项目甲")
    inspiration_token = current_inspiration_id.set(None)
    try:
        first_result = _rewrite("第一条灵感")
        first_items = inspiration_logic.get_inspirations_for_project("user-1", "项目甲")
        assert "设为项目「项目甲」的当前灵感" in first_result
        assert len(first_items) == 1
        first_id = first_items[0]["id"]

        second_result = _rewrite("第二条灵感")
        second_items = inspiration_logic.get_inspirations_for_project("user-1", "项目甲")
        assert "设为项目「项目甲」的当前灵感" in second_result
        assert len(second_items) == 1
        second_id = second_items[0]["id"]
        assert second_id != first_id

        current_project_name.set("项目乙")
        current_inspiration_id.set(second_id)
        overwrite_result = _rewrite("第二条灵感修订版")
        assert "设为项目「项目乙」的当前灵感" in overwrite_result

        all_items = inspiration_logic.get_all_inspirations("user-1")
        first = next(item for item in all_items if item["id"] == first_id)
        second = next(item for item in all_items if item["id"] == second_id)
        assert first["project_links"] == []
        assert second["project_links"] == ["项目甲", "项目乙"]
        assert second["content"] == "第二条灵感修订版"
        missing = inspiration_logic.activate_inspiration_for_project("user-1", "missing", "项目甲")
        assert missing["success"] is False
    finally:
        current_inspiration_id.reset(inspiration_token)
        current_project_name.reset(project_token)
        current_user_id.reset(user_token)


def test_rewrite_without_project_keeps_new_inspiration_as_draft(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(inspiration_logic, "USERDATA_ROOT", str(tmp_path))
    user_token = current_user_id.set("user-2")
    project_token = current_project_name.set(None)
    inspiration_token = current_inspiration_id.set(None)
    try:
        result = _rewrite("未归档灵感")
        drafts = inspiration_logic.get_all_inspirations("user-2", scope="drafts")
        assert "新灵感草稿" in result
        assert len(drafts) == 1
        assert drafts[0]["project_links"] == []
    finally:
        current_inspiration_id.reset(inspiration_token)
        current_project_name.reset(project_token)
        current_user_id.reset(user_token)
