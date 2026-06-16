"""本地嵌入服务进程管理。

本模块只管理可选的本地 OpenAI 兼容 embedding 服务，不直接参与向量索引
构建，避免把进程生命周期逻辑散落到路由或业务服务中。
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import tarfile
import threading
import time
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

from core.network_probe import get_hf_endpoint, get_gh_proxy, is_mainland_china, probe_hf_endpoint

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
LOCAL_EMBEDDING_CTX_SIZE = int(os.getenv("SPARKARC_LOCAL_EMBEDDING_CTX_SIZE", "4096") or "4096")
LOCAL_EMBEDDING_BATCH = int(os.getenv("SPARKARC_LOCAL_EMBEDDING_BATCH", "1024") or "1024")
LOCAL_EMBEDDING_UBATCH = int(os.getenv("SPARKARC_LOCAL_EMBEDDING_UBATCH", "256") or "256")
LOCAL_EMBEDDING_STARTUP_TIMEOUT = float(os.getenv("SPARKARC_LOCAL_EMBEDDING_STARTUP_TIMEOUT", "120") or "120")
LOCAL_EMBEDDING_AUTO_DOWNLOAD_SERVER = os.getenv("SPARKARC_LOCAL_EMBEDDING_AUTO_DOWNLOAD_SERVER", "1").lower() not in {"0", "false", "no"}
LLAMA_CPP_RELEASE_TAG = os.getenv("SPARKARC_LLAMA_CPP_RELEASE_TAG", "b9632")
DOWNLOAD_ENDPOINT_PROBE_TIMEOUT = 1.5
HF_OFFICIAL_ENDPOINT = "https://huggingface.co"
HF_MIRROR_ENDPOINT = "https://hf-mirror.com"
GITHUB_RELEASE_BASE_URL = "https://github.com/ggml-org/llama.cpp/releases/download"
GITHUB_RELEASE_PROXY_PREFIX = "https://gh-proxy.com/"
QWEN3_GGUF_REPO_ID = "Qwen/Qwen3-Embedding-0.6B-GGUF"
QWEN3_GGUF_FILENAME = "Qwen3-Embedding-0.6B-Q8_0.gguf"
QWEN3_GGUF_MIN_BYTES = 600 * 1024 * 1024

_lock = threading.Lock()
_process: subprocess.Popen | None = None
_alive_cache: tuple[float, bool] = (0.0, False)
_hf_endpoint_cache: tuple[float, str | None] = (0.0, None)
_startup_state: dict[str, Any] = {
    "phase": "idle",
    "message": "",
    "progress": 0,
    "error": "",
    "updated_at": "",
}


@dataclass(frozen=True)
class _ReleaseAsset:
    name: str
    archive_type: str


def _now_state_ts() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _set_startup_state(phase: str, message: str = "", *, progress: int | None = None, error: str = "") -> None:
    with _lock:
        _startup_state.update({
            "phase": phase,
            "message": message,
            "error": error,
            "updated_at": _now_state_ts(),
        })
        if progress is not None:
            _startup_state["progress"] = max(0, min(100, int(progress)))


def _get_startup_state() -> dict[str, Any]:
    with _lock:
        return dict(_startup_state)


def local_embedding_model_name() -> str:
    """返回 UI 与测试接口使用的本地嵌入模型显示名。"""
    return f"local:{QWEN3_EMBEDDING_MODEL}"


def _probe_url_available(url: str, timeout: float | None = None) -> bool:
    """用真实网络连通性判断下载端点是否可用。"""
    request = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "SparkArc-local-embedding"})
    try:
        with urllib.request.urlopen(request, timeout=timeout or DOWNLOAD_ENDPOINT_PROBE_TIMEOUT) as response:
            return 200 <= int(response.status) < 400
    except Exception:
        return False


def _hf_endpoint() -> str | None:
    """返回应使用的 HF endpoint；官方可达时返回 None，让 hf_hub_download 使用默认官方端点。

    内部复用 core.network_probe 的统一探测入口，避免各模块各自维护镜像逻辑。
    """
    global _hf_endpoint_cache
    cached_at, cached_endpoint = _hf_endpoint_cache
    if time.monotonic() - cached_at < 300:
        return cached_endpoint

    recommended = get_hf_endpoint()
    if recommended == HF_OFFICIAL_ENDPOINT or not recommended:
        _hf_endpoint_cache = (time.monotonic(), None)
        return None

    # 用真实模型文件二次确认镜像可用
    if probe_hf_endpoint(recommended, repo_id=QWEN3_GGUF_REPO_ID, filename=QWEN3_GGUF_FILENAME):
        _hf_endpoint_cache = (time.monotonic(), recommended)
        return recommended

    _hf_endpoint_cache = (time.monotonic(), None)
    return None


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

    _set_startup_state("downloading_model", "正在下载本地嵌入模型", progress=10)
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        from huggingface_hub import hf_hub_download
    except ImportError as exc:
        raise RuntimeError("缺少 huggingface_hub，无法自动下载本地嵌入模型") from exc

    download_kwargs = {
        "repo_id": QWEN3_GGUF_REPO_ID,
        "filename": QWEN3_GGUF_FILENAME,
        "local_dir": str(target.parent),
        "local_dir_use_symlinks": False,
        "resume_download": True,
    }
    endpoint = _hf_endpoint()
    if endpoint:
        download_kwargs["endpoint"] = endpoint
    downloaded = hf_hub_download(**download_kwargs)
    downloaded_path = Path(downloaded).resolve()
    if downloaded_path != target and downloaded_path.is_file():
        if target.exists():
            target.unlink()
        downloaded_path.replace(target)
    if not target.is_file() or target.stat().st_size < QWEN3_GGUF_MIN_BYTES:
        raise RuntimeError(f"本地嵌入模型下载不完整：{target}")
    _set_startup_state("model_ready", "本地嵌入模型已就绪", progress=40)
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


def _llama_cpp_assets(tag: str) -> list[_ReleaseAsset]:
    system = platform.system().lower()
    machine = platform.machine().lower()
    is_arm = machine in {"arm64", "aarch64"}
    is_x64 = machine in {"x86_64", "amd64", "x64"}

    if system == "windows":
        return [
            _ReleaseAsset(f"llama-{tag}-bin-win-arm64.zip", "zip"),
        ] if is_arm else [
            _ReleaseAsset(f"llama-{tag}-bin-win-cpu-x64.zip", "zip"),
        ]
    if system == "linux":
        if is_arm:
            return [
                _ReleaseAsset(f"llama-{tag}-bin-ubuntu-arm64.tar.gz", "tar.gz"),
                _ReleaseAsset(f"llama-{tag}-bin-ubuntu-arm64.zip", "zip"),
            ]
        if is_x64:
            return [
                _ReleaseAsset(f"llama-{tag}-bin-ubuntu-x64.tar.gz", "tar.gz"),
                _ReleaseAsset(f"llama-{tag}-bin-ubuntu-x64.zip", "zip"),
            ]

    raise RuntimeError(
        f"当前平台暂不支持自动下载 llama.cpp 预编译包：{platform.system()} {platform.machine()}。"
        "请手动安装 llama-server，或通过 SPARKARC_LOCAL_EMBEDDING_SERVER_EXE 指定路径。"
    )


def _download_url_candidates(tag: str, asset_name: str) -> list[str]:
    """构造 llama.cpp 预编译包下载候选 URL。

    在中国大陆网络下优先使用 gh-proxy 前缀，其他地区优先官方直链。
    proxy 前缀由 core.network_probe 统一提供，避免写死。
    """
    official_url = f"{GITHUB_RELEASE_BASE_URL}/{tag}/{asset_name}"
    proxy_prefix = get_gh_proxy()
    proxy_url = f"{proxy_prefix.rstrip('/')}/{official_url}"

    if is_mainland_china():
        return [proxy_url, official_url]
    return [official_url, proxy_url]


def _select_download_url(candidates: list[str]) -> list[str]:
    """按真实可达性排序候选下载 URL，避免先打明显不可用的端点。"""
    reachable = [url for url in candidates if _probe_url_available(url)]
    if reachable:
        return reachable + [url for url in candidates if url not in reachable]
    return candidates


def _extract_archive(archive_path: Path, extract_dir: Path, archive_type: str) -> None:
    extract_dir.mkdir(parents=True, exist_ok=True)
    if archive_type == "zip":
        with zipfile.ZipFile(archive_path, "r") as archive:
            archive.extractall(extract_dir)
        return
    if archive_type == "tar.gz":
        with tarfile.open(archive_path, "r:gz") as archive:
            archive.extractall(extract_dir)
        return
    raise RuntimeError(f"不支持的 llama.cpp 压缩包格式：{archive_type}")


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
    runtime_dir = get_llama_cpp_runtime_dir()
    runtime_dir.mkdir(parents=True, exist_ok=True)

    _set_startup_state("downloading_server", "正在准备 llama.cpp 本地服务", progress=45)
    errors: list[str] = []
    for asset in _llama_cpp_assets(tag):
        archive_path = runtime_dir / asset.name
        suffix = ".tar.gz" if asset.archive_type == "tar.gz" else ".zip"
        extract_dir = runtime_dir / asset.name.removesuffix(suffix)

        try:
            if not archive_path.is_file():
                last_error: Exception | None = None
                for url in _select_download_url(_download_url_candidates(tag, asset.name)):
                    try:
                        urllib.request.urlretrieve(url, archive_path)
                        last_error = None
                        break
                    except Exception as exc:
                        last_error = exc
                        if archive_path.exists():
                            archive_path.unlink(missing_ok=True)
                if last_error is not None:
                    raise last_error

            _extract_archive(archive_path, extract_dir, asset.archive_type)
            cached = _find_cached_llama_server()
            if cached is not None:
                _set_startup_state("server_ready", "llama.cpp 本地服务已就绪", progress=60)
                return cached
        except Exception as exc:
            errors.append(f"{asset.name}: {exc}")

    raise RuntimeError("无法准备 llama-server：" + "；".join(errors))


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
        str(max(1024, min(QWEN3_EMBEDDING_MAX_CONTEXT_TOKENS, LOCAL_EMBEDDING_CTX_SIZE))),
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
        "display_model": local_embedding_model_name() if alive else QWEN3_EMBEDDING_MODEL,
        "dimensions": QWEN3_EMBEDDING_DIMENSIONS,
        "server_executable": str(_find_cached_llama_server() or (shutil.which(LOCAL_EMBEDDING_SERVER_EXE.strip() or "llama-server") or "")),
        "auto_download_server": LOCAL_EMBEDDING_AUTO_DOWNLOAD_SERVER,
        "hf_endpoint": _hf_endpoint() or HF_OFFICIAL_ENDPOINT,
        "startup": _get_startup_state(),
        "command": preview_local_embedding_command(),
    }


def start_local_embedding_service() -> dict[str, Any]:
    """启动本地嵌入服务；若端口已有可用服务则只返回状态。"""
    global _process
    _set_startup_state("starting", "正在启动本地嵌入服务", progress=1, error="")
    try:
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
            _set_startup_state("ready", "本地嵌入服务已启动", progress=100)
            return get_local_embedding_status()
        if started_process is not None:
            deadline = time.monotonic() + max(1.0, LOCAL_EMBEDDING_STARTUP_TIMEOUT)
            _set_startup_state("loading", "正在加载本地嵌入模型", progress=70)
            while time.monotonic() < deadline:
                if started_process.poll() is not None:
                    break
                if is_local_embedding_alive(timeout=2.0, ttl=0):
                    _set_startup_state("ready", "本地嵌入服务已启动", progress=100)
                    break
                time.sleep(0.5)
        status = get_local_embedding_status()
        if not status.get("alive"):
            _set_startup_state("error", "本地嵌入服务启动失败", progress=100, error="服务未在超时时间内就绪")
        return status
    except Exception as exc:
        _set_startup_state("error", "本地嵌入服务启动失败", progress=100, error=str(exc))
        raise


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
