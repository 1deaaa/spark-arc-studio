import os
import sys
import subprocess
import logging

# 配置日志
logger = logging.getLogger("alembic_runner")
logging.basicConfig(level=logging.INFO)

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

    logger.info("🔄 开始执行数据库自动迁移...")
    
    # 构造通用环境变量 (确保 UTF-8)
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    
    try:
        # 1. 迁移 Users 数据库 (分支: users)
        logger.info("  > 正在迁移 [users] 数据库...")
        # upgrade users@head
        cmd_users = [sys.executable, "-m", "alembic", "-x", "db=users", "upgrade", "users@head"]
        result = subprocess.run(
            cmd_users, 
            cwd=base_dir, 
            env=env,
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            logger.error(f"❌ [users] 迁移失败:\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}")
            raise RuntimeError(f"Users DB migration failed with code {result.returncode}")
        else:
            logger.info("  ✅ [users] 数据库迁移完成")
            logger.debug(result.stdout)

        # 2. 迁移 LLM 数据库 (分支: llm)
        logger.info("  > 正在迁移 [llm] 数据库...")
        # upgrade llm@head
        cmd_llm = [sys.executable, "-m", "alembic", "-x", "db=llm", "upgrade", "llm@head"]
        result_llm = subprocess.run(
            cmd_llm, 
            cwd=base_dir, 
            env=env,
            capture_output=True,
            text=True
        )
        
        if result_llm.returncode != 0:
            logger.error(f"❌ [llm] 迁移失败:\nSTDOUT: {result_llm.stdout}\nSTDERR: {result_llm.stderr}")
            raise RuntimeError(f"LLM DB migration failed with code {result_llm.returncode}")
        else:
            logger.info("  ✅ [llm] 数据库迁移完成")
            logger.debug(result_llm.stdout)
            
        logger.info("✨ 所有数据库迁移已完成！")
        
    except Exception as e:
        logger.error(f"❌ 自动迁移执行异常: {e}")
        raise e
