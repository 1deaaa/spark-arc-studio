import asyncio
from types import SimpleNamespace

from agents.agent_style import utils as style_utils
from agents.routes.style import get_style_profile, list_styles, set_default_style


class _JsonRequest:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    async def json(self) -> dict:
        return self._payload


def test_new_user_starts_without_any_style(monkeypatch, tmp_path) -> None:
    userdata_root = str(tmp_path / "userdata")
    monkeypatch.setattr("core.utils.USERDATA_ROOT", userdata_root)
    monkeypatch.setattr(style_utils, "USERDATA_ROOT", userdata_root)

    user_id = "new-style-user"
    result = asyncio.run(list_styles(user={"user_id": user_id}))

    assert result == {
        "success": True,
        "styles": [],
        "default_style_name": "",
    }
    user_root = tmp_path / "userdata" / f"uid_{user_id}"
    assert list((user_root / "styles").glob("*.md")) == []
    assert not (user_root / "default_style.json").exists()


def test_profile_metadata_separates_project_binding_from_default(
    monkeypatch, tmp_path
) -> None:
    userdata_root = str(tmp_path / "userdata")
    monkeypatch.setattr("core.utils.USERDATA_ROOT", userdata_root)
    monkeypatch.setattr(style_utils, "USERDATA_ROOT", userdata_root)

    user_id = "style-user"
    project_name = "demo"
    style_utils.save_style_profile_to_file("项目风格", "## 项目风格", user_id=user_id)
    style_utils.save_style_profile_to_file("默认风格", "## 默认风格", user_id=user_id)
    style_utils.save_user_default_style_binding(user_id, "默认风格")

    request = SimpleNamespace(query_params={"projectName": project_name})
    default_result = asyncio.run(
        get_style_profile(request, user={"user_id": user_id})
    )
    assert default_result["style_name"] == "默认风格"
    assert default_result["project_style_name"] is None

    style_utils.save_project_style_binding(user_id, project_name, "项目风格")
    project_result = asyncio.run(
        get_style_profile(request, user={"user_id": user_id})
    )
    assert project_result["style_name"] == "项目风格"
    assert project_result["project_style_name"] == "项目风格"


def test_clear_default_style_returns_to_no_style_tendency(monkeypatch, tmp_path) -> None:
    userdata_root = str(tmp_path / "userdata")
    monkeypatch.setattr("core.utils.USERDATA_ROOT", userdata_root)
    monkeypatch.setattr(style_utils, "USERDATA_ROOT", userdata_root)

    user_id = "style-user"
    project_name = "demo"
    style_utils.save_style_profile_to_file("默认风格", "## 默认风格", user_id=user_id)
    style_utils.save_user_default_style_binding(user_id, "默认风格")

    result = asyncio.run(
        set_default_style(_JsonRequest({"styleName": None}), user={"user_id": user_id})
    )

    assert result == {"success": True, "default_style_name": ""}
    assert style_utils.load_user_default_style_binding(user_id) is None
    assert style_utils.resolve_project_style_author_id(user_id, project_name) is None
