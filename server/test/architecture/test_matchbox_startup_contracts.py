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
