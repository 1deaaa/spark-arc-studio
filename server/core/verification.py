from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Optional


TURNSTILE_SITEVERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"

SUPPORTED_PROVIDERS = ("turnstile",)


class VerificationUnavailableError(RuntimeError):
    """Raised when the configured verification provider cannot be reached."""


class VerificationConfigError(ValueError):
    """Raised when admin attempts to persist invalid verification config."""


@dataclass(frozen=True)
class RegistrationVerificationConfig:
    enabled: bool
    provider: str
    site_key: str


@dataclass(frozen=True)
class RegistrationVerificationAdminView:
    """Full admin-facing view of the registration verification config.

    The secret key value is never returned to the client; only ``secret_key_set``
    indicates whether a non-empty value is currently persisted.
    """

    enabled: bool
    provider: str
    site_key: str
    secret_key_set: bool
    supported_providers: tuple = SUPPORTED_PROVIDERS


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


def get_registration_verification_admin_view() -> RegistrationVerificationAdminView:
    """Admin-facing snapshot, including whether a secret key is persisted (masked)."""
    provider = (_env("SPARKARC_REGISTRATION_VERIFICATION_PROVIDER", "turnstile") or "turnstile").lower()
    site_key = (
        _env("SPARKARC_TURNSTILE_SITE_KEY")
        or _env("TURNSTILE_SITE_KEY")
        or _env("CF_TURNSTILE_SITE_KEY")
    )
    secret_key = _turnstile_secret_key()
    enabled = _env_bool("SPARKARC_REGISTRATION_VERIFICATION_ENABLED", False) and bool(site_key) and bool(secret_key)
    return RegistrationVerificationAdminView(
        enabled=enabled,
        provider=provider,
        site_key=site_key,
        secret_key_set=bool(secret_key),
    )


def _get_project_dotenv_path() -> Path:
    """Project-root ``.env`` is the canonical location for verification config."""
    server_root = Path(__file__).resolve().parents[1]
    return server_root.parent / ".env"


def _persist_env_values(updates: Dict[str, Optional[str]]) -> None:
    """Write/clear keys in the project root ``.env`` and refresh in-process state.

    - ``value is None`` (or empty string) removes the key from the file.
    - Non-empty values are written via ``python-dotenv``'s ``set_key`` to preserve
      formatting and quoting consistency with the rest of the project.
    - ``os.environ`` is synchronised so the running process picks up the change
      immediately (since :func:`_env` consults ``os.environ`` first).
    - The local dotenv cache is invalidated so the next read reflects the file.
    """
    import os

    from dotenv import set_key, unset_key

    env_path = _get_project_dotenv_path()
    env_path.parent.mkdir(parents=True, exist_ok=True)
    if not env_path.exists():
        env_path.write_text("", encoding="utf-8")

    for key, value in updates.items():
        if value is None or (isinstance(value, str) and not value.strip()):
            unset_key(str(env_path), key)
            os.environ.pop(key, None)
            continue
        clean = value.strip() if isinstance(value, str) else str(value)
        set_key(str(env_path), key, clean, quote_mode="never")
        os.environ[key] = clean

    global _DOTENV_CACHE
    _DOTENV_CACHE = None


def update_registration_verification_settings(
    *,
    enabled: bool,
    provider: Optional[str] = None,
    site_key: Optional[str] = None,
    secret_key: Optional[str] = None,
) -> RegistrationVerificationAdminView:
    """Persist registration verification config to the project root ``.env``.

    Validation rules:
    - ``provider`` must be one of :data:`SUPPORTED_PROVIDERS`.
    - When ``enabled=True``, both ``site_key`` and a persisted secret must exist
      after the update (i.e. either supplied here or already on disk).
    - ``secret_key=None`` keeps the existing persisted secret (so admins can
      edit only the site key without re-entering the secret). Passing an empty
      string clears the secret.
    """
    desired_provider = (provider or "turnstile").strip().lower() or "turnstile"
    if desired_provider not in SUPPORTED_PROVIDERS:
        raise VerificationConfigError(f"unsupported provider: {desired_provider}")

    updates: Dict[str, Optional[str]] = {
        "SPARKARC_REGISTRATION_VERIFICATION_PROVIDER": desired_provider,
    }

    if site_key is not None:
        updates["SPARKARC_TURNSTILE_SITE_KEY"] = site_key.strip() or None

    if secret_key is not None:
        updates["SPARKARC_TURNSTILE_SECRET_KEY"] = secret_key.strip() or None

    updates["SPARKARC_REGISTRATION_VERIFICATION_ENABLED"] = "1" if enabled else "0"

    if enabled:
        prospective_site = (
            updates.get("SPARKARC_TURNSTILE_SITE_KEY")
            if "SPARKARC_TURNSTILE_SITE_KEY" in updates
            else (
                _env("SPARKARC_TURNSTILE_SITE_KEY")
                or _env("TURNSTILE_SITE_KEY")
                or _env("CF_TURNSTILE_SITE_KEY")
            )
        )
        prospective_secret = (
            updates.get("SPARKARC_TURNSTILE_SECRET_KEY")
            if "SPARKARC_TURNSTILE_SECRET_KEY" in updates
            else _turnstile_secret_key()
        )
        if not prospective_site:
            raise VerificationConfigError("site_key is required to enable verification")
        if not prospective_secret:
            raise VerificationConfigError("secret_key is required to enable verification")

    _persist_env_values(updates)
    return get_registration_verification_admin_view()


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
