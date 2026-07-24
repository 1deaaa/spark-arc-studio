#!/usr/bin/env bash
# pyloader.unix.sh - Universal Portable Python Environment Deployer for Linux/macOS
# Uses python-build-standalone (github.com/astral-sh/python-build-standalone)
# for a truly portable Python with ZERO system impact.
#
# Deployment flow:
#   Step 1: Download python-build-standalone archive
#   Step 2: Extract to .runtime/python/
#   Step 3: Run init_env.py if exists (project-specific optional hook)
#   Step 4: pip install -r requirements.txt if exists
#   Then write .deploy_complete marker.
#
# Minimum: Linux 2.6+ / macOS 10.12+ with bash and curl.

set -e

# ===== PYTHON VERSION CONFIG =====
PYTHON_MAJOR_MINOR="3.13"
PYTHON_VERSION="${PYLOADER_PYTHON_VERSION:-3.13.1}"
PYTHON_RELEASE_TAG="${PYLOADER_PYTHON_RELEASE_TAG:-20241206}"
# ============================================================

# ===== PATHS =====
BASE_DIR="$(cd "$(dirname "$0")" && pwd)"
RUNTIME_ROOT="$BASE_DIR/.runtime"
ENV_DIR="$RUNTIME_ROOT/python"
MARKER_FILE="$ENV_DIR/.deploy_complete"
REQ_HASH_FILE="$ENV_DIR/.requirements.sha256"
PYTHON_EXE="$ENV_DIR/bin/python3"
INIT_SCRIPT="$BASE_DIR/init_env.py"
REQ_FILE="$BASE_DIR/requirements.txt"
PROJECT_ROOT="$(cd "$BASE_DIR/.." && pwd)"
SPARKARC_CONFIG="$PROJECT_ROOT/sparkarc.json"

# ===== MIRROR CONFIG =====
# 本脚本开头会根据出口 IP 自动探测网络区域并选择镜像。
# 环境变量 PYLOADER_* 仅作为高级用户覆盖手段；正常使用无需设置。
PIP_MIRROR="${PYLOADER_PIP_MIRROR:-}"
PYTHON_MIRROR_BASE="${PYLOADER_PYTHON_MIRROR_BASE:-}"

read_network_config() {
    local resource="$1"
    local country="${2:-}"
    if ! command -v python3 >/dev/null 2>&1; then
        error "python3 is required to read $SPARKARC_CONFIG before portable Python is installed."
        exit 1
    fi
    python3 - "$SPARKARC_CONFIG" "$resource" "$country" <<'PY'
import json
import sys

path, resource, country = sys.argv[1:]
with open(path, encoding="utf-8") as stream:
    config = json.load(stream)
route = config["network"]["resources"][resource]
preferred = route["mainland"] if country == "CN" else route["default"]
fallback = route["default"] if country == "CN" else route["mainland"]
for value in [*preferred, *fallback]:
    if isinstance(value, str) and value.strip():
        print(value.strip())
        break
PY
}

read_geoip_providers() {
    if ! command -v python3 >/dev/null 2>&1; then
        return 0
    fi
    python3 - "$SPARKARC_CONFIG" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as stream:
    config = json.load(stream)
for value in config["network"]["geoIpProviders"]:
    if isinstance(value, str) and value.strip():
        print(value.strip())
PY
}

# 探测 IP 归属地（中国大陆返回 CN），失败时返回空字符串。
detect_country_code() {
    local provider code candidate total best_code="" best_count=0 tied=0
    local codes=()
    local seen=" "

    while IFS= read -r provider; do
        code=""
        if command -v curl >/dev/null 2>&1; then
            code="$(curl --noproxy '*' -fsSL --max-time 3 "$provider" 2>/dev/null | \
                python3 -c "import sys,json; d=json.load(sys.stdin); print((d.get('countryCode') or d.get('country_code') or d.get('country') or '').strip().upper())" 2>/dev/null)" || true
        fi
        if [ "${#code}" -eq 2 ]; then
            codes+=("$code")
        fi
    done < <(read_geoip_providers)

    for candidate in "${codes[@]}"; do
        case "$seen" in
            *" $candidate "*) continue ;;
        esac
        seen+="$candidate "
        total=0
        for code in "${codes[@]}"; do
            if [ "$code" = "$candidate" ]; then
                total=$((total + 1))
            fi
        done
        if [ "$total" -gt "$best_count" ]; then
            best_code="$candidate"
            best_count="$total"
            tied=0
        elif [ "$total" -eq "$best_count" ]; then
            tied=1
        fi
    done

    if [ "$best_count" -ge 2 ] && [ "$tied" -eq 0 ]; then
        echo "$best_code"
        return 0
    fi
    echo ""
    return 1
}

resolve_mirrors() {
    if [ -n "$PIP_MIRROR" ] && [ -n "$PYTHON_MIRROR_BASE" ]; then
        # 调用方已显式覆盖，不再探测
        return 0
    fi

    local country=""
    country="$(detect_country_code)"

    if [ -z "$PIP_MIRROR" ]; then
        PIP_MIRROR="$(read_network_config pypi "$country")"
    fi
    if [ -z "$PYTHON_MIRROR_BASE" ]; then
        PYTHON_MIRROR_BASE="$(read_network_config python_standalone "$country")"
    fi

    if [ "$country" = "CN" ]; then
        log "Detected mainland China network (CN), using configured domestic candidates."
    else
        log "Network region: ${country:-UNKNOWN}, using configured default candidates."
    fi
}

# ===== COLORS =====
COLOR_YELLOW='\033[1;33m'
COLOR_GREEN='\033[1;32m'
COLOR_RED='\033[1;31m'
COLOR_RESET='\033[0m'

log() { echo -e "${COLOR_YELLOW}[pyloader]${COLOR_RESET} $*"; }
error() { echo -e "${COLOR_RED}[ERROR]${COLOR_RESET} $*" >&2; }

resolve_mirrors

# ===== PLATFORM DETECTION =====
detect_platform() {
    local uname_s uname_m
    uname_s="$(uname -s)"
    uname_m="$(uname -m)"

    case "$uname_s" in
        Linux*)     OS=unknown-linux-gnu ;;
        Darwin*)    OS=apple-darwin ;;
        *)          error "Unsupported OS: $uname_s"; exit 1 ;;
    esac

    case "$uname_m" in
        x86_64|amd64)   ARCH=x86_64 ;;
        arm64|aarch64)  ARCH=aarch64 ;;
        *)              error "Unsupported architecture: $uname_m"; exit 1 ;;
    esac
}

# ===== HELPERS =====
get_current_python_version() {
    if [ ! -x "$PYTHON_EXE" ]; then
        echo ""
        return
    fi
    "$PYTHON_EXE" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')" 2>/dev/null || echo ""
}

get_requirements_hash() {
    if [ ! -f "$REQ_FILE" ]; then
        echo ""
        return
    fi
    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum "$REQ_FILE" | awk '{print $1}'
    else
        shasum -a 256 "$REQ_FILE" | awk '{print $1}'
    fi
}

get_stored_hash() {
    if [ ! -f "$REQ_HASH_FILE" ]; then
        echo ""
        return
    fi
    head -n 1 "$REQ_HASH_FILE" 2>/dev/null | tr -d '[:space:]'
}

file_size() {
    local path="$1"
    # macOS uses stat -f%z, Linux uses stat -c%s
    stat -f%z "$path" 2>/dev/null || stat -c%s "$path" 2>/dev/null || echo 0
}

resolve_archive_url() {
    detect_platform
    local archive_name="cpython-${PYTHON_VERSION}%2B${PYTHON_RELEASE_TAG}-${ARCH}-${OS}-install_only.tar.gz"
    # PYTHON_MIRROR_BASE 已根据网络区域自动选择：国内用 USTC 镜像，海外用 GitHub 官方
    if [ "$PYTHON_MIRROR_BASE" = "https://github.com" ]; then
        echo "https://github.com/astral-sh/python-build-standalone/releases/download/${PYTHON_RELEASE_TAG}/${archive_name}"
    else
        echo "${PYTHON_MIRROR_BASE}/github-release/astral-sh/python-build-standalone/LatestRelease/${archive_name}"
    fi
}

download_file() {
    local url="$1"
    local out="$2"
    if command -v curl >/dev/null 2>&1; then
        curl -fsSL --max-time 180 -o "$out" "$url"
    else
        error "curl is required but not installed."
        exit 1
    fi
}

extract_archive() {
    local archive="$1"
    local dest="$2"
    log "Extracting Python to $dest ..."
    rm -rf "$dest"
    mkdir -p "$dest"
    tar -xzf "$archive" -C "$dest" --strip-components=1
}

# ===== MAIN =====
main() {
    log "Running environment deployment..."

    local current_version stored_hash current_hash
    current_version="$(get_current_python_version)"
    current_hash="$(get_requirements_hash)"
    stored_hash="$(get_stored_hash)"

    if [ -f "$MARKER_FILE" ] && [ -n "$current_version" ] && \
       echo "$current_version" | grep -q "^${PYTHON_MAJOR_MINOR}\." && \
       { [ -z "$current_hash" ] || [ "$current_hash" = "$stored_hash" ]; }; then
        log "Already deployed with Python $current_version. Skipping."
        exit 0
    fi

    if [ -f "$MARKER_FILE" ] && [ -n "$current_version" ] && \
       echo "$current_version" | grep -q "^${PYTHON_MAJOR_MINOR}\." && \
       [ "$current_hash" != "$stored_hash" ]; then
        log "requirements.txt changed. Refreshing environment packages."
    fi

    local archive_url archive_local
    archive_url="$(resolve_archive_url)"
    archive_local="$RUNTIME_ROOT/$(basename "$archive_url")"

    mkdir -p "$RUNTIME_ROOT"

    if [ ! -f "$archive_local" ]; then
        log "Downloading Python ${PYTHON_VERSION} standalone ..."
        log "      Source: $archive_url"
        download_file "$archive_url" "$archive_local"
    else
        log "Found local archive: $(basename "$archive_local")"
    fi

    local size
    size="$(file_size "$archive_local")"
    if [ "$size" -lt 1048576 ]; then
        error "Downloaded file too small, likely an error page"
        rm -f "$archive_local"
        exit 1
    fi

    extract_archive "$archive_local" "$ENV_DIR"
    rm -f "$archive_local"

    log "${COLOR_GREEN}Python extracted to .runtime/python/${COLOR_RESET}"

    # ---- Step 3: Run project-specific init script (if exists) ----
    if [ -f "$INIT_SCRIPT" ]; then
        log "Running init_env.py (project-specific setup) ..."
        "$PYTHON_EXE" -X utf8 "$INIT_SCRIPT" || { error "init_env.py failed."; exit 1; }
    else
        log "No init_env.py found, skipping."
    fi

    # ---- Step 4: Install standard requirements.txt (if exists) ----
    if [ -f "$REQ_FILE" ]; then
        log "Installing requirements.txt ..."
        "$PYTHON_EXE" -X utf8 -m pip install --isolated --no-user -i "$PIP_MIRROR" -r "$REQ_FILE" || \
            { error "pip install -r requirements.txt failed."; exit 1; }
    else
        log "No requirements.txt found, skipping."
    fi

    # ---- Mark deployment as complete ----
    local marker_content
    marker_content="Deployed: $(date '+%Y-%m-%d %H:%M:%S') | Python $PYTHON_VERSION (standalone, zero-registry) | Release $PYTHON_RELEASE_TAG"
    echo "$marker_content" > "$MARKER_FILE"

    if [ -n "$current_hash" ]; then
        echo "$current_hash" > "$REQ_HASH_FILE"
    elif [ -f "$REQ_HASH_FILE" ]; then
        rm -f "$REQ_HASH_FILE"
    fi

    log "${COLOR_GREEN}========================================${COLOR_RESET}"
    log "${COLOR_GREEN}Deployment complete!${COLOR_RESET}"
    log "${COLOR_GREEN}========================================${COLOR_RESET}"
}

main "$@"
