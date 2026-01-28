#!/usr/bin/env python
"""
生成新的数据库迁移脚本

用法:
    python gen_migration.py users "add_new_field"
    python gen_migration.py llm "update_model_schema"

功能：
    - 调用 Alembic 自动生成迁移脚本
    - 支持交互式检测【重命名】操作（不再需要手动修改文件）
    - 自动拦截【删除列/表】等危险操作并请求确认
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
    print("👉 请留意后续的交互提示：如果检测到字段重命名或删除，系统会询问你。")

    # 确保在 server 目录下运行
    server_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 构造命令
    # 注意：我们不捕获输出，以便让子进程直接与用户终端交互（输入/输出）
    cmd = [
        sys.executable, "-m", "alembic",
        "-x", f"db={db}",
        "revision", "--autogenerate",
        "-m", msg,
        f"--head={db}@head"
    ]

    try:
        # 执行
        result = subprocess.run(cmd, cwd=server_dir)

        if result.returncode == 0:
            print("\n✅ 流程结束。")
            print("   如果有新生成的迁移文件，请在 alembic/versions/ 目录下查看确认。")
            print("   下次重启服务时将自动应用此更改。")
        else:
            print("\n❌ 生成失败或被取消")
            sys.exit(result.returncode)
            
    except KeyboardInterrupt:
        print("\n⛔ 用户中断操作")
        sys.exit(1)

if __name__ == "__main__":
    main()
