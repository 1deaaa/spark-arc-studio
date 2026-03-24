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
    "llm": os.path.join(os.path.dirname(os.path.abspath(__file__)), "llm", "llm_mgr", "llm_config.db"),
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


def _post_clear_autogen(ts: str) -> None:
    """
    clear 完成后，自动再执行一次常规 autogenerate。

    这样可以把“空库生成 baseline”与“真实库对比模型”的两个阶段串起来：
    - 如果 reset 后已完全一致，则 env.py 会阻止生成空迁移；
    - 如果仍有差异，则会自动补出一份普通迁移，无需手工再跑 gen。
    """
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
