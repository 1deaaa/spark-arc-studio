"""守护项目上下文服务的层次边界与旧入口兼容性。"""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys

from agents import project_context
from agents.routes import context_builder


SERVER_ROOT = Path(__file__).resolve().parents[2]


def test_project_context_import_does_not_initialize_route_package() -> None:
    """领域上下文服务不得通过包初始化间接加载全部 HTTP 路由。"""
    code = (
        "import sys; import agents.project_context; "
        "raise SystemExit(1 if 'agents.routes' in sys.modules else 0)"
    )

    completed = subprocess.run(
        [sys.executable, "-c", code],
        cwd=SERVER_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr or completed.stdout


def test_auto_write_services_import_without_initializing_route_package() -> None:
    code = (
        "import sys; import agents.auto_write_state; import agents.auto_write_service; "
        "raise SystemExit(1 if 'agents.routes' in sys.modules else 0)"
    )

    completed = subprocess.run(
        [sys.executable, "-c", code],
        cwd=SERVER_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr or completed.stdout


def test_route_context_builder_is_only_a_compatibility_export() -> None:
    """旧路径必须暴露同一实现，不能形成第二份上下文逻辑。"""
    public_names = (
        "build_scene_context",
        "build_scriptwriter_context",
        "build_scriptwriter_handoff_context",
        "build_story_tags_hint",
        "format_outline_scene_contract",
        "get_current_beat",
        "load_all_roles",
        "load_beats_data",
        "load_character_bundle",
        "load_full_outline",
        "load_narrative_memory",
        "load_outline_data",
        "load_project_context_bundle",
        "load_synopsis_data",
        "load_worldview",
        "resolve_outline_scene_contract",
        "resolve_outline_scene_contract_for_task",
    )

    for name in public_names:
        assert getattr(context_builder, name) is getattr(project_context, name)
