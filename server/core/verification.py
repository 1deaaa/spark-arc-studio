from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Optional


TURNSTILE_SITEVERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


class VerificationUnavailableError(RuntimeError):
    """Raised when the configured verification provider cannot be reached."""


@dataclass(frozen=True)
class RegistrationVerificationConfig:
    enabled: bool
    provider: str
    site_key: str


@dataclass(frozen=True)
class VerificationResult:
    success: bool
    message: str = ""
    error_code: str = ""
    provider_response: Optional[Dict[str, Any]] = None


_DOTENV_CACHE: Optional[Dict[str, str]] = None
_ASYNC_CLIENT_FACTORY: Optional[Callable[..., Any]] = None


def _get_async_client_factory() -> Callable[..., Any]:
    if _ASYNC_CLIENT_FACTORY is not None:
        return _ASYNC_CLIENT_FACTORY

    import httpx

    return httpx.AsyncClient


def _load_dotenv_values() -> Dict[str, str]:
    global _DOTENV_CACHE
    if _DOTENV_CACHE is not None:
        return _DOTENV_CACHE

    server_root = Path(__file__).resolve().parents[1]
    project_root = server_root.parent
    values: Dict[str, str] = {}
    for env_path in (project_root / ".env", server_root / ".env"):
        if not env_path.exists():
            continue
        values.update(_parse_dotenv_file(env_path))
    _DOTENV_CACHE = values
    return values


def _parse_dotenv_file(path: Path) -> Dict[str, str]:
    parsed: Dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return parsed

    for line in lines:
        clean = line.strip()
        if not clean or clean.startswith("#") or "=" not in clean:
            continue
        key, value = clean.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            parsed[key] = value
    return parsed


def _env(name: str, default: str = "") -> str:
    import os

    raw = os.environ.get(name)
    if raw is None:
        raw = _load_dotenv_values().get(name)
    return (raw if raw is not None else default).strip()


def _env_bool(name: str, default: bool) -> bool:
    raw = _env(name)
    if not raw:
        return default
    return raw.lower() in {"1", "true", "yes", "on", "enabled"}


def _turnstile_secret_key() -> str:
    return (
        _env("SPARKARC_TURNSTILE_SECRET_KEY")
        or _env("TURNSTILE_SECRET_KEY")
        or _env("CF_TURNSTILE_SECRET_KEY")
    )


def get_registration_verification_config() -> RegistrationVerificationConfig:
    provider = (_env("SPARKARC_REGISTRATION_VERIFICATION_PROVIDER", "turnstile") or "turnstile").lower()
    site_key = (
        _env("SPARKARC_TURNSTILE_SITE_KEY")
        or _env("TURNSTILE_SITE_KEY")
        or _env("CF_TURNSTILE_SITE_KEY")
    )
    secret_key = _turnstile_secret_key()
    provider_ready = bool(site_key and secret_key) if provider == "turnstile" else False
    enabled = provider_ready and _env_bool("SPARKARC_REGISTRATION_VERIFICATION_ENABLED", provider_ready)
    return RegistrationVerificationConfig(enabled=enabled, provider=provider, site_key=site_key)


async def verify_registration_challenge(
    token: Optional[str],
    *,
    provider: Optional[str] = None,
    remote_ip: Optional[str] = None,
) -> VerificationResult:
    config = get_registration_verification_config()
    if not config.enabled:
        return VerificationResult(success=True)

    requested_provider = (provider or config.provider).strip().lower()
    if requested_provider != config.provider:
        return VerificationResult(
            success=False,
            message="人机验证方式不匹配，请刷新页面后重试",
            error_code="provider_mismatch",
        )

    clean_token = (token or "").strip()
    if not clean_token:
        return VerificationResult(
            success=False,
            message="请先完成人机验证",
            error_code="missing_token",
        )

    if config.provider == "turnstile":
        return await _verify_turnstile(clean_token, remote_ip=remote_ip)

    return VerificationResult(
        success=False,
        message="当前验证方式尚未接入",
        error_code="unsupported_provider",
    )


async def _verify_turnstile(token: str, *, remote_ip: Optional[str] = None) -> VerificationResult:
    secret_key = _turnstile_secret_key()
    if not secret_key:
        raise VerificationUnavailableError("Turnstile secret key is not configured")

    data = {
        "secret": secret_key,
        "response": token,
    }
    if remote_ip:
        data["remoteip"] = remote_ip

    try:
        async_client_factory = _get_async_client_factory()
        async with async_client_factory(timeout=8.0) as client:
            response = await client.post(TURNSTILE_SITEVERIFY_URL, data=data)
            response.raise_for_status()
            payload = response.json()
    except Exception as exc:
        raise VerificationUnavailableError("Turnstile validation request failed") from exc

    if payload.get("success") is True:
        return VerificationResult(success=True, provider_response=payload)

    return VerificationResult(
        success=False,
        message="人机验证未通过，请重试",
        error_code="turnstile_failed",
        provider_response=payload,
    )
