import json
import os

from flask import jsonify, request

from core.auth import optional_auth
from core.request_context import get_current_info

from .. import story_bp


@story_bp.route('/剧本示例.story')
@optional_auth
@get_current_info
def get_dialogue_data():
    """读取示例剧本文件，若缺失则返回空字符串"""
    try:
        file_path = os.path.join(os.path.dirname(__file__), '..', '..', '剧本示例.story')
        file_path = os.path.abspath(file_path)
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return jsonify(data)
        return jsonify("")
    except Exception as exc:  # pragma: no cover - 调试辅助
        print(f"加载剧本示例.story 出错: {exc}")
        return jsonify("")


@story_bp.route('/save', methods=['POST'])
@optional_auth
@get_current_info
def save_dialogue():
    """保存示例剧本文件内容"""
    try:
        data = request.json
        file_path = os.path.join(os.path.dirname(__file__), '..', '..', '剧本示例.story')
        file_path = os.path.abspath(file_path)
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return jsonify({"success": True, "message": "保存成功"})
    except Exception as exc:
        return jsonify({"success": False, "message": f"保存失败: {exc}"}), 500