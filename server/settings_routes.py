from flask import Blueprint, request, jsonify, current_app
import os
from utils import get_worldview_file_path, get_character_settings_dir, ensure_project_worldview_and_character_settings
from auth import require_auth

# 创建蓝图
settings_bp = Blueprint('settings_bp', __name__)

@settings_bp.route('/api/worldview/<project_name>', methods=['GET'])
@require_auth
def get_worldview(project_name):
    """获取世界观内容"""
    try:
        # 确保项目的世界观和角色设定存在
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
            
        # 确保项目的世界观和角色设定存在
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
        # 确保项目的世界观和角色设定存在
        ensure_project_worldview_and_character_settings(project_name)
        
        character_settings_dir = get_character_settings_dir(project_name)
        
        if not os.path.exists(character_settings_dir):
            return jsonify([]), 200
            
        characters = []
        for filename in os.listdir(character_settings_dir):
            if filename.endswith('.txt'):
                file_path = os.path.join(character_settings_dir, filename)
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                # 从文件名中提取角色ID和名称
                name = filename[:-4]  # 去掉.txt后缀
                character_id = name
                
                characters.append({
                    'id': character_id,
                    'name': name,
                    'content': content
                })
                
        return jsonify(characters), 200
    except Exception as e:
        current_app.logger.error(f"获取角色设定失败: {str(e)}")
        return jsonify({'error': '获取角色设定失败'}), 500

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
            
        # 确保项目的世界观和角色设定存在
        ensure_project_worldview_and_character_settings(project_name)
        
        character_settings_dir = get_character_settings_dir(project_name)
        os.makedirs(character_settings_dir, exist_ok=True)
        
        # 创建角色文件
        filename = f"{character_name}.txt"
        file_path = os.path.join(character_settings_dir, filename)
        
        # 如果文件已存在，添加数字后缀
        counter = 1
        original_filename = filename
        while os.path.exists(file_path):
            name_without_ext = original_filename[:-4]
            filename = f"{name_without_ext}_{counter}.txt"
            file_path = os.path.join(character_settings_dir, filename)
            counter += 1
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(f"# {character_name}\n\n")
            
        # 从文件名中提取角色ID
        character_id = filename[:-4]  # 去掉.txt后缀
            
        return jsonify({
            'success': True, 
            'message': '角色创建成功',
            'character': {
                'id': character_id,
                'name': character_name,
                'content': f"# {character_name}\n\n"
            }
        }), 200
    except Exception as e:
        current_app.logger.error(f"创建角色失败: {str(e)}")
        return jsonify({'success': False, 'message': '创建角色失败'}), 500

@settings_bp.route('/api/character-settings/save', methods=['POST'])
@require_auth
def save_character():
    """保存角色设定"""
    try:
        data = request.get_json()
        project_name = data.get('projectName')
        character_id = data.get('id')
        content = data.get('content', '')
        
        if not project_name or not character_id:
            return jsonify({'success': False, 'message': '缺少项目名称或角色ID'}), 400
            
        # 确保项目的世界观和角色设定存在
        ensure_project_worldview_and_character_settings(project_name)
        
        character_settings_dir = get_character_settings_dir(project_name)
        filename = f"{character_id}.txt"
        file_path = os.path.join(character_settings_dir, filename)
        
        if not os.path.exists(file_path):
            return jsonify({'success': False, 'message': '角色文件不存在'}), 404
            
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
            
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
        
        if not project_name or not character_id or not new_name:
            return jsonify({'success': False, 'message': '缺少项目名称、角色ID或新名称'}), 400
            
        # 确保项目的世界观和角色设定存在
        ensure_project_worldview_and_character_settings(project_name)
        
        character_settings_dir = get_character_settings_dir(project_name)
        old_filename = f"{character_id}.txt"
        old_file_path = os.path.join(character_settings_dir, old_filename)
        
        if not os.path.exists(old_file_path):
            return jsonify({'success': False, 'message': '角色文件不存在'}), 404
            
        # 创建新文件名
        new_filename = f"{new_name}.txt"
        new_file_path = os.path.join(character_settings_dir, new_filename)
        
        # 如果新文件名已存在，添加数字后缀
        counter = 1
        original_new_filename = new_filename
        while os.path.exists(new_file_path):
            name_without_ext = original_new_filename[:-4]
            new_filename = f"{name_without_ext}_{counter}.txt"
            new_file_path = os.path.join(character_settings_dir, new_filename)
            counter += 1
        
        # 重命名文件
        os.rename(old_file_path, new_file_path)
            
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
        
        if not project_name or not character_id:
            return jsonify({'success': False, 'message': '缺少项目名称或角色ID'}), 400
            
        # 确保项目的世界观和角色设定存在
        ensure_project_worldview_and_character_settings(project_name)
        
        character_settings_dir = get_character_settings_dir(project_name)
        filename = f"{character_id}.txt"
        file_path = os.path.join(character_settings_dir, filename)
        
        if not os.path.exists(file_path):
            return jsonify({'success': False, 'message': '角色文件不存在'}), 404
            
        os.remove(file_path)
            
        return jsonify({'success': True, 'message': '角色删除成功'}), 200
    except Exception as e:
        current_app.logger.error(f"删除角色失败: {str(e)}")
        return jsonify({'success': False, 'message': '删除角色失败'}), 500