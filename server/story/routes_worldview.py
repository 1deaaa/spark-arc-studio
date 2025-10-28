import os

from flask import jsonify, request

from auth import require_auth, optional_auth
from request_context import get_current_info
from utils import (
    ensure_project_directory,
    ensure_project_worldview_and_character_settings,
    get_project_worldview_path,
)

from . import story_bp


def _write_worldview(user_id: int, project_name: str, content: str) -> None:
    ensure_project_worldview_and_character_settings(user_id, project_name)
    worldview_path = get_project_worldview_path(user_id, project_name)
    ensure_project_directory(user_id, project_name)
    with open(worldview_path, 'w', encoding='utf-8') as f:
        f.write(content)


@story_bp.route('/api/worldview/<project_name>', methods=['GET'])
@optional_auth
@get_current_info
def get_worldview(project_name):
    """读取指定项目的世界观文本"""
    try:
        user_id = request.current_user['user_id']
        ensure_project_worldview_and_character_settings(user_id, project_name)
        worldview_path = get_project_worldview_path(user_id, project_name)
        if not os.path.exists(worldview_path):
            return jsonify({'content': ''})
        with open(worldview_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return jsonify({'content': content})
    except Exception as exc:
        return jsonify({'error': f'读取世界观失败: {exc}'}), 500


@story_bp.route('/api/worldview/<project_name>', methods=['POST'])
@require_auth
@get_current_info
def save_worldview(project_name):
    """直接通过路径参数保存世界观内容"""
    try:
        user_id = request.current_user['user_id']
        data = request.json or {}
        content = data.get('content', '')
        _write_worldview(user_id, project_name, content)
        return jsonify({'success': True, 'message': '保存成功'})
    except Exception as exc:
        return jsonify({'success': False, 'message': f'保存失败: {exc}'}), 500


@story_bp.route('/api/worldview', methods=['POST'])
@require_auth
def save_worldview_content():
    """兼容 body 内带项目名称的保存方式"""
    try:
        user_id = request.current_user['user_id']
        data = request.get_json() or {}
        project_name = data.get('projectName')
        content = data.get('content', '')
        if not project_name:
            return jsonify({'success': False, 'message': '缺少项目名称'}), 400
        _write_worldview(user_id, project_name, content)
        return jsonify({'success': True, 'message': '世界观保存成功'})
    except Exception as exc:
        return jsonify({'success': False, 'message': f'保存世界观失败: {exc}'}), 500
