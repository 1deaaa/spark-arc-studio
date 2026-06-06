from __future__ import annotations

import argparse
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

import requests

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
    return parser.parse_args()


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


def _monitor_server(icon, health_url: str, controller_pid: int, server_pid: int | None, state_path: Path) -> None:
    failures = 0
    while True:
        if not is_process_alive(controller_pid):
            break
        if server_pid and not is_process_alive(server_pid):
            break
        try:
            response = requests.get(health_url, timeout=2.0)
            if response.status_code == 200 and response.text.strip() == "sparkarc-ok":
                failures = 0
            else:
                failures += 1
        except Exception:
            failures += 1

        if failures >= 3:
            break
        time.sleep(2.0)

    _remove_state_file(state_path)
    icon.stop()


def main() -> int:
    args = _parse_args()
    pystray, image_module = _load_runtime()

    state_path = Path(args.state_path)
    icon_path = resolve_tray_icon_path(args.server_root)
    if icon_path is None:
        return 1

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
        pystray.MenuItem("启动界面", _open_ui, default=True),
        pystray.MenuItem("退出", _force_exit),
    )
    icon = pystray.Icon("sparkarc-server-helper", tray_image, args.title, menu)

    def _setup(_icon) -> None:
        _icon.visible = True
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
            args=(_icon, args.health_url, controller_pid, server_pid, state_path),
            name="sparkarc-tray-server-monitor",
            daemon=True,
        ).start()

    try:
        icon.run(setup=_setup)
    finally:
        _remove_state_file(state_path)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
