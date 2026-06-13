from __future__ import annotations

import asyncio
import ctypes
import importlib.util
import json
import os
import platform
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Mapping

import httpx

DEFAULT_TRAY_TITLE = "SparkArc Server"
DEFAULT_SERVER_URL = "http://localhost:6688"
DEFAULT_HEALTH_URL = "http://127.0.0.1:6688/health"
HELPER_STATE_FILENAME = "sparkarc_server_tray_helper.json"
HELPER_LOG_FILENAME = "sparkarc_server_tray_helper.log"

_TRUTHY_VALUES = {"1", "true", "yes", "on"}
_FALSY_VALUES = {"0", "false", "no", "off"}
_ICON_CANDIDATES = (
    Path("..") / "client" / "public" / "icon.png",
    Path("..") / "client" / "src-tauri" / "icons" / "icon.png",
    Path("..") / "client" / "src-tauri" / "icons" / "icon.ico",
    Path("..") / "client" / "public" / "icon.ico",
)


def read_bool_env(
    name: str,
    *,
    default: bool = False,
    env: Mapping[str, str] | None = None,
) -> bool:
    raw = (env or os.environ).get(name)
    if raw is None:
        return default
    normalized = str(raw).strip().lower()
    if normalized in _TRUTHY_VALUES:
        return True
    if normalized in _FALSY_VALUES:
        return False
    return default


def running_in_embedded_python(executable: str | None = None) -> bool:
    target = Path(executable or sys.executable)
    normalized_parts = [part.lower() for part in target.parts]
    return ".runtime" in normalized_parts and "python" in normalized_parts


def resolve_tray_icon_path(server_root: str | Path | None = None) -> Path | None:
    root = Path(server_root or Path(__file__).resolve().parents[1])
    for candidate in _ICON_CANDIDATES:
        resolved = (root / candidate).resolve()
        if resolved.exists():
            return resolved
    return None


def should_enable_system_tray(
    *,
    env: Mapping[str, str] | None = None,
    system_name: str | None = None,
) -> bool:
    current_env = env or os.environ

    if read_bool_env("CI", env=current_env):
        return False

    tray_override = current_env.get("SPARKARC_SERVER_TRAY")
    if tray_override is not None:
        return read_bool_env("SPARKARC_SERVER_TRAY", env=current_env)

    system = (system_name or platform.system()).strip()
    if system == "Linux":
        if current_env.get("WSL_DISTRO_NAME"):
            return False
        return bool(current_env.get("DISPLAY") or current_env.get("WAYLAND_DISPLAY"))

    return system in {"Windows", "Darwin"}


def resolve_shutdown_target_pids(
    *,
    reload_active: bool,
    current_pid: int | None = None,
    parent_pid: int | None = None,
) -> tuple[int, int | None]:
    current = int(current_pid or os.getpid())
    parent = int(parent_pid or os.getppid())

    if reload_active and parent > 1 and parent != current:
        return parent, current

    return current, None


def get_helper_state_path(server_url: str = DEFAULT_SERVER_URL) -> Path:
    temp_root = Path(tempfile.gettempdir()) / "sparkarc"
    temp_root.mkdir(parents=True, exist_ok=True)
    safe_name = server_url.replace("://", "_").replace(":", "_").replace("/", "_")
    return temp_root / f"{safe_name}_{HELPER_STATE_FILENAME}"


def get_helper_log_path(server_url: str = DEFAULT_SERVER_URL) -> Path:
    temp_root = Path(tempfile.gettempdir()) / "sparkarc"
    temp_root.mkdir(parents=True, exist_ok=True)
    safe_name = server_url.replace("://", "_").replace(":", "_").replace("/", "_")
    return temp_root / f"{safe_name}_{HELPER_LOG_FILENAME}"


def is_process_alive(pid: int | None) -> bool:
    if not pid or pid <= 0:
        return False
    if platform.system() == "Windows":
        process_query_limited_information = 0x1000
        still_active = 259
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(process_query_limited_information, False, int(pid))
        if not handle:
            return False
        try:
            exit_code = ctypes.c_ulong()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                return False
            return exit_code.value == still_active
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _load_helper_state(state_path: Path) -> dict | None:
    try:
        if not state_path.exists():
            return None
        return json.loads(state_path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _write_helper_state(state_path: Path, payload: dict) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _choose_helper_python() -> str:
    executable = Path(sys.executable)
    if platform.system() == "Windows":
        pythonw_exe = executable.with_name("pythonw.exe")
        if pythonw_exe.exists():
            return str(pythonw_exe)
    return str(executable)


def _tray_runtime_ready() -> bool:
    return bool(importlib.util.find_spec("pystray")) and bool(importlib.util.find_spec("PIL"))


def _build_helper_command(
    *,
    server_root: str | Path,
    state_path: Path,
    title: str,
    server_url: str,
    health_url: str,
    controller_pid: int,
    server_pid: int | None,
    log_path: Path,
) -> list[str]:
    return [
        _choose_helper_python(),
        "-X",
        "utf8",
        "-m",
        "core.system_tray_helper",
        "--server-root",
        str(server_root),
        "--state-path",
        str(state_path),
        "--title",
        title,
        "--server-url",
        server_url,
        "--health-url",
        health_url,
        "--controller-pid",
        str(controller_pid),
        "--server-pid",
        str(server_pid or 0),
        "--log-path",
        str(log_path),
    ]


def ensure_tray_helper_process(
    *,
    server_root: str | Path,
    title: str = DEFAULT_TRAY_TITLE,
    server_url: str = DEFAULT_SERVER_URL,
    health_url: str = DEFAULT_HEALTH_URL,
    controller_pid: int,
    server_pid: int | None,
) -> bool:
    state_path = get_helper_state_path(server_url)
    log_path = get_helper_log_path(server_url)
    existing_state = _load_helper_state(state_path)
    existing_pid = None
    if existing_state:
        try:
            existing_pid = int(existing_state.get("helper_pid") or 0)
        except Exception:
            existing_pid = None
    if is_process_alive(existing_pid):
        return False
    if state_path.exists():
        try:
            state_path.unlink()
        except OSError:
            pass
    if not _tray_runtime_ready():
        print("⚠️ pystray or Pillow not found in current Python environment, skipping tray assistant.", flush=True)
        return False

    command = _build_helper_command(
        server_root=server_root,
        state_path=state_path,
        title=title,
        server_url=server_url,
        health_url=health_url,
        controller_pid=controller_pid,
        server_pid=server_pid,
        log_path=log_path,
    )
    log_file = log_path.open("a", encoding="utf-8")
    popen_kwargs: dict = {
        "cwd": str(server_root),
        "stdout": log_file,
        "stderr": subprocess.STDOUT,
        "stdin": subprocess.DEVNULL,
        "start_new_session": True,
    }
    if platform.system() == "Windows":
        popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS  # type: ignore[attr-defined]

    try:
        process = subprocess.Popen(command, **popen_kwargs)
    finally:
        log_file.close()
    _write_helper_state(
        state_path,
        {
            "helper_pid": process.pid,
            "server_url": server_url,
            "health_url": health_url,
            "controller_pid": controller_pid,
            "server_pid": server_pid,
            "title": title,
        },
    )
    return True


async def launch_tray_helper_after_health_check(
    *,
    server_root: str | Path,
    title: str = DEFAULT_TRAY_TITLE,
    server_url: str = DEFAULT_SERVER_URL,
    health_url: str = DEFAULT_HEALTH_URL,
    timeout_seconds: float = 15.0,
) -> bool:
    if not should_enable_system_tray():
        return False

    reload_active = read_bool_env("SPARKARC_SERVER_RELOAD_ACTIVE", default=False)
    controller_pid, server_pid = resolve_shutdown_target_pids(reload_active=reload_active)

    deadline = asyncio.get_running_loop().time() + timeout_seconds
    async with httpx.AsyncClient(timeout=2.0) as client:
        while asyncio.get_running_loop().time() < deadline:
            try:
                response = await client.get(health_url)
                if response.status_code == 200 and response.text.strip() == "sparkarc-ok":
                    launched = ensure_tray_helper_process(
                        server_root=server_root,
                        title=title,
                        server_url=server_url,
                        health_url=health_url,
                        controller_pid=controller_pid,
                        server_pid=server_pid,
                    )
                    if launched:
                        print("🖥️ System tray assistant started", flush=True)
                    return launched
            except Exception:
                pass
            await asyncio.sleep(0.5)
    print("⚠️ System tray assistant health check timed out, skipping launch.", flush=True)
    return False
