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
