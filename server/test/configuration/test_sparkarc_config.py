"""守护 sparkarc.json 作为公开仓库与网络候选的唯一人工维护源。"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from core import network_probe
from core.sparkarc_config import (
    geoip_providers,
    load_sparkarc_config,
    network_candidates,
    repository_urls,
)


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def test_repository_urls_are_derived_from_root_manifest() -> None:
    config = load_sparkarc_config()
    urls = repository_urls()

    assert urls["slug"] == config["repository"]["slug"]
    assert urls["web"] == f"https://github.com/{urls['slug']}"
    assert urls["clone"] == f"{urls['web']}.git"
    assert urls["release_api"] == f"https://api.github.com/repos/{urls['slug']}/releases/latest"
    assert urls["release_page"] == f"{urls['web']}/releases/latest"


def test_mainland_clone_candidates_use_configured_proxies_before_official(monkeypatch) -> None:
    monkeypatch.setattr(network_probe, "is_mainland_china", lambda: True)

    candidates = network_probe.get_git_clone_candidates(probe=False)
    prefixes = network_candidates("gh_proxy", mainland=True)

    assert candidates[-1] == repository_urls()["clone"]
    assert candidates[0] == f"{prefixes[0].rstrip('/')}/{repository_urls()['clone']}"


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


def test_non_mainland_clone_candidates_keep_proxy_fallback(monkeypatch) -> None:
    monkeypatch.setattr(network_probe, "is_mainland_china", lambda: False)

    candidates = network_probe.get_git_clone_candidates(probe=False)

    assert candidates[0] == repository_urls()["clone"]
    assert len(candidates) > 1
    assert all(repository_urls()["clone"] in candidate for candidate in candidates[1:])


def test_powershell_probe_does_not_redeclare_repository_or_proxy_values() -> None:
    script = (PROJECT_ROOT / "scripts" / "network_probe.ps1").read_text(encoding="utf-8")
    manifest = json.loads((PROJECT_ROOT / "sparkarc.json").read_text(encoding="utf-8"))

    assert "Get-SparkArcConfig" in script
    assert "UseProxy = $false" in script
    assert "Invoke-ClientLocationLookup" not in script
    assert manifest["repository"]["slug"] not in script
    assert "https://ghfast.top/" not in script
    assert "https://ghproxy.net/" not in script


def test_windows_pyloader_does_not_hardcode_ustc_verification_address() -> None:
    script = (PROJECT_ROOT / "server" / "pyloader.win.ps1").read_text(encoding="utf-8")

    assert 'document\\.cookie\\s*=\\s*"addr=' in script
    assert 'System.Net.IPAddress]::TryParse' in script
    assert 'System.Net.Cookie("addr", $verificationAddress' in script
    assert 'System.Net.Cookie("addr", "122.' not in script
    assert "System.Security.Cryptography.SHA256]::Create" in script
    assert "$FinalReqHash = Get-RequirementsHash" in script


def test_windows_start_registers_service_from_server_import_root() -> None:
    script = (PROJECT_ROOT / "start.bat").read_text(encoding="utf-8")

    assert "sys.path.insert(0, os.path.join(root, 'server'))" in script
    assert "from core.service_registry import record_service_install" in script
    assert "[ERROR] Failed to register the local SparkArc service." in script


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
