"""
守护对象：
- Matchbox 启动期只初始化数据库与配置，不提前加载 LLM SDK 运行时重依赖。
- 后台预热可以主动加载运行时，但轻初始化路径必须保持快速。

本测试禁止：
- 调用真实 LLM
- 连接真实外部服务
- 读写真实 Matchbox 运行库
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


SERVER_ROOT = Path(__file__).resolve().parents[2]


def _run_probe(code: str, tmp_path: Path) -> str:
    env = os.environ.copy()
    env["AGENT_MATCHBOX_HOME"] = str(tmp_path / "matchbox-home")

    completed = subprocess.run(
        [sys.executable, "-X", "utf8", "-c", code],
        cwd=SERVER_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )
    return completed.stdout


def _run_standalone_probe(code: str, tmp_path: Path) -> str:
    """只暴露 Matchbox 包路径，验证它不依赖 SparkArc 的 ``core``。"""
    env = os.environ.copy()
    env.pop("AGENT_MATCHBOX_DISABLED", None)
    env["PYTHONPATH"] = str(SERVER_ROOT / "llm")
    env["AGENT_MATCHBOX_HOME"] = str(tmp_path / "standalone-matchbox-home")

    completed = subprocess.run(
        [sys.executable, "-X", "utf8", "-c", code],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )
    return completed.stdout


def test_matchbox_manager_import_keeps_llm_runtime_lazy(tmp_path: Path) -> None:
    code = """
import importlib
import sys

importlib.import_module("llm.agen_matchbox.manager")

for name in (
    "llm.agen_matchbox.gateway",
    "llm.agen_matchbox.tracked_model",
    "langchain_openai",
):
    print(f"{name}={name in sys.modules}")
"""

    output = _run_probe(code, tmp_path)

    assert "llm.agen_matchbox.gateway=False" in output
    assert "llm.agen_matchbox.tracked_model=False" in output
    assert "langchain_openai=False" in output


def test_initialize_matchbox_defaults_keeps_llm_runtime_lazy(tmp_path: Path) -> None:
    code = """
import sys
import os
from pathlib import Path

from core.auto_migrate import BASE_DIR, run_db_upgrade
from llm.agen_matchbox import initialize_matchbox

Path(os.environ["AGENT_MATCHBOX_HOME"]).mkdir(parents=True, exist_ok=True)
run_db_upgrade("llm", BASE_DIR)
initialize_matchbox(ensure_defaults=True)

for name in (
    "llm.agen_matchbox.gateway",
    "llm.agen_matchbox.tracked_model",
    "langchain_openai",
):
    print(f"{name}={name in sys.modules}")
"""

    output = _run_probe(code, tmp_path)

    assert "llm.agen_matchbox.gateway=False" in output
    assert "llm.agen_matchbox.tracked_model=False" in output
    assert "langchain_openai=False" in output


def test_matchbox_can_initialize_without_sparkarc_core(tmp_path: Path) -> None:
    code = """
import sys

from agen_matchbox import initialize_matchbox

manager = initialize_matchbox(ensure_defaults=True)
connection = manager.engine.connect()
try:
    tables = set(manager.engine.dialect.get_table_names(connection))
finally:
    connection.close()
    manager.engine.dispose()

print(f"manager={type(manager).__name__}")
print(f"has_llm_platforms={'llm_platforms' in tables}")
print(f"core_loaded={'core' in sys.modules}")
"""

    output = _run_standalone_probe(code, tmp_path)

    assert "manager=AIManager" in output
    assert "has_llm_platforms=True" in output
    assert "core_loaded=False" in output


def test_matchbox_hf_mirror_does_not_import_sparkarc_core(tmp_path: Path) -> None:
    code = """
import sys

from agen_matchbox import hf_mirror

print(f"candidates={len(hf_mirror.get_hf_candidates(probe=False))}")
print(f"core_loaded={'core' in sys.modules}")
"""

    output = _run_standalone_probe(code, tmp_path)

    assert "candidates=2" in output
    assert "core_loaded=False" in output


def test_matchbox_gui_entry_can_import_without_sparkarc_core(tmp_path: Path) -> None:
    code = """
import sys

from agen_matchbox.matchbox_cfg_gui import LLMConfigGUI

print(f"gui={LLMConfigGUI.__name__}")
print(f"core_loaded={'core' in sys.modules}")
print(f"host_adapter_loaded={'llm.matchbox_adapter' in sys.modules}")
"""

    output = _run_standalone_probe(code, tmp_path)

    assert "gui=LLMConfigGUI" in output
    assert "core_loaded=False" in output
    assert "host_adapter_loaded=False" in output
