"""平台身份标识的生成与兼容规范。"""

from __future__ import annotations

import hashlib
import re
import uuid


_PLATFORM_KEY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_LEGACY_DATABASE_PLATFORM_KEY_RE = re.compile(r"^legacy-db-\d+(?:-\d+)?$")


def normalize_platform_key(value: object) -> str | None:
    """规范化平台身份标识；空值返回 None，非法值直接报错。"""
    if value is None:
        return None
    key = str(value).strip()
    if not key:
        return None
    if not _PLATFORM_KEY_RE.fullmatch(key):
        raise ValueError("platform_key 只能包含字母、数字、点、下划线、冒号和连字符")
    return key


def generate_platform_key() -> str:
    """为新平台生成不依赖名称和 URL 的稳定身份标识。"""
    return f"platform-{uuid.uuid4().hex}"


def legacy_config_platform_key(name: object, base_url: object) -> str:
    """为没有 platform_key 的旧 YAML 配置生成确定性的兼容标识。"""
    seed = f"{str(name or '').strip()}\x00{str(base_url or '').strip()}"
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    return f"legacy-{digest[:32]}"


def legacy_database_platform_key(platform_id: int) -> str:
    """为历史数据库行生成基于主键的确定性兼容标识。"""
    return f"legacy-db-{int(platform_id)}"


def is_legacy_database_platform_key(value: object) -> bool:
    """判断平台 key 是否为历史数据库行专用的内部兼容标识。"""
    if not isinstance(value, str):
        return False
    return bool(_LEGACY_DATABASE_PLATFORM_KEY_RE.fullmatch(value.strip()))
