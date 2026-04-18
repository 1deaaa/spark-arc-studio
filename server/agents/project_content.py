from __future__ import annotations

import os

from core.utils import get_project_path


def load_worldview(user_id: str, project_name: str) -> str:
    path = os.path.join(get_project_path(user_id, project_name), "世界观.txt")
    if not os.path.exists(path):
        return ""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()
