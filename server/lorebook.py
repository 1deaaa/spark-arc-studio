from flask import Blueprint, request, jsonify, current_app
import os
import json
from utils import get_worldview_file_path, get_character_settings_dir, ensure_project_worldview_and_character_settings
from auth import require_auth

def get_character_bind_file_path(character_settings_dir):
    """获取角色绑定文件路径"""
    return os.path.join(character_settings_dir, 'chr.bind')

def load_character_bindings(character_settings_dir):
    """加载所有角色的绑定数据"""
    bind_file_path = get_character_bind_file_path(character_settings_dir)
    if not os.path.exists(bind_file_path):
        return {}
    
    try:
        with open(bind_file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}

def save_character_bindings(character_settings_dir, bindings):
    """保存所有角色的绑定数据"""
    bind_file_path = get_character_bind_file_path(character_settings_dir)
    with open(bind_file_path, 'w', encoding='utf-8') as f:
        json.dump(bindings, f, ensure_ascii=False, indent=2)

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
            
        # 加载所有角色的绑定数据
        character_bindings = load_character_bindings(character_settings_dir)
        
        characters = []
        for filename in sorted(os.listdir(character_settings_dir), key=str.lower):
            if filename.startswith('chr_') and filename.endswith('_设定.txt'):
                txt_file_path = os.path.join(character_settings_dir, filename)
                with open(txt_file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                # 从文件名中提取角色ID
                # 文件名格式: chr_(id)_设定.txt
                parts = filename.split('_')
                if len(parts) >= 2:
                    try:
                        character_id = int(parts[1])
                    except ValueError:
                        continue  # 跳过无效的文件名
                else:
                    continue  # 跳过无效的文件名
                
                # 从文件内容中提取角色名称（第一行）
                lines = content.split('\n')
                name = lines[0].strip() if lines else ''
                if name.startswith('# '):
                    name = name[2:]  # 去掉 "# " 前缀
                
                # 获取该角色的绑定数据
                bind_data = character_bindings.get(str(character_id), {})
                
                characters.append({
                    'id': character_id,
                    'name': name,
                    'content': content,
                    'bind': bind_data
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
        
        # 找到下一个可用的角色ID（从0开始且连续分配）
        next_id = 0
        if os.path.exists(character_settings_dir):
            # 获取所有已存在的角色ID
            existing_ids = set()
            for item in os.listdir(character_settings_dir):
                if item.startswith('chr_') and item.endswith('_设定.txt'):
                    # 文件名格式: chr_(id)_设定.txt
                    parts = item.split('_')
                    if len(parts) >= 2:
                        try:
                            char_id = int(parts[1])
                            existing_ids.add(char_id)
                        except ValueError:
                            pass
            
            # 找到第一个未被使用的ID
            while next_id in existing_ids:
                next_id += 1
        
        # 创建角色文件
        txt_filename = f"chr_{next_id}_设定.txt"
        txt_file_path = os.path.join(character_settings_dir, txt_filename)
        
        with open(txt_file_path, 'w', encoding='utf-8') as f:
            f.write(f"# {character_name}\n\n在这里描述你的角色...")
            
        # 更新绑定数据
        character_bindings = load_character_bindings(character_settings_dir)
        character_bindings[str(next_id)] = {}  # 初始化空的绑定数据
        save_character_bindings(character_settings_dir, character_bindings)
            
        return jsonify({
            'success': True,
            'message': '角色创建成功',
            'character': {
                'id': next_id,
                'name': character_name,
                'content': f"# {character_name}\n\n在这里描述你的角色..."
            }
        }), 200
    except Exception as e:
        current_app.logger.error(f"创建角色失败: {str(e)}")
        return jsonify({'success': False, 'message': '创建角色失败'}), 500

@settings_bp.route('/api/character-settings/save', methods=['POST'])
@require_auth
def save_character():
    """保存角色设定和绑定数据"""
    try:
        data = request.get_json()
        project_name = data.get('projectName')
        character_id = data.get('id')
        content = data.get('content', '')
        bind_data = data.get('bind', {})  # 获取绑定数据
        
        if not project_name or not character_id:
            return jsonify({'success': False, 'message': '缺少项目名称或角色ID'}), 400
            
        # 确保项目的世界观和角色设定存在
        ensure_project_worldview_and_character_settings(project_name)
        
        character_settings_dir = get_character_settings_dir(project_name)
        txt_filename = f"chr_{character_id}_设定.txt"
        txt_file_path = os.path.join(character_settings_dir, txt_filename)
        
        # 保存角色内容到.txt文件
        if not os.path.exists(txt_file_path):
            return jsonify({'success': False, 'message': '角色文件不存在'}), 404
            
        with open(txt_file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        # 保存绑定数据到统一的绑定文件
        character_bindings = load_character_bindings(character_settings_dir)
        character_bindings[str(character_id)] = bind_data
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
        
        if not project_name or not character_id or not new_name:
            return jsonify({'success': False, 'message': '缺少项目名称、角色ID或新名称'}), 400
            
        # 确保项目的世界观和角色设定存在
        ensure_project_worldview_and_character_settings(project_name)
        
        character_settings_dir = get_character_settings_dir(project_name)
        txt_filename = f"chr_{character_id}_设定.txt"
        txt_file_path = os.path.join(character_settings_dir, txt_filename)
        
        if not os.path.exists(txt_file_path):
            return jsonify({'success': False, 'message': '角色文件不存在'}), 404
            
        # 读取原有内容
        with open(txt_file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        # 更新第一行的角色名
        if lines:
            lines[0] = f"# {new_name}\n"
        else:
            lines.append(f"# {new_name}\n")
        
        # 写回文件
        with open(txt_file_path, 'w', encoding='utf-8') as f:
            f.writelines(lines)
            
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
        txt_filename = f"chr_{character_id}_设定.txt"
        txt_file_path = os.path.join(character_settings_dir, txt_filename)
        
        if not os.path.exists(txt_file_path):
            return jsonify({'success': False, 'message': '角色文件不存在'}), 404
            
        # 删除.txt文件
        os.remove(txt_file_path)
        
        # 从统一的绑定文件中删除该角色的绑定数据
        character_bindings = load_character_bindings(character_settings_dir)
        if str(character_id) in character_bindings:
            del character_bindings[str(character_id)]
            save_character_bindings(character_settings_dir, character_bindings)
            
        return jsonify({'success': True, 'message': '角色删除成功'}), 200
    except Exception as e:
        current_app.logger.error(f"删除角色失败: {str(e)}")
        return jsonify({'success': False, 'message': '删除角色失败'}), 500