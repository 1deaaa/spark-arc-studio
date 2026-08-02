"""Matchbox 自有的 Hugging Face 镜像发现与可达性探测。"""

from __future__ import annotations

import re
import threading
import time
from typing import Any, Optional
from urllib.parse import urlsplit

import requests

from .env_utils import get_env_var


OFFICIAL_HF_ENDPOINT = "https://huggingface.co"
MAINLAND_HF_MIRROR = "https://hf-mirror.com"

_GEOIP_PROVIDERS = (
    "https://api.country.is/",
    "https://ipwho.is/",
    "https://freeipapi.com/api/json/",
)
_cache_lock = threading.RLock()
_region_cache: tuple[float, Optional[bool]] = (0.0, None)
_candidate_cache: tuple[float, tuple[str, ...], list[str]] = (0.0, (), [])


def _float_env(name: str, default: float, *, minimum: float = 0.1) -> float:
    raw = get_env_var(name)
    try:
        return max(float(raw), minimum) if raw is not None else default
    except (TypeError, ValueError):
        return default


def _normalize_endpoint(value: object) -> Optional[str]:
    endpoint = str(value or "").strip().rstrip("/")
    if not endpoint:
        return None
    parts = urlsplit(endpoint)
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        return None
    return endpoint


def _configured_candidates() -> list[str]:
    raw_candidates = get_env_var("AGENT_MATCHBOX_HF_ENDPOINTS", "") or ""
    configured = re.split(r"[,;\r\n]+", raw_candidates)
    candidates = [get_env_var("HF_ENDPOINT"), *configured]
    normalized: list[str] = []
    for candidate in candidates:
        endpoint = _normalize_endpoint(candidate)
        if endpoint and endpoint not in normalized:
            normalized.append(endpoint)
    return normalized


def _extract_country_code(data: dict[str, Any]) -> Optional[str]:
    raw = data.get("countryCode") or data.get("country_code") or data.get("country")
    country_code = str(raw or "").strip().upper()
    return country_code if len(country_code) == 2 else None


def _probe_region_provider(url: str, timeout: float) -> Optional[str]:
    try:
        with requests.Session() as session:
            session.trust_env = False
            response = session.get(url, timeout=timeout)
            response.raise_for_status()
            payload = response.json()
        return _extract_country_code(payload) if isinstance(payload, dict) else None
    except Exception:
        return None


def is_mainland_china() -> bool:
    """判断当前出口是否位于中国大陆；无法确认时按非大陆处理。"""
    global _region_cache

    override = str(get_env_var("AGENT_MATCHBOX_HF_REGION", "") or "").strip().lower()
    if override in {"cn", "china", "mainland"}:
        return True
    if override in {"global", "overseas", "non-cn"}:
        return False

    now = time.monotonic()
    cache_ttl = _float_env("AGENT_MATCHBOX_HF_REGION_CACHE_TTL", 300.0)
    with _cache_lock:
        cached_at, cached_value = _region_cache
        if cached_value is not None and now - cached_at < cache_ttl:
            return cached_value

    timeout = _float_env("AGENT_MATCHBOX_HF_REGION_TIMEOUT", 2.0)
    votes: dict[str, int] = {}
    for provider in _GEOIP_PROVIDERS:
        country_code = _probe_region_provider(provider, timeout)
        if country_code:
            votes[country_code] = votes.get(country_code, 0) + 1

    ordered = sorted(votes.items(), key=lambda item: (-item[1], item[0]))
    confirmed = bool(
        ordered
        and ordered[0][1] >= 2
        and (len(ordered) == 1 or ordered[0][1] > ordered[1][1])
    )
    result = confirmed and ordered[0][0] == "CN"
    with _cache_lock:
        _region_cache = (now, result)
    return result


def probe_hf_endpoint(endpoint: str, timeout: Optional[float] = None) -> bool:
    """探测一个 Hugging Face endpoint 是否可达。"""
    normalized = _normalize_endpoint(endpoint)
    if normalized is None:
        return False
    request_timeout = timeout or _float_env("AGENT_MATCHBOX_HF_PROBE_TIMEOUT", 3.0)
    try:
        response = requests.head(normalized, timeout=request_timeout, allow_redirects=True)
        if 200 <= response.status_code < 400:
            return True
    except Exception:
        pass

    try:
        response = requests.get(
            normalized,
            timeout=request_timeout,
            allow_redirects=True,
            stream=True,
        )
        with response:
            return 200 <= response.status_code < 400
    except Exception:
        return False


def get_hf_candidates(*, probe: bool = True) -> list[str]:
    """返回按配置、区域和可达性排序的 Hugging Face 候选地址。"""
    global _candidate_cache

    configured = _configured_candidates()
    regional_defaults = (
        [MAINLAND_HF_MIRROR, OFFICIAL_HF_ENDPOINT]
        if is_mainland_china()
        else [OFFICIAL_HF_ENDPOINT, MAINLAND_HF_MIRROR]
    )
    candidates = list(dict.fromkeys([*configured, *regional_defaults]))
    if not probe:
        return candidates

    now = time.monotonic()
    cache_ttl = _float_env("AGENT_MATCHBOX_HF_PROBE_CACHE_TTL", 60.0)
    cache_key = tuple(candidates)
    with _cache_lock:
        cached_at, cached_key, cached_candidates = _candidate_cache
        if cached_key == cache_key and now - cached_at < cache_ttl:
            return list(cached_candidates)

    reachable = [endpoint for endpoint in candidates if probe_hf_endpoint(endpoint)]
    result = [*reachable, *(endpoint for endpoint in candidates if endpoint not in reachable)]
    with _cache_lock:
        _candidate_cache = (now, cache_key, result)
    return list(result)


def reset_hf_mirror_cache() -> None:
    """清空进程内探测缓存，供配置热更新与测试使用。"""
    global _region_cache, _candidate_cache
    with _cache_lock:
        _region_cache = (0.0, None)
        _candidate_cache = (0.0, (), [])
