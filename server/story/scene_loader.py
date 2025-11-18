import json
import os
from typing import List

from .scene_models import SceneModel, scene_models_from_payload


def load_story_file(file_path: str) -> List[SceneModel]:
    if not os.path.exists(file_path):
        return []
    try:
        with open(file_path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (json.JSONDecodeError, OSError):
        return []
    return scene_models_from_payload(payload)
