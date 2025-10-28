import os
import shutil

from flask import jsonify, request

from auth import require_auth, optional_auth
from request_context import get_current_info
from utils import (
    ensure_project_directory,
    ensure_project_stories_directory,
    ensure_project_worldview_and_character_settings,
    get_project_path,
    get_user_projects_root,
)

from . import story_bp


@story_bp.route('/api/projects', methods=['GET'])
@optional_auth
@get_current_info
def get_projects():
    """列出当前用户的所有项目"""
    try:
        user_id = request.current_user['user_id']
        projects_root = get_user_projects_root(user_id)
        if not os.path.exists(projects_root):
            os.makedirs(projects_root)
            return jsonify([])
        projects = [
            name
            for name in os.listdir(projects_root)
            if os.path.isdir(os.path.join(projects_root, name))
        ]
        return jsonify(sorted(projects))
    except Exception as exc:
        return jsonify({"success": False, "message": f"获取项目列表失败: {exc}"}), 500


@story_bp.route('/api/projects', methods=['POST'])
@require_auth
@get_current_info
def create_project():
    """创建新项目并初始化目录结构"""
    try:
        user_id = request.current_user['user_id']
        data = request.json or {}
        project_name = data.get('projectName')
        if not project_name:
            return jsonify({"success": False, "message": "项目名称不能为空"}), 400

        project_path = get_project_path(user_id, project_name)
        if os.path.exists(project_path):
            return jsonify({"success": False, "message": "项目已存在"}), 409

        ensure_project_directory(user_id, project_name)
        ensure_project_stories_directory(user_id, project_name)
        ensure_project_worldview_and_character_settings(user_id, project_name)
        return jsonify({"success": True, "message": "项目创建成功"})
    except Exception as exc:
        return jsonify({"success": False, "message": f"项目创建失败: {exc}"}), 500


@story_bp.route('/api/projects/<project_name>', methods=['DELETE'])
@require_auth
@get_current_info
def delete_project(project_name):
    """删除指定项目"""
    try:
        user_id = request.current_user['user_id']
        project_path = get_project_path(user_id, project_name)
        if not os.path.exists(project_path):
            return jsonify({"success": False, "message": "项目不存在"}), 404
        shutil.rmtree(project_path)
        return jsonify({"success": True, "message": "项目删除成功"})
    except Exception as exc:
        return jsonify({"success": False, "message": f"项目删除失败: {exc}"}), 500
