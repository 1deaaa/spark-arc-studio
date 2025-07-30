from flask import Blueprint, jsonify, request
from auth import require_auth
import os
import json
import shutil
from utils import get_project_path, ensure_project_directory, get_user_projects_root, get_project_stories_path, ensure_project_stories_directory, get_project_worldview_path, ensure_project_worldview_file, get_project_characters_path, ensure_project_characters_directory, ensure_project_worldview_and_character_settings

story_bp = Blueprint('story_bp', __name__)

@story_bp.route('/剧本示例.story')
@require_auth
def get_dialogue_data():
    """获取对话数据，优先从文件读取，文件不存在则返回默认数据"""
    try:
        # 尝试读取文件
        file_path = os.path.join(os.path.dirname(__file__), '剧本示例.story')
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return jsonify(data)
        else:
            print("剧本示例.story 文件不存在，返回默认数据")
            return jsonify("")
    except Exception as e:
        print(f"加载剧本示例.story 出错: {e}")
        return jsonify("")

@story_bp.route('/save', methods=['POST'])
@require_auth
def save_dialogue():
    """保存对话数据到文件"""
    try:
        data = request.json
        file_path = os.path.join('.', '剧本示例.story')
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return jsonify({"success": True, "message": "保存成功"})
    except Exception as e:
        return jsonify({"success": False, "message": f"保存失败: {str(e)}"}), 500

@story_bp.route('/api/story-files/<project_name>')
@require_auth
def get_story_files(project_name):
    """获取用户项目stories文件夹下所有文件的文件树结构"""
    try:
        user_id = request.current_user['user_id']
        stories_path = ensure_project_stories_directory(user_id, project_name)
        
        def scan_directory(path, relative_path=""):
            """递归扫描目录，构建文件树"""
            items = []
            if not os.path.exists(path):
                return items
                
            for item in sorted(os.listdir(path), key=str.lower):  # 按首字母排序
                item_path = os.path.join(path, item)
                if os.path.isfile(item_path) and item.endswith('.story'):
                    # STORY文件，去掉.story后缀
                    name = item[:-6]  # 去掉.story后缀
                    items.append({
                        'name': name,
                        'type': 'story',
                        'path': os.path.join(relative_path, name) if relative_path else name
                    })
                elif os.path.isdir(item_path) and not item.startswith('.'):
                    # 文件夹
                    children = scan_directory(item_path, os.path.join(relative_path, item) if relative_path else item)
                    items.append({
                        'name': item,
                        'type': 'folder',
                        'children': children
                    })
            return items
        
        # 扫描用户的项目stories目录，返回其内容
        file_tree = scan_directory(stories_path)
        return jsonify(file_tree)
    except Exception as e:
        print(f"获取JSON文件列表失败: {e}")
        return jsonify([])

@story_bp.route('/api/file-operations/move', methods=['POST'])
@require_auth
def move_file():
    """移动文件或文件夹"""
    try:
        user_id = request.current_user['user_id']
        data = request.json
        project_name = data.get('projectName')
        if not project_name:
            return jsonify({"success": False, "message": "缺少项目名称"}), 400
        
        stories_path = get_project_stories_path(user_id, project_name)
        source_path = os.path.join(stories_path, data['sourcePath'])
        target_path = os.path.join(stories_path, data['targetPath'])
        
        print(f"移动文件请求:")
        print(f"  用户ID: {user_id}")
        print(f"  源路径: {data['sourcePath']}")
        print(f"  目标路径: {data['targetPath']}")
        print(f"  完整源路径: {source_path}")
        print(f"  完整目标路径: {target_path}")
        print(f"  源文件是否存在: {os.path.exists(source_path)}")
        
        # 如果源路径不存在，尝试添加.story扩展名
        if not os.path.exists(source_path) and not os.path.isdir(source_path):
            story_source_path = source_path + '.story'
            if os.path.exists(story_source_path):
                source_path = story_source_path
                # 如果目标路径也不包含扩展名，也添加.story
                if not target_path.endswith('.story'):
                    target_path = target_path + '.story'
        
        print(f"  最终源路径: {source_path}")
        print(f"  最终目标路径: {target_path}")
          # 如果源路径不存在，尝试添加.story扩展名
        if not os.path.exists(source_path) and not os.path.isdir(source_path):
            story_source_path = source_path + '.story'
            if os.path.exists(story_source_path):
                source_path = story_source_path
                # 如果目标路径也不包含扩展名，也添加.story
                if not target_path.endswith('.story'):
                    target_path = target_path + '.story'
        
        print(f"  最终源路径: {source_path}")
        print(f"  最终目标路径: {target_path}")
        
        if not os.path.exists(source_path):
            return jsonify({"success": False, "message": f"源文件不存在: {source_path}"}), 404
        
        # 确保目标目录存在
        target_dir = os.path.dirname(target_path)
        if target_dir and not os.path.exists(target_dir):
            print(f"  创建目标目录: {target_dir}")
            os.makedirs(target_dir, exist_ok=True)
        
        # 移动文件或文件夹
        shutil.move(source_path, target_path)
        print(f"  移动成功")
        
        return jsonify({"success": True, "message": "文件移动成功"})
    except Exception as e:
        print(f"移动文件失败: {str(e)}")
        return jsonify({"success": False, "message": f"文件移动失败: {str(e)}"}), 500

@story_bp.route('/api/file-operations/create', methods=['POST'])
@require_auth
def create_file_or_folder():
    """创建文件或文件夹"""
    try:
        user_id = request.current_user['user_id']
        data = request.json
        project_name = data.get('projectName')
        if not project_name:
            return jsonify({"success": False, "message": "缺少项目名称"}), 400
            
        stories_path = ensure_project_stories_directory(user_id, project_name)
        file_type = data['type']  # 'file' 或 'folder'
        file_path = os.path.join(stories_path, data['path'])
        
        if file_type == 'folder':
            os.makedirs(file_path, exist_ok=True)
        else:  # file
            # 为 story 文件自动添加后缀
            if not file_path.endswith('.story') and not file_path.endswith('.txt'):
                file_path += '.story'
            
            # 检查文件是否已存在
            if os.path.exists(file_path):
                return jsonify({"success": False, "message": f"文件 '{os.path.basename(file_path)}' 已存在"}), 409
            
            # 确保目录存在
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            # 创建文件
            if file_path.endswith('.story'):
                # 创建空的STORY文件
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump([], f, ensure_ascii=False, indent=2)
            elif file_path.endswith('.txt'):
                # 创建空的TXT文件
                with open(file_path, 'w', encoding='utf-8') as f:
                    pass # 创建空文件
            else:
                # 理论上不会到达这里, 但为了安全起见
                return jsonify({"success": False, "message": "不支持的文件类型"}), 400
        
        return jsonify({"success": True, "message": "创建成功"})
    except Exception as e:
        return jsonify({"success": False, "message": f"创建失败: {str(e)}"}), 500

@story_bp.route('/api/file-operations/delete', methods=['POST'])
@require_auth
def delete_file_or_folder():
    """删除文件或文件夹"""
    try:
        user_id = request.current_user['user_id']
        data = request.json
        project_name = data.get('projectName')
        if not project_name:
            return jsonify({"success": False, "message": "缺少项目名称"}), 400

        stories_path = get_project_stories_path(user_id, project_name)
        file_path = os.path.join(stories_path, data['path'])
        
        print(f"删除请求:")
        print(f"  用户ID: {user_id}")
        print(f"  原始路径: {data['path']}")
        print(f"  完整路径: {file_path}")
        print(f"  路径是否存在: {os.path.exists(file_path)}")
        
        # 如果路径不存在，且不是文件夹，尝试添加.story扩展名
        if not os.path.exists(file_path) and not os.path.isdir(file_path):
            story_file_path = file_path + '.story'
            print(f"  尝试.story扩展名: {story_file_path}")
            print(f"  .story文件是否存在: {os.path.exists(story_file_path)}")
            if os.path.exists(story_file_path):
                file_path = story_file_path
        
        if os.path.isdir(file_path):
            shutil.rmtree(file_path)
            print(f"  删除文件夹成功")
        elif os.path.isfile(file_path):
            os.remove(file_path)
            print(f"  删除文件成功")
        else:
            return jsonify({"success": False, "message": f"文件或文件夹不存在: {file_path}"}), 404
        
        return jsonify({"success": True, "message": "删除成功"})
    except Exception as e:
        print(f"删除失败: {str(e)}")
        return jsonify({"success": False, "message": f"删除失败: {str(e)}"}), 500

@story_bp.route('/api/file-operations/rename', methods=['POST'])
@require_auth
def rename_file_or_folder():
    """重命名文件或文件夹"""
    try:
        user_id = request.current_user['user_id']
        data = request.json
        project_name = data.get('projectName')
        if not project_name:
            return jsonify({"success": False, "message": "缺少项目名称"}), 400
            
        stories_path = get_project_stories_path(user_id, project_name)
        old_path = os.path.join(stories_path, data['oldPath'])
        new_path = os.path.join(stories_path, data['newPath'])
        
        print(f"重命名请求:")
        print(f"  用户ID: {user_id}")
        print(f"  原路径: {data['oldPath']}")
        print(f"  新路径: {data['newPath']}")
        print(f"  完整原路径: {old_path}")
        print(f"  完整新路径: {new_path}")
        
        # 如果原路径不存在，尝试添加.story扩展名
        if not os.path.exists(old_path) and not os.path.isdir(old_path):
            story_old_path = old_path + '.story'
            if os.path.exists(story_old_path):
                old_path = story_old_path
                # 如果新路径也不包含扩展名，也添加.story
                if not new_path.endswith('.story'):
                    new_path = new_path + '.story'
        
        print(f"  最终原路径: {old_path}")
        print(f"  最终新路径: {new_path}")
        print(f"  原路径是否存在: {os.path.exists(old_path)}")
        
        os.rename(old_path, new_path)
        
        return jsonify({"success": True, "message": "重命名成功"})
    except Exception as e:
        print(f"重命名失败: {str(e)}")
        return jsonify({"success": False, "message": f"重命名失败: {str(e)}"}), 500

@story_bp.route('/api/file-operations/copy', methods=['POST'])
@require_auth
def copy_file():
    """复制文件或文件夹"""
    try:
        user_id = request.current_user['user_id']
        data = request.json
        project_name = data.get('projectName')
        if not project_name:
            return jsonify({"success": False, "message": "缺少项目名称"}), 400

        stories_path = get_project_stories_path(user_id, project_name)
        source_path = data.get('sourcePath')
        target_path = data.get('targetPath')
        
        if not source_path or not target_path:
            return jsonify({"success": False, "message": "源路径和目标路径不能为空"}), 400
        source_full_path = os.path.join(stories_path, source_path)
        target_full_path = os.path.join(stories_path, target_path)
        
        print(f"复制请求:")
        print(f"  用户ID: {user_id}")
        print(f"  源路径: {source_path}")
        print(f"  目标路径: {target_path}")
        print(f"  完整源路径: {source_full_path}")
        print(f"  完整目标路径: {target_full_path}")
        
        # 如果源路径不存在，尝试添加.story扩展名
        if not os.path.exists(source_full_path) and not os.path.isdir(source_full_path):
            story_source_path = source_full_path + '.story'
            if os.path.exists(story_source_path):
                source_full_path = story_source_path
                # 如果目标路径也不包含扩展名，也添加.story
                if not target_full_path.endswith('.story'):
                    target_full_path = target_full_path + '.story'
        
        print(f"  最终源路径: {source_full_path}")
        print(f"  最终目标路径: {target_full_path}")
        
        if not os.path.exists(source_full_path):
            return jsonify({"success": False, "message": "源文件不存在"}), 404
        
        if os.path.exists(target_full_path):
            return jsonify({"success": False, "message": "目标路径已存在"}), 409
        
        # 确保目标目录存在
        target_dir = os.path.dirname(target_full_path)
        if target_dir and not os.path.exists(target_dir):
            os.makedirs(target_dir)
        
        if os.path.isdir(source_full_path):
            # 复制文件夹
            import shutil
            shutil.copytree(source_full_path, target_full_path)
        else:
            # 复制文件
            import shutil
            shutil.copy2(source_full_path, target_full_path)
        return jsonify({"success": True, "message": "复制成功"})
    except Exception as e:
        return jsonify({"success": False, "message": f"复制失败: {str(e)}"}), 500

@story_bp.route('/api/upload-story', methods=['POST'])
@require_auth
def upload_story():
    """上传故事文件到指定项目的stories目录"""
    try:
        user_id = request.current_user['user_id']
        project_name = request.form.get('projectName')
        if not project_name:
            return jsonify({"success": False, "message": "缺少项目名称"}), 400

        stories_path = ensure_project_stories_directory(user_id, project_name)
        
        if 'file' not in request.files:
            return jsonify({"success": False, "message": "没有文件"}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({"success": False, "message": "没有选择文件"}), 400
        if not file.filename.endswith('.story'):
            return jsonify({"success": False, "message": "只支持STORY文件"}), 400
        
        # 保存文件
        filename = file.filename
        file_path = os.path.join(stories_path, filename)
        
        # 如果文件已存在，生成新的文件名
        base_name = os.path.splitext(filename)[0]
        counter = 1
        while os.path.exists(file_path):
            new_filename = f"{base_name}_{counter}.story"
            file_path = os.path.join(stories_path, new_filename)
            filename = new_filename
            counter += 1
        
        file.save(file_path)
        
        # 返回不带.story后缀的文件名（用于前端识别）
        return jsonify({
            "success": True, 
            "message": "上传成功",
            "filename": os.path.splitext(filename)[0]
        })
    except Exception as e:
        return jsonify({"success": False, "message": f"上传失败: {str(e)}"}), 500

@story_bp.route('/api/save-story', methods=['POST'])
@require_auth
def save_story():
    """保存故事数据到指定文件"""
    try:
        user_id = request.current_user['user_id']
        data = request.json
        project_name = data.get('projectName')
        filename = data.get('filename')
        story_data = data.get('data')

        if not project_name:
            return jsonify({"success": False, "message": "缺少项目名称"}), 400
        if not filename:
            return jsonify({"success": False, "message": "文件名不能为空"}), 400
        if not story_data:
            return jsonify({"success": False, "message": "数据不能为空"}), 400
            
        stories_path = ensure_project_stories_directory(user_id, project_name)
        file_path = os.path.join(stories_path, filename)
        if not file_path.endswith('.story'):
            file_path += '.story'
        
        # 保存文件
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(story_data, f, ensure_ascii=False, indent=2)
        
        return jsonify({"success": True, "message": "保存成功"})
    except Exception as e:
        return jsonify({"success": False, "message": f"保存失败: {str(e)}"}), 500

@story_bp.route('/api/file-content/<project_name>/<path:filename>')
@require_auth
def get_file_content(project_name, filename):
    """获取指定项目文件的内容"""
    try:
        user_id = request.current_user['user_id']
        stories_path = get_project_stories_path(user_id, project_name)
        print(f"请求文件内容: {filename} (用户ID: {user_id}, 项目: {project_name})")
        file_path = os.path.join(stories_path, filename)
        if not file_path.endswith('.story'):
            file_path += '.story'
        
        print(f"完整文件路径: {file_path}")
        print(f"文件是否存在: {os.path.exists(file_path)}")
            
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return jsonify(data)
        else:
            return jsonify({"error": "文件不存在"}), 404
    except Exception as e:
        print(f"读取文件失败: {str(e)}")
        return jsonify({"error": f"读取文件失败: {str(e)}"}), 500

@story_bp.route('/api/file-content-txt/<project_name>/<path:filename>')
@require_auth
def get_txt_file_content(project_name, filename):
    """获取指定项目txt文件的内容"""
    try:
        user_id = request.current_user['user_id']
        stories_path = get_project_stories_path(user_id, project_name)
        print(f"请求txt文件内容: {filename} (用户ID: {user_id}, 项目: {project_name})")
        file_path = os.path.join(stories_path, filename)
        if not file_path.endswith('.txt'):
            file_path += '.txt'
        
        print(f"完整txt文件路径: {file_path}")
        print(f"txt文件是否存在: {os.path.exists(file_path)}")
            
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                return jsonify(content)
        else:
            return jsonify({"error": "文件不存在"}), 404
    except Exception as e:
        print(f"读取txt文件失败: {str(e)}")
        return jsonify({"error": f"读取txt文件失败: {str(e)}"}), 500

@story_bp.route('/api/save-txt', methods=['POST'])
@require_auth
def save_txt_file():
    """保存txt文件内容到指定文件"""
    try:
        user_id = request.current_user['user_id']
        data = request.json
        project_name = data.get('projectName')
        filename = data.get('filename')
        content = data.get('content')

        if not project_name:
            return jsonify({"success": False, "message": "缺少项目名称"}), 400
        if not filename:
            return jsonify({"success": False, "message": "文件名不能为空"}), 400
            
        stories_path = ensure_project_stories_directory(user_id, project_name)
        file_path = os.path.join(stories_path, filename)
        if not file_path.endswith('.txt'):
            file_path += '.txt'
        
        # 保存文件
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return jsonify({"success": True, "message": "保存成功"})
    except Exception as e:
        return jsonify({"success": False, "message": f"保存失败: {str(e)}"}), 500

@story_bp.route('/api/projects', methods=['GET'])
@require_auth
def get_projects():
    """获取用户的所有项目列表"""
    try:
        user_id = request.current_user['user_id']
        projects_root = get_user_projects_root(user_id)
        if not os.path.exists(projects_root):
            os.makedirs(projects_root)
            return jsonify([])
        
        projects = [d for d in os.listdir(projects_root) if os.path.isdir(os.path.join(projects_root, d))]
        return jsonify(sorted(projects))
    except Exception as e:
        return jsonify({"success": False, "message": f"获取项目列表失败: {str(e)}"}), 500

@story_bp.route('/api/projects', methods=['POST'])
@require_auth
def create_project():
    """创建一个新项目"""
    try:
        user_id = request.current_user['user_id']
        data = request.json
        project_name = data.get('projectName')
        if not project_name:
            return jsonify({"success": False, "message": "项目名称不能为空"}), 400
        
        project_path = get_project_path(user_id, project_name)
        if os.path.exists(project_path):
            return jsonify({"success": False, "message": "项目已存在"}), 409
            
        # 创建项目目录和stories子目录
        ensure_project_directory(user_id, project_name)
        ensure_project_stories_directory(user_id, project_name)
        # 确保世界观文件和角色设定目录存在
        ensure_project_worldview_and_character_settings(project_name)
        return jsonify({"success": True, "message": "项目创建成功"})
    except Exception as e:
        return jsonify({"success": False, "message": f"项目创建失败: {str(e)}"}), 500

@story_bp.route('/api/projects/<project_name>', methods=['DELETE'])
@require_auth
def delete_project(project_name):
    """删除一个项目"""
    try:
        user_id = request.current_user['user_id']
        project_path = get_project_path(user_id, project_name)
        
        if not os.path.exists(project_path):
            return jsonify({"success": False, "message": "项目不存在"}), 404
            
        shutil.rmtree(project_path)
        return jsonify({"success": True, "message": "项目删除成功"})
    except Exception as e:
        return jsonify({"success": False, "message": f"项目删除失败: {str(e)}"}), 500

# 新增的API端点，用于处理世界观和角色设定

@story_bp.route('/api/worldview/<project_name>', methods=['GET'])
@require_auth
def get_worldview(project_name):
    """获取指定项目的世界观内容"""
    try:
        user_id = request.current_user['user_id']
        worldview_path = get_project_worldview_path(user_id, project_name)
        
        if os.path.exists(worldview_path):
            with open(worldview_path, 'r', encoding='utf-8') as f:
                content = f.read()
                return jsonify({"content": content})
        else:
            return jsonify({"content": ""})
    except Exception as e:
        return jsonify({"error": f"读取世界观失败: {str(e)}"}), 500

@story_bp.route('/api/worldview/<project_name>', methods=['POST'])
@require_auth
def save_worldview(project_name):
    """保存世界观内容到指定项目"""
    try:
        user_id = request.current_user['user_id']
        data = request.json
        content = data.get('content', '')
        
        worldview_path = get_project_worldview_path(user_id, project_name)
        
        # 确保项目目录存在
        ensure_project_directory(user_id, project_name)
        
        # 保存文件
        with open(worldview_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return jsonify({"success": True, "message": "保存成功"})
    except Exception as e:
        return jsonify({"success": False, "message": f"保存失败: {str(e)}"}), 500

@story_bp.route('/api/characters/<project_name>', methods=['GET'])
@require_auth
def get_characters(project_name):
    """获取指定项目的所有角色列表"""
    try:
        user_id = request.current_user['user_id']
        characters_path = get_project_characters_path(user_id, project_name)
        
        if not os.path.exists(characters_path):
            return jsonify([])
            
        characters = []
        for item in sorted(os.listdir(characters_path), key=str.lower):
            item_path = os.path.join(characters_path, item)
            if os.path.isfile(item_path) and item.endswith('.txt'):
                character_id = int(os.path.splitext(item)[0])
                with open(item_path, 'r', encoding='utf-8') as f:
                    name = f.readline().strip()  # 第一行是角色名
                characters.append({
                    'id': character_id,
                    'name': name
                })
        return jsonify(characters)
    except Exception as e:
        return jsonify({"error": f"获取角色列表失败: {str(e)}"}), 500

@story_bp.route('/api/characters/<project_name>/<int:character_id>', methods=['GET'])
@require_auth
def get_character(project_name, character_id):
    """获取指定项目的指定角色内容"""
    try:
        user_id = request.current_user['user_id']
        characters_path = get_project_characters_path(user_id, project_name)
        character_file = os.path.join(characters_path, f"{character_id}.txt")
        bind_file = os.path.join(characters_path, f"{character_id}.bind")
        
        if not os.path.exists(character_file):
            return jsonify({"error": "角色不存在"}), 404
            
        with open(character_file, 'r', encoding='utf-8') as f:
            content = f.read()
            
        bind_data = {}
        if os.path.exists(bind_file):
            with open(bind_file, 'r', encoding='utf-8') as f:
                bind_data = json.load(f)
                
        return jsonify({
            "content": content,
            "bind": bind_data
        })
    except Exception as e:
        return jsonify({"error": f"读取角色失败: {str(e)}"}), 500

@story_bp.route('/api/characters/<project_name>/<int:character_id>', methods=['POST'])
@require_auth
def save_character(project_name, character_id):
    """保存角色内容和绑定数据到指定项目"""
    try:
        user_id = request.current_user['user_id']
        data = request.json
        content = data.get('content', '')
        bind_data = data.get('bind', {})
        
        characters_path = get_project_characters_path(user_id, project_name)
        character_file = os.path.join(characters_path, f"{character_id}.txt")
        bind_file = os.path.join(characters_path, f"{character_id}.bind")
        
        # 确保角色目录存在
        ensure_project_characters_directory(user_id, project_name)
        
        # 保存角色文件
        with open(character_file, 'w', encoding='utf-8') as f:
            f.write(content)
            
        # 保存绑定文件
        with open(bind_file, 'w', encoding='utf-8') as f:
            json.dump(bind_data, f, ensure_ascii=False, indent=2)
        
        return jsonify({"success": True, "message": "保存成功"})
    except Exception as e:
        return jsonify({"success": False, "message": f"保存失败: {str(e)}"}), 500

@story_bp.route('/api/characters/<project_name>', methods=['POST'])
@require_auth
def create_character(project_name):
    """在指定项目中创建一个新角色"""
    try:
        user_id = request.current_user['user_id']
        data = request.json
        name = data.get('name', '新角色')
        
        characters_path = get_project_characters_path(user_id, project_name)
        
        # 确保角色目录存在
        ensure_project_characters_directory(user_id, project_name)
        
        # 找到下一个可用的角色ID
        next_id = 0
        if os.path.exists(characters_path):
            for item in os.listdir(characters_path):
                if item.endswith('.txt'):
                    try:
                        char_id = int(os.path.splitext(item)[0])
                        if char_id >= next_id:
                            next_id = char_id + 1
                    except ValueError:
                        pass
        
        character_file = os.path.join(characters_path, f"{next_id}.txt")
        bind_file = os.path.join(characters_path, f"{next_id}.bind")
        
        # 创建角色文件
        with open(character_file, 'w', encoding='utf-8') as f:
            f.write(f"{name}\n\n在这里描述你的角色...")
            
        # 创建空的绑定文件
        with open(bind_file, 'w', encoding='utf-8') as f:
            json.dump({}, f, ensure_ascii=False, indent=2)
            
        return jsonify({"success": True, "message": "角色创建成功", "id": next_id})
    except Exception as e:
        return jsonify({"success": False, "message": f"角色创建失败: {str(e)}"}), 500

@story_bp.route('/api/characters/<project_name>/<int:character_id>', methods=['DELETE'])
@require_auth
def delete_character(project_name, character_id):
    """删除指定项目中的指定角色"""
    try:
        user_id = request.current_user['user_id']
        characters_path = get_project_characters_path(user_id, project_name)
        character_file = os.path.join(characters_path, f"{character_id}.txt")
        bind_file = os.path.join(characters_path, f"{character_id}.bind")
        
        if os.path.exists(character_file):
            os.remove(character_file)
        if os.path.exists(bind_file):
            os.remove(bind_file)
            
        return jsonify({"success": True, "message": "角色删除成功"})
    except Exception as e:
        return jsonify({"success": False, "message": f"角色删除失败: {str(e)}"}), 500

@story_bp.route('/api/characters/<project_name>/<int:character_id>/rename', methods=['POST'])
@require_auth
def rename_character(project_name, character_id):
    """重命名指定项目中的指定角色"""
    try:
        user_id = request.current_user['user_id']
        data = request.json
        new_name = data.get('name', '')
        
        if not new_name:
            return jsonify({"success": False, "message": "角色名不能为空"}), 400
            
        characters_path = get_project_characters_path(user_id, project_name)
        character_file = os.path.join(characters_path, f"{character_id}.txt")
        
        if not os.path.exists(character_file):
            return jsonify({"success": False, "message": "角色不存在"}), 404
            
        # 读取原有内容
        with open(character_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        # 更新第一行的角色名
        lines[0] = f"{new_name}\n"
        
        # 写回文件
        with open(character_file, 'w', encoding='utf-8') as f:
            f.writelines(lines)
            
        return jsonify({"success": True, "message": "角色重命名成功"})
    except Exception as e:
        return jsonify({"success": False, "message": f"角色重命名失败: {str(e)}"}), 500