import os
import logging
import sqlite3

# 配置日志
logger = logging.getLogger("alembic_runner")
logging.basicConfig(level=logging.INFO)

import configparser
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory

# 定义基础目录
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def _get_current_db_revision(db_path: str) -> str:
    """Read current revision from database directly (fast)."""
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

def _get_head_revision(server_dir: str, db_name: str) -> str:
    """Get head revision ID using Alembic ScriptDirectory (without loading env.py)."""
    # This assumes version_locations is standard.
    # To be perfectly safe, we'll set up a minimal Config just to read scripts.
    alembic_cfg_path = os.path.join(server_dir, "alembic.ini")
    alembic_cfg = Config(alembic_cfg_path)
    
    # 手动设置 version_locations 以匹配我们在 alembic.ini 中的配置
    # 如果 ini 配置了 [users] version_locations，我们需要通过 Config 读取
    # 这里我们直接根据已知结构构建路径，更快
    version_dir = os.path.join(server_dir, "alembic", "versions", db_name)
    if not os.path.exists(version_dir):
        return None
        
    # 构建临时 Config 来读取脚本信息
    alembic_cfg.set_main_option("script_location", os.path.join(server_dir, "alembic"))
    alembic_cfg.set_main_option("version_locations", version_dir)
    
    try:
        script = ScriptDirectory.from_config(alembic_cfg)
        return script.get_current_head()
    except Exception as e:
        logger.warning(f"Error reading script head: {e}")
        return None

def run_db_upgrade(db_name: str, base_dir: str):
    """
    对指定数据库执行 upgrade head (In-Process Optimized)
    """
    db_config = {
        "users": os.path.join(base_dir, "data", "users.db"),
        "llm": os.path.join(base_dir, "llm", "llm_mgr", "llm_config.db")
    }
    db_path = db_config.get(db_name)
    
    # 1. Fast Check
    current_rev = _get_current_db_revision(db_path)
    head_rev = _get_head_revision(base_dir, db_name)

    if not head_rev:
        logger.warning(f"⚠️ [{db_name}] 未检测到迁移脚本 (head 为空)。跳过自动升级。")
        return

    if current_rev and current_rev == head_rev:
        logger.info(f"✨ [{db_name}] 数据库已是最新 ({current_rev}). Skipping upgrade.")
        return

    logger.info(f"🔄 Upgrading [{db_name}] database: {current_rev} -> {head_rev}")
    
    # 2. Run Upgrade via API
    alembic_cfg_path = os.path.join(base_dir, "alembic.ini")
    alembic_cfg = Config(alembic_cfg_path)
    # 必须传递 -x db={db} 给 env.py
    alembic_cfg.cmd_opts = type("CmdOpts", (), {"x": [f"db={db_name}"]})()
    
    # 还要确保使用正确的 config section
    # 我们可以通过 name 参数传递 section name，但 command.upgrade 不接受 name 参数
    # command.upgrade(config, revision, sql=False, tag=None)
    # env.py 读取 config.config_ini_section 是一个 hack，通常由 Alembic CLI 设置。
    # API 调用时，Config 对象本身不包含 section 信息，除非我们 manually load section.
    # 但我们的 env.py 逻辑里：
    # section = config.config_ini_section -> 这在 API 模式下可能不存在 或 为 None
    # fallback -> context.get_x_argument -> active!
    # 所以只要 x 参数存在，env.py 就能工作。
    
    original_cwd = os.getcwd()
    try:
        # 切换 CWD 确保 alembic.ini 能找到 relative path
        os.chdir(base_dir)
        
        # 指定 section name? command.upgrade 不直接支持指定 section，
        # 但我们可以让 env.py 依赖 x 参数，这是最稳健的。
        # 我们在上面已经设置了 cmd_opts.x
        
        # 另外，我们需要确保 version_locations 正确。
        # alembic.ini 里有 [users] 和 [llm] section 定义了 version_locations。
        # 当我们初始化 Config(ini_path) 时，它只加载 default [alembic] section。
        # 我们需要 merge 对应 section 的配置。
        
        cp = configparser.ConfigParser()
        cp.read(alembic_cfg_path)
        if cp.has_section(db_name):
            for key, value in cp.items(db_name):
                alembic_cfg.set_main_option(key, value)
        
        # 执行升级
        command.upgrade(alembic_cfg, "head")
        
        logger.info(f"✅ [{db_name}] Upgrade completed.")
    except Exception as e:
        logger.error(f"❌ [{db_name}] Upgrade failed: {e}")
        raise e
    finally:
        os.chdir(original_cwd)

def run_auto_migrations():
    """
    启动时自动运行 Alembic 迁移
    
    不再进行手动的版本表检查或 SQL 操作，完全委托给 Alembic。
    """
    base_dir = BASE_DIR
    alembic_ini_path = os.path.join(base_dir, "alembic.ini")
    
    if not os.path.exists(alembic_ini_path):
        logger.warning(f"⚠️ Alembic 配置文件未找到: {alembic_ini_path}，跳过自动迁移。")
        return

    # 构造通用环境变量 (确保 UTF-8)
    logger.info("🛠️  正在检查数据库迁移状态...")

    try:
        # 1. 迁移 Users 数据库
        run_db_upgrade("users", base_dir)

        # 2. 迁移 LLM 数据库
        run_db_upgrade("llm", base_dir)
        
    except Exception as e:
        # 启动时的迁移错误通常是致命的，应该抛出异常阻止应用启动
        logger.error(f"❌ 自动迁移流程发生错误: {e}")
        raise e
