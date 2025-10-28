import json
import os

from flask import jsonify, request

from auth import require_auth
from request_context import get_current_info
from utils import get_project_path

from . import story_bp


@story_bp.route('/api/blueprint/<project_name>', methods=['GET'])
@require_auth
@get_current_info
def get_blueprint(project_name):
    """读取项目蓝图数据"""
    try:
        user_id = request.current_user['user_id']
        blueprint_file = os.path.join(get_project_path(user_id, project_name), f"{project_name}.blueprint")
        if not os.path.exists(blueprint_file):
            return jsonify({})
        with open(blueprint_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return jsonify(data)
    except Exception as exc:
        return jsonify({'error': f'读取蓝图失败: {exc}'}), 500


@story_bp.route('/api/blueprint/<project_name>', methods=['POST'])
@require_auth
@get_current_info
def save_blueprint(project_name):
    """保存项目蓝图数据"""
    try:
        user_id = request.current_user['user_id']
        data = request.json
        blueprint_file = os.path.join(get_project_path(user_id, project_name), f"{project_name}.blueprint")
        with open(blueprint_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return jsonify({'success': True, 'message': '蓝图保存成功'})
    except Exception as exc:
        return jsonify({'success': False, 'message': f'保存蓝图失败: {exc}'}), 500
