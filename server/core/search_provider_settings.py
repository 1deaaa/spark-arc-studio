"""联网搜索提供商的系统默认配置与用户覆盖配置。

系统默认 URL 与密钥写入被 Git 忽略的 ``server/data/.env``；用户覆盖写入
Matchbox 配置库，并复用其主密钥加密能力。运行时统一按“用户覆盖 → 系统默认”
解析，系统默认仅在“为全体用户提供推理服务”开启时向普通用户开放。
"""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, Optional
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from dotenv import dotenv_values, set_key, unset_key

from .search_provider_models import SearchProviderUserConfig


DEFAULT_EXA_MCP_URL = "https://mcp.exa.ai/mcp"
DEFAULT_TAVILY_MCP_URL = "https://mcp.tavily.com/mcp"
SUPPORTED_SEARCH_PROVIDERS = ("exa", "tavily")

_URL_ENV_KEYS = {
    "exa": "SPARKARC_EXA_MCP_URL",
    "tavily": "SPARKARC_TAVILY_MCP_URL",
}
_API_KEY_ENV_KEYS = {
    "exa": "SPARKARC_EXA_API_KEY",
    "tavily": "SPARKARC_TAVILY_API_KEY",
}
_DEFAULT_URLS = {
    "exa": DEFAULT_EXA_MCP_URL,
    "tavily": DEFAULT_TAVILY_MCP_URL,
}
_OFFICIAL_MCP_HOSTS = {
    "exa": "mcp.exa.ai",
    "tavily": "mcp.tavily.com",
}
_API_KEY_QUERY_PARAMS = {
    "exa": "exaApiKey",
    "tavily": "tavilyApiKey",
}

_lock = threading.Lock()


class SearchProviderConfigError(ValueError):
    """搜索提供商配置不合法。"""


class SearchProviderUnavailableError(RuntimeError):
    """当前用户没有可用的搜索提供商配置。"""


def matchbox_secret_rotation_handler(
    *,
    session,
    plan_secret_rewrite: Callable[..., dict],
    new_key: str,
    old_key: Optional[str],
    allow_clear_unrecoverable: bool,
    add_unresolved: Callable[[str], None],
    add_rewrite: Callable[[Callable[[], None], dict], None],
) -> None:
    """把 SparkArc 搜索密钥接入 Matchbox 的通用主密钥轮换事务。"""
    for search_config in session.query(SearchProviderUserConfig).all():
        plan = plan_secret_rewrite(
            raw_value=search_config.api_key,
            new_key=new_key,
            old_key=old_key,
            allow_clear_unrecoverable=allow_clear_unrecoverable,
        )
        if plan["action"] == "unresolved":
            add_unresolved(f"DB搜索用户Key:{search_config.user_id}:{search_config.provider}")
            continue
        if plan["action"] == "write":
            add_rewrite(
                lambda target=search_config, value=plan["value"]: setattr(target, "api_key", value),
                plan,
            )


@dataclass(frozen=True)
class SearchProviderRuntimeConfig:
    provider: str
    url: str
    api_key: str = ""
    source: str = "system"

    @property
    def is_official_url(self) -> bool:
        host = (urlsplit(self.url).hostname or "").lower()
        return host == _OFFICIAL_MCP_HOSTS[self.provider]

    @property
    def request_url(self) -> str:
        """官方 MCP 使用其查询参数协议，自定义代理保持原始 URL。"""
        if not self.api_key or not self.is_official_url:
            return self.url
        return _append_query_param(
            self.url,
            _API_KEY_QUERY_PARAMS[self.provider],
            self.api_key,
        )

    @property
    def request_headers(self) -> Dict[str, str]:
        """自定义 MCP 代理的密钥按原值写入 Authorization。"""
        if not self.api_key or self.is_official_url:
            return {}
        return {"Authorization": self.api_key}


@dataclass(frozen=True)
class SearchProviderAdminView:
    provider: str
    url: str
    api_key_set: bool


def _normalize_provider(provider: str) -> str:
    normalized = str(provider or "").strip().lower()
    if normalized not in SUPPORTED_SEARCH_PROVIDERS:
        raise SearchProviderConfigError(f"不支持的搜索提供商：{normalized or '空值'}")
    return normalized


def _validate_url(url: str, provider: str) -> str:
    clean = str(url or "").strip() or _DEFAULT_URLS[provider]
    parts = urlsplit(clean)
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        raise SearchProviderConfigError("MCP URL 必须是有效的 HTTP 或 HTTPS 地址。")
    return clean


def _data_env_path() -> Path:
    configured = (os.environ.get("SPARKARC_SEARCH_PROVIDER_ENV_PATH") or "").strip()
    if configured:
        path = Path(configured).expanduser()
        if path.is_absolute():
            return path
        return Path(__file__).resolve().parents[2] / path
    return Path(__file__).resolve().parents[1] / "data" / ".env"


def _read_persisted_values() -> Dict[str, str]:
    path = _data_env_path()
    if not path.exists():
        return {}
    return {
        str(key): str(value or "").strip()
        for key, value in dotenv_values(path).items()
        if key
    }


def _read_value(key: str, persisted: Dict[str, str]) -> str:
    process_value = os.environ.get(key)
    if process_value is not None and process_value.strip():
        return process_value.strip()
    return str(persisted.get(key) or "").strip()


def _append_query_param(url: str, key: str, value: str) -> str:
    parts = urlsplit(url)
    query_items = [
        (name, item)
        for name, item in parse_qsl(parts.query, keep_blank_values=True)
        if name != key
    ]
    query_items.append((key, value))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query_items), parts.fragment))


def get_system_search_provider_runtime_config(provider: str) -> SearchProviderRuntimeConfig:
    """读取站点级搜索配置，不应用全体推理服务开关。"""
    normalized = _normalize_provider(provider)
    persisted = _read_persisted_values()
    return SearchProviderRuntimeConfig(
        provider=normalized,
        url=_validate_url(_read_value(_URL_ENV_KEYS[normalized], persisted), normalized),
        api_key=_read_value(_API_KEY_ENV_KEYS[normalized], persisted),
        source="system",
    )


def _get_user_record(user_id: str, provider: str):
    from llm.agen_matchbox import matchbox

    manager = matchbox()
    with manager.Session() as session:
        record = session.query(SearchProviderUserConfig).filter_by(
            user_id=str(user_id),
            provider=provider,
        ).first()
        if not record:
            return None
        return {
            "url": record.url,
            "api_key": record.api_key,
        }


def _decrypt_user_key(raw_key: Optional[str]) -> str:
    if not raw_key:
        return ""
    from llm.agen_matchbox.security import SecurityManager

    resolution = SecurityManager.get_instance().decrypt(raw_key)
    if resolution.has_plaintext:
        return str(resolution.value or "")
    raise SearchProviderConfigError(
        resolution.message or "搜索服务密钥无法解密，请前往设置重新配置。"
    )


def _system_search_service_enabled() -> bool:
    from llm.agen_matchbox import matchbox

    return bool(matchbox().get_system_config().get("llm_auto_key"))


def get_search_provider_runtime_config(
    provider: str,
    *,
    user_id: Optional[str] = None,
) -> SearchProviderRuntimeConfig:
    """按用户覆盖与系统托管开关解析实际搜索配置。"""
    normalized = _normalize_provider(provider)
    normalized_user_id = str(user_id or "").strip()
    if normalized_user_id:
        record = _get_user_record(normalized_user_id, normalized)
        if record:
            return SearchProviderRuntimeConfig(
                provider=normalized,
                url=_validate_url(record["url"], normalized),
                api_key=_decrypt_user_key(record["api_key"]),
                source="user",
            )
        if not _system_search_service_enabled():
            raise SearchProviderUnavailableError(
                "当前没有可用的联网搜索配置。请前往设置 → 模型平台 → 联网搜索服务，"
                "配置个人 MCP URL；密钥可留空使用免密钥模式。"
            )
    return get_system_search_provider_runtime_config(normalized)


def get_search_provider_admin_views() -> list[SearchProviderAdminView]:
    return [
        SearchProviderAdminView(
            provider=provider,
            url=config.url,
            api_key_set=bool(config.api_key),
        )
        for provider in SUPPORTED_SEARCH_PROVIDERS
        for config in [get_system_search_provider_runtime_config(provider)]
    ]


def get_search_provider_user_view(user_id: str) -> Dict[str, object]:
    """返回用户覆盖、系统默认和最终可用状态，绝不返回密钥明文。"""
    normalized_user_id = str(user_id)
    system_enabled = _system_search_service_enabled()
    providers = []
    for provider in SUPPORTED_SEARCH_PROVIDERS:
        system_config = get_system_search_provider_runtime_config(provider)
        record = _get_user_record(normalized_user_id, provider)
        user_configured = bool(record)
        effective_source = "user" if user_configured else ("system" if system_enabled else "unavailable")
        effective_url = record["url"] if record else (system_config.url if system_enabled else "")
        providers.append({
            "provider": provider,
            "default_url": _DEFAULT_URLS[provider],
            "system": {
                "enabled": system_enabled,
                "url": system_config.url,
                "api_key_set": bool(system_config.api_key),
            },
            "user": {
                "configured": user_configured,
                "url": record["url"] if record else "",
                "api_key_set": bool(record and record["api_key"]),
            },
            "effective": {
                "available": user_configured or system_enabled,
                "source": effective_source,
                "url": effective_url,
                "api_key_set": bool(record["api_key"]) if record else bool(system_config.api_key),
            },
        })
    return {
        "system_service_enabled": system_enabled,
        "providers": providers,
    }


def update_search_provider_user_settings(
    user_id: str,
    provider: str,
    *,
    url: str,
    api_key: Optional[str] = None,
) -> Dict[str, object]:
    """保存用户覆盖；``api_key=None`` 保留现有密钥，空字符串切换为免密钥。"""
    from llm.agen_matchbox import matchbox
    from llm.agen_matchbox.security import SecurityManager

    normalized = _normalize_provider(provider)
    clean_url = _validate_url(url, normalized)
    manager = matchbox()
    with manager.Session() as session:
        record = session.query(SearchProviderUserConfig).filter_by(
            user_id=str(user_id),
            provider=normalized,
        ).first()
        if not record:
            record = SearchProviderUserConfig(
                user_id=str(user_id),
                provider=normalized,
                url=clean_url,
            )
            session.add(record)
        else:
            record.url = clean_url

        if api_key is not None:
            clean_key = str(api_key).strip()
            record.api_key = (
                SecurityManager.get_instance().encrypt(clean_key)
                if clean_key
                else None
            )
        session.commit()
    return get_search_provider_user_view(str(user_id))


def reset_search_provider_user_settings(user_id: str, provider: str) -> Dict[str, object]:
    """删除用户覆盖，恢复系统默认或不可用状态。"""
    from llm.agen_matchbox import matchbox

    normalized = _normalize_provider(provider)
    manager = matchbox()
    with manager.Session() as session:
        session.query(SearchProviderUserConfig).filter_by(
            user_id=str(user_id),
            provider=normalized,
        ).delete(synchronize_session=False)
        session.commit()
    return get_search_provider_user_view(str(user_id))


def delete_search_provider_user_settings(user_id: str) -> None:
    """账户删除后清理其搜索配置。"""
    from llm.agen_matchbox import matchbox

    manager = matchbox(required=False)
    if manager is None:
        return
    with manager.Session() as session:
        session.query(SearchProviderUserConfig).filter_by(user_id=str(user_id)).delete(
            synchronize_session=False
        )
        session.commit()


def update_search_provider_settings(
    provider: str,
    *,
    url: Optional[str] = None,
    api_key: Optional[str] = None,
) -> SearchProviderAdminView:
    """更新站点默认配置；空密钥恢复系统免密钥访问。"""
    normalized = _normalize_provider(provider)
    env_path = _data_env_path()
    with _lock:
        env_path.parent.mkdir(parents=True, exist_ok=True)
        if not env_path.exists():
            env_path.write_text("", encoding="utf-8")

        if url is not None:
            clean_url = _validate_url(url, normalized)
            set_key(str(env_path), _URL_ENV_KEYS[normalized], clean_url, quote_mode="never")
            os.environ[_URL_ENV_KEYS[normalized]] = clean_url

        if api_key is not None:
            clean_key = api_key.strip()
            key_name = _API_KEY_ENV_KEYS[normalized]
            if clean_key:
                set_key(str(env_path), key_name, clean_key, quote_mode="never")
                os.environ[key_name] = clean_key
            else:
                unset_key(str(env_path), key_name)
                os.environ.pop(key_name, None)

        config = get_system_search_provider_runtime_config(normalized)
        return SearchProviderAdminView(
            provider=normalized,
            url=config.url,
            api_key_set=bool(config.api_key),
        )
