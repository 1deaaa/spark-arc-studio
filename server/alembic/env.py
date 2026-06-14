"""
Alembic migration environment configuration.

Supports:
- users.db: User accounts, sessions, chat messages, shares (UserInfo base)
- llm_config.db: LLM platforms and model configs (matchbox Base)

Usage:
1. Generate migration: alembic -x db=users revision --autogenerate -m "description"
2. Apply migration: alembic -x db=users upgrade head
3. Rollback: alembic -x db=users downgrade -1

Features:
- 智能重命名检测：自动检测同表同类型的 drop + add 操作，提示可能是重命名
- 危险操作警告：生成迁移时检测 drop_column/drop_table 等危险操作并要求确认

⚠️ 注意：本项目实施绝对严格的禁止手写和修改迁移文件规定。
在调整表结构时，只允许修改 models.py并执行 gen_migration.py。
不得尝试触碰生成的脚本！否则可能破坏自愈机制和结构链。
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
from core.models import SqliteJSONB
from core.migration_specs import get_database_url, load_metadata

# Alembic Config object
config = context.config

# Setup logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

# ========================================
# Database Configuration
# ========================================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DATABASES = {
    "users": {
        "url": get_database_url("users"),
        "metadata": None,
    },
    "llm": {
        "url": get_database_url("llm"),
        "metadata": None,
    },
}


def _is_internal_table(name: str) -> bool:
    if not name:
        return False
    return name == "alembic_version" or name == "sqlite_sequence" or name.startswith("_alembic_tmp_")


def _include_object(obj, name, type_, reflected, compare_to):
    if type_ == "table":
        return not _is_internal_table(name)
    if type_ == "column":
        try:
            table_name = obj.table.name
        except Exception:
            table_name = ""
        return not _is_internal_table(table_name)
    return True


def _render_item(type_, obj, autogen_context):
    if type_ == "type" and isinstance(obj, SqliteJSONB):
        autogen_context.imports.add("from core.models import SqliteJSONB")
        return "SqliteJSONB()"
    return False


# Determine target metadata based on db argument
# 如果不分离 metadata，autogenerate 会试图在 LLM 库中创建 Users 表（因为 metadata 包含所有），
# 导致检测到冲突或错误的迁移操作。
# 优先从 config section 获取 db name (当使用 -n users 时)
section = config.config_ini_section
if section in ("users", "llm"):
    db_name = section
else:
    db_name = context.get_x_argument(as_dictionary=True).get("db", "users")

try:
    target_metadata = load_metadata(db_name)
    DATABASES[db_name]["metadata"] = target_metadata
except ImportError:
    # Fallback if dependencies are missing (e.g. in incorrect Env). Autogenerate
    # should fail loudly rather than producing an invalid empty migration.
    target_metadata = None


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
    1. 假如没有检测到变更，阻止生成空迁移文件。
    2. 检测危险操作 (Drop Table, Drop Column) 并警告。
    3. 尝试识别重命名 (Drop Column A + Add Column B)。
    """
    # 仅在 autogenerate 模式下生效
    if not context.config.cmd_opts or not getattr(context.config.cmd_opts, 'autogenerate', False):
        return

    script = directives[0]
    
    # 1. 检查是否为空迁移
    # 如果没有 upgrade ops，或者 ops 为空，说明没有变更
    if script.upgrade_ops.is_empty():
        print(f"\nℹ️  No database model changes detected.")
        directives[:] = [] # Clear directive list to prevent file generation
        return

    ops_list = script.upgrade_ops.ops
    
    def process_ops_list(ops_collection, table_name=None):
        # 提取当前层级的 drops 和 adds
        drops = []
        adds = []
        others = []
        
        # 索引映射
        drop_indices = {}
        add_indices = {}
        
        # 暂存 modifying ops 以便递归
        sub_modify_ops = []

        new_ops = []
        
        for idx, op in enumerate(ops_collection):
            if isinstance(op, ops.ModifyTableOps):
                # 递归处理子操作
                process_ops_list(op.ops, op.table_name)
                # 如果处理后子操作非空，或者原意保留空？一般保留
                new_ops.append(op)
            elif isinstance(op, ops.DropColumnOp):
                drops.append(op)
                drop_indices[len(drops)-1] = idx
            elif isinstance(op, ops.AddColumnOp):
                adds.append(op)
                add_indices[len(adds)-1] = idx
            else:
                 new_ops.append(op)

        # 如果没有成对的 drop/add，直接返回（如果是在 ModifyTableOps 内部，我们不能简单的 append 到 new_ops，因为顺序问题）
        # 这里为了简单，我们先把 non-drop/add 的放进去? 
        # 不，原地修改 list 比较困难，我们用 reconstruction 策略。
        
        # 简化策略：
        # 我们只在当前层级寻找匹配。
        # 对于 ModifyTableOps，递归调用已经原地修改了 op.ops
        
        # 现在处理当前层级 (可能是 top level，也可能是 ModifyTableOps 内部)
        # 如果 drops 和 adds 都有值，尝试匹配
        
        if not drops or not adds:
            return # 无需处理
            
        handled_drops = set()
        handled_adds = set()
        
        replacements = [] # list of (original_op, new_op) or just list of ops to append
        
        t_name = table_name # 如果在 ModifyTableOps 内，已有 table_name
        
        for i, drop_op in enumerate(drops):
            if i in handled_drops: continue
            
            # 如果是 top level，drop_op 有 table_name。如果是 nested，可能也带，但通常 ModifyTableOps 覆盖。
            current_table = t_name if t_name else drop_op.table_name
            
            for j, add_op in enumerate(adds):
                if j in handled_adds: continue
                
                target_table = t_name if t_name else add_op.table_name
                
                if current_table == target_table:
                   # 发现同表一删一增
                    print(f"\n🔍 [Rename Detection] Found in table '{current_table}':")
                    print(f"   - To drop: {drop_op.column_name}")
                    print(f"   - To add: {add_op.column.name} (type: {add_op.column.type})")
                    
                    force_rename = os.environ.get("SPARKARC_AUTOGEN_FORCE_RENAME") == "1"
                    
                    if force_rename:
                        print(f"   🤖 [Auto mode] Treating as rename.")
                        user_input = 'y'
                    elif os.environ.get("SPARKARC_AUTOGEN_NO_INTERACTIVE") == "1":
                         pass # Skip interactive
                         user_input = 'n'
                    else:
                        user_input = input("   👉 Is this a [RENAME] operation? (y/n, default n): ").lower().strip()
                        
                    if user_input == 'y':
                        # Make AlterColumnOp
                        rename_op = ops.AlterColumnOp(
                            current_table,
                            drop_op.column_name,
                            modify_name=add_op.column.name,
                            new_column_name=add_op.column.name,
                            existing_type=add_op.column.type
                        )
                        # 我们需要替换原有的 drop 和 add
                        # 这在 list reconstruction 中比较麻烦。
                        # 我们采用两步法：
                        # 1. 标记 handle
                        # 2. 重建 list
                        handled_drops.add(drop_op) # Use object identity
                        handled_adds.add(add_op)
                        replacements.append(rename_op)
                        print(f"   ✅ Converted to rename operation.")
                        break
        
        # Reconstruct ops_collection IN PLACE
        # 原始列表包含了 modify_ops, drops, adds, others
        # 我们保留顺序有些困难，但 Alembic ops 顺序通常 drops first?
        # 不重要，只要都在。
        # 简单清空原列表，填入新的
        
        final_list = []
        
        # 注意：我们需要保持原有 ModifyTableOps 和 others 的位置？
        # 或者直接: [valid_drops] + [valid_adds] + [others] + [replacements] + [modify_ops] ?
        # 最好按原序遍历，如果是在 handled 中则跳过，最后追加 replacements。
        
        for op in ops_collection:
            if isinstance(op, ops.ModifyTableOps):
                final_list.append(op) # 已经递归处理过
            elif op in handled_drops:
                pass
            elif op in handled_adds:
                pass
            else:
                final_list.append(op)
                
        final_list.extend(replacements)
        
        # Replace contents
        ops_collection[:] = final_list
        
    process_ops_list(ops_list)
    
    # 3. 检查危险操作 (Drop) 并确认
    # 再次遍历 (flatten) 来检查剩余的 Drop
    def check_dangerous(ops_iter):
        danger = []
        for op in ops_iter:
            if isinstance(op, ops.ModifyTableOps):
                danger.extend(check_dangerous(op.ops))
            elif isinstance(op, ops.DropColumnOp):
                if not _is_internal_table(op.table_name):
                    danger.append(f"❌ Drop column: {op.table_name}.{op.column_name}")
            elif isinstance(op, ops.DropTableOp):
                if not _is_internal_table(op.table_name):
                    danger.append(f"❌ Drop table: {op.table_name}")
        return danger

    dangerous_ops = check_dangerous(script.upgrade_ops.ops)
            
    if dangerous_ops:
        print("\n" + "!"*60)
        print("⚠️  WARNING: Generated migration contains the following [DANGEROUS OPERATIONS]:")
        for msg in dangerous_ops:
            print("   " + msg)
        print("!"*60)
        
        auto_yes = os.environ.get("SPARKARC_AUTOGEN_YES") == "1"
        if auto_yes:
            confirm = "y"
        else:
            confirm = input("\n👉 Confirm you want to include these drop operations? (y/n): ").lower().strip()
            
        if confirm != 'y':
            print("\n⛔ Cancelled. All migration operations cleared.")
            directives[:] = [] # Clear directives, do not generate file
            return

    # 4. 最终确认
    # 如果处理后为空?
    if script.upgrade_ops.is_empty():
         directives[:] = []


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
        include_object=_include_object,
        process_revision_directives=process_revision_directives, # 注入钩子
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Run migrations in online mode.
    
    Connects to database and executes migrations.
    """
    # 优先从 config section 获取 db name (当使用 -n users 时)
    section = config.config_ini_section
    if section in ("users", "llm"):
        db_name = section
    else:
        db_name = context.get_x_argument(as_dictionary=True).get("db", "users")

    db_config = DATABASES.get(db_name, DATABASES["users"])
    
    url = db_config["url"]
    target_meta = db_config["metadata"]
    
    is_sqlite = url.startswith("sqlite:")
    # SQLite 迁移使用 NullPool 避免文件锁残留；PostgreSQL 也保持短连接，迁移完成即释放。
    connectable = create_engine(url, poolclass=pool.NullPool)

    with connectable.connect() as connection:
        if is_sqlite:
            from sqlalchemy import text
            db_list = connection.execute(text("PRAGMA database_list")).fetchall()
            print(f"DEBUG: Connected databases: {db_list}")

        # Clean up leftover temp tables from interrupted batch operations.
        if is_sqlite:
            from sqlalchemy import text
            temp_tables = connection.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '_alembic_tmp_%'")
            ).fetchall()
            for (name,) in temp_tables:
                connection.execute(text(f"DROP TABLE IF EXISTS {name}"))

        context.configure(
            connection=connection,
            target_metadata=target_meta,
            # SQLite 的 ALTER TABLE 能力有限，只有 SQLite 需要 batch mode。
            render_as_batch=is_sqlite,
            # Compare type differences
            compare_type=True,
            include_object=_include_object,
            render_item=_render_item,
            process_revision_directives=process_revision_directives, # 注入钩子
        )

        with context.begin_transaction():
            context.run_migrations()
        
        # 显式提交（虽然 begin_transaction 会自动提交，但在某些 SQLite 环境下双保险）
        connection.commit()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

