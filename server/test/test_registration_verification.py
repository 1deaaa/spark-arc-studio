import asyncio
from pathlib import Path
import sys

import pytest


SERVER_ROOT = Path(__file__).resolve().parents[1]
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))


from core import verification


@pytest.fixture(autouse=True)
def _ignore_local_dotenv(monkeypatch):
    monkeypatch.setattr(verification, "_DOTENV_CACHE", {})
    monkeypatch.setattr(verification, "_ASYNC_CLIENT_FACTORY", None)


def test_registration_verification_defaults_off_without_turnstile_secret(monkeypatch):
    monkeypatch.setenv("SPARKARC_REGISTRATION_VERIFICATION_ENABLED", "1")
    monkeypatch.setenv("SPARKARC_REGISTRATION_VERIFICATION_PROVIDER", "turnstile")
    monkeypatch.setenv("SPARKARC_TURNSTILE_SITE_KEY", "site-key")
    monkeypatch.delenv("SPARKARC_TURNSTILE_SECRET_KEY", raising=False)
    monkeypatch.delenv("TURNSTILE_SECRET_KEY", raising=False)
    monkeypatch.delenv("CF_TURNSTILE_SECRET_KEY", raising=False)

    config = verification.get_registration_verification_config()
    result = asyncio.run(verification.verify_registration_challenge(""))

    assert config.enabled is False
    assert result.success is True


def test_registration_verification_requires_token(monkeypatch):
    monkeypatch.setenv("SPARKARC_REGISTRATION_VERIFICATION_ENABLED", "1")
    monkeypatch.setenv("SPARKARC_REGISTRATION_VERIFICATION_PROVIDER", "turnstile")
    monkeypatch.setenv("SPARKARC_TURNSTILE_SITE_KEY", "site-key")
    monkeypatch.setenv("SPARKARC_TURNSTILE_SECRET_KEY", "secret")

    result = asyncio.run(verification.verify_registration_challenge(""))

    assert result.success is False
    assert result.error_code == "missing_token"


def test_turnstile_verification_posts_token_and_remote_ip(monkeypatch):
    captured = {}

    class DummyResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"success": True, "hostname": "example.com"}

    class DummyClient:
        def __init__(self, timeout):
            captured["timeout"] = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, url, data):
            captured["url"] = url
            captured["data"] = data
            return DummyResponse()

    monkeypatch.setenv("SPARKARC_REGISTRATION_VERIFICATION_ENABLED", "1")
    monkeypatch.setenv("SPARKARC_REGISTRATION_VERIFICATION_PROVIDER", "turnstile")
    monkeypatch.setenv("SPARKARC_TURNSTILE_SITE_KEY", "site-key")
    monkeypatch.setenv("SPARKARC_TURNSTILE_SECRET_KEY", "secret")
    monkeypatch.setattr(verification, "_ASYNC_CLIENT_FACTORY", DummyClient)

    result = asyncio.run(
        verification.verify_registration_challenge(
            "visitor-token",
            provider="turnstile",
            remote_ip="203.0.113.10",
        )
    )

    assert result.success is True
    assert captured["url"] == verification.TURNSTILE_SITEVERIFY_URL
    assert captured["data"] == {
        "secret": "secret",
        "response": "visitor-token",
        "remoteip": "203.0.113.10",
    }


def test_turnstile_failure_is_normalized(monkeypatch):
    class DummyResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"success": False, "error-codes": ["timeout-or-duplicate"]}

    class DummyClient:
        def __init__(self, timeout):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, url, data):
            return DummyResponse()

    monkeypatch.setenv("SPARKARC_REGISTRATION_VERIFICATION_ENABLED", "1")
    monkeypatch.setenv("SPARKARC_REGISTRATION_VERIFICATION_PROVIDER", "turnstile")
    monkeypatch.setenv("SPARKARC_TURNSTILE_SITE_KEY", "site-key")
    monkeypatch.setenv("SPARKARC_TURNSTILE_SECRET_KEY", "secret")
    monkeypatch.setattr(verification, "_ASYNC_CLIENT_FACTORY", DummyClient)

    result = asyncio.run(verification.verify_registration_challenge("used-token"))

    assert result.success is False
    assert result.error_code == "turnstile_failed"
    assert result.provider_response == {"success": False, "error-codes": ["timeout-or-duplicate"]}
