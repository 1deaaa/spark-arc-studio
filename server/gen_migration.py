#!/usr/bin/env python
"""
生成新的数据库迁移脚本

用法:
    python gen_migration.py users "add_new_field"
    python gen_migration.py llm "update_model_schema"
"""
import sys
import os
import subprocess

def main():
    if len(sys.argv) < 3:
        print("用法: python gen_migration.py <db> <message>")
        print("  db: 'users' 或 'llm'")
        print("  message: 迁移说明，例如 'add_email_field'")
        print("\n示例:")
        print("  python gen_migration.py users \"增加手机号字段\"")
        sys.exit(1)

    db = sys.argv[1]
    msg = sys.argv[2]

    if db not in ("users", "llm"):
        print(f"❌ 错误: db 必须是 'users' 或 'llm'，收到: '{db}'")
        sys.exit(1)

    print(f"🔄 正在为 [{db}] 数据库生成迁移脚本...")

    # 确保在 server 目录下运行
    server_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 构造命令
    cmd = [
        sys.executable, "-m", "alembic",
        "-x", f"db={db}",
        "revision", "--autogenerate",
        "-m", msg,
        f"--head={db}@head"
    ]

    # 执行
    result = subprocess.run(cmd, cwd=server_dir)

    if result.returncode == 0:
        print("\n✅ 迁移脚本生成成功！")
        print("⚠️  重要提醒：")
        print("   请务必查看 alembic/versions/ 目录下新生成的 .py 文件。")
        print("   如果包含 'op.drop_column' 或 'op.drop_table' 等危险操作，请确认是否符合预期！")
        print("   特别是【改名】操作会被识别为删除+新增，需要手动改成 alter_column！")
        print("   下次重启服务时将自动应用此更改。")
    else:
        print("\n❌ 生成失败")
        sys.exit(1)

if __name__ == "__main__":
    main()
