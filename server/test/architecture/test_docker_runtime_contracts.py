from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def test_docker_runtime_keeps_local_embedding_native_dependencies() -> None:
    dockerfile = (PROJECT_ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert "apt-get install" in dockerfile
    assert "libgomp1" in dockerfile
    assert "libgomp.so.1" in dockerfile


def test_docker_deployments_keep_runtime_cache_persistent() -> None:
    compose = (PROJECT_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    gitea_deploy = (PROJECT_ROOT / ".gitea" / "workflows" / "deploy.yml").read_text(encoding="utf-8")

    assert "SPARKARC_RUNTIME_CACHE_DIR=/app/server/.runtime" in compose
    assert "./server/.runtime:/app/server/.runtime" in compose
    assert "SPARKARC_RUNTIME_CACHE_DIR=\"/app/server/.runtime\"" in gitea_deploy
    assert "sparkarc_runtime_cache" in gitea_deploy
