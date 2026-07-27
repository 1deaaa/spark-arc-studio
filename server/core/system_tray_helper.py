from __future__ import annotations

import argparse
import datetime
import json
import os
import platform
import signal
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path
from typing import Any

from core.system_tray import is_process_alive, resolve_tray_icon_path


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="SparkArc 独立系统托盘助手")
    parser.add_argument("--server-root", required=True)
    parser.add_argument("--state-path", required=True)
    parser.add_argument("--title", default="SparkArc Server")
    parser.add_argument("--server-url", required=True)
    parser.add_argument("--health-url", required=True)
    parser.add_argument("--controller-pid", type=int, required=True)
    parser.add_argument("--server-pid", type=int, default=0)
    parser.add_argument("--log-path", default="")
    return parser.parse_args()


def _log(log_path: Path | None, message: str) -> None:
    if log_path is None:
        return
    timestamp = datetime.datetime.now().isoformat(timespec="seconds")
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {message}\n")
    except OSError:
        pass


def _load_runtime():
    import pystray
    from PIL import Image

    return pystray, Image


def _remove_state_file(state_path: Path) -> None:
    try:
        if state_path.exists():
            state_path.unlink()
    except OSError:
        pass


def _write_state_file(state_path: Path, payload: dict[str, Any]) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _terminate_targets(controller_pid: int, server_pid: int | None) -> None:
    system = platform.system()
    if system == "Windows":
        subprocess.run(
            ["taskkill", "/PID", str(controller_pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return

    targets = [controller_pid]
    if server_pid and server_pid not in targets:
        targets.append(server_pid)

    for target_pid in targets:
        try:
            os.kill(target_pid, signal.SIGTERM)
        except OSError:
            pass

    time.sleep(0.5)

    for target_pid in targets:
        if is_process_alive(target_pid):
            try:
                os.kill(target_pid, signal.SIGKILL)
            except OSError:
                pass


def _monitor_server(
    icon,
    controller_pid: int,
    server_pid: int | None,
    state_path: Path,
    log_path: Path | None,
) -> None:
    while True:
        if not is_process_alive(controller_pid):
            _log(log_path, f"控制进程已退出，停止托盘: {controller_pid}")
            break
        if server_pid and not is_process_alive(server_pid):
            _log(log_path, f"服务子进程已退出，停止托盘: {server_pid}")
            break
        time.sleep(2.0)

    _remove_state_file(state_path)
    icon.stop()


def main() -> int:
    args = _parse_args()
    log_path = Path(args.log_path) if args.log_path else None
    _log(log_path, "托盘助手进程启动")
    pystray, image_module = _load_runtime()

    state_path = Path(args.state_path)
    icon_path = resolve_tray_icon_path(args.server_root)
    if icon_path is None:
        _log(log_path, f"未找到图标，server_root={args.server_root}")
        return 1
    _log(log_path, f"使用图标: {icon_path}")

    with image_module.open(icon_path) as raw_icon:
        tray_image = raw_icon.copy()

    controller_pid = int(args.controller_pid)
    server_pid = int(args.server_pid) or None
    exit_requested = threading.Event()

    def _open_ui(_icon, _item) -> None:
        threading.Thread(
            target=lambda: webbrowser.open(args.server_url, new=2),
            name="sparkarc-tray-open-browser",
            daemon=True,
        ).start()

    def _force_exit(_icon, _item) -> None:
        exit_requested.set()

        def _kill_and_stop() -> None:
            _terminate_targets(controller_pid, server_pid)
            _remove_state_file(state_path)
            _icon.stop()

        threading.Thread(
            target=_kill_and_stop,
            name="sparkarc-tray-force-exit",
            daemon=True,
        ).start()

    menu = pystray.Menu(
        pystray.MenuItem("Open SparkArc in browser", _open_ui, default=True),
        pystray.MenuItem("Exit Spark Server", _force_exit),
    )
    icon = pystray.Icon("sparkarc-server-helper", tray_image, args.title, menu)

    def _setup(_icon) -> None:
        _icon.visible = True
        _log(log_path, "托盘图标已设为可见")
        _write_state_file(
            state_path,
            {
                "helper_pid": os.getpid(),
                "title": args.title,
                "server_url": args.server_url,
                "health_url": args.health_url,
                "controller_pid": controller_pid,
                "server_pid": server_pid,
            },
        )
        threading.Thread(
            target=_monitor_server,
            args=(_icon, controller_pid, server_pid, state_path, log_path),
            name="sparkarc-tray-server-monitor",
            daemon=True,
        ).start()
        _log(log_path, "服务监控线程已启动")

    try:
        icon.run(setup=_setup)
    except Exception as exc:
        _log(log_path, f"托盘主循环异常: {exc!r}")
        raise
    finally:
        _remove_state_file(state_path)
        _log(log_path, "托盘助手进程结束")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
