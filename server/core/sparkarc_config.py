"""读取仓库根目录的跨语言 SparkArc 常量清单。"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_CONFIG_PATH = _PROJECT_ROOT / "sparkarc.json"
_REQUIRED_NETWORK_RESOURCES = {
    "pypi",
    "npm_registry",
    "github_release",
    "gh_proxy",
    "huggingface",
    "python_standalone",
    "node_distribution",
}


def project_config_path() -> Path:
    """返回受版本控制的跨语言常量文件路径。"""
    return _CONFIG_PATH


def _require_string(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RuntimeError(f"sparkarc.json 的 {name} 必须是非空字符串。")
    return value.strip()


def _require_url_list(value: Any, name: str) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
        raise RuntimeError(f"sparkarc.json 的 {name} 必须是 URL 字符串数组。")
    return [item.strip() for item in value]


def _validate_config(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict) or raw.get("schemaVersion") != 1:
        raise RuntimeError("sparkarc.json 的 schemaVersion 必须为 1。")

    repository = raw.get("repository")
    if not isinstance(repository, dict) or repository.get("provider") != "github":
        raise RuntimeError('sparkarc.json 当前仅支持 repository.provider = "github"。')
    slug = _require_string(repository.get("slug"), "repository.slug")
    if len(slug.split("/")) != 2:
        raise RuntimeError("sparkarc.json 的 repository.slug 必须是 owner/repository 格式。")

    network = raw.get("network")
    if not isinstance(network, dict):
        raise RuntimeError("sparkarc.json 缺少 network 配置。")
    providers = _require_url_list(network.get("geoIpProviders"), "network.geoIpProviders")
    if len(set(providers)) < 2:
        raise RuntimeError("sparkarc.json 的 network.geoIpProviders 至少需要两个不同的服务。")
    resources = network.get("resources")
    if not isinstance(resources, dict):
        raise RuntimeError("sparkarc.json 缺少 network.resources 配置。")
    missing = sorted(_REQUIRED_NETWORK_RESOURCES - set(resources))
    if missing:
        raise RuntimeError(f"sparkarc.json 缺少网络资源：{', '.join(missing)}。")
    for resource_name, route in resources.items():
        if not isinstance(route, dict):
            raise RuntimeError(f"sparkarc.json 的 network.resources.{resource_name} 必须是对象。")
        _require_url_list(route.get("default"), f"network.resources.{resource_name}.default")
        _require_url_list(route.get("mainland"), f"network.resources.{resource_name}.mainland")
    return raw


@lru_cache(maxsize=1)
def load_sparkarc_config() -> dict[str, Any]:
    """加载并校验项目常量；启动期失败优先暴露配置错误。"""
    try:
        raw = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
    except OSError as exc:
        raise RuntimeError(f"无法读取 {_CONFIG_PATH}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{_CONFIG_PATH} 不是有效 JSON: {exc}") from exc
    return _validate_config(raw)


def repository_urls() -> dict[str, str]:
    """从唯一仓库标识派生公开仓库、克隆与 Release 地址。"""
    slug = str(load_sparkarc_config()["repository"]["slug"])
    web = f"https://github.com/{slug}"
    return {
        "slug": slug,
        "web": web,
        "clone": f"{web}.git",
        "release_api": f"https://api.github.com/repos/{slug}/releases/latest",
        "release_page": f"{web}/releases/latest",
    }


def network_candidates(
    resource: str,
    *,
    mainland: bool,
    include_fallback: bool = True,
) -> list[str]:
    """按出口区域返回资源候选，保持配置中的优先级。"""
    resources = load_sparkarc_config()["network"]["resources"]
    route = resources.get(resource)
    if not isinstance(route, dict):
        raise ValueError(f"sparkarc.json 未定义网络资源：{resource}")
    preferred_key, fallback_key = ("mainland", "default") if mainland else ("default", "mainland")
    values = list(route[preferred_key])
    if include_fallback:
        values.extend(route[fallback_key])
    return list(dict.fromkeys(str(value).strip() for value in values if str(value).strip()))


def geoip_providers() -> list[str]:
    """返回用于无代理直连投票的出口地址查询服务。"""
    return list(load_sparkarc_config()["network"]["geoIpProviders"])
