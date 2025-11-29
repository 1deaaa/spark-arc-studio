import json
import os

from flask import jsonify, request

from core.auth import require_auth, optional_auth
from core.request_context import get_current_info
from core.utils import (
    ensure_project_characters_directory,
    get_project_characters_path,
)

from .. import story_bp


def _ensure_bindings(characters_path: str) -> dict:
    mapping_file = os.path.join(characters_path, 'chr.bind')
    if not os.path.exists(mapping_file):
        return {}
    with open(mapping_file, 'r', encoding='utf-8') as f:
        try:
            return json.load(f) or {}
        except json.JSONDecodeError:
            return {}


def _write_bindings(characters_path: str, bindings: dict) -> None:
    mapping_file = os.path.join(characters_path, 'chr.bind')
    with open(mapping_file, 'w', encoding='utf-8') as f:
        json.dump(bindings, f, ensure_ascii=False, indent=2)


@story_bp.route('/api/characters/<project_name>', methods=['GET'])
@optional_auth
@get_current_info
def get_characters(project_name):
    """获取项目的角色列表"""
    try:
        user_id = request.current_user['user_id']
        characters_path = get_project_characters_path(user_id, project_name)
        mapping_file = os.path.join(characters_path, 'chr.bind')
        if not os.path.exists(mapping_file):
            return jsonify([])
        with open(mapping_file, 'r', encoding='utf-8') as f:
            char_map = json.load(f)
        characters = [{'id': int(cid), 'name': name} for cid, name in char_map.items()]
        characters.sort(key=lambda item: item['id'])
        return jsonify(characters)
    except Exception as exc:
        return jsonify({'error': f'获取角色列表失败: {exc}'}), 500


@story_bp.route('/api/characters/<project_name>/<int:character_id>', methods=['GET'])
@optional_auth
@get_current_info
def get_character(project_name, character_id):
    """获取指定角色内容"""
    try:
        user_id = request.current_user['user_id']
        characters_path = get_project_characters_path(user_id, project_name)
        character_file = os.path.join(characters_path, f"{character_id}.txt")
        if not os.path.exists(character_file):
            return jsonify({'error': '角色不存在'}), 404
        with open(character_file, 'r', encoding='utf-8') as f:
            content = f.read()
        return jsonify({'content': content})
    except Exception as exc:
        return jsonify({'error': f'读取角色失败: {exc}'}), 500


@story_bp.route('/api/characters/<project_name>/<int:character_id>', methods=['POST'])
@require_auth
def save_character(project_name, character_id):
    """保存角色内容"""
    try:
        user_id = request.current_user['user_id']
        data = request.json or {}
        content = data.get('content', '')
        characters_path = get_project_characters_path(user_id, project_name)
        ensure_project_characters_directory(user_id, project_name)
        character_file = os.path.join(characters_path, f"{character_id}.txt")
        with open(character_file, 'w', encoding='utf-8') as f:
            f.write(content)
        return jsonify({'success': True, 'message': '保存成功'})
    except Exception as exc:
        return jsonify({'success': False, 'message': f'保存失败: {exc}'}), 500


@story_bp.route('/api/characters/<project_name>', methods=['POST'])
@require_auth
def create_character(project_name):
    """创建新角色并返回其 ID"""
    try:
        user_id = request.current_user['user_id']
        data = request.json or {}
        name = data.get('name', '新角色')
        characters_path = ensure_project_characters_directory(user_id, project_name)
        char_map = _ensure_bindings(characters_path)
        existing_ids = {int(k) for k in char_map.keys()}
        next_id = 0
        while next_id in existing_ids:
            next_id += 1
        char_map[str(next_id)] = name
        _write_bindings(characters_path, char_map)
        character_file = os.path.join(characters_path, f"{next_id}.txt")
        with open(character_file, 'w', encoding='utf-8') as f:
            f.write(f"{name}\n\n在这里描述你的角色...")
        return jsonify({'success': True, 'message': '角色创建成功', 'id': next_id})
    except Exception as exc:
        return jsonify({'success': False, 'message': f'角色创建失败: {exc}'}), 500


@story_bp.route('/api/characters/<project_name>/<int:character_id>', methods=['DELETE'])
@require_auth
def delete_character(project_name, character_id):
    """删除角色及其绑定"""
    try:
        user_id = request.current_user['user_id']
        characters_path = get_project_characters_path(user_id, project_name)
        char_map = _ensure_bindings(characters_path)
        if str(character_id) in char_map:
            del char_map[str(character_id)]
            _write_bindings(characters_path, char_map)
        character_file = os.path.join(characters_path, f"{character_id}.txt")
        if os.path.exists(character_file):
            os.remove(character_file)
        return jsonify({'success': True, 'message': '角色删除成功'})
    except Exception as exc:
        return jsonify({'success': False, 'message': f'角色删除失败: {exc}'}), 500


@story_bp.route('/api/characters/<project_name>/<int:character_id>/rename', methods=['POST'])
@require_auth
def rename_character(project_name, character_id):
    """重命名角色"""
    try:
        user_id = request.current_user['user_id']
        data = request.json or {}
        new_name = data.get('name', '')
        if not new_name:
            return jsonify({'success': False, 'message': '角色名不能为空'}), 400
        characters_path = get_project_characters_path(user_id, project_name)
        char_map = _ensure_bindings(characters_path)
        if str(character_id) in char_map:
            char_map[str(character_id)] = new_name
            _write_bindings(characters_path, char_map)
        character_file = os.path.join(characters_path, f"{character_id}.txt")
        if os.path.exists(character_file):
            with open(character_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            if lines:
                lines = f"{new_name}\n"
            with open(character_file, 'w', encoding='utf-8') as f:
                f.writelines(lines)
        return jsonify({'success': True, 'message': '角色重命名成功'})
    except Exception as exc:
        return jsonify({'success': False, 'message': f'角色重命名失败: {exc}'}), 500


@story_bp.route('/api/character-settings/<project_name>', methods=['GET'])
@optional_auth
def get_character_settings_list(project_name):
    """返回角色设定详细内容"""
    try:
        user_id = request.current_user['user_id']
        characters_path = ensure_project_characters_directory(user_id, project_name)
        bindings = _ensure_bindings(characters_path)
        characters = []
        for char_id, name in bindings.items():
            char_file = os.path.join(characters_path, f"{char_id}.txt")
            content = ''
            if os.path.exists(char_file):
                with open(char_file, 'r', encoding='utf-8') as f:
                    content = f.read()
            characters.append({'id': int(char_id), 'name': name, 'content': content})
        characters.sort(key=lambda item: item['id'])
        return jsonify(characters)
    except Exception as exc:
        return jsonify({'error': f'获取角色设定失败: {exc}'}), 500


@story_bp.route('/api/character-settings', methods=['POST'])
@require_auth
def create_new_character():
    """创建角色并返回完整设定信息"""
    try:
        user_id = request.current_user['user_id']
        data = request.get_json() or {}
        project_name = data.get('projectName')
        character_name = data.get('name')
        if not project_name or not character_name:
            return jsonify({'success': False, 'message': '缺少项目名称或角色名称'}), 400
        characters_path = ensure_project_characters_directory(user_id, project_name)
        bindings = _ensure_bindings(characters_path)
        existing_ids = {int(k) for k in bindings.keys()}
        next_id = 0
        while next_id in existing_ids:
            next_id += 1
        initial_content = f"# {character_name}\n\n在这里描述你的角色..."
        char_file = os.path.join(characters_path, f"{next_id}.txt")
        with open(char_file, 'w', encoding='utf-8') as f:
            f.write(initial_content)
        bindings[str(next_id)] = character_name
        _write_bindings(characters_path, bindings)
        return jsonify({
            'success': True,
            'message': '角色创建成功',
            'character': {
                'id': next_id,
                'name': character_name,
                'content': initial_content,
            },
        })
    except Exception as exc:
        return jsonify({'success': False, 'message': f'创建角色失败: {exc}'}), 500


@story_bp.route('/api/character-settings/save', methods=['POST'])
@require_auth
def save_character_content():
    """保存角色设定正文"""
    try:
        user_id = request.current_user['user_id']
        data = request.get_json() or {}
        project_name = data.get('projectName')
        character_id = data.get('id')
        content = data.get('content', '')
        if not project_name or character_id is None:
            return jsonify({'success': False, 'message': '缺少项目名称或角色ID'}), 400
        characters_path = get_project_characters_path(user_id, project_name)
        char_file = os.path.join(characters_path, f"{character_id}.txt")
        with open(char_file, 'w', encoding='utf-8') as f:
            f.write(content)
        return jsonify({'success': True, 'message': '角色设定保存成功'})
    except Exception as exc:
        return jsonify({'success': False, 'message': f'保存角色设定失败: {exc}'}), 500


@story_bp.route('/api/character-settings/rename', methods=['POST'])
@require_auth
def rename_character_setting():
    """重命名角色设定"""
    try:
        user_id = request.current_user['user_id']
        data = request.get_json() or {}
        project_name = data.get('projectName')
        character_id = data.get('id')
        new_name = data.get('newName')
        if not project_name or character_id is None or not new_name:
            return jsonify({'success': False, 'message': '缺少项目名称、角色ID或新名称'}), 400
        characters_path = get_project_characters_path(user_id, project_name)
        bindings = _ensure_bindings(characters_path)
        if str(character_id) not in bindings:
            return jsonify({'success': False, 'message': '角色不存在'}), 404
        bindings[str(character_id)] = new_name
        _write_bindings(characters_path, bindings)
        return jsonify({'success': True, 'message': '角色重命名成功'})
    except Exception as exc:
        return jsonify({'success': False, 'message': f'重命名角色失败: {exc}'}), 500


@story_bp.route('/api/character-settings/delete', methods=['POST'])
@require_auth
def delete_character_setting():
    """删除角色设定"""
    try:
        user_id = request.current_user['user_id']
        data = request.get_json() or {}
        project_name = data.get('projectName')
        character_id = data.get('id')
        if not project_name or character_id is None:
            return jsonify({'success': False, 'message': '缺少项目名称或角色ID'}), 400
        characters_path = get_project_characters_path(user_id, project_name)
        char_file = os.path.join(characters_path, f"{character_id}.txt")
        if os.path.exists(char_file):
            os.remove(char_file)
        bindings = _ensure_bindings(characters_path)
        if str(character_id) in bindings:
            del bindings[str(character_id)]
            _write_bindings(characters_path, bindings)
        return jsonify({'success': True, 'message': '角色删除成功'})
    except Exception as exc:
        return jsonify({'success': False, 'message': f'删除角色失败: {exc}'}), 500