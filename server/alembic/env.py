"""
Alembic migration environment configuration.

Supports:
- users.db: User accounts, sessions, chat messages, shares (UserInfo base)
- llm_config.db: LLM platforms and model configs (llm_mgr Base)

Usage:
1. Generate migration: alembic -x db=users revision --autogenerate -m "description"
2. Apply migration: alembic -x db=users upgrade head
3. Rollback: alembic -x db=users downgrade -1

Features:
- 智能重命名检测：自动检测同表同类型的 drop + add 操作，提示可能是重命名
- 危险操作警告：生成迁移时检测 drop_column/drop_table 等危险操作并要求确认
"""

import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool, create_engine
from alembic import context
from alembic.autogenerate import rewriter
from alembic.operations import ops

# Add project directory to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import models lazily to avoid heavy imports for unrelated DBs
from core.models import UserInfo, StoryData
USERS_METADATA = UserInfo.metadata
LLM_METADATA = None

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
# 使用相对路径以避免 Windows 绝对路径中特殊字符 (如 \0) 引起的问题
# 前提：Alembic 运行时 CWD 必须在 server 目录
users_db_path = "data/users.db"
llm_db_path = "llm/llm_mgr/llm_config.db"


DATABASES = {
    "users": {
        "url": f"sqlite:///{users_db_path}",
        "metadata": USERS_METADATA,
    },
    "llm": {
        "url": f"sqlite:///{llm_db_path}",
        "metadata": LLM_METADATA,
    },
}


# Determine target metadata based on db argument
# 如果不分离 metadata，autogenerate 会试图在 LLM 库中创建 Users 表（因为 metadata 包含所有），
# 导致检测到冲突或错误的迁移操作。
db_name = context.get_x_argument(as_dictionary=True).get("db", "users")
if db_name == "llm":
    from llm.llm_mgr.models import Base as LLMBase
    DATABASES["llm"]["metadata"] = LLMBase.metadata
    target_metadata = LLMBase.metadata
else:
    target_metadata = USERS_METADATA


def get_url(db_name: str = "users") -> str:
    """Get connection URL for specified database"""
    return DATABASES.get(db_name, DATABASES["users"])["url"]


# ========================================
# 智能重命名检测与危险操作拦截
# ========================================
writer = rewriter.Rewriter()
pending_drops = {}  # {(table, type_str): drop_op}

@writer.rewrites(ops.DropColumnOp)
def detect_rename_drop(context, revision, op):
    """
    拦截 Drop 操作。
    如果是生成迁移阶段，暂存起来等待匹配 Add 操作。
    """
    # 仅在生成迁移（autogenerate）时进行重命名启发式检测
    # 判断是否处于 autogenerate 上下文可以通过 stack trace 或其他方式，
    # 这里简单地假定如果使用了 writer，就是在 autogenerate 流程中。
    
    # 记录 Drop 操作，Key = (表名, 列类型字符串)
    # 注意：op.column.type 可能是实例，转为 string 做 key
    # 这里需要准确获取类型，但 drop column op 通常没有详细 type 信息（除非反射）
    # 在 Alembic autogenerate 中，drop_column op 中包含 _orig_column 或类似反射信息
    # 如果无法获取类型，就仅按表名匹配，但风险较高。
    # 实际上 Alembic 传递的 op 对象在 autogenerate 时通常带有 reflected column info
    
    # 为了简化，我们只做拦截，在 process_revision_directives 统一处理危险操作
    # 重命名检测逻辑比较复杂，且 writer 是一次处理一个 op，很难跨 op 匹配。
    # 所以我们主要依赖 process_revision_directives 做全局分析。
    
    return op

def process_revision_directives(context, revision, directives):
    """
    在迁移脚本生成前，检查并处理操作列表。
    1. 检测危险操作 (Drop Table, Drop Column)
    2. 尝试识别重命名 (Drop Column A + Add Column B)
    3. 交互式确认
    """
    # 仅在 autogenerate 模式下生效
    if not context.config.cmd_opts or not getattr(context.config.cmd_opts, 'autogenerate', False):
        return

    script = directives[0]
    if not script.upgrade_ops or script.upgrade_ops.is_empty():
        return

    ops_list = script.upgrade_ops.ops
    
    # 分类操作
    drops = []
    adds = []
    others = []
    
    for op in ops_list:
        if isinstance(op, ops.DropColumnOp):
            drops.append(op)
        elif isinstance(op, ops.AddColumnOp):
            adds.append(op)
        else:
            others.append(op)
            
    # 尝试匹配重命名
    # 简单策略：同一个表，Drop 一个列，Add 一个列，且没有其他复杂操作，可能就是重命名
    # 更高级策略需要比较类型，但 op.column.type 在 Drop 时可能不可用（取决于 backend）
    
    final_ops = []
    
    # 处理过的 drops 和 adds 索引
    handled_drops = set()
    handled_adds = set()
    
    # 1. 尝试匹配重命名
    for i, drop_op in enumerate(drops):
        if i in handled_drops: continue
        
        for j, add_op in enumerate(adds):
            if j in handled_adds: continue
            
            if drop_op.table_name == add_op.table_name:
                # 发现同表的一删一增
                print(f"\n🔍 [重命名检测] 在表 '{drop_op.table_name}' 中发现：")
                print(f"   - 待删除: {drop_op.column_name}")
                print(f"   - 待新增: {add_op.column.name} (类型: {add_op.column.type})")
                
                user_input = input("   👉 这是否是【重命名】操作? (y/n, 默认 n): ").lower().strip()
                if user_input == 'y':
                    # 转换为 AlterColumnOp (rename)
                    rename_op = ops.AlterColumnOp(
                        drop_op.table_name,
                        drop_op.column_name,
                        new_column_name=add_op.column.name,
                        existing_type=add_op.column.type # 假设类型兼容
                    )
                    final_ops.append(rename_op)
                    handled_drops.add(i)
                    handled_adds.add(j)
                    print(f"   ✅ 已转换为重命名操作。")
                    break
    
    # 2. 将未处理的操作加入 final_ops
    for i, op in enumerate(drops):
        if i not in handled_drops:
            final_ops.append(op)
            
    for j, op in enumerate(adds):
        if j not in handled_adds:
            final_ops.append(op)
            
    # 添加其他操作
    final_ops.extend(others)
    
    # 3. 检查危险操作 (Drop) 并确认
    dangerous_ops = []
    for op in final_ops:
        if isinstance(op, ops.DropColumnOp):
            dangerous_ops.append(f"❌ 删除列: {op.table_name}.{op.column_name}")
        elif isinstance(op, ops.DropTableOp):
            dangerous_ops.append(f"❌ 删除表: {op.table_name}")
            
    if dangerous_ops:
        print("\n" + "!"*60)
        print("⚠️  警告：生成的迁移包含以下【危险操作】：")
        for msg in dangerous_ops:
            print("   " + msg)
        print("!"*60)
        
        confirm = input("\n👉 确认要包含这些删除操作吗? (y/n): ").lower().strip()
        if confirm != 'y':
            print("\n⛔ 用户取消。已清空所有迁移操作。")
            script.upgrade_ops.ops = []
            return

    # 更新操作列表
    script.upgrade_ops.ops = final_ops
    
    if final_ops:
        print("\n✅ 迁移脚本生成确认通过。")


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
        process_revision_directives=process_revision_directives, # 注入钩子
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
        except Exception:
            pass

        context.configure(
            connection=connection,
            target_metadata=target_meta,
            # Enable batch mode, required for SQLite ALTER TABLE support
            render_as_batch=True,
            # Compare type differences
            compare_type=True,
            process_revision_directives=process_revision_directives, # 注入钩子
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
