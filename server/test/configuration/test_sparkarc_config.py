"""守护 sparkarc.json 作为公开仓库与网络候选的唯一人工维护源。"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from core import network_probe
from core.sparkarc_config import (
    geoip_providers,
    load_sparkarc_config,
    network_candidates,
    repository_urls,
)


PROJECT_ROOT = Path(__file__).resolve().parents[3]
WINDOWS_POWERSHELL_SCRIPTS = (
    PROJECT_ROOT / "server" / "pyloader.win.ps1",
    PROJECT_ROOT / "scripts" / "network_probe.ps1",
)


def test_repository_urls_are_derived_from_root_manifest() -> None:
    config = load_sparkarc_config()
    urls = repository_urls()

    assert urls["slug"] == config["repository"]["slug"]
    assert urls["web"] == f"https://github.com/{urls['slug']}"
    assert urls["clone"] == f"{urls['web']}.git"
    assert urls["mainland_clones"] == config["repository"]["mainlandCloneUrls"]
    assert urls["release_api"] == f"https://api.github.com/repos/{urls['slug']}/releases/latest"
    assert urls["release_page"] == f"{urls['web']}/releases/latest"


def test_mainland_clone_candidates_use_gitee_before_official_without_proxies(monkeypatch) -> None:
    monkeypatch.setattr(network_probe, "is_mainland_china", lambda: True)

    candidates = network_probe.get_git_clone_candidates(probe=False)
    assert candidates[-1] == repository_urls()["clone"]
    assert candidates[:-1] == repository_urls()["mainland_clones"]
    assert all("ghproxy" not in candidate and "gh-proxy" not in candidate for candidate in candidates)


def test_network_probe_reads_geoip_and_route_data_from_manifest(monkeypatch) -> None:
    monkeypatch.setattr(network_probe, "is_mainland_china", lambda: False)
    assert network_probe._GEOIP_PROVIDERS == geoip_providers()
    assert network_probe.get_hf_candidates(probe=False) == network_candidates(
        "huggingface",
        mainland=False,
    )


def test_single_direct_geoip_result_is_not_enough_to_classify_region(monkeypatch) -> None:
    monkeypatch.setattr(network_probe, "_GEOIP_PROVIDERS", ["https://one.example.invalid/"])
    monkeypatch.setattr(
        network_probe,
        "_fetch_json_direct",
        lambda *_args, **_kwargs: {"country_code": "US", "country_name": "United States"},
    )
    monkeypatch.setattr(network_probe, "_region_cache", (0.0, None))

    region = network_probe.lookup_region()

    assert region["country_code"] == "UNKNOWN"
    assert region["is_mainland_china"] is None
    assert region["confidence"] == "unknown"


def test_geoip_request_explicitly_ignores_environment_proxy(monkeypatch) -> None:
    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, str]:
            return {"country": "CN"}

    class FakeSession:
        def __init__(self) -> None:
            self.trust_env = True

        def __enter__(self):
            return self

        def __exit__(self, *_args) -> None:
            return None

        def get(self, _url: str, *, timeout: float):
            assert timeout > 0
            assert self.trust_env is False
            return FakeResponse()

    monkeypatch.setattr(network_probe.requests, "Session", FakeSession)

    assert network_probe._fetch_json_direct("https://geo.example.invalid/") == {"country": "CN"}


def test_two_matching_direct_geoip_results_classify_mainland(monkeypatch) -> None:
    monkeypatch.setattr(
        network_probe,
        "_GEOIP_PROVIDERS",
        ["https://one.example.invalid/", "https://two.example.invalid/"],
    )
    monkeypatch.setattr(
        network_probe,
        "_fetch_json_direct",
        lambda *_args, **_kwargs: {"country_code": "CN", "country_name": "China"},
    )
    monkeypatch.setattr(network_probe, "_region_cache", (0.0, None))

    region = network_probe.lookup_region()

    assert region["country_code"] == "CN"
    assert region["is_mainland_china"] is True
    assert region["confidence"] == "direct_consensus"


def test_non_mainland_clone_candidates_keep_gitee_fallback(monkeypatch) -> None:
    monkeypatch.setattr(network_probe, "is_mainland_china", lambda: False)

    candidates = network_probe.get_git_clone_candidates(probe=False)

    assert candidates[0] == repository_urls()["clone"]
    assert candidates[1:] == repository_urls()["mainland_clones"]


def test_powershell_probe_does_not_redeclare_repository_or_proxy_values() -> None:
    script = (PROJECT_ROOT / "scripts" / "network_probe.ps1").read_text(encoding="utf-8")
    manifest = json.loads((PROJECT_ROOT / "sparkarc.json").read_text(encoding="utf-8"))

    assert "Get-SparkArcConfig" in script
    assert "UseProxy = $false" in script
    assert "Invoke-ClientLocationLookup" not in script
    assert manifest["repository"]["slug"] not in script
    assert "https://ghfast.top/" not in script
    assert "https://ghproxy.net/" not in script

    clone_function = script.split("function Get-GitCloneCandidates", 1)[1].split(
        "function Get-RecommendedMirror", 1
    )[0]
    assert "$SparkArcConfig.repository.mainlandCloneUrls" in clone_function
    assert 'Get-RecommendedMirror -Type "gh_proxy"' not in clone_function
    assert "$proxiedCandidates" not in clone_function


def test_windows_pyloader_does_not_hardcode_ustc_verification_address() -> None:
    script = (PROJECT_ROOT / "server" / "pyloader.win.ps1").read_text(encoding="utf-8")

    assert 'document\\.cookie\\s*=\\s*"addr=' in script
    assert 'System.Net.IPAddress]::TryParse' in script
    assert 'System.Net.Cookie("addr", $verificationAddress' in script
    assert 'System.Net.Cookie("addr", "122.' not in script
    assert "System.Security.Cryptography.SHA256]::Create" in script
    assert "$FinalReqHash = Get-RequirementsHash" in script


def test_windows_powershell_startup_scripts_are_ascii() -> None:
    for script_path in WINDOWS_POWERSHELL_SCRIPTS:
        script_bytes = script_path.read_bytes()
        assert script_bytes.isascii(), f"PowerShell 5.1 startup script must be ASCII: {script_path}"


@pytest.mark.skipif(sys.platform != "win32", reason="Windows PowerShell is only available on Windows")
def test_windows_powershell_51_parses_startup_scripts() -> None:
    powershell = (
        Path(os.environ.get("WINDIR", r"C:\Windows"))
        / "System32"
        / "WindowsPowerShell"
        / "v1.0"
        / "powershell.exe"
    )
    if not powershell.is_file():
        pytest.skip("Windows PowerShell executable was not found")

    parser_command = (
        "$tokens = $null; $errors = $null; "
        "if ($PSVersionTable.PSVersion.Major -ne 5) { exit 2 }; "
        "[System.Management.Automation.Language.Parser]::ParseFile("
        "$env:SPARKARC_PS_PARSE_TARGET, [ref]$tokens, [ref]$errors) > $null; "
        "if ($errors.Count -gt 0) { $errors | ForEach-Object { "
        "[Console]::Error.WriteLine($_.ToString()) }; exit 1 }"
    )
    for script_path in WINDOWS_POWERSHELL_SCRIPTS:
        completed = subprocess.run(
            [
                str(powershell),
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                parser_command,
            ],
            capture_output=True,
            text=True,
            check=False,
            env={**os.environ, "SPARKARC_PS_PARSE_TARGET": str(script_path)},
        )
        assert completed.returncode == 0, completed.stderr or completed.stdout


def test_launcher_calls_managed_checkout_the_app_data_directory() -> None:
    deployment = (PROJECT_ROOT / "client" / "src-tauri" / "src" / "deployment" / "mod.rs").read_text(
        encoding="utf-8"
    )

    assert "无法将已校验的源码切换到受管目录" not in deployment
    assert "受管目录包含未声明的本地修改" not in deployment
    assert "无法将已校验的源码切换到 APP 数据目录" in deployment
    assert "APP 数据目录包含未声明的本地修改" in deployment


def test_launcher_only_uses_managed_root_and_source_startup_cannot_override_it() -> None:
    windows_script = (PROJECT_ROOT / "start.bat").read_text(encoding="utf-8")
    unix_script = (PROJECT_ROOT / "start.sh").read_text(encoding="utf-8")
    server_app = (PROJECT_ROOT / "server" / "app.py").read_text(encoding="utf-8")
    launcher_lib = (PROJECT_ROOT / "client" / "src-tauri" / "src" / "lib.rs").read_text(
        encoding="utf-8"
    )
    launcher_constants = (PROJECT_ROOT / "client" / "launcher" / "constants.ts").read_text(
        encoding="utf-8"
    )

    for source in (windows_script, unix_script, server_app):
        assert "record_service_install" not in source
        assert "service_registry" not in source

    assert "ensure_managed_checkout" in launcher_lib
    assert "valid_record_project_root" not in launcher_lib
    assert "find_sibling_backend" not in launcher_lib
    assert "LAUNCHER_SERVICE_RECORD_FILE" not in launcher_constants
    assert "LAUNCHER_LOCAL_BACKEND_DIR_NAMES" not in launcher_constants


def test_generated_public_address_outputs_are_in_sync() -> None:
    completed = subprocess.run(
        ["node", "scripts/sync-sparkarc-config.mjs", "--check"],
        cwd=PROJECT_ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
