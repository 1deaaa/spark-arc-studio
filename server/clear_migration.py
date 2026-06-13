#!/usr/bin/env python
"""
清理迁移历史并以当前模型状态作为新的初始基线。

流程：
1) 强制将数据库升级到当前迁移 head（确保结构一致）。
2) 备份/删除所有迁移脚本。
3) 使用空数据库自动生成“基线迁移”（包含完整建表）。
4) 将真实数据库 stamp 到新的 head（不重复执行建表）。
5) 自动再执行一次常规 autogenerate，补齐 reset 后仍可能存在的差异。

警告：该操作会清空迁移历史，可能影响回滚能力。
如果第 1 步无法成功，则必须先修复迁移链，不能继续 reset，
否则只会“保留数据并强行标记为 head”，并不能保证真实结构已同步。
"""
import os
import sys
import shutil
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from alembic import command
from alembic.config import Config

from core.migration_specs import (
    BASE_DIR,
    get_db_path,
    get_db_spec,
    get_version_dir,
    iter_db_names,
    load_metadata,
)

VALID_DBS = tuple(iter_db_names())


def _build_config(db_name: str, *, autogenerate: bool = False) -> Config:
    cfg = Config(str(BASE_DIR / "alembic.ini"), ini_section=db_name)
    cfg.set_main_option("script_location", str(BASE_DIR / "alembic"))
    cfg.set_main_option("version_locations", str(get_version_dir(db_name)))
    cfg.set_main_option("path_separator", "os")
    cfg.cmd_opts = type(
        "CmdOpts",
        (),
        {
            "x": [f"db={db_name}"],
            "autogenerate": autogenerate,
        },
    )()
    return cfg


@contextmanager
def _alembic_db_override(db_name: str, db_path: str | os.PathLike[str]):
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


def _confirm(force: bool) -> None:
    if force:
        return
    print("\n⚠️  This operation will clear all migration history, keeping only the new baseline migration.")
    print("⚠️  It is recommended to back up your database files and migration scripts first.\n")
    text = input("Type YES to continue: ").strip()
    if text != "YES":
        raise SystemExit("Cancelled.")


def _backup_or_delete(version_dir: str, backup_root: str, keep_backup: bool) -> None:
    if not os.path.isdir(version_dir):
        return
    os.makedirs(backup_root, exist_ok=True)
    for name in os.listdir(version_dir):
        if not name.endswith(".py"):
            continue
        src = os.path.join(version_dir, name)
        if keep_backup:
            shutil.move(src, os.path.join(backup_root, name))
        else:
            os.remove(src)


def _upgrade_to_head(server_dir: str, db_name: str) -> None:
    try:
        with _server_cwd():
            command.upgrade(_build_config(db_name), "head")
        return True
    except Exception as exc:
        print(f"   ❌ [{db_name}] Upgrade to head failed: {exc}")
        return False


def _generate_baseline(server_dir: str, db_name: str, temp_db: str, message: str) -> None:
    with _alembic_db_override(db_name, temp_db), _server_cwd():
        command.revision(
            _build_config(db_name, autogenerate=True),
            message=message,
            autogenerate=True,
            head="base",
        )


def _stamp_head(server_dir: str, db_name: str) -> None:
    with _server_cwd():
        command.stamp(_build_config(db_name), "head")


def _clear_version_table(db_name: str) -> None:
    import sqlite3

    db_path = str(get_db_path(db_name))
    if not os.path.exists(db_path):
        return
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("DELETE FROM alembic_version")
        conn.commit()
        conn.close()
    except Exception:
        # 如果表不存在或被锁，留给 stamp 处理
        pass


def _clean_ghost_structure(db_name: str) -> None:
    """
    清理 DB 中存在但 Model 未定义的幽灵列和幽灵表。

    clear_migration 的 stamp 只是把版本号标记为 head，
    但不会改变 DB 的物理结构。如果 DB 中残留了旧迁移留下的幽灵列/表，
    后续 gen_migration 基于本地 DB 物理状态生成的迁移会包含 drop 指令，
    导致云端（从链构建，无幽灵结构）升级失败。

    因此必须在 stamp 后主动清理，保证 DB 物理结构与 Model 完全一致。
    """
    from sqlalchemy import create_engine, inspect as sa_inspect, text
    from sqlalchemy.pool import NullPool

    db_path = str(get_db_path(db_name))
    if not db_path or not os.path.exists(db_path):
        return

    # 加载目标 Model 元数据
    try:
        target_metadata = load_metadata(db_name)
    except ImportError:
        print(f"   ⚠️ [{db_name}] Unable to load model metadata, skipping ghost cleanup.")
        return

    normalized_path = db_path.replace("\\", "/")
    db_url = f"sqlite:///{normalized_path}"
    engine = create_engine(db_url, poolclass=NullPool)

    def _is_internal(name: str) -> bool:
        return (
            name == "alembic_version"
            or name.startswith("sqlite_")
            or name.startswith("_alembic_tmp_")
        )

    try:
        inspector = sa_inspect(engine)
        existing_tables = set(inspector.get_table_names())
        model_table_names = {
            name for name in target_metadata.tables
            if not _is_internal(name)
        }

        # 1) 清理幽灵列
        ghost_cols = []
        for table_name, table in target_metadata.tables.items():
            if _is_internal(table_name) or table_name not in existing_tables:
                continue
            existing_col_names = {c["name"] for c in inspector.get_columns(table_name)}
            model_col_names = {col.name for col in table.columns}
            extra_cols = existing_col_names - model_col_names
            if extra_cols:
                ghost_cols.extend(f"{table_name}.{c}" for c in extra_cols)
                # SQLite 3.35+ 支持 ALTER TABLE DROP COLUMN
                # 使用原始 SQL 以避免 Alembic Operations 的复杂依赖
                with engine.connect() as conn:
                    for col_name in extra_cols:
                        conn.execute(text(f'ALTER TABLE "{table_name}" DROP COLUMN "{col_name}"'))
                    conn.commit()
                print(f"   🗑️ [{db_name}] Dropping ghost columns: {', '.join(f'{table_name}.{c}' for c in extra_cols)}")

        # 2) 清理幽灵表
        ghost_tables = existing_tables - model_table_names - {"alembic_version", "sqlite_sequence"}
        ghost_tables = {t for t in ghost_tables if not t.startswith("_alembic_tmp_")}
        if ghost_tables:
            with engine.connect() as conn:
                for table_name in ghost_tables:
                    conn.execute(text(f'DROP TABLE IF EXISTS "{table_name}"'))
                conn.commit()
            print(f"   🗑️ [{db_name}] Dropping ghost tables: {', '.join(ghost_tables)}")

        if not ghost_cols and not ghost_tables:
            print(f"   ✅ [{db_name}] DB physical structure fully matches model, no ghost structures.")

    except Exception as e:
        print(f"   ⚠️ [{db_name}] Ghost cleanup encountered an error (non-fatal): {e}")
    finally:
        engine.dispose()


def _post_clear_autogen(ts: str) -> None:
    """
    clear 完成后，自动再执行一次隔离 autogenerate 验证。

    新版 gen_migration 不再用真实运行库作为对比基准，而是用临时库从迁移链
    升级到 head 后再比对 Models。因此这里主要用于确认新 baseline 能独立
    表达当前模型结构。
    """
    # 清理真实 DB 幽灵结构，避免 reset 后本地运行库长期携带陈旧列/表。
    print("\n🧹 Cleaning ghost structures (columns/tables in DB not defined in Model)...")
    for db in VALID_DBS:
        _clean_ghost_structure(db)

    from gen_migration import run_gen

    print("\n🧪 Running post-reset automatic migration check...")
    for db in VALID_DBS:
        message = f"post_clear_{db}_{ts}"
        if not run_gen(db, message):
            raise SystemExit(f"❌ [{db}] Post-reset automatic migration generation failed.")


def main():
    args = sys.argv[1:]
    force = "--yes" in args
    keep_backup = "--no-backup" not in args

    server_dir = str(BASE_DIR)
    versions_root = os.path.join(server_dir, "alembic", "versions")

    _confirm(force)

    print("\n🔄 Syncing databases to latest migration...")
    failed_upgrades = []
    for db in VALID_DBS:
        if not _upgrade_to_head(server_dir, db):
            failed_upgrades.append(db)

    if failed_upgrades:
        failed_text = ", ".join(failed_upgrades)
        raise SystemExit(
            f"❌ The following databases could not be upgraded to current head: {failed_text}. "
            "To prevent incorrect stamping before structure sync, please fix the corresponding migrations first, then run clear_migration."
        )

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_root = os.path.join(server_dir, ".backup_migrations", ts)

    print("🧹 Clearing migration history...")
    for db in VALID_DBS:
        version_dir = os.path.join(versions_root, db)
        backup_dir = os.path.join(backup_root, db)
        _backup_or_delete(version_dir, backup_dir, keep_backup)

    temp_root = os.path.join(server_dir, ".migration_reset_tmp")
    os.makedirs(temp_root, exist_ok=True)

    print("🧱 Generating new baseline migration...")
    for db in VALID_DBS:
        temp_db = os.path.join(temp_root, f"{db}_empty_{ts}.db")
        if os.path.exists(temp_db):
            os.remove(temp_db)
        message = f"baseline_{db}_{ts}"
        _generate_baseline(server_dir, db, temp_db, message)
        if os.path.exists(temp_db):
            os.remove(temp_db)

    print("🏷️  Stamping databases to new baseline...\n")
    for db in VALID_DBS:
        _clear_version_table(db)
        _stamp_head(server_dir, db)

    _post_clear_autogen(ts)

    print("✅ Cleanup complete. New migration baseline generated, and a post-reset migration check has been run automatically.")
    if keep_backup:
        print(f"📦 Old migrations backed up to: {backup_root}")


if __name__ == "__main__":
    main()
