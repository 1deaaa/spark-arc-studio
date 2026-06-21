"""运行时缓存目录工具。"""

from __future__ import annotations

import os
from pathlib import Path


def get_runtime_cache_dir() -> Path:
    """返回 SparkArc 运行时缓存根目录。

    本地开发默认继续使用 ``server/.runtime``，Docker 部署可通过
    ``SPARKARC_RUNTIME_CACHE_DIR`` 指向持久卷内目录。
    """
    server_root = Path(__file__).resolve().parents[1]
    configured = (os.getenv("SPARKARC_RUNTIME_CACHE_DIR") or "").strip()
    if configured:
        cache_dir = Path(configured).expanduser()
        if not cache_dir.is_absolute():
            cache_dir = server_root / cache_dir
        return cache_dir
    return server_root / ".runtime"


def configure_runtime_cache_environment() -> dict[str, str]:
    """为第三方模型/分词器库设置持久缓存环境变量。

    已由用户或部署环境显式设置的变量不会被覆盖。
    """
    cache_root = get_runtime_cache_dir()
    values = {
        "HF_HOME": str(cache_root / "huggingface"),
        "HF_HUB_CACHE": str(cache_root / "huggingface" / "hub"),
        "TRANSFORMERS_CACHE": str(cache_root / "huggingface" / "transformers"),
        "TIKTOKEN_CACHE_DIR": str(cache_root / "tiktoken"),
    }
    for key, value in values.items():
        os.environ.setdefault(key, value)
    return {key: os.environ[key] for key in values}
