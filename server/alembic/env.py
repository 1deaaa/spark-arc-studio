"""
Alembic migration environment configuration.

Supports:
- users.db: User accounts, sessions, chat messages, shares (UserInfo base)
- llm_config.db: LLM platforms and model configs (llm_mgr Base)

Usage:
1. Generate migration: alembic -x db=users revision --autogenerate -m "description"
2. Apply migration: alembic -x db=users upgrade head
3. Rollback: alembic -x db=users downgrade -1
"""

import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool, create_engine
from alembic import context

# Add project directory to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import all models so autogenerate can detect them
from core.models import UserInfo, StoryData
from llm.llm_mgr.models import Base as LLMBase

# Alembic Config object
config = context.config

# Setup logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ========================================
# Database Configuration
# ========================================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Database URL mapping
# Database URL mapping
# 使用相对路径以避免 Windows 绝对路径中特殊字符 (如 \0) 引起的问题
# 前提：Alembic 运行时 CWD 必须在 server 目录
users_db_path = "data/users.db"
llm_db_path = "llm/llm_mgr/llm_config.db"

# Database URL mapping
# 使用相对路径以避免 Windows 绝对路径中特殊字符 (如 \0) 引起的问题
# 前提：Alembic 运行时 CWD 必须在 server 目录
users_db_path = "data/users.db"
llm_db_path = "llm/llm_mgr/llm_config.db"


DATABASES = {
    "users": {
        "url": f"sqlite:///{users_db_path}",
        "metadata": UserInfo.metadata,
    },
    "llm": {
        "url": f"sqlite:///{llm_db_path}",
        "metadata": LLMBase.metadata,
    },
}

print(f"DEBUG: env.py BASE_DIR: {BASE_DIR}")
print(f"DEBUG: Users DB URL: {DATABASES['users']['url']}")

# Determine target metadata based on db argument
# 如果不分离 metadata，autogenerate 会试图在 LLM 库中创建 Users 表（因为 metadata 包含所有），
# 导致检测到冲突或错误的迁移操作。
db_name = context.get_x_argument(as_dictionary=True).get("db", "users")
if db_name == "llm":
    target_metadata = LLMBase.metadata
else:
    target_metadata = UserInfo.metadata


def get_url(db_name: str = "users") -> str:
    """Get connection URL for specified database"""
    return DATABASES.get(db_name, DATABASES["users"])["url"]


def run_migrations_offline() -> None:
    """
    Run migrations in offline mode.
    
    Only generates SQL scripts, does not execute.
    """
    db_name = context.get_x_argument(as_dictionary=True).get("db", "users")
    db_config = DATABASES.get(db_name, DATABASES["users"])
    
    url = db_config["url"]
    target_meta = db_config["metadata"]
    
    context.configure(
        url=url,
        target_metadata=target_meta,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Run migrations in online mode.
    
    Connects to database and executes migrations.
    """
    db_name = context.get_x_argument(as_dictionary=True).get("db", "users")
    db_config = DATABASES.get(db_name, DATABASES["users"])
    
    url = db_config["url"]
    target_meta = db_config["metadata"]
    
    connectable = create_engine(url)

    with connectable.connect() as connection:
        # DEBUG: Check actual database file
        try:
            from sqlalchemy import text
            db_list = connection.execute(text("PRAGMA database_list")).fetchall()
            print(f"DEBUG: Connected databases: {db_list}")
            tables = connection.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()
            print(f"DEBUG: Tables in DB: {tables}")
        except Exception as e:
            print(f"DEBUG: Check failed: {e}")

        context.configure(
            connection=connection,
            target_metadata=target_meta,
            # Enable batch mode, required for SQLite ALTER TABLE support
            render_as_batch=True,
            # Compare type differences
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
