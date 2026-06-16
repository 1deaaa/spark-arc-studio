"""SparkArc 服务端安装位置注册表。

本模块在用户主目录下的隐藏目录 ``~/.sparkarc`` 中维护一个轻量状态文件，
让 launcher、脚本和后端本身都能快速定位当前系统上唯一（或最近一次使用）的
SparkArc 项目根目录。

设计原则：
  1. 不依赖外部库，只用标准库读写 JSON。
  2. 幂等：重复写入同一目录不会破坏数据。
  3. 向后兼容：读取失败时优雅降级，调用方自行决定行为。
"""

from __future__ import annotations

import json
import os
import platform
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_SPARKARC_DIR_NAME = ".sparkarc"
_SERVICE_RECORD_FILE = "service.json"


def get_sparkarc_user_dir() -> Path:
    """返回 SparkArc 在用户主目录下的隐藏状态目录 ``~/.sparkarc``。"""
    home = Path.home()
    return home / _SPARKARC_DIR_NAME


def get_service_record_path() -> Path:
    """返回服务端安装记录文件路径 ``~/.sparkarc/service.json``。"""
    return get_sparkarc_user_dir() / _SERVICE_RECORD_FILE


def _ensure_user_dir() -> Path:
    d = get_sparkarc_user_dir()
    d.mkdir(parents=True, exist_ok=True)
    return d


def record_service_install(project_root: str | Path) -> dict[str, Any]:
    """记录（或更新）当前 SparkArc 项目根目录。

    参数:
        project_root: SparkArc 项目根目录（包含 server/、client/ 的目录）。

    返回:
        写入磁盘的记录字典。
    """
    root = Path(project_root).resolve()
    record = {
        "projectRoot": str(root),
        "installedAt": datetime.now(timezone.utc).isoformat(),
        "platform": platform.system().lower(),
        "machine": platform.machine().lower(),
    }

    _ensure_user_dir()
    path = get_service_record_path()
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    # 原子替换，避免写一半被读取
    os.replace(tmp, path)
    return record


def read_service_record() -> dict[str, Any] | None:
    """读取已记录的服务端安装信息。

    返回:
        记录字典；若文件不存在、损坏或关键字段缺失则返回 None。
    """
    path = get_service_record_path()
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return None
        if not data.get("projectRoot"):
            return None
        return dict(data)
    except Exception:
        return None


def is_service_record_valid(record: dict[str, Any] | None) -> bool:
    """检查记录中的 projectRoot 是否仍然有效。

    有效标准：目录存在，且至少包含 server/app.py 或 start.bat/start.sh 之一。
    """
    if not record:
        return False
    root = Path(record.get("projectRoot") or "").expanduser()
    if not root.is_dir():
        return False
    # 检查关键文件是否存在，确保这不是一个已被删除的目录残留记录
    return (
        (root / "server" / "app.py").is_file()
        or (root / "start.bat").is_file()
        or (root / "start.sh").is_file()
    )


def clear_service_record() -> None:
    """清除服务端安装记录。"""
    path = get_service_record_path()
    if path.is_file():
        path.unlink()


def resolve_service_project_root() -> Path | None:
    """一站式接口：返回当前系统上已注册且有效的 SparkArc 项目根目录。"""
    record = read_service_record()
    if not is_service_record_valid(record):
        return None
    return Path(record["projectRoot"]).expanduser().resolve()
