from flask import Blueprint, request, jsonify, current_app
import os
import json
from utils import get_worldview_file_path, get_character_settings_dir, ensure_project_worldview_and_character_settings, load_character_bindings, save_character_bindings
from auth import require_auth

# 创建蓝图
settings_bp = Blueprint('settings_bp', __name__)

@settings_bp.route('/api/worldview/<project_name>', methods=['GET'])
@require_auth
def get_worldview(project_name):
    """获取世界观内容"""
    try:
        ensure_project_worldview_and_character_settings(project_name)
        worldview_path = get_worldview_file_path(project_name)
        if not os.path.exists(worldview_path):
            return jsonify({'content': ''}), 200
        with open(worldview_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return jsonify({'content': content}), 200
    except Exception as e:
        current_app.logger.error(f"获取世界观失败: {str(e)}")
        return jsonify({'error': '获取世界观失败'}), 500


@settings_bp.route('/api/worldview', methods=['POST'])
@require_auth
def save_worldview():
    """保存世界观内容"""
    try:
        data = request.get_json()
        project_name = data.get('projectName')
        content = data.get('content', '')
        if not project_name:
            return jsonify({'success': False, 'message': '缺少项目名称'}), 400
        ensure_project_worldview_and_character_settings(project_name)
        worldview_path = get_worldview_file_path(project_name)
        with open(worldview_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return jsonify({'success': True, 'message': '世界观保存成功'}), 200
    except Exception as e:
        current_app.logger.error(f"保存世界观失败: {str(e)}")
        return jsonify({'success': False, 'message': '保存世界观失败'}), 500


@settings_bp.route('/api/character-settings/<project_name>', methods=['GET'])
@require_auth
def get_character_settings(project_name):
    """获取所有角色设定"""
    try:
        ensure_project_worldview_and_character_settings(project_name)
        character_settings_dir = get_character_settings_dir(project_name)
        
        if not os.path.exists(character_settings_dir):
            return jsonify([]), 200
            
        character_bindings = load_character_bindings(character_settings_dir)
        
        characters = []
        for filename in sorted(os.listdir(character_settings_dir), key=str.lower):
            if filename.startswith('chr_') and filename.endswith('_设定.txt'):
                txt_file_path = os.path.join(character_settings_dir, filename)
                with open(txt_file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                parts = filename.split('_')
                if len(parts) < 2:
                    continue
                try:
                    character_id = int(parts[1])
                except (ValueError, IndexError):
                    continue
                
                name = character_bindings.get(str(character_id), '')

                if not name:
                    lines = content.split('\n')
                    if lines and lines.startswith('# '):
                        name = lines[2:].strip()
                
                characters.append({
                    'id': character_id,
                    'name': name,
                    'content': content,
                })
                
        return jsonify(characters), 200
    except Exception as e:
        current_app.logger.error(f"获取角色设定失败: {str(e)}")
        return jsonify({'error': f'获取角色设定失败: {e}'}), 500

@settings_bp.route('/api/character-settings', methods=['POST'])
@require_auth
def create_character():
    """创建新角色"""
    try:
        data = request.get_json()
        project_name = data.get('projectName')
        character_name = data.get('name')
        
        if not project_name or not character_name:
            return jsonify({'success': False, 'message': '缺少项目名称或角色名称'}), 400
            
        ensure_project_worldview_and_character_settings(project_name)
        character_settings_dir = get_character_settings_dir(project_name)
        os.makedirs(character_settings_dir, exist_ok=True)
        
        existing_ids = set()
        for item in os.listdir(character_settings_dir):
            if item.startswith('chr_') and item.endswith('_设定.txt'):
                parts = item.split('_')
                if len(parts) >= 2:
                    try:
                        existing_ids.add(int(parts[1]))
                    except (ValueError, IndexError):
                        pass
        
        next_id = 0
        while next_id in existing_ids:
            next_id += 1
        
        txt_filename = f"chr_{next_id}_设定.txt"
        txt_file_path = os.path.join(character_settings_dir, txt_filename)
        initial_content = f"# {character_name}\n\n在这里描述你的角色..."
        
        with open(txt_file_path, 'w', encoding='utf-8') as f:
            f.write(initial_content)
            
        character_bindings = load_character_bindings(character_settings_dir)
        character_bindings[str(next_id)] = character_name
        save_character_bindings(character_settings_dir, character_bindings)
            
        return jsonify({
            'success': True,
            'message': '角色创建成功',
            'character': {
                'id': next_id,
                'name': character_name,
                'content': initial_content,
            }
        }), 200
    except Exception as e:
        current_app.logger.error(f"创建角色失败: {str(e)}")
        return jsonify({'success': False, 'message': '创建角色失败'}), 500

@settings_bp.route('/api/character-settings/save', methods=['POST'])
@require_auth
def save_character():
    """保存角色设定内容. This does NOT handle renaming."""
    try:
        data = request.get_json()
        project_name = data.get('projectName')
        character_id = data.get('id')
        content = data.get('content', '')
        
        if not project_name or character_id is None:
            return jsonify({'success': False, 'message': '缺少项目名称或角色ID'}), 400
            
        character_settings_dir = get_character_settings_dir(project_name)
        txt_filename = f"chr_{character_id}_设定.txt"
        txt_file_path = os.path.join(character_settings_dir, txt_filename)
        
        if not os.path.exists(txt_file_path):
            return jsonify({'success': False, 'message': '角色文件不存在'}), 404
            
        with open(txt_file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        lines = content.split('\n')
        name = ''
        if lines and lines.startswith('# '):
            name = lines[2:].strip()

        if name:
            character_bindings = load_character_bindings(character_settings_dir)
            character_bindings[str(character_id)] = name
            save_character_bindings(character_settings_dir, character_bindings)
            
        return jsonify({'success': True, 'message': '角色设定保存成功'}), 200
    except Exception as e:
        current_app.logger.error(f"保存角色设定失败: {str(e)}")
        return jsonify({'success': False, 'message': '保存角色设定失败'}), 500

@settings_bp.route('/api/character-settings/rename', methods=['POST'])
@require_auth
def rename_character():
    """重命名角色"""
    try:
        data = request.get_json()
        project_name = data.get('projectName')
        character_id = data.get('id')
        new_name = data.get('newName')
        
        if not project_name or character_id is None or not new_name:
            return jsonify({'success': False, 'message': '缺少项目名称、角色ID或新名称'}), 400
            
        character_settings_dir = get_character_settings_dir(project_name)
        txt_filename = f"chr_{character_id}_设定.txt"
        txt_file_path = os.path.join(character_settings_dir, txt_filename)
        
        if not os.path.exists(txt_file_path):
            return jsonify({'success': False, 'message': '角色文件不存在'}), 404
            
        with open(txt_file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        if lines:
            lines = f"# {new_name}\n"
        else:
            lines.append(f"# {new_name}\n")
        
        with open(txt_file_path, 'w', encoding='utf-8') as f:
            f.writelines(lines)

        character_bindings = load_character_bindings(character_settings_dir)
        character_bindings[str(character_id)] = new_name
        save_character_bindings(character_settings_dir, character_bindings)
            
        return jsonify({'success': True, 'message': '角色重命名成功'}), 200
    except Exception as e:
        current_app.logger.error(f"重命名角色失败: {str(e)}")
        return jsonify({'success': False, 'message': '重命名角色失败'}), 500

@settings_bp.route('/api/character-settings/delete', methods=['POST'])
@require_auth
def delete_character():
    """删除角色"""
    try:
        data = request.get_json()
        project_name = data.get('projectName')
        character_id = data.get('id')
        
        if not project_name or character_id is None:
            return jsonify({'success': False, 'message': '缺少项目名称或角色ID'}), 400
            
        character_settings_dir = get_character_settings_dir(project_name)
        txt_filename = f"chr_{character_id}_设定.txt"
        txt_file_path = os.path.join(character_settings_dir, txt_filename)
        
        if os.path.exists(txt_file_path):
            os.remove(txt_file_path)
        
        character_bindings = load_character_bindings(character_settings_dir)
        if str(character_id) in character_bindings:
            del character_bindings[str(character_id)]
            save_character_bindings(character_settings_dir, character_bindings)
            
        return jsonify({'success': True, 'message': '角色删除成功'}), 200
    except Exception as e:
        current_app.logger.error(f"删除角色失败: {str(e)}")
        return jsonify({'success': False, 'message': '删除角色失败'}), 500