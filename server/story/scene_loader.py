import json
import os
from typing import List

from .scene_models import SceneModel, scene_models_from_payload
from .arc_parser import parse_arc, detect_format


def load_story_file(file_path: str) -> List[SceneModel]:
    if not os.path.exists(file_path):
        return []
    
    try:
        with open(file_path, "r", encoding="utf-8") as handle:
            content = handle.read()
            
        # Detect format
        fmt = detect_format(content)
        
        if fmt == 'json':
            payload = json.loads(content)
        elif fmt == 'arc':
            payload = parse_arc(content)
        else:
            # Fallback: try JSON
            try:
                payload = json.loads(content)
            except:
                return []
                
    except (json.JSONDecodeError, OSError, Exception):
        return []
        
    return scene_models_from_payload(payload)
