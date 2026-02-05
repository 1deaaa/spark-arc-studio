#!/usr/bin/env python
"""
生成新的数据库迁移脚本

用法:
    python gen_migration.py
    python gen_migration.py users
    python gen_migration.py "增加手机号字段"
    python gen_migration.py users "add_new_field"
    python gen_migration.py llm "update_model_schema"

功能：
    - 调用 Alembic 自动生成迁移脚本
    - 支持交互式检测【重命名】操作（不再需要手动修改文件）
    - 自动拦截【删除列/表】等危险操作并请求确认
    - 默认对所有数据库执行自动检测，仅在有变更时生成迁移
"""
import sys
import os
import subprocess
import sqlite3
import re
from datetime import datetime

VALID_DBS = ("users", "llm")
DB_PATHS = {
    "users": os.path.join("data", "users.db"),
    "llm": os.path.join("llm", "llm_mgr", "llm_config.db"),
}


def _snapshot_versions(versions_dir: str):
    if not os.path.isdir(versions_dir):
        return set()
    return {f for f in os.listdir(versions_dir) if f.endswith(".py")}


def _has_branch_revisions(versions_dir: str, db: str) -> bool:
    if not os.path.isdir(versions_dir):
        return False
    for name in os.listdir(versions_dir):
        if not name.endswith(".py"):
            continue
        file_path = os.path.join(versions_dir, name)
        _, _, label = _parse_revision_info(file_path)
        if label == db:
            return True
    return False


def _is_empty_revision(file_path: str) -> bool:
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        parts = content.split("def downgrade", 1)
        upgrade_section = parts[0]
        if "pass" in upgrade_section and "op." not in upgrade_section and "batch_op" not in upgrade_section:
            return True
    except Exception:
        return False
    return False


def _parse_revision_info(file_path: str):
    revision_id = None
    down_revs = []
    branch_label = None
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        rev_match = re.search(r"revision\s*:\s*[^=]*=\s*'([^']+)'", content)
        if rev_match:
            revision_id = rev_match.group(1)
        down_match = re.search(r"down_revision\s*:\s*[^=]*=\s*([^\n]+)", content)
        if down_match:
            raw = down_match.group(1)
            down_revs = re.findall(r"'([^']+)'", raw)
        label_match = re.search(r"branch_labels\s*:\s*[^=]*=\s*([^\n]+)", content)
        if label_match:
            label_raw = label_match.group(1)
            if "'users'" in label_raw:
                branch_label = "users"
            elif "'llm'" in label_raw:
                branch_label = "llm"
    except Exception:
        return None, [], None
    return revision_id, down_revs, branch_label


def _with_branch_filtered_versions(versions_dir: str, db: str, func):
    temp_dir = os.path.join(versions_dir, ".tmp_other")
    os.makedirs(temp_dir, exist_ok=True)
    moved = []

    revisions = {}
    children = {}
    roots = []

    for name in os.listdir(versions_dir):
        if not name.endswith(".py"):
            continue
        file_path = os.path.join(versions_dir, name)
        rev_id, down_revs, label = _parse_revision_info(file_path)
        if not rev_id:
            continue
        revisions[rev_id] = {"file": file_path, "label": label, "down": down_revs}
        if label == db:
            roots.append(rev_id)
        for down in down_revs:
            children.setdefault(down, []).append(rev_id)

    keep = set()
    stack = list(roots)
    while stack:
        cur = stack.pop()
        if cur in keep:
            continue
        keep.add(cur)
        for nxt in children.get(cur, []):
            stack.append(nxt)

    has_child = set()
    for parent, kids in children.items():
        if parent in keep and any(k in keep for k in kids):
            has_child.add(parent)
    heads = [rev for rev in keep if rev not in has_child]

    for rev_id, info in revisions.items():
        file_path = info["file"]
        if rev_id not in keep:
            name = os.path.basename(file_path)
            target = os.path.join(temp_dir, name)
            os.replace(file_path, target)
            moved.append((target, file_path))
    try:
        return func(heads, keep)
    finally:
        for src, dst in moved:
            os.replace(src, dst)


def _default_message(db_name: str) -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"auto_{db_name}_{ts}"


def _reset_alembic_version(db_path: str) -> bool:
    if not os.path.exists(db_path):
        return True
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='alembic_version'")
        if cur.fetchone() is not None:
            cur.execute("DROP TABLE alembic_version")
            conn.commit()
        conn.close()
        return True
    except Exception:
        return False


def _force_alembic_version(db_path: str, revision_id: str) -> bool:
    if not os.path.exists(db_path) or not revision_id:
        return False
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32) NOT NULL)")
        cur.execute("DELETE FROM alembic_version")
        cur.execute("INSERT INTO alembic_version (version_num) VALUES (?)", (revision_id,))
        conn.commit()
        conn.close()
        return True
    except Exception:
        return False


def _cleanup_alembic_temp_tables(db_path: str) -> None:
    if not os.path.exists(db_path):
        return
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        rows = cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '_alembic_tmp_%'").fetchall()
        for (name,) in rows:
            cur.execute(f"DROP TABLE IF EXISTS {name}")
        conn.commit()
        conn.close()
    except Exception:
        return


def _get_current_revision(db_path: str) -> str:
    if not os.path.exists(db_path):
        return ""
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='alembic_version'")
        if cur.fetchone() is None:
            conn.close()
            return ""
        row = cur.execute("SELECT version_num FROM alembic_version").fetchone()
        conn.close()
        return row[0] if row else ""
    except Exception:
        return ""


def _db_has_user_tables(db_path: str) -> bool:
    if not os.path.exists(db_path):
        return False
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        rows = cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        conn.close()
        tables = [r[0] for r in rows]
        tables = [t for t in tables if t not in ("alembic_version", "sqlite_sequence")]
        return len(tables) > 0
    except Exception:
        return False


def _run_autogen(server_dir: str, db: str, msg: str) -> bool:
    versions_dir = os.path.join(server_dir, "alembic", "versions")
    before = _snapshot_versions(versions_dir)
    has_any_revisions = len(before) > 0
    has_branch_revisions = _has_branch_revisions(versions_dir, db)
    db_path = os.path.join(server_dir, DB_PATHS[db])

    if not has_any_revisions:
        db_path = os.path.join(server_dir, DB_PATHS[db])
        if not _reset_alembic_version(db_path):
            print("\n❌ 重置 alembic_version 失败，无法继续生成迁移脚本")
            return False

    print(f"\n🔄 正在为 [{db}] 数据库生成迁移脚本...")
    print("👉 请留意后续的交互提示：如果检测到字段重命名或删除，系统会询问你。")

    _cleanup_alembic_temp_tables(db_path)

    # 先将数据库升级到最新迁移，避免 autogenerate 报 "Target database is not up to date"
    def _run_commands(heads, keep):
        head_rev = heads[0] if heads else ""
        has_branch_revisions = len(keep) > 0
        if has_any_revisions and has_branch_revisions:
            current_rev = _get_current_revision(db_path)
            if not current_rev and head_rev and _db_has_user_tables(db_path):
                if not _force_alembic_version(db_path, head_rev):
                    print("\n❌ 版本记录补写失败，无法继续生成迁移脚本")
                    return False
                current_rev = head_rev
            if current_rev and current_rev not in keep and head_rev:
                if not _force_alembic_version(db_path, head_rev):
                    print("\n❌ 修复版本记录失败，无法继续生成迁移脚本")
                    return False
            if not (current_rev and head_rev and current_rev == head_rev):
                _cleanup_alembic_temp_tables(db_path)
                upgrade_cmd = [
                    sys.executable, "-m", "alembic",
                    "-x", f"db={db}",
                    "upgrade", f"{db}@head"
                ]
                upgrade_result = subprocess.run(upgrade_cmd, cwd=server_dir)
                if upgrade_result.returncode != 0:
                    print("\n❌ 迁移升级失败，无法继续生成迁移脚本")
                    return False

        autogen_cmd = [
            sys.executable, "-m", "alembic",
            "-x", f"db={db}",
            "revision", "--autogenerate",
            "-m", msg,
            f"--head={db}@head"
        ]

        if not has_branch_revisions:
            autogen_cmd[-1] = "--head=base"
            autogen_cmd.insert(-1, "--branch-label")
            autogen_cmd.insert(-1, db)

        before_files = _snapshot_versions(versions_dir)
        result = subprocess.run(autogen_cmd, cwd=server_dir)
        if result.returncode != 0:
            after_files = _snapshot_versions(versions_dir)
            new_files = after_files - before_files
            for name in new_files:
                try:
                    os.remove(os.path.join(versions_dir, name))
                except Exception:
                    pass
            print("\n❌ 生成失败或被取消")
            return False
        return True

    if not _with_branch_filtered_versions(versions_dir, db, _run_commands):
        return False

    after = _snapshot_versions(versions_dir)
    new_files = sorted(after - before)
    if not new_files:
        print("\nℹ️ 未检测到结构变化，未生成迁移文件。")
        return True

    cleaned = []
    for name in list(new_files):
        path = os.path.join(versions_dir, name)
        if _is_empty_revision(path):
            if not has_branch_revisions:
                rev_id, down_revs, label = _parse_revision_info(path)
                if label == db and not down_revs:
                    # Keep empty base revision to establish branch head.
                    continue
            try:
                os.remove(path)
                cleaned.append(name)
                new_files.remove(name)
            except Exception:
                pass

    if cleaned and not new_files:
        print("\nℹ️ 未检测到结构变化，已清理空迁移文件。")
        return True

    print("\n✅ 流程结束。")
    print("   新生成的迁移文件:")
    for name in new_files:
        print(f"   - {name}")
    print("   下次重启服务时将自动应用此更改。")
    return True

def main():
    args = sys.argv[1:]

    dbs = list(VALID_DBS)
    msg = None

    if len(args) == 1:
        if args[0] in VALID_DBS:
            dbs = [args[0]]
        else:
            msg = args[0]
    elif len(args) >= 2:
        if args[0] not in VALID_DBS:
            print(f"❌ 错误: db 必须是 'users'/'llm'，收到: '{args[0]}'")
            sys.exit(1)
        dbs = [args[0]]
        msg = " ".join(args[1:]).strip()

    # 确保在 server 目录下运行
    server_dir = os.path.dirname(os.path.abspath(__file__))

    try:
        overall_ok = True
        for db in dbs:
            use_msg = msg or _default_message(db)
            ok = _run_autogen(server_dir, db, use_msg)
            overall_ok = overall_ok and ok

        if not overall_ok:
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n⛔ 用户中断操作")
        sys.exit(1)

if __name__ == "__main__":
    main()
