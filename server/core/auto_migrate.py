import os
import logging
import sqlite3
import configparser

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory

# 统一日志出口；避免重复配置 root logger
logger = logging.getLogger("alembic_runner")
if not logging.getLogger().handlers:
    logging.basicConfig(level=logging.INFO)

# 服务根目录（server/）
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DB_PATHS = {
    "users": os.path.join(BASE_DIR, "data", "users.db"),
    "llm": os.path.join(BASE_DIR, "llm", "llm_mgr", "llm_config.db"),
}

def _get_current_db_revision(db_path: str) -> str:
    """快速读取数据库当前版本号，用于短路跳过无变更的升级。"""
    if not os.path.exists(db_path):
        return None
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT version_num FROM alembic_version")
        row = cur.fetchone()
        conn.close()
        if row:
            return row[0]
    except Exception:
        pass
    return None


def _has_user_tables(db_path: str) -> bool:
    """判断数据库是否已存在业务表，用于区分“空库”与“旧库未纳管”场景。"""
    if not os.path.exists(db_path):
        return False
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
        rows = [name for (name,) in cur.fetchall()]
        conn.close()
        return any(
            name not in ("alembic_version",) and not name.startswith("_alembic_tmp_")
            for name in rows
        )
    except Exception:
        return False

def _get_head_revision(server_dir: str, db_name: str) -> str:
    """读取迁移脚本的 head 版本号（不触发 env.py）。"""
    alembic_cfg_path = os.path.join(server_dir, "alembic.ini")
    alembic_cfg = Config(alembic_cfg_path)
    
    # 直接指定 version_locations 以读取对应分支的脚本
    version_dir = os.path.join(server_dir, "alembic", "versions", db_name)
    if not os.path.exists(version_dir):
        return None
        
    # 构建最小 Config 以读取脚本信息
    alembic_cfg.set_main_option("script_location", os.path.join(server_dir, "alembic"))
    alembic_cfg.set_main_option("version_locations", version_dir)
    
    try:
        script = ScriptDirectory.from_config(alembic_cfg)
        return script.get_current_head()
    except Exception as e:
        logger.warning(f"Error reading script head: {e}")
        return None

def _build_alembic_config(base_dir: str, db_name: str) -> Config:
    """构造带分支配置的 Alembic Config（确保 version_locations 正确）。"""
    alembic_cfg_path = os.path.join(base_dir, "alembic.ini")
    alembic_cfg = Config(alembic_cfg_path)
    alembic_cfg.cmd_opts = type("CmdOpts", (), {"x": [f"db={db_name}"]})()

    cp = configparser.ConfigParser()
    cp.read(alembic_cfg_path)
    if cp.has_section(db_name):
        for key, value in cp.items(db_name):
            alembic_cfg.set_main_option(key, value)
    return alembic_cfg


def run_db_upgrade(db_name: str, base_dir: str) -> None:
    """对指定数据库执行 upgrade head（进程内调用）。"""
    db_path = DB_PATHS.get(db_name)
    
    # 1) 快速检查：已是 head 直接跳过
    current_rev = _get_current_db_revision(db_path)
    head_rev = _get_head_revision(base_dir, db_name)

    if not head_rev:
        logger.warning(f"⚠️ [{db_name}] 未检测到迁移脚本 (head 为空)。跳过自动升级。")
        return

    if current_rev and current_rev == head_rev:
        logger.info(f"✨ [{db_name}] 数据库已是最新 ({current_rev}). 跳过自动升级。")
        return

    # 旧库未纳管：有业务表但没有版本号 -> 直接 stamp 到 head
    if current_rev is None and _has_user_tables(db_path):
        logger.warning(f"⚠️ [{db_name}] 检测到旧库未纳管，执行 stamp 到 head。")
        original_cwd = os.getcwd()
        try:
            os.chdir(base_dir)
            alembic_cfg = _build_alembic_config(base_dir, db_name)
            command.stamp(alembic_cfg, "head")
            logger.info(f"✅ [{db_name}] Stamp completed.")
        except Exception as e:
            logger.error(f"❌ [{db_name}] Stamp failed: {e}")
            raise e
        finally:
            os.chdir(original_cwd)
        return

    logger.info(f"🔄 Upgrading [{db_name}] database: {current_rev} -> {head_rev}")
    
    # 2) 执行升级
    original_cwd = os.getcwd()
    try:
        # 切换 CWD 确保 alembic.ini 能找到 relative path
        os.chdir(base_dir)
        alembic_cfg = _build_alembic_config(base_dir, db_name)
        command.upgrade(alembic_cfg, "head")
        
        logger.info(f"✅ [{db_name}] Upgrade completed.")
    except Exception as e:
        logger.error(f"❌ [{db_name}] Upgrade failed: {e}")
        raise e
    finally:
        os.chdir(original_cwd)

def run_auto_migrations():
    """
    启动时自动运行 Alembic 迁移。
    目标：把迁移放在最早阶段完成，避免后续模块初始化时持锁或访问旧结构。
    """
    base_dir = BASE_DIR
    alembic_ini_path = os.path.join(base_dir, "alembic.ini")
    
    if not os.path.exists(alembic_ini_path):
        logger.warning(f"⚠️ Alembic 配置文件未找到: {alembic_ini_path}，跳过自动迁移。")
        return

    logger.info("🛠️  正在检查数据库迁移状态...")

    try:
        # 1) 迁移 Users 数据库
        run_db_upgrade("users", base_dir)

        # 2) 迁移 LLM 数据库
        run_db_upgrade("llm", base_dir)
        
    except Exception as e:
        # 启动期迁移失败直接阻断启动，避免运行在不一致的结构上
        logger.error(f"❌ 自动迁移流程发生错误: {e}")
        raise e
