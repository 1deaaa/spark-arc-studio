#!/bin/sh
# ============================================================
# SparkArc 容器启动入口脚本
# ============================================================
# 解决 Docker Volume/Bind Mount 挂载导致 Git 已更新文件被旧持久化文件遮蔽的问题。
#
# 同步策略：
#   1) 构建镜像时，将“需要受 Git 更新管理的目录快照”备份到 /_pristine_code。
#   2) 每次容器启动时，把这些受管文件覆盖回挂载目录。
#   3) 同时清理“上一版本受管、当前版本已删除”的陈旧文件。
#   4) 非受管数据（如 *.db、.env）不覆盖不删除，保持持久化。
# ============================================================

set -eu

MANAGED_MANIFEST_NAME=".sparkarc_managed_manifest"

is_preserved_runtime_file() {
    target_dir="$1"
    rel_path="$2"

    case "$rel_path" in
        *.db|*.db-journal|*.db-wal|*.db-shm|.env|matchbox_state.json|notices.json)
            return 0
            ;;
    esac

    case "$target_dir" in
        */shares_data)
            case "$rel_path" in
                ver_*.md)
                    return 0
                    ;;
            esac
            ;;
    esac

    return 1
}

sync_managed_dir() {
    src_dir="$1"
    target_dir="$2"

    if [ ! -d "$src_dir" ]; then
        return
    fi

    echo "[sync] 同步受管目录: $target_dir"
    mkdir -p "$target_dir"

    new_manifest="$target_dir/${MANAGED_MANIFEST_NAME}.new"
    : > "$new_manifest"

    # 复制当前版本受管文件（排除运行时数据文件）
    find "$src_dir" -type f | while read -r src_file; do
        rel_path="${src_file#$src_dir/}"

        case "$rel_path" in
            "$MANAGED_MANIFEST_NAME"|"$MANAGED_MANIFEST_NAME.new")
                continue
                ;;
        esac

        if is_preserved_runtime_file "$target_dir" "$rel_path"; then
            continue
        fi

        dest="$target_dir/$rel_path"
        dest_dir=$(dirname "$dest")
        mkdir -p "$dest_dir"
        cp -f "$src_file" "$dest"
        printf '%s\n' "$rel_path" >> "$new_manifest"
    done

    # 清理当前版本已删除的旧受管文件（首次部署后也生效）
    find "$target_dir" -type f | while read -r target_file; do
        rel_path="${target_file#$target_dir/}"

        case "$rel_path" in
            "$MANAGED_MANIFEST_NAME"|"$MANAGED_MANIFEST_NAME.new")
                continue
                ;;
            *.py|*.yaml|*.yml|*.json|*.toml|*.ini|*.cfg|*.txt|*.md|*.png|*.jpg|*.jpeg|*.gif|*.webp|*.svg|*.sh|requirements.txt|LICENSE|README|README.*)
                ;;
            *)
                continue
                ;;
        esac

        if is_preserved_runtime_file "$target_dir" "$rel_path"; then
            continue
        fi

        if ! grep -Fqx "$rel_path" "$new_manifest"; then
            rm -f "$target_file"
        fi
    done

    # 原子替换 manifest
    mv -f "$new_manifest" "$target_dir/$MANAGED_MANIFEST_NAME"
}

sync_managed_dir "/_pristine_code/server/llm/agen_matchbox" "/app/server/llm/agen_matchbox"
sync_managed_dir "/_pristine_code/server/data" "/app/server/data"
sync_managed_dir "/_pristine_code/server/shares_data" "/app/server/shares_data"

echo "✅ 受管文件同步完成"

# 启动应用
exec "$@"

