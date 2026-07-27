"""通用网络环境探测与镜像选择组件（Python 版）。

设计目标：
  1. 给所有需要访问 Hugging Face / GitHub / PyPI 的 Python 代码提供统一的
     「当前网络该用哪个镜像」决策入口。
  2. 不依赖项目业务逻辑，纯工具函数。
  3. 优先使用公益、无需 API Key、额度宽松的 IP 归属地服务。
  4. 探测结果带短时缓存，避免同一进程内反复查询。

典型用法：
    from core.network_probe import get_hf_endpoint, is_mainland_china

    endpoint = get_hf_endpoint()          # 返回 "https://huggingface.co" 或镜像
    os.environ["HF_ENDPOINT"] = endpoint  # 让 huggingface_hub / transformers 自动走镜像

    if is_mainland_china():
        ...
"""

from __future__ import annotations

import os
import time
from typing import Any

import requests

from core.sparkarc_config import (
    geoip_providers,
    network_candidates,
    repository_urls,
)

# 公益 IP 归属地 API 与候选下载源统一由仓库根目录 sparkarc.json 声明。
_GEOIP_PROVIDERS: list[str] = geoip_providers()

_PROBE_TIMEOUT = 3.0
# 区域探测缓存 TTL（秒）。这是所有 Python 端网络探测的统一缓存时间。
# 设置较短（5 秒），让用户在切换网络（如开启/关闭梯子）后，下一次下载请求
# 就能重新探测并切换镜像，而不用等很久。
NETWORK_PROBE_CACHE_TTL_SECONDS = 5

# 资源名称受 sparkarc.json 的 network.resources 约束；这里仅保留兼容入口白名单。
_SUPPORTED_MIRROR_TYPES = {
    "pypi",
    "github_release",
    "huggingface",
    "gh_proxy",
    "python_standalone",
    "node_distribution",
    "npm_registry",
}

_region_cache: tuple[float, dict[str, Any] | None] = (0.0, None)


def _now() -> float:
    return time.monotonic()


def _fetch_json_direct(url: str, timeout: float = 5.0) -> dict[str, Any] | None:
    """绕过 HTTP(S)_PROXY 查询独立 GeoIP 源，避免代理出口污染判断。"""
    try:
        with requests.Session() as session:
            session.trust_env = False
            resp = session.get(url, timeout=timeout)
            resp.raise_for_status()
            data = resp.json()
            return data if isinstance(data, dict) else None
    except Exception:
        return None


def _extract_country(data: dict[str, Any]) -> tuple[str, str] | None:
    country_code = (
        data.get("countryCode")
        or data.get("country_code")
        or data.get("country")
        or ""
    )
    country_name = (
        data.get("countryName")
        or data.get("country_name")
        or data.get("country")
        or ""
    )
    country_code = str(country_code).strip().upper()
    if len(country_code) != 2:
        return None
    return country_code, str(country_name).strip()


def _lookup_direct_consensus() -> dict[str, Any] | None:
    """用至少两个无代理 GeoIP 服务的一致结果确认出口国家。"""
    votes: dict[str, list[tuple[str, str]]] = {}
    for provider in _GEOIP_PROVIDERS:
        data = _fetch_json_direct(provider)
        if not data:
            continue
        country = _extract_country(data)
        if not country:
            continue
        country_code, country_name = country
        votes.setdefault(country_code, []).append((country_name, provider))

    if not votes:
        return None
    ordered = sorted(votes.items(), key=lambda item: (-len(item[1]), item[0]))
    country_code, records = ordered[0]
    is_tied = len(ordered) > 1 and len(ordered[1][1]) == len(records)
    if len(records) < 2 or is_tied:
        return None
    country_name = next((name for name, _ in records if name), country_code)
    return {
        "country_code": country_code,
        "country_name": country_name,
        "is_mainland_china": country_code == "CN",
        "provider": ", ".join(provider for _, provider in records),
        "confidence": "direct_consensus",
    }


def probe_url(url: str, timeout: float | None = None, method: str = "HEAD") -> bool:
    """探测某个 URL 是否可达。"""
    timeout = timeout if timeout is not None else _PROBE_TIMEOUT
    try:
        resp = requests.request(method, url, timeout=timeout, allow_redirects=True)
        return 200 <= resp.status_code < 400
    except Exception:
        # 某些镜像对 HEAD 不友好，回退 GET 只读响应头
        if method == "HEAD":
            try:
                resp = requests.get(url, timeout=timeout, allow_redirects=True, stream=True)
                with resp:
                    return 200 <= resp.status_code < 400
            except Exception:
                return False
        return False


def lookup_region() -> dict[str, Any]:
    """查询当前网络出口的 IP 归属地。

    所有 GeoIP 请求必须绕过进程代理，且至少两个独立服务结果一致。
    返回字段：country_code, country_name, is_mainland_china, provider, confidence。
    """
    global _region_cache
    cached_at, cached = _region_cache
    if cached is not None and _now() - cached_at < NETWORK_PROBE_CACHE_TTL_SECONDS:
        return dict(cached)

    result: dict[str, Any] = {
        "country_code": "UNKNOWN",
        "country_name": "Unknown",
        "is_mainland_china": None,
        "provider": "fallback",
        "confidence": "unknown",
    }

    result = _lookup_direct_consensus() or result

    _region_cache = (_now(), result)
    return dict(result)


def is_mainland_china() -> bool:
    """当前网络是否在中国大陆。"""
    return bool(lookup_region().get("is_mainland_china"))


def get_country_code() -> str:
    """当前网络出口的国家代码，如 CN/US/JP。"""
    return str(lookup_region().get("country_code") or "UNKNOWN")


def get_recommended_mirror(resource_type: str, probe: bool = True) -> str:
    """根据网络归属地返回某类资源的推荐镜像 URL。

    资源类型由 sparkarc.json 的 network.resources 声明。
    """
    if resource_type not in _SUPPORTED_MIRROR_TYPES:
        raise ValueError(f"不支持的资源类型：{resource_type}")

    candidates = network_candidates(resource_type, mainland=is_mainland_china())
    if not candidates:
        raise RuntimeError(f"资源类型 {resource_type} 没有可用镜像候选")

    if not probe:
        return candidates[0]

    for url in candidates:
        if probe_url(url):
            return url

    # 全部不可达时返回首选，让调用方自行失败并给出可读错误
    return candidates[0]


def get_hf_candidates(probe: bool = True) -> list[str]:
    """返回当前网络环境下 Hugging Face endpoint 的候选列表（按推荐顺序）。"""
    candidates = network_candidates("huggingface", mainland=is_mainland_china())
    if not probe:
        return candidates
    reachable = [u for u in candidates if probe_url(u)]
    unreachable = [u for u in candidates if u not in reachable]
    return reachable + unreachable


def get_hf_endpoint(probe: bool = True) -> str:
    """返回当前网络环境下推荐的 Hugging Face endpoint。"""
    candidates = get_hf_candidates(probe=probe)
    if candidates:
        return candidates[0]
    return network_candidates("huggingface", mainland=False, include_fallback=False)[0]


def get_pypi_mirror(probe: bool = True) -> str:
    """返回当前网络环境下推荐的 PyPI mirror。"""
    return get_recommended_mirror("pypi", probe=probe)


def get_github_release_mirror(probe: bool = True) -> str:
    """返回当前网络环境下推荐的 GitHub Release 镜像/代理前缀。"""
    return get_recommended_mirror("github_release", probe=probe)


def get_gh_proxy(probe: bool = True) -> str:
    """返回当前网络环境下推荐的 GitHub 文件代理前缀。"""
    return get_recommended_mirror("gh_proxy", probe=probe)


def apply_hf_environment() -> dict[str, str]:
    """自动设置 Hugging Face 相关环境变量，并返回设置后的键值。

    适合在程序启动早期调用一次，让 transformers / huggingface_hub 自动走镜像。
    """
    hf_endpoint = get_hf_endpoint()
    os.environ["HF_ENDPOINT"] = hf_endpoint
    # huggingface_hub 优先读取 HF_ENDPOINT；HuggingFaceHub 也读 HF_HOME
    # 这里不覆盖 HF_HOME，避免污染用户缓存目录。
    return {"HF_ENDPOINT": hf_endpoint}


def probe_hf_endpoint(
    endpoint: str,
    repo_id: str = "Qwen/Qwen3-Embedding-0.6B-GGUF",
    filename: str = "Qwen3-Embedding-0.6B-Q8_0.gguf",
    timeout: float = 3.0,
) -> bool:
    """用真实模型文件探测某个 HF endpoint 是否可用。"""
    url = f"{endpoint.rstrip('/')}/{repo_id}/resolve/main/{filename}"
    return probe_url(url, timeout=timeout, method="HEAD")


def get_git_clone_candidates(repo_url: str | None = None, probe: bool = True) -> list[str]:
    """按出口区域排序 Git 克隆候选；默认仓库在大陆优先使用公开 Gitee 镜像。"""
    del probe  # 保留兼容参数；仓库可达性由实际克隆过程逐项确认。
    if repo_url:
        return [repo_url]
    repository = repository_urls()
    official_url = repository["clone"]
    mainland_mirrors = repository["mainland_clones"]
    mainland = is_mainland_china()
    candidates = [*mainland_mirrors, official_url] if mainland else [official_url, *mainland_mirrors]
    return list(dict.fromkeys(candidates))


def get_git_clone_url(repo_url: str | None = None) -> str:
    """返回当前网络环境下首选的 Git 克隆地址。"""
    return get_git_clone_candidates(repo_url=repo_url)[0]


def get_network_snapshot() -> dict[str, Any]:
    """返回完整的网络环境快照，便于日志和调试。"""
    region = lookup_region()
    return {
        **region,
        "mirrors": {
            "huggingface": get_hf_endpoint(),
            "pypi": get_pypi_mirror(),
            "github_release": get_github_release_mirror(),
            "gh_proxy": get_gh_proxy(),
            "git_clone": get_git_clone_url(),
        },
        "probe_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
