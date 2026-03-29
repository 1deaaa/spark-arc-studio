#!/bin/sh
# ============================================================
# SparkArc 容器启动入口脚本
# ============================================================
# 解决 Docker Volume 挂载导致代码文件被旧数据"遮蔽"的问题。
#
# 原理：
#   构建镜像时，将 llm_mgr 的代码文件备份到 /_pristine_code/ 目录。
#   每次容器启动时，将备份的代码文件同步回挂载目录，
#   而数据文件（.db, .yaml, .json, .env）保持 Volume 中的版本不变。
# ============================================================

PRISTINE_DIR="/_pristine_code/agen_matchbox"
TARGET_DIR="/app/server/llm/agen_matchbox"

# 如果备份目录存在，执行代码同步
if [ -d "$PRISTINE_DIR" ]; then
    echo "🔄 同步 llm_mgr 代码文件..."

    # 同步所有 .py 文件（包括新增的）
    find "$PRISTINE_DIR" -name "*.py" | while read src; do
        # 计算相对路径并拼接目标路径
        rel_path="${src#$PRISTINE_DIR/}"
        dest="$TARGET_DIR/$rel_path"

        # 确保目标子目录存在
        dest_dir=$(dirname "$dest")
        mkdir -p "$dest_dir"

        # 覆盖目标文件
        cp -f "$src" "$dest"
    done

    echo "✅ 代码同步完成"
fi

# 启动应用
exec "$@"

