"""本地嵌入服务进程管理。

本模块只管理可选的本地 OpenAI 兼容 embedding 服务，不直接参与向量索引
构建，避免把进程生命周期逻辑散落到路由或业务服务中。
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import threading
import time
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

import requests

from .embedding_contract import (
    QWEN3_EMBEDDING_DIMENSIONS,
    QWEN3_EMBEDDING_MAX_CONTEXT_TOKENS,
    QWEN3_EMBEDDING_MODEL,
)


LOCAL_EMBEDDING_BASE_URL = os.getenv("SPARKARC_LOCAL_EMBEDDING_BASE_URL", "http://127.0.0.1:18080/v1")
LOCAL_EMBEDDING_API_KEY = os.getenv("SPARKARC_LOCAL_EMBEDDING_API_KEY", "local-embedding")
LOCAL_EMBEDDING_MODEL_PATH = os.getenv("SPARKARC_LOCAL_EMBEDDING_MODEL_PATH", "")
LOCAL_EMBEDDING_SERVER_EXE = os.getenv("SPARKARC_LOCAL_EMBEDDING_SERVER_EXE", "llama-server")
LOCAL_EMBEDDING_THREADS = int(os.getenv("SPARKARC_LOCAL_EMBEDDING_THREADS", "0") or "0")
LOCAL_EMBEDDING_PARALLEL = int(os.getenv("SPARKARC_LOCAL_EMBEDDING_PARALLEL", "4") or "4")
LOCAL_EMBEDDING_BATCH = int(os.getenv("SPARKARC_LOCAL_EMBEDDING_BATCH", "2048") or "2048")
LOCAL_EMBEDDING_UBATCH = int(os.getenv("SPARKARC_LOCAL_EMBEDDING_UBATCH", "512") or "512")
LOCAL_EMBEDDING_STARTUP_TIMEOUT = float(os.getenv("SPARKARC_LOCAL_EMBEDDING_STARTUP_TIMEOUT", "120") or "120")
LOCAL_EMBEDDING_AUTO_DOWNLOAD_SERVER = os.getenv("SPARKARC_LOCAL_EMBEDDING_AUTO_DOWNLOAD_SERVER", "1").lower() not in {"0", "false", "no"}
LLAMA_CPP_RELEASE_TAG = os.getenv("SPARKARC_LLAMA_CPP_RELEASE_TAG", "b9632")
LLAMA_CPP_RELEASE_BASE_URL = os.getenv(
    "SPARKARC_LLAMA_CPP_RELEASE_BASE_URL",
    "https://github.com/ggml-org/llama.cpp/releases/download",
)
QWEN3_GGUF_REPO_ID = "Qwen/Qwen3-Embedding-0.6B-GGUF"
QWEN3_GGUF_FILENAME = "Qwen3-Embedding-0.6B-Q8_0.gguf"
QWEN3_GGUF_MIN_BYTES = 600 * 1024 * 1024

_lock = threading.Lock()
_process: subprocess.Popen | None = None
_alive_cache: tuple[float, bool] = (0.0, False)


def get_default_model_path() -> Path:
    """返回 SparkArc 默认本地 GGUF 模型缓存路径。"""
    server_root = Path(__file__).resolve().parents[2]
    return server_root / ".runtime" / "models" / "embedding" / QWEN3_GGUF_FILENAME


def get_llama_cpp_runtime_dir() -> Path:
    """返回 llama.cpp 预编译运行时缓存目录。"""
    configured = os.getenv("SPARKARC_LLAMA_CPP_RUNTIME_DIR", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    server_root = Path(__file__).resolve().parents[2]
    return server_root / ".runtime" / "llama.cpp"


def resolve_model_path() -> Path:
    """解析当前应使用的本地 GGUF 模型路径。"""
    configured = (LOCAL_EMBEDDING_MODEL_PATH or "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    return get_default_model_path()


def ensure_local_model_available() -> Path:
    """确保本地 Qwen3 Embedding 0.6B Q8 GGUF 文件存在，不存在则下载。"""
    target = resolve_model_path()
    if target.is_file() and target.stat().st_size >= QWEN3_GGUF_MIN_BYTES:
        return target

    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        from huggingface_hub import hf_hub_download
    except ImportError as exc:
        raise RuntimeError("缺少 huggingface_hub，无法自动下载本地嵌入模型") from exc

    downloaded = hf_hub_download(
        repo_id=QWEN3_GGUF_REPO_ID,
        filename=QWEN3_GGUF_FILENAME,
        local_dir=str(target.parent),
        local_dir_use_symlinks=False,
        resume_download=True,
    )
    downloaded_path = Path(downloaded).resolve()
    if downloaded_path != target and downloaded_path.is_file():
        if target.exists():
            target.unlink()
        downloaded_path.replace(target)
    if not target.is_file() or target.stat().st_size < QWEN3_GGUF_MIN_BYTES:
        raise RuntimeError(f"本地嵌入模型下载不完整：{target}")
    return target


def _llama_server_names() -> tuple[str, ...]:
    if os.name == "nt":
        return ("llama-server.exe", "llama-server")
    return ("llama-server",)


def _is_runnable_server(path: Path) -> bool:
    if not path.is_file():
        return False
    if os.name == "nt":
        return path.name.lower() == "llama-server.exe"
    return path.name == "llama-server"


def _make_executable(path: Path) -> None:
    if os.name != "nt" and path.is_file():
        path.chmod(path.stat().st_mode | 0o755)


def _find_cached_llama_server() -> Path | None:
    runtime_dir = get_llama_cpp_runtime_dir()
    if not runtime_dir.exists():
        return None
    for name in _llama_server_names():
        candidates = sorted(
            (path for path in runtime_dir.rglob(name) if _is_runnable_server(path)),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        if candidates:
            _make_executable(candidates[0])
            return candidates[0]
    return None


def _llama_cpp_asset_name(tag: str) -> str:
    system = platform.system().lower()
    machine = platform.machine().lower()
    is_arm = machine in {"arm64", "aarch64"}
    is_x64 = machine in {"x86_64", "amd64", "x64"}

    if system == "windows":
        return f"llama-{tag}-bin-win-arm64.zip" if is_arm else f"llama-{tag}-bin-win-cpu-x64.zip"
    if system == "linux":
        if is_arm:
            return f"llama-{tag}-bin-ubuntu-arm64.zip"
        if is_x64:
            return f"llama-{tag}-bin-ubuntu-x64.zip"

    raise RuntimeError(
        f"当前平台暂不支持自动下载 llama.cpp 预编译包：{platform.system()} {platform.machine()}。"
        "请手动安装 llama-server，或通过 SPARKARC_LOCAL_EMBEDDING_SERVER_EXE 指定路径。"
    )


def ensure_llama_server_available() -> Path:
    """确保 llama-server 可执行文件可用，优先复用项目 .runtime 缓存。"""
    cached = _find_cached_llama_server()
    if cached is not None:
        return cached

    if not LOCAL_EMBEDDING_AUTO_DOWNLOAD_SERVER:
        raise RuntimeError(
            "未找到 llama-server，且已禁用自动下载。请安装 llama.cpp server，"
            "或通过 SPARKARC_LOCAL_EMBEDDING_SERVER_EXE 指定可执行文件路径。"
        )

    tag = LLAMA_CPP_RELEASE_TAG.strip() or "b9632"
    asset_name = _llama_cpp_asset_name(tag)
    runtime_dir = get_llama_cpp_runtime_dir()
    runtime_dir.mkdir(parents=True, exist_ok=True)
    archive_path = runtime_dir / asset_name
    extract_dir = runtime_dir / asset_name.removesuffix(".zip")

    if not archive_path.is_file():
        url = f"{LLAMA_CPP_RELEASE_BASE_URL.rstrip('/')}/{tag}/{asset_name}"
        urllib.request.urlretrieve(url, archive_path)

    extract_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive_path, "r") as archive:
        archive.extractall(extract_dir)

    cached = _find_cached_llama_server()
    if cached is not None:
        return cached

    raise RuntimeError(f"已下载 llama.cpp 预编译包，但未找到 llama-server：{archive_path}")


def _base_endpoint(path: str) -> str:
    return LOCAL_EMBEDDING_BASE_URL.rstrip("/") + path


def resolve_server_executable() -> str:
    """解析 llama-server 可执行文件，兼容 Windows、Linux 与 Docker。"""
    executable = LOCAL_EMBEDDING_SERVER_EXE.strip() or "llama-server"
    candidate = Path(executable).expanduser()
    if candidate.is_absolute() or any(sep in executable for sep in ("/", "\\")):
        if candidate.is_file():
            return str(candidate)
        raise RuntimeError(f"本地嵌入服务可执行文件不存在：{candidate}")
    resolved = shutil.which(executable)
    if resolved:
        return resolved
    return str(ensure_llama_server_available())


def is_local_embedding_alive(timeout: float = 2.0, *, ttl: float = 2.0) -> bool:
    """探测本地 OpenAI 兼容服务是否可用。"""
    global _alive_cache
    now = time.monotonic()
    cached_at, cached_value = _alive_cache
    if ttl > 0 and now - cached_at < ttl:
        return cached_value
    try:
        response = requests.post(
            _base_endpoint("/embeddings"),
            headers={
                "Authorization": f"Bearer {LOCAL_EMBEDDING_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": QWEN3_EMBEDDING_MODEL,
                "input": "连通性测试",
                "dimensions": QWEN3_EMBEDDING_DIMENSIONS,
                "encoding_format": "float",
            },
            timeout=timeout,
        )
        if not response.ok:
            _alive_cache = (now, False)
            return False
        data = response.json()
        vector = (((data.get("data") or [{}])[0] or {}).get("embedding") or [])
        ok = len(vector) == QWEN3_EMBEDDING_DIMENSIONS
        _alive_cache = (now, ok)
        return ok
    except Exception:
        _alive_cache = (now, False)
        return False


def _build_command_for_model(model_path: Path, *, validate_executable: bool = True) -> list[str]:
    """基于给定模型路径构造 llama.cpp embedding 服务命令。"""

    host = "127.0.0.1"
    port = "18080"
    if "://" in LOCAL_EMBEDDING_BASE_URL:
        tail = LOCAL_EMBEDDING_BASE_URL.split("://", 1)[1].split("/", 1)[0]
        if ":" in tail:
            host, port = tail.rsplit(":", 1)

    executable = resolve_server_executable() if validate_executable else (
        str(_find_cached_llama_server() or (shutil.which(LOCAL_EMBEDDING_SERVER_EXE.strip() or "llama-server") or (LOCAL_EMBEDDING_SERVER_EXE.strip() or "llama-server")))
    )
    command = [
        executable,
        "--model",
        str(model_path),
        "--host",
        host,
        "--port",
        port,
        "--embedding",
        "--pooling",
        "last",
        "--ctx-size",
        str(QWEN3_EMBEDDING_MAX_CONTEXT_TOKENS),
        "--parallel",
        str(max(1, LOCAL_EMBEDDING_PARALLEL)),
        "--batch-size",
        str(max(1, LOCAL_EMBEDDING_BATCH)),
        "--ubatch-size",
        str(max(1, LOCAL_EMBEDDING_UBATCH)),
    ]
    if LOCAL_EMBEDDING_THREADS > 0:
        command.extend(["--threads", str(LOCAL_EMBEDDING_THREADS)])
    return command


def build_local_embedding_command() -> list[str]:
    """构造推荐的 llama.cpp 本地 embedding 服务命令，并确保模型已存在。"""
    return _build_command_for_model(ensure_local_model_available(), validate_executable=True)


def preview_local_embedding_command() -> list[str]:
    """返回本地 embedding 服务命令预览，不触发模型下载。"""
    return _build_command_for_model(resolve_model_path(), validate_executable=False)


def get_local_embedding_status() -> dict[str, Any]:
    """读取本地嵌入服务状态。"""
    with _lock:
        running = _process is not None and _process.poll() is None
        pid = _process.pid if running and _process is not None else None
    alive = is_local_embedding_alive(timeout=1.0)
    return {
        "configured": resolve_model_path().is_file(),
        "model_path": str(resolve_model_path()),
        "running": running,
        "alive": alive,
        "pid": pid,
        "base_url": LOCAL_EMBEDDING_BASE_URL,
        "model": QWEN3_EMBEDDING_MODEL,
        "dimensions": QWEN3_EMBEDDING_DIMENSIONS,
        "server_executable": str(_find_cached_llama_server() or (shutil.which(LOCAL_EMBEDDING_SERVER_EXE.strip() or "llama-server") or "")),
        "auto_download_server": LOCAL_EMBEDDING_AUTO_DOWNLOAD_SERVER,
        "command": preview_local_embedding_command(),
    }


def start_local_embedding_service() -> dict[str, Any]:
    """启动本地嵌入服务；若端口已有可用服务则只返回状态。"""
    global _process
    should_return_status = False
    started_process: subprocess.Popen | None = None
    with _lock:
        if _process is not None and _process.poll() is None:
            should_return_status = True
        elif is_local_embedding_alive(timeout=1.0):
            should_return_status = True
        else:
            command = build_local_embedding_command()
            popen_kwargs: dict[str, Any] = {
                "stdout": subprocess.DEVNULL,
                "stderr": subprocess.DEVNULL,
            }
            if os.name == "nt":
                popen_kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            _process = subprocess.Popen(command, **popen_kwargs)
            started_process = _process

    if should_return_status:
        return get_local_embedding_status()
    if started_process is not None:
        deadline = time.monotonic() + max(1.0, LOCAL_EMBEDDING_STARTUP_TIMEOUT)
        while time.monotonic() < deadline:
            if started_process.poll() is not None:
                break
            if is_local_embedding_alive(timeout=2.0, ttl=0):
                break
            time.sleep(0.5)
    return get_local_embedding_status()


def stop_local_embedding_service() -> dict[str, Any]:
    """停止由当前后端进程拉起的本地嵌入服务。"""
    global _process
    with _lock:
        process = _process
        _process = None
    if process is not None and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
    return get_local_embedding_status()
