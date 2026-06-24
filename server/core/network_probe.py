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

# 公益 IP 归属地 API（按优先级排列）。
# freeipapi.com：完全免费、无需 Key、返回 countryCode/countryName，额度较宽松。
_GEOIP_PROVIDERS: list[str] = [
    "https://freeipapi.com/api/json/",
    "https://ipapi.co/json/",
    "https://ipwho.is/json/",
]

_PROBE_TIMEOUT = 3.0
# 区域探测缓存 TTL（秒）。这是所有 Python 端网络探测的统一缓存时间。
# 设置较短（5 秒），让用户在切换网络（如开启/关闭梯子）后，下一次下载请求
# 就能重新探测并切换镜像，而不用等很久。
NETWORK_PROBE_CACHE_TTL_SECONDS = 5

# 镜像表：同一资源类型，越靠前优先级越高。
_MIRROR_TABLE: dict[str, dict[str, list[str]]] = {
    "pypi": {
        "default": ["https://pypi.org/simple/"],
        "mainland": [
            "https://mirrors.aliyun.com/pypi/simple/",
            "https://pypi.tuna.tsinghua.edu.cn/simple/",
            "https://mirrors.ustc.edu.cn/pypi/web/simple/",
        ],
    },
    "github_release": {
        "default": ["https://github.com/"],
        "mainland": [
            "https://mirrors.ustc.edu.cn/github-release/",
            "https://gh-proxy.com/",
        ],
    },
    "huggingface": {
        # 国内最常用、额度最宽的 HF 公益镜像。
        "default": ["https://huggingface.co"],
        "mainland": [
            "https://hf-mirror.com",
        ],
    },
    "gh_proxy": {
        "default": ["https://gh-proxy.com/"],
        "mainland": ["https://gh-proxy.com/"],
    },
}

_region_cache: tuple[float, dict[str, Any] | None] = (0.0, None)


def _now() -> float:
    return time.monotonic()


def _fetch_json(url: str, timeout: float = 5.0) -> dict[str, Any] | None:
    try:
        resp = requests.get(url, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, dict) else None
    except Exception:
        return None


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

    返回字段：country_code, country_name, is_mainland_china, provider
    """
    global _region_cache
    cached_at, cached = _region_cache
    if cached is not None and _now() - cached_at < NETWORK_PROBE_CACHE_TTL_SECONDS:
        return dict(cached)

    result: dict[str, Any] = {
        "country_code": "UNKNOWN",
        "country_name": "Unknown",
        "is_mainland_china": False,
        "provider": "fallback",
    }

    for provider in _GEOIP_PROVIDERS:
        data = _fetch_json(provider)
        if not data:
            continue

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

        if len(country_code) >= 2:
            result = {
                "country_code": country_code,
                "country_name": str(country_name).strip(),
                "is_mainland_china": country_code == "CN",
                "provider": provider,
            }
            break

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

    resource_type 支持：pypi / github_release / huggingface / gh_proxy
    """
    if resource_type not in _MIRROR_TABLE:
        raise ValueError(f"不支持的资源类型：{resource_type}")

    cfg = _MIRROR_TABLE[resource_type]
    if is_mainland_china():
        candidates = list(cfg.get("mainland", [])) + list(cfg.get("default", []))
    else:
        candidates = list(cfg.get("default", [])) + list(cfg.get("mainland", []))

    candidates = [u for u in candidates if isinstance(u, str) and u.strip()]
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
    if "huggingface" not in _MIRROR_TABLE:
        return []
    cfg = _MIRROR_TABLE["huggingface"]
    if is_mainland_china():
        candidates = list(cfg.get("mainland", [])) + list(cfg.get("default", []))
    else:
        candidates = list(cfg.get("default", [])) + list(cfg.get("mainland", []))
    candidates = [u for u in candidates if isinstance(u, str) and u.strip()]
    if not probe:
        return candidates
    reachable = [u for u in candidates if probe_url(u)]
    unreachable = [u for u in candidates if u not in reachable]
    return reachable + unreachable


def get_hf_endpoint(probe: bool = True) -> str:
    """返回当前网络环境下推荐的 Hugging Face endpoint。"""
    candidates = get_hf_candidates(probe=probe)
    return candidates[0] if candidates else _MIRROR_TABLE["huggingface"]["default"][0]


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


def get_git_clone_url(repo_url: str = "https://github.com/1deaaa/spark-arc-studio.git") -> str:
    """根据网络归属地返回适合 git clone 的 URL。

    中国大陆网络下通过 gh-proxy.com 代理 GitHub HTTPS 克隆地址，
    其他地区直接返回原始地址。
    """
    if is_mainland_china():
        proxy = get_gh_proxy().rstrip("/")
        return f"{proxy}/{repo_url}"
    return repo_url


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
