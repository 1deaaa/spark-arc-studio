import os
import sys
import subprocess
import logging
import re
import sqlite3

# 配置日志
logger = logging.getLogger("alembic_runner")
logging.basicConfig(level=logging.INFO)


def _has_branch_revisions(versions_dir: str, branch_label: str) -> bool:
    if not os.path.isdir(versions_dir):
        return False
    for name in os.listdir(versions_dir):
        if not name.endswith(".py"):
            continue
        file_path = os.path.join(versions_dir, name)
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            label_match = re.search(r"branch_labels\s*=\s*([^\n]+)", content)
            if label_match and f"'{branch_label}'" in label_match.group(1):
                return True
        except Exception:
            continue
    return False


def _cleanup_alembic_version_if_orphan(db_name: str, base_dir: str) -> None:
    versions_dir = os.path.join(base_dir, "alembic", "versions")
    if _has_branch_revisions(versions_dir, db_name):
        return

    db_path = _get_db_path(base_dir, db_name)
    if not db_path or not os.path.exists(db_path):
        return

    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='alembic_version'")
        if cur.fetchone() is None:
            conn.close()
            return
        cur.execute("DELETE FROM alembic_version")
        conn.commit()
        conn.close()
        logger.info(f"⚠️ [{db_name}] 未检测到迁移历史，已自动清空 alembic_version。")
    except Exception:
        return

def _extract_revisions(output: str):
    """从 Alembic 输出中提取 revision id 列表。"""
    if not output:
        return []

    revisions = []

    # 1) 解析包含 "Rev:" 的输出（heads/current --verbose 等）
    revisions.extend(re.findall(r"Rev:\s*([0-9a-fA-F]+)", output))

    # 2) 解析 current 的简洁输出
    # 示例: "Current revision(s) for sqlite:///...: 1975ea83b712 (head)"
    current_matches = re.findall(r"Current revision\(s\).*?:\s*([^\n]+)", output)
    for match in current_matches:
        # 可能是 "rev1 (head), rev2" 形式
        parts = [p.strip() for p in match.split(",") if p.strip()]
        for part in parts:
            rev = re.match(r"([0-9a-fA-F]+)", part)
            if rev:
                revisions.append(rev.group(1))

    # 去重并保持稳定顺序
    seen = set()
    unique = []
    for r in revisions:
        if r not in seen:
            seen.add(r)
            unique.append(r)
    return unique


def _get_revisions(cmd, base_dir, env):
    result = subprocess.run(
        cmd,
        cwd=base_dir,
        env=env,
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        return None, result
    combined_output = (result.stdout or "") + "\n" + (result.stderr or "")
    return _extract_revisions(combined_output), result


def _alembic_cmd(*args):
    cmd = [sys.executable, "-m", "alembic"]
    cmd.extend(args)
    return cmd


def _extract_revisions_for_branch(output: str, branch_label: str):
    """从 heads/current --verbose 输出中过滤指定分支的 revisions。"""
    if not output:
        return []

    revisions = []
    blocks = re.split(r"\n\s*\n", output.strip())
    for block in blocks:
        rev_match = re.search(r"Rev:\s*([0-9a-fA-F]+)", block)
        if not rev_match:
            continue

        # Alembic 可能输出 Branch names 或 Branch labels
        labels_match = re.search(r"Branch (?:labels?|names?):\s*([^\n]+)", block)
        if not labels_match:
            continue
        labels = [l.strip() for l in labels_match.group(1).split(",") if l.strip()]
        if branch_label in labels:
            revisions.append(rev_match.group(1))

    return revisions


def _needs_upgrade(db_name: str, base_dir: str, env: dict):
    """判断指定数据库是否需要迁移。返回 True 表示需要执行 upgrade。"""
    cmd_heads = _alembic_cmd("-x", f"db={db_name}", "heads", "--verbose")
    heads_all, heads_result = _get_revisions(cmd_heads, base_dir, env)
    if heads_result.returncode != 0:
        logger.warning(f"⚠️ [{db_name}] 获取 heads 失败，将继续尝试迁移。\nSTDOUT: {heads_result.stdout}\nSTDERR: {heads_result.stderr}")
        return True

    heads_output = (heads_result.stdout or "") + "\n" + (heads_result.stderr or "")
    heads = _extract_revisions_for_branch(heads_output, db_name)
    if not heads:
        # 如果未找到分支 head，说明没有该库的迁移历史，跳过迁移
        if heads_all:
            logger.warning(f"⚠️ [{db_name}] 未找到分支 head，跳过迁移。")
        else:
            logger.warning(f"⚠️ [{db_name}] 未找到任何迁移版本，跳过迁移。")
        return False

    # 优先直接读取 DB 中的 alembic_version
    db_path = _get_db_path(base_dir, db_name)
    current = _get_db_versions(db_path)
    current_output = ""

    if not current:
        cmd_current = _alembic_cmd("-x", f"db={db_name}", "current", "--verbose")
        current_all, current_result = _get_revisions(cmd_current, base_dir, env)
        if current_all is None:
            logger.warning(f"⚠️ [{db_name}] 获取 current 失败，将继续尝试迁移。\nSTDOUT: {current_result.stdout}\nSTDERR: {current_result.stderr}")
            return True

        # 过滤当前库所属分支的 revision
        current_output = (current_result.stdout or "") + "\n" + (current_result.stderr or "")
        current = _extract_revisions_for_branch(current_output, db_name)
        if not current and current_all and heads and len(heads) == 1:
            # current 输出可能缺少分支信息，且当前库只有一个 head 时可回退到全量解析
            current = current_all

    if os.environ.get("SPARKARC_MIGRATE_DEBUG") == "1":
        logger.info(f"[debug][{db_name}] heads_raw:\n{heads_output}")
        if current_output:
            logger.info(f"[debug][{db_name}] current_raw:\n{current_output}")

    # 无版本信息时，说明是全新库，需要迁移
    if not current:
        if os.environ.get("SPARKARC_MIGRATE_DEBUG") == "1":
            logger.info(f"[debug][{db_name}] current 为空，视为需要迁移。heads={heads}")
        return True

    needs = set(current) != set(heads)
    if os.environ.get("SPARKARC_MIGRATE_DEBUG") == "1":
        logger.info(f"[debug][{db_name}] heads={heads} current={current} needs_migrate={needs}")
    return needs


def _get_db_path(base_dir: str, db_name: str) -> str:
    if db_name == "users":
        return os.path.join(base_dir, "data", "users.db")
    if db_name == "llm":
        return os.path.join(base_dir, "llm", "llm_mgr", "llm_config.db")
    return ""


def _get_db_versions(db_path: str):
    if not db_path or not os.path.exists(db_path):
        return []
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='alembic_version'")
        if cur.fetchone() is None:
            conn.close()
            return []
        cur.execute("SELECT version_num FROM alembic_version")
        rows = [r[0] for r in cur.fetchall() if r and r[0]]
        conn.close()
        return rows
    except Exception:
        return []


def _write_db_version(db_path: str, version: str) -> bool:
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32) NOT NULL)")
        cur.execute("DELETE FROM alembic_version")
        cur.execute("INSERT INTO alembic_version (version_num) VALUES (?)", (version,))
        conn.commit()
        conn.close()
        return True
    except Exception:
        return False


def _alembic_version_empty(db_path: str) -> bool:
    if not db_path or not os.path.exists(db_path):
        return False
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='alembic_version'")
        if cur.fetchone() is None:
            conn.close()
            return False
        cur.execute("SELECT COUNT(1) FROM alembic_version")
        count = cur.fetchone()[0]
        conn.close()
        return count == 0
    except Exception:
        return False


def _db_has_user_tables(db_path: str) -> bool:
    if not db_path or not os.path.exists(db_path):
        return False
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in cur.fetchall()]
        conn.close()
        tables = [t for t in tables if t not in ("alembic_version", "sqlite_sequence")]
        return len(tables) > 0
    except Exception:
        return False


def _get_branch_heads(db_name: str, base_dir: str, env: dict):
    cmd_heads = _alembic_cmd("-x", f"db={db_name}", "heads", "--verbose")
    _, heads_result = _get_revisions(cmd_heads, base_dir, env)
    if heads_result.returncode != 0:
        return []
    heads_output = (heads_result.stdout or "") + "\n" + (heads_result.stderr or "")
    return _extract_revisions_for_branch(heads_output, db_name)


def _sync_version_to_head(db_name: str, base_dir: str, env: dict) -> bool:
    db_path = _get_db_path(base_dir, db_name)
    heads = _get_branch_heads(db_name, base_dir, env)
    if len(heads) == 1:
        return _write_db_version(db_path, heads[0])
    return False


def _maybe_stamp(db_name: str, base_dir: str, env: dict) -> bool:
    db_path = _get_db_path(base_dir, db_name)
    if _alembic_version_empty(db_path) and _db_has_user_tables(db_path):
        if os.environ.get("SPARKARC_ALLOW_STAMP") != "1":
            logger.warning(f"⚠️ [{db_name}] alembic_version 为空，默认不执行 stamp，改为尝试 upgrade。")
            return False
        heads = _get_branch_heads(db_name, base_dir, env)
        if not heads:
            logger.warning(f"⚠️ [{db_name}] 无迁移 head 可用，跳过 stamp。")
            return True
        if len(heads) == 1:
            if _write_db_version(db_path, heads[0]):
                logger.info(f"  ✅ [{db_name}] 版本已记录 (stamp)")
                return True
        logger.info(f"  ℹ️ [{db_name}] alembic_version 为空且存在业务表，改为 stamp 记录版本。")
        cmd_stamp = _alembic_cmd("-x", f"db={db_name}", "stamp", f"{db_name}@head")
        result = subprocess.run(
            cmd_stamp,
            cwd=base_dir,
            env=env,
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            logger.error(f"❌ [{db_name}] stamp 失败:\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}")
            return False
        logger.info(f"  ✅ [{db_name}] 版本已记录 (stamp)")
        return True
    return False


def run_auto_migrations():
    """
    启动时自动运行 Alembic 迁移
    
    使用 subprocess 调用 alembic 命令行工具，确保环境隔离和通过性。
    针对 users 和 llm 两个数据库分别执行 upgrade head
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    alembic_ini_path = os.path.join(base_dir, "alembic.ini")
    
    if not os.path.exists(alembic_ini_path):
        logger.warning(f"⚠️ Alembic 配置文件未找到: {alembic_ini_path}，跳过自动迁移。")
        return

    # 构造通用环境变量 (确保 UTF-8)
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"

    # 如果迁移文件被清空，自动清理版本表，避免版本号与实际迁移历史不一致
    _cleanup_alembic_version_if_orphan("users", base_dir)
    _cleanup_alembic_version_if_orphan("llm", base_dir)

    # 先检查是否需要迁移
    needs_users = _needs_upgrade("users", base_dir, env)
    needs_llm = _needs_upgrade("llm", base_dir, env)

    if not needs_users and not needs_llm:
        logger.debug("数据库已是最新版本，无需迁移")
        return

    logger.info("🔄 开始执行数据库自动迁移...")
    
    try:
        # 1. 迁移 Users 数据库 (分支: users)
        if needs_users:
            if not _maybe_stamp("users", base_dir, env):
                logger.info("  > 正在迁移 [users] 数据库...")
                # upgrade users@head
                cmd_users = _alembic_cmd("-x", "db=users", "upgrade", "users@head")
                result = subprocess.run(
                    cmd_users,
                    cwd=base_dir,
                    env=env
                )
                
                if result.returncode != 0:
                    logger.error("❌ [users] 迁移失败，请查看上方 Alembic 输出。")
                    raise RuntimeError(f"Users DB migration failed with code {result.returncode}")
                else:
                    _sync_version_to_head("users", base_dir, env)
                    logger.info("  ✅ [users] 数据库迁移完成")
                    logger.debug("[users] Alembic migration completed")
        else:
            logger.info("  ⏭️ [users] 无需迁移")

        # 2. 迁移 LLM 数据库 (分支: llm)
        if needs_llm:
            if not _maybe_stamp("llm", base_dir, env):
                logger.info("  > 正在迁移 [llm] 数据库...")
                # upgrade llm@head
                cmd_llm = _alembic_cmd("-x", "db=llm", "upgrade", "llm@head")
                result_llm = subprocess.run(
                    cmd_llm,
                    cwd=base_dir,
                    env=env
                )
                
                if result_llm.returncode != 0:
                    logger.error("❌ [llm] 迁移失败，请查看上方 Alembic 输出。")
                    raise RuntimeError(f"LLM DB migration failed with code {result_llm.returncode}")
                else:
                    _sync_version_to_head("llm", base_dir, env)
                    logger.info("  ✅ [llm] 数据库迁移完成")
                    logger.debug("[llm] Alembic migration completed")
        else:
            logger.info("  ⏭️ [llm] 无需迁移")
            
        logger.info("✨ 所有数据库迁移已完成！")
        
    except Exception as e:
        logger.error(f"❌ 自动迁移执行异常: {e}")
        raise e
