"""
守护对象：
- 平台充值地址是平台级配置，必须进入数据库。
- matchbox_cfg.yaml 的导入、强制重置与导出必须保留充值地址。
- 用户自定义平台与系统平台使用同一套充值地址归一逻辑。
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


def test_matchbox_yaml_platform_recharge_url_roundtrip(tmp_path: Path) -> None:
    code = r"""
from pathlib import Path
import os
import yaml

from llm.agen_matchbox.manager import AIManager
from llm.agen_matchbox.models import LLMPlatform

home = Path(os.environ["AGENT_MATCHBOX_HOME"])
home.mkdir(parents=True, exist_ok=True)
cfg = {
    "充值测试平台": {
        "base_url": "https://api.billing-example.test/v1",
        "recharge_url": "https://billing-example.test/top-up",
        "models": {
            "测试模型": "billing-model",
        },
    },
}
(home / "matchbox_cfg.yaml").write_text(
    yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False),
    encoding="utf-8",
)

manager = AIManager()
manager.ensure_database_schema()
manager.admin_reload_from_yaml()

with manager.Session() as session:
    platform = session.query(LLMPlatform).filter_by(name="充值测试平台").one()
    print(f"db_recharge_url={platform.recharge_url}")

exported = manager.admin_build_export_data()
print(f"export_recharge_url={exported['充值测试平台']['recharge_url']}")
"""

    output = _run_probe(code, tmp_path)

    assert "db_recharge_url=https://billing-example.test/top-up" in output
    assert "export_recharge_url=https://billing-example.test/top-up" in output


def test_matchbox_custom_platform_recharge_url_updates_and_clears(tmp_path: Path) -> None:
    code = r"""
from llm.agen_matchbox.manager import AIManager
from llm.agen_matchbox.models import LLMPlatform

manager = AIManager()
manager.ensure_database_schema()
platform = manager.add_platform(
    "用户充值平台",
    "https://api.custom-billing.test/v1",
    user_id="user-1",
    recharge_url="https://custom-billing.test/pay",
)

with manager.Session() as session:
    stored = session.query(LLMPlatform).filter_by(id=platform.id).one()
    print(f"created_recharge_url={stored.recharge_url}")

manager.update_platform_details(
    "user-1",
    platform.id,
    "用户充值平台",
    "https://api.custom-billing.test/v1",
    recharge_url="",
    update_recharge_url=True,
)

with manager.Session() as session:
    stored = session.query(LLMPlatform).filter_by(id=platform.id).one()
    print(f"cleared_recharge_url={stored.recharge_url}")
"""

    output = _run_probe(code, tmp_path)

    assert "created_recharge_url=https://custom-billing.test/pay" in output
    assert "cleared_recharge_url=None" in output
