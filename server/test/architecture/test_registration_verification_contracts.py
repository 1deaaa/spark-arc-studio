from __future__ import annotations

from core import verification


def test_registration_verification_persists_to_server_data_env_by_default(monkeypatch, tmp_path) -> None:
    server_root = tmp_path / "server"
    server_root.mkdir()

    monkeypatch.setattr(verification.Path, "resolve", lambda self: server_root / "core" / "verification.py")
    monkeypatch.delenv("SPARKARC_REGISTRATION_VERIFICATION_ENV_PATH", raising=False)
    for key in (
        "SPARKARC_REGISTRATION_VERIFICATION_ENABLED",
        "SPARKARC_REGISTRATION_VERIFICATION_PROVIDER",
        "SPARKARC_TURNSTILE_SITE_KEY",
        "SPARKARC_TURNSTILE_SECRET_KEY",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(verification, "_DOTENV_CACHE", None)

    view = verification.update_registration_verification_settings(
        enabled=True,
        provider="turnstile",
        site_key="site-key",
        secret_key="secret-key",
    )

    env_path = server_root / "data" / ".env"
    env_text = env_path.read_text(encoding="utf-8")
    assert view.enabled is True
    assert "SPARKARC_TURNSTILE_SITE_KEY=site-key" in env_text
    assert "SPARKARC_TURNSTILE_SECRET_KEY=secret-key" in env_text


def test_registration_verification_empty_container_env_falls_back_to_persisted_file(monkeypatch, tmp_path) -> None:
    server_root = tmp_path / "server"
    data_dir = server_root / "data"
    data_dir.mkdir(parents=True)
    (data_dir / ".env").write_text(
        "\n".join(
            [
                "SPARKARC_REGISTRATION_VERIFICATION_ENABLED=1",
                "SPARKARC_REGISTRATION_VERIFICATION_PROVIDER=turnstile",
                "SPARKARC_TURNSTILE_SITE_KEY=file-site-key",
                "SPARKARC_TURNSTILE_SECRET_KEY=file-secret-key",
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(verification.Path, "resolve", lambda self: server_root / "core" / "verification.py")
    monkeypatch.setenv("SPARKARC_REGISTRATION_VERIFICATION_ENABLED", "")
    monkeypatch.setenv("SPARKARC_REGISTRATION_VERIFICATION_PROVIDER", "")
    monkeypatch.setenv("SPARKARC_TURNSTILE_SITE_KEY", "")
    monkeypatch.setenv("SPARKARC_TURNSTILE_SECRET_KEY", "")
    monkeypatch.setattr(verification, "_DOTENV_CACHE", None)

    config = verification.get_registration_verification_config()

    assert config.enabled is True
    assert config.provider == "turnstile"
    assert config.site_key == "file-site-key"
