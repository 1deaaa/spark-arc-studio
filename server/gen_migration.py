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
    - 正确处理 users 和 llm 两个数据库分支
    - 依赖 env.py 中的逻辑来：
        1. 自动忽略空迁移（无变更不生成文件）
        2. 拦截危险操作
        3. 识别重命名
"""
import sys
import os
import subprocess
from datetime import datetime

VALID_DBS = ("users", "llm")

def _default_message(db_name: str) -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"auto_{db_name}_{ts}"

def run_gen(db: str, message: str):
    """
    运行 alembic revision --autogenerate
    """
    server_dir = os.path.dirname(os.path.abspath(__file__))
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    
    # 1. 先尝试升级数据库到最新 (Upgrade to head)
    # 这确保 autogenerate 可以在最新的基准上对比
    # 使用 -n {db} 读取 alembic.ini 中的对应 section (包含 version_locations)
    # 并添加 -x db={db} 以确保 env.py 能正确获取目标数据库名称
    
    upgrade_cmd = [
        sys.executable, "-m", "alembic",
        "-n", db,
        "-x", f"db={db}",
        "upgrade", "head"
    ]
    print(f"\n🔄 [Alembic] 正在同步 [{db}] 数据库到最新版本...")
    try:
        ur = subprocess.run(upgrade_cmd, cwd=server_dir, env=env)
        if ur.returncode != 0:
            print(f"❌ [{db}] 数据库同步失败，无法生成新的迁移。")
            return False
    except Exception as e:
        print(f"❌ 升级异常: {e}")
        return False
    
    # 2. 生成新迁移 (Generate revision)
    # 同样使用 -n {db} 和 -x db={db}
    cmd = [
        sys.executable, "-m", "alembic",
        "-n", db,
        "-x", f"db={db}",
        "revision", "--autogenerate",
        "-m", message,
        "--head=head"
    ]
    
    print(f"🔄 [Alembic] 正在为 [{db}] 数据库检测变更...")
    print(f"   (Command: {' '.join(cmd)})")

    try:
        result = subprocess.run(cmd, cwd=server_dir, env=env)
        if result.returncode != 0:
            print(f"❌ [{db}] 生成失败 (Code: {result.returncode})")
            return False
        else:
            return True
    except KeyboardInterrupt:
        print("\n⛔ 用户中断")
        return False
    except Exception as e:
        print(f"❌ 执行异常: {e}")
        return False

def main():
    args = sys.argv[1:]
    
    target_dbs = list(VALID_DBS)
    message = None
    
    # 解析参数
    # 情况1: python gen_migration.py users "msg"
    # 情况2: python gen_migration.py "msg" (全量)
    # 情况3: python gen_migration.py users
    
    if len(args) >= 1:
        if args[0] in VALID_DBS:
            target_dbs = [args[0]]
            if len(args) >= 2:
                message = args[1]
        else:
            # 假设第一个参数是 message，意味着针对所有 DB
            target_dbs = list(VALID_DBS)
            message = args[0]
            
    server_dir = os.path.dirname(os.path.abspath(__file__))
    
    print("🚀 开始运行迁移生成脚本...")
    
    for db in target_dbs:
        db_msg = message if message else _default_message(db)
        if not run_gen(db, db_msg):
            sys.exit(1)
            
    print("\n✨ 所有操作已完成。")

if __name__ == "__main__":
    main()
