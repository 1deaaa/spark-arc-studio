import os
import logging
import sqlite3
import configparser
import sqlalchemy as sa

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
}


def _get_llm_db_path() -> str:
    """动态解析 llm 数据库路径。

    优先使用当前网关模块导出的路径解析逻辑，避免目录重命名后这里仍然指向旧路径。
    """
    try:
        from llm.agen_matchbox.paths import get_db_file_path

        return str(get_db_file_path("llm_config.db"))
    except Exception:
        # 兜底到当前目录结构，避免导入异常时完全失效
        return os.path.join(BASE_DIR, "llm", "agen_matchbox", "llm_config.db")


def _get_db_path(db_name: str) -> str:
    if db_name == "llm":
        return _get_llm_db_path()
    return DB_PATHS.get(db_name)


# ============================================================
# 工具函数
# ============================================================

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
    """判断数据库是否已存在业务表，用于区分"空库"与"旧库未纳管"场景。"""
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


def _get_target_metadata(db_name: str):
    """加载指定数据库对应的 SQLAlchemy Metadata。"""
    if db_name == "users":
        from core.models import UserInfo
        return UserInfo.metadata
    elif db_name == "llm":
        try:
            from llm.agen_matchbox.models import Base as LLMBase
            return LLMBase.metadata
        except ImportError as e:
            logger.warning(f"⚠️ 无法加载 LLM 模型元数据: {e}")
            return None
    return None


def _is_internal_table(name: str) -> bool:
    if not name:
        return False
    return name == "alembic_version" or name.startswith("sqlite_") or name.startswith("_alembic_tmp_")


def _has_schema_drift(db_name: str, db_path: str) -> bool:
    """检查数据库结构是否与当前模型存在缺失差异（缺表/缺列）。"""
    if not db_path or not os.path.exists(db_path):
        return False

    target_metadata = _get_target_metadata(db_name)
    if target_metadata is None:
        return False

    from sqlalchemy import create_engine, inspect as sa_inspect
    from sqlalchemy.pool import NullPool

    normalized_path = db_path.replace("\\", "/")
    db_url = f"sqlite:///{normalized_path}"
    engine = create_engine(db_url, poolclass=NullPool)
    try:
        inspector = sa_inspect(engine)
        existing_tables = set(inspector.get_table_names())

        for table_name, table in target_metadata.tables.items():
            if _is_internal_table(table_name):
                continue

            if table_name not in existing_tables:
                return True

            existing_col_names = {c["name"] for c in inspector.get_columns(table_name)}
            for col in table.columns:
                if col.name not in existing_col_names:
                    return True

        return False
    finally:
        engine.dispose()


# ============================================================
# 孤儿版本自愈
# ============================================================

def _heal_orphan_revision(db_name: str, db_path: str, base_dir: str) -> None:
    """
    孤儿版本自愈：当 DB 中记录的 revision 在迁移文件链中不存在时触发
    （最常见原因：管理员重置了迁移，开发者的 DB 停在了旧版本号）。

    自愈策略（纯增量，永远不删除任何数据或现有结构）：
      1. 扫描 Model 元数据，补全所有缺失的表（整表创建）。
      2. 扫描已存在表的列，补全所有缺失的列（batch_alter）。
      3. 清除孤儿版本号，stamp 到当前迁移 head。

    前提假设：只要站长没有手动修改数据库结构或迁移文件，
    此函数即可保证应用正常启动，无需任何人工干预。
    """
    from sqlalchemy import create_engine, inspect as sa_inspect
    from sqlalchemy.pool import NullPool
    from alembic.runtime.migration import MigrationContext
    from alembic.operations import Operations

    logger.warning(f"⚕️  [{db_name}] 检测到孤儿版本，启动结构自愈流程...")

    target_metadata = _get_target_metadata(db_name)
    if target_metadata is None:
        raise RuntimeError(
            f"[{db_name}] 无法加载模型元数据，无法自动修复孤儿版本。"
            "请检查模型导入是否正常。"
        )

    # 规范化为 SQLite URL（处理 Windows 反斜杠）
    normalized_path = db_path.replace("\\", "/")
    db_url = f"sqlite:///{normalized_path}"
    engine = create_engine(db_url, poolclass=NullPool)

    added_tables = []
    added_columns = []
    # 内部表，跳过不处理
    SKIP_NAMES = {"alembic_version"}

    try:
        # ── 第一轮：补全缺失的整张表 ───────────────────────────
        inspector = sa_inspect(engine)
        existing_tables = set(inspector.get_table_names())

        for table_name, table in target_metadata.tables.items():
            if table_name in SKIP_NAMES or table_name.startswith("_alembic_tmp_"):
                continue
            if table_name not in existing_tables:
                table.create(engine)
                added_tables.append(table_name)
                logger.info(f"   ➕ 创建缺失的表: {table_name}")

        # ── 第二轮：补全缺失的列（重新 inspect，反映第一轮刚建的表）──
        inspector = sa_inspect(engine)
        existing_tables = set(inspector.get_table_names())

        with engine.connect() as conn:
            migration_ctx = MigrationContext.configure(
                conn, opts={"render_as_batch": True}
            )
            op_obj = Operations(migration_ctx)

            for table_name, table in target_metadata.tables.items():
                if table_name in SKIP_NAMES or table_name.startswith("_alembic_tmp_"):
                    continue
                if table_name not in existing_tables:
                    continue  # 第一轮刚建的表已含全部列

                existing_col_names = {c["name"] for c in inspector.get_columns(table_name)}
                missing_cols = [col for col in table.columns if col.name not in existing_col_names]

                if not missing_cols:
                    continue

                with op_obj.batch_alter_table(table_name) as batch_op:
                    for col in missing_cols:
                        # SQLite 不允许向含有数据的表添加 NOT NULL 且无默认值的列，
                        # 此时以 nullable 方式安全添加（现有行该列为 NULL，业务层可接受）
                        nullable = col.nullable
                        server_default = col.server_default

                        if not nullable and server_default is None and col.default is None:
                            logger.warning(
                                f"   ⚠️ {table_name}.{col.name}: NOT NULL 且无默认值，"
                                f"自愈时以 nullable 方式添加（现有行将为 NULL）"
                            )
                            nullable = True

                        batch_op.add_column(
                            sa.Column(col.name, col.type, nullable=nullable, server_default=server_default)
                        )
                        added_columns.append(f"{table_name}.{col.name}")
                        logger.info(f"   ➕ 补全缺失的列: {table_name}.{col.name}")

            conn.commit()

        # ── 清除孤儿版本号，stamp 到当前 head ──────────────────
        # 兼容“旧库未纳管”场景：数据库可能尚未创建 alembic_version 表。
        with sqlite3.connect(db_path) as raw_conn:
            try:
                raw_conn.execute("DELETE FROM alembic_version")
                raw_conn.commit()
            except sqlite3.OperationalError:
                # 表不存在时由后续 stamp 自动创建并写入版本号。
                pass

        original_cwd = os.getcwd()
        try:
            os.chdir(base_dir)
            cfg = _build_alembic_config(base_dir, db_name)
            command.stamp(cfg, "head")
        finally:
            os.chdir(original_cwd)

        # ── 汇报自愈结果 ────────────────────────────────────────
        if added_tables or added_columns:
            logger.info(f"✅ [{db_name}] 结构自愈完成。")
            if added_tables:
                logger.info(f"   新建的表: {', '.join(added_tables)}")
            if added_columns:
                logger.info(f"   补全的列: {', '.join(added_columns)}")
        else:
            logger.info(f"✅ [{db_name}] DB 结构与模型完全一致，仅更新了版本号。")

    finally:
        engine.dispose()


# ============================================================
# 核心升级入口
# ============================================================

def run_db_upgrade(db_name: str, base_dir: str) -> None:
    """对指定数据库执行 upgrade head（进程内调用）。"""
    db_path = _get_db_path(db_name)

    # 1) 快速检查：已是 head 直接跳过
    current_rev = _get_current_db_revision(db_path)
    head_rev = _get_head_revision(base_dir, db_name)

    if not head_rev:
        logger.warning(f"⚠️ [{db_name}] 未检测到迁移脚本 (head 为空)。跳过自动升级。")
        return

    if current_rev and current_rev == head_rev:
        if _has_schema_drift(db_name, db_path):
            logger.warning(
                f"⚠️ [{db_name}] 版本号已是 head ({current_rev})，"
                f"但检测到结构漂移（缺表/缺列），执行结构自愈。"
            )
            _heal_orphan_revision(db_name, db_path, base_dir)
            return

        logger.info(f"✨ [{db_name}] 数据库已是最新 ({current_rev}). 跳过自动升级。")
        return

    # 旧库未纳管：有业务表但没有版本号
    if current_rev is None and _has_user_tables(db_path):
        logger.warning(
            f"⚠️ [{db_name}] 检测到旧库未纳管（有业务表但无版本号），"
            f"将执行结构自愈并对齐到 head。"
        )
        _heal_orphan_revision(db_name, db_path, base_dir)
        return

    logger.info(f"🔄 Upgrading [{db_name}] database: {current_rev} -> {head_rev}")

    # 2) 执行升级
    original_cwd = os.getcwd()
    try:
        os.chdir(base_dir)
        alembic_cfg = _build_alembic_config(base_dir, db_name)
        command.upgrade(alembic_cfg, "head")
        logger.info(f"✅ [{db_name}] Upgrade completed.")
    except Exception as e:
        err_msg = str(e)
        if "Can't locate revision identified by" in err_msg:
            # 孤儿版本：迁移链被重置导致 DB 中记录的 revision 在迁移文件里找不到。
            # 触发结构自愈，无需人工干预。
            logger.warning(f"⚠️  [{db_name}] 迁移链断裂（迁移可能已被重置）: {err_msg}")
            # 先还原 CWD，再进入自愈（自愈函数内部自管 CWD）
            os.chdir(original_cwd)
            _heal_orphan_revision(db_name, db_path, base_dir)
        else:
            logger.error(f"❌ [{db_name}] Upgrade failed: {e}")
            raise e
    finally:
        # 确保 CWD 始终复原
        try:
            os.chdir(original_cwd)
        except Exception:
            pass


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

