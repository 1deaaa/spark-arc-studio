#!/usr/bin/env python
"""
生成新的数据库迁移脚本。

核心原则：autogenerate 永远对比“由已提交迁移链升级出的临时库”和当前
SQLAlchemy Models，绝不直接拿开发机真实运行库当基准。这样本地 DB 即使
被启动期自愈、手工修过、版本号错过，也不会吞掉应该发给下游的 migration。

用法:
    python gen_migration.py
    python gen_migration.py users
    python gen_migration.py "增加手机号字段"
    python gen_migration.py users "add_new_field"
    python gen_migration.py llm "update_model_schema"
"""

from __future__ import annotations

import os
import sys
import tempfile
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory

from core.migration_specs import BASE_DIR, get_db_spec, get_version_dir, iter_db_names
from core.auto_migrate import _describe_schema_drift, _format_schema_drift


VALID_DBS = tuple(iter_db_names())


def _default_message(db_name: str) -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"auto_{db_name}_{ts}"


def _build_config(db_name: str) -> Config:
    cfg = Config(str(BASE_DIR / "alembic.ini"), ini_section=db_name)
    cfg.set_main_option("script_location", str(BASE_DIR / "alembic"))
    cfg.set_main_option("version_locations", str(get_version_dir(db_name)))
    cfg.set_main_option("path_separator", "os")
    cfg.cmd_opts = type(
        "CmdOpts",
        (),
        {
            "x": [f"db={db_name}"],
            "autogenerate": True,
        },
    )()
    return cfg


def _current_script_head(db_name: str) -> str | None:
    version_dir = get_version_dir(db_name)
    if not version_dir.exists() or not any(version_dir.glob("*.py")):
        return None
    script = ScriptDirectory.from_config(_build_config(db_name))
    return script.get_current_head()


@contextmanager
def _alembic_db_override(db_name: str, db_path: Path):
    spec = get_db_spec(db_name)
    previous = os.environ.get(spec.env_key)
    os.environ[spec.env_key] = str(db_path)
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop(spec.env_key, None)
        else:
            os.environ[spec.env_key] = previous


@contextmanager
def _server_cwd():
    original = Path.cwd()
    os.chdir(BASE_DIR)
    try:
        yield
    finally:
        os.chdir(original)


def _upgrade_temp_to_head(db_name: str, db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if _current_script_head(db_name) is None:
        # 首次建库还没有任何 revision；autogenerate 会直接生成 baseline。
        return
    with _alembic_db_override(db_name, db_path), _server_cwd():
        command.upgrade(_build_config(db_name), "head")


def _verify_chain_matches_models(db_name: str, db_path: Path) -> None:
    if db_path.exists():
        db_path.unlink()
    _upgrade_temp_to_head(db_name, db_path)

    drift = _describe_schema_drift(db_name, str(db_path))
    if any(drift.values()):
        raise RuntimeError(
            f"[{db_name}] 迁移链升级出的临时库与当前 Models 不一致: "
            f"{_format_schema_drift(drift)}。"
            "请检查刚生成的 migration 是否遗漏字段，或是否存在旧迁移链中的幽灵结构。"
        )


def run_gen(db_name: str, message: str) -> bool:
    """Generate one branch migration from a clean temporary database."""

    server_dir = BASE_DIR
    version_dir = get_version_dir(db_name)
    version_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n🔄 [Alembic] 正在为 [{db_name}] 构造临时 head 数据库...")
    try:
        with tempfile.TemporaryDirectory(prefix=f"sparkarc_{db_name}_migration_") as temp_dir:
            temp_root = Path(temp_dir)
            autogen_db = temp_root / f"{db_name}_autogen.db"
            verify_db = temp_root / f"{db_name}_verify.db"

            _upgrade_temp_to_head(db_name, autogen_db)

            before_files = {p.resolve() for p in version_dir.glob("*.py")}
            revision_head = "head" if _current_script_head(db_name) else "base"

            print(f"🔄 [Alembic] 正在为 [{db_name}] 检测模型变更...")
            with _alembic_db_override(db_name, autogen_db), _server_cwd():
                command.revision(
                    _build_config(db_name),
                    message=message,
                    autogenerate=True,
                    head=revision_head,
                )

            after_files = {p.resolve() for p in version_dir.glob("*.py")}
            new_files = sorted(after_files - before_files)

            print(f"🧪 [Alembic] 正在验证 [{db_name}] 迁移链可从零升级到当前 Models...")
            _verify_chain_matches_models(db_name, verify_db)

            if new_files:
                rel_files = [str(p.relative_to(server_dir)) for p in new_files]
                print(f"✅ [{db_name}] 已生成迁移: {', '.join(rel_files)}")
            else:
                print(f"ℹ️  [{db_name}] 未检测到模型变更，未生成迁移文件。")
            return True
    except KeyboardInterrupt:
        print("\n⛔ 用户中断")
        return False
    except Exception as exc:
        print(f"❌ [{db_name}] 生成/验证失败: {exc}")
        return False


def main() -> None:
    args = sys.argv[1:]

    target_dbs = list(VALID_DBS)
    message = None

    # 情况1: python gen_migration.py users "msg"
    # 情况2: python gen_migration.py "msg" (全量)
    # 情况3: python gen_migration.py users
    if args:
        if args[0] in VALID_DBS:
            target_dbs = [args[0]]
            if len(args) >= 2:
                message = args[1]
        else:
            target_dbs = list(VALID_DBS)
            message = args[0]

    print("🚀 开始运行迁移生成脚本（临时库隔离模式）...")

    for db_name in target_dbs:
        db_msg = message if message else _default_message(db_name)
        if not run_gen(db_name, db_msg):
            sys.exit(1)

    print("\n✨ 所有操作已完成。")


if __name__ == "__main__":
    main()
