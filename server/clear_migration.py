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
import subprocess
from datetime import datetime

VALID_DBS = ("users", "llm")

ENV_DB_KEYS = {
    "users": "SPARKARC_ALEMBIC_USERS_DB",
    "llm": "SPARKARC_ALEMBIC_LLM_DB",
}

DB_PATHS = {
    "users": os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "users.db"),
    "llm": os.path.join(os.path.dirname(os.path.abspath(__file__)), "llm", "agen_matchbox", "llm_config.db"),
}


def _run(cmd, cwd, env, allow_fail: bool = False) -> bool:
    result = subprocess.run(cmd, cwd=cwd, env=env)
    if result.returncode != 0 and not allow_fail:
        raise RuntimeError(f"Command failed: {' '.join(cmd)}")
    return result.returncode == 0


def _confirm(force: bool) -> None:
    if force:
        return
    print("\n⚠️  该操作会清空全部迁移历史，仅保留新的基线迁移。")
    print("⚠️  建议先备份数据库文件与迁移脚本。\n")
    text = input("输入 YES 继续: ").strip()
    if text != "YES":
        raise SystemExit("已取消。")


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
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    cmd = [
        sys.executable,
        "-m",
        "alembic",
        "-n",
        db_name,
        "-x",
        f"db={db_name}",
        "upgrade",
        "head",
    ]
    return _run(cmd, cwd=server_dir, env=env, allow_fail=True)


def _generate_baseline(server_dir: str, db_name: str, temp_db: str, message: str) -> None:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env[ENV_DB_KEYS[db_name]] = temp_db
    cmd = [
        sys.executable,
        "-m",
        "alembic",
        "-n",
        db_name,
        "-x",
        f"db={db_name}",
        "revision",
        "--autogenerate",
        "-m",
        message,
        "--head",
        "base",
    ]
    _run(cmd, cwd=server_dir, env=env)


def _stamp_head(server_dir: str, db_name: str) -> None:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env.pop(ENV_DB_KEYS[db_name], None)
    cmd = [
        sys.executable,
        "-m",
        "alembic",
        "-n",
        db_name,
        "-x",
        f"db={db_name}",
        "stamp",
        "head",
    ]
    _run(cmd, cwd=server_dir, env=env)


def _clear_version_table(db_name: str) -> None:
    import sqlite3

    db_path = DB_PATHS[db_name]
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

    db_path = DB_PATHS[db_name]
    if not db_path or not os.path.exists(db_path):
        return

    # 加载目标 Model 元数据
    if db_name == "users":
        from core.models import UserInfo
        target_metadata = UserInfo.metadata
    elif db_name == "llm":
        try:
            from llm.agen_matchbox.models import Base as LLMBase
            target_metadata = LLMBase.metadata
        except ImportError:
            print(f"   ⚠️ [{db_name}] 无法加载模型元数据，跳过幽灵清理。")
            return
    else:
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
                print(f"   🗑️ [{db_name}] 清理幽灵列: {', '.join(f'{table_name}.{c}' for c in extra_cols)}")

        # 2) 清理幽灵表
        ghost_tables = existing_tables - model_table_names - {"alembic_version", "sqlite_sequence"}
        ghost_tables = {t for t in ghost_tables if not t.startswith("_alembic_tmp_")}
        if ghost_tables:
            with engine.connect() as conn:
                for table_name in ghost_tables:
                    conn.execute(text(f'DROP TABLE IF EXISTS "{table_name}"'))
                conn.commit()
            print(f"   🗑️ [{db_name}] 清理幽灵表: {', '.join(ghost_tables)}")

        if not ghost_cols and not ghost_tables:
            print(f"   ✅ [{db_name}] DB 物理结构与 Model 完全一致，无幽灵结构。")

    except Exception as e:
        print(f"   ⚠️ [{db_name}] 幽灵清理异常（非致命）: {e}")
    finally:
        engine.dispose()


def _post_clear_autogen(ts: str) -> None:
    """
    clear 完成后，自动再执行一次常规 autogenerate。

    这样可以把"空库生成 baseline"与"真实库对比模型"的两个阶段串起来：
    - 如果 reset 后已完全一致，则 env.py 会阻止生成空迁移；
    - 如果仍有差异，则会自动补出一份普通迁移，无需手工再跑 gen。
    """
    # 先清理幽灵结构，确保 autogenerate 基于干净的物理状态
    print("\n🧹 正在清理幽灵结构（DB 中存在但 Model 未定义的列/表）...")
    for db in VALID_DBS:
        _clean_ghost_structure(db)

    from gen_migration import run_gen

    print("\n🧪 正在执行 reset 后的自动迁移检测...")
    for db in VALID_DBS:
        message = f"post_clear_{db}_{ts}"
        if not run_gen(db, message):
            raise SystemExit(f"❌ [{db}] reset 后自动生成迁移失败。")


def main():
    args = sys.argv[1:]
    force = "--yes" in args
    keep_backup = "--no-backup" not in args

    server_dir = os.path.dirname(os.path.abspath(__file__))
    versions_root = os.path.join(server_dir, "alembic", "versions")

    _confirm(force)

    print("\n🔄 正在同步数据库到最新迁移...")
    failed_upgrades = []
    for db in VALID_DBS:
        if not _upgrade_to_head(server_dir, db):
            failed_upgrades.append(db)

    if failed_upgrades:
        failed_text = ", ".join(failed_upgrades)
        raise SystemExit(
            f"❌ 以下数据库无法先升级到当前 head：{failed_text}。"
            "为避免在结构未同步时被错误 stamp，请先修复对应迁移，再执行 clear_migration。"
        )

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_root = os.path.join(server_dir, ".backup_migrations", ts)

    print("🧹 正在清理迁移历史...")
    for db in VALID_DBS:
        version_dir = os.path.join(versions_root, db)
        backup_dir = os.path.join(backup_root, db)
        _backup_or_delete(version_dir, backup_dir, keep_backup)

    temp_root = os.path.join(server_dir, ".migration_reset_tmp")
    os.makedirs(temp_root, exist_ok=True)

    print("🧱 正在生成新的基线迁移...")
    for db in VALID_DBS:
        temp_db = os.path.join(temp_root, f"{db}_empty_{ts}.db")
        if os.path.exists(temp_db):
            os.remove(temp_db)
        message = f"baseline_{db}_{ts}"
        _generate_baseline(server_dir, db, temp_db, message)
        if os.path.exists(temp_db):
            os.remove(temp_db)

    print("🏷️  正在标记数据库为新基线...\n")
    for db in VALID_DBS:
        _clear_version_table(db)
        _stamp_head(server_dir, db)

    _post_clear_autogen(ts)

    print("✅ 清理完成。新的迁移基线已生成，并已自动执行一次常规迁移检测。")
    if keep_backup:
        print(f"📦 旧迁移已备份到: {backup_root}")


if __name__ == "__main__":
    main()
