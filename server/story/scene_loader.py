import json
import os
from typing import List

from .scene_models import SceneModel, scene_models_from_payload
from .arc_parser import parse_arc, detect_format


def load_story_file(file_path: str) -> List[SceneModel]:
    """从 .arc 文件加载剧本模型"""
    if not os.path.exists(file_path):
        return []
    
    try:
        with open(file_path, "r", encoding="utf-8") as handle:
            content = handle.read()
            
        # 彻底移除 JSON 支持，仅解析 ARC 格式
        payload = parse_arc(content)
                
    except (OSError, Exception):
        return []
        
    return scene_models_from_payload(payload)
