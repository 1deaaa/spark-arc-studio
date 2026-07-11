from __future__ import annotations

import asyncio
import json

from fastapi.responses import JSONResponse


def test_delete_project_refuses_to_remove_directory_while_background_task_is_alive(
    monkeypatch,
    tmp_path,
) -> None:
    from story import routes_project

    project_path = tmp_path / "demo"
    project_path.mkdir()

    monkeypatch.setattr(routes_project, "get_project_path", lambda user_id, project_name: str(project_path))
    monkeypatch.setattr(
        routes_project,
        "_cancel_project_background_builds",
        lambda user_id, project_name: ["自动写作任务未在等待时间内停止"],
    )
    remove_calls: list[tuple] = []
    monkeypatch.setattr(
        routes_project,
        "_remove_project_directory_with_retries",
        lambda *args: remove_calls.append(args),
    )

    response = asyncio.run(routes_project.delete_project("demo", {"user_id": "7"}))

    assert isinstance(response, JSONResponse)
    assert response.status_code == 409
    assert json.loads(response.body)["details"] == ["自动写作任务未在等待时间内停止"]
    assert remove_calls == []
    assert project_path.is_dir()
