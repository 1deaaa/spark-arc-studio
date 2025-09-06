from flask import Blueprint, jsonify, request
from auth import require_auth, optional_auth
from request_context import get_current_info
import os
import json
import shutil
from utils import (
    get_project_path,
    ensure_project_directory,
    get_user_projects_root,
    get_project_stories_path,
    ensure_project_stories_directory,
    get_project_worldview_path,
    ensure_project_worldview_file,
    get_project_characters_path,
    ensure_project_characters_directory,
    ensure_project_worldview_and_character_settings,
)

story_bp = Blueprint('story_bp', __name__)

@story_bp.route('/剧本示例.story')
@optional_auth
@get_current_info
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
@optional_auth
@get_current_info
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
@optional_auth
@get_current_info
def get_story_files(project_name):
    """获取用户项目stories文件夹下所有文件的文件树结构"""
    try:
        user_id = request.current_user['user_id']
        stories_path = ensure_project_stories_directory(user_id, project_name)
        # 读取用户自定义顺序（项目根目录）
        from utils import get_project_path
        project_root = get_project_path(user_id, project_name)
        order_file = os.path.join(project_root, 'stories_order.json')
        order_map = {}
        if os.path.exists(order_file):
            try:
                with open(order_file, 'r', encoding='utf-8') as f:
                    order_map = json.load(f) or {}
            except Exception:
                order_map = {}

        def reorder_by_user_order(items_list, dir_rel_path):
            """按用户在 stories_order.json 中保存的顺序重排；未配置则保持原有顺序"""
            order = order_map.get(dir_rel_path or "")
            if not order or not isinstance(order, list):
                return items_list
            index_map = {name: i for i, name in enumerate(order)}
            # 稳定排序：出现在顺序表的按索引靠前；其余保持原相对顺序但排在后面
            def key_fn(it):
                name = it.get('name', '')
                return (0 if name in index_map else 1, index_map.get(name, 0))
            return sorted(items_list, key=key_fn)

        def scan_directory(path, relative_path=""):
            """递归扫描目录，构建文件树"""
            folders = []
            files = []
            if not os.path.exists(path):
                return []

            for item in os.listdir(path):
                if item.startswith('.'):  # 隐藏项略过
                    continue
                item_path = os.path.join(path, item)
                if os.path.isdir(item_path):
                    # 文件夹
                    rel_dir = os.path.join(relative_path, item) if relative_path else item
                    web_dir = rel_dir.replace(os.sep, '/')
                    children = scan_directory(item_path, rel_dir)
                    folders.append({
                        'name': item,
                        'type': 'folder',
                        'path': web_dir,
                        'children': children
                    })
                elif os.path.isfile(item_path) and item.endswith('.story'):
                    # STORY文件，去掉.story后缀
                    name = item[:-6]
                    rel = os.path.join(relative_path, name) if relative_path else name
                    web_path = rel.replace(os.sep, '/')
                    files.append({
                        'name': name,
                        'type': 'story',
                        'path': web_path
                    })

            # 应用用户自定义顺序，各自内部排序；最终文件夹在前、文件在后
            folders = reorder_by_user_order(folders, relative_path)
            files = reorder_by_user_order(files, relative_path)
            return folders + files
        
        # 扫描用户的项目stories目录，返回其内容
        file_tree = scan_directory(stories_path)
        return jsonify(file_tree)
    except Exception as e:
        print(f"获取JSON文件列表失败: {e}")
        return jsonify([])

@story_bp.route('/api/file-operations/save-order', methods=['POST'])
@require_auth
@get_current_info
def save_stories_order():
    """保存某目录（相对 stories 根）下的用户自定义顺序到项目根 stories_order.json。"""
    try:
        user_id = request.current_user['user_id']
        data = request.json
        project_name = data.get('projectName')
        dir_path = data.get('dirPath', '')  # '' 表示根目录
        order = data.get('order', [])
        if not project_name:
            return jsonify({"success": False, "message": "缺少项目名称"}), 400
        if not isinstance(order, list):
            return jsonify({"success": False, "message": "order 必须是数组"}), 400

        project_root = get_project_path(user_id, project_name)
        stories_path = ensure_project_stories_directory(user_id, project_name)

        # 规范 dir_path 分隔符
        dir_path = (dir_path or '').strip('/\\')
        # 校验目录是否存在
        target_dir = os.path.join(stories_path, dir_path) if dir_path else stories_path
        if not os.path.isdir(target_dir):
            return jsonify({"success": False, "message": "目录不存在"}), 404

        order_file = os.path.join(project_root, 'stories_order.json')
        order_map = {}
        if os.path.exists(order_file):
            try:
                with open(order_file, 'r', encoding='utf-8') as f:
                    order_map = json.load(f) or {}
            except Exception:
                order_map = {}

        order_map[dir_path] = order
        with open(order_file, 'w', encoding='utf-8') as f:
            json.dump(order_map, f, ensure_ascii=False, indent=2)

        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "message": f"保存排序失败: {str(e)}"}), 500

@story_bp.route('/api/file-operations/move', methods=['POST'])
@require_auth
@get_current_info
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
        
        # 如果源路径不存在，尝试添加.story扩展名
        if not os.path.exists(source_path) and not os.path.isdir(source_path):
            story_source_path = source_path + '.story'
            if os.path.exists(story_source_path):
                source_path = story_source_path
                # 如果目标路径也不包含扩展名，也添加.story
                if not target_path.endswith('.story'):
                    target_path = target_path + '.story'
        
        if not os.path.exists(source_path):
            return jsonify({"success": False, "message": f"源文件不存在: {source_path}"}), 404
        
        # 确保目标目录存在
        target_dir = os.path.dirname(target_path)
        if target_dir and not os.path.exists(target_dir):
            os.makedirs(target_dir, exist_ok=True)
        
        # 移动文件或文件夹
        shutil.move(source_path, target_path)
        
        return jsonify({"success": True, "message": "文件移动成功"})
    except Exception as e:
        return jsonify({"success": False, "message": f"文件移动失败: {str(e)}"}), 500

@story_bp.route('/api/file-operations/create', methods=['POST'])
@require_auth
@get_current_info
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
            
            if os.path.exists(file_path):
                return jsonify({"success": False, "message": f"文件 '{os.path.basename(file_path)}' 已存在"}), 409
            
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            if file_path.endswith('.story'):
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump([], f, ensure_ascii=False, indent=2)
            elif file_path.endswith('.txt'):
                with open(file_path, 'w', encoding='utf-8') as f:
                    pass # 创建空文件
            else:
                return jsonify({"success": False, "message": "不支持的文件类型"}), 400
        
        return jsonify({"success": True, "message": "创建成功"})
    except Exception as e:
        return jsonify({"success": False, "message": f"创建失败: {str(e)}"}), 500

@story_bp.route('/api/file-operations/delete', methods=['POST'])
@require_auth
@get_current_info
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
        
        # 如果路径不存在，且不是文件夹，尝试添加.story扩展名
        if not os.path.exists(file_path) and not os.path.isdir(file_path):
            story_file_path = file_path + '.story'
            if os.path.exists(story_file_path):
                file_path = story_file_path
        
        if os.path.isdir(file_path):
            shutil.rmtree(file_path)
        elif os.path.isfile(file_path):
            os.remove(file_path)
        else:
            return jsonify({"success": False, "message": f"文件或文件夹不存在: {file_path}"}), 404
        
        return jsonify({"success": True, "message": "删除成功"})
    except Exception as e:
        return jsonify({"success": False, "message": f"删除失败: {str(e)}"}), 500

@story_bp.route('/api/file-operations/rename', methods=['POST'])
@require_auth
@get_current_info
def rename_file_or_folder():
    """重命名文件或文件夹"""
    try:
        user_id = request.current_user['user_id']
        data = request.json
        project_name = data.get('projectName')
        if not project_name:
            return jsonify({"success": False, "message": "缺少项目名称"}), 400
            
        stories_path = get_project_stories_path(user_id, project_name)
        old_rel = data.get('oldPath')
        new_rel = data.get('newPath')
        if not old_rel or not new_rel:
            return jsonify({"success": False, "message": "参数 oldPath/newPath 不能为空"}), 400
        old_path = os.path.join(stories_path, old_rel)
        new_path = os.path.join(stories_path, new_rel)
        
        # 如果原路径不存在，尝试添加.story扩展名
        if not os.path.exists(old_path) and not os.path.isdir(old_path):
            story_old_path = old_path + '.story'
            if os.path.exists(story_old_path):
                old_path = story_old_path
                if not new_path.endswith('.story'):
                    new_path = new_path + '.story'
        
        # 目标存在则冲突
        if os.path.exists(new_path):
            return jsonify({"success": False, "message": "目标已存在"}), 409

        # 确保目标目录存在
        new_dir = os.path.dirname(new_path)
        if new_dir and not os.path.exists(new_dir):
            os.makedirs(new_dir, exist_ok=True)

        os.rename(old_path, new_path)
        
        return jsonify({"success": True, "message": "重命名成功"})
    except Exception as e:
        return jsonify({"success": False, "message": f"重命名失败: {str(e)}"}), 500

@story_bp.route('/api/file-operations/copy', methods=['POST'])
@require_auth
@get_current_info
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
        
        if not os.path.exists(source_full_path) and not os.path.isdir(source_full_path):
            story_source_path = source_full_path + '.story'
            if os.path.exists(story_source_path):
                source_full_path = story_source_path
                if not target_full_path.endswith('.story'):
                    target_full_path = target_full_path + '.story'
        
        if not os.path.exists(source_full_path):
            return jsonify({"success": False, "message": "源文件不存在"}), 404
        
        if os.path.exists(target_full_path):
            return jsonify({"success": False, "message": "目标路径已存在"}), 409
        
        target_dir = os.path.dirname(target_full_path)
        if target_dir and not os.path.exists(target_dir):
            os.makedirs(target_dir)
        
        if os.path.isdir(source_full_path):
            shutil.copytree(source_full_path, target_full_path)
        else:
            shutil.copy2(source_full_path, target_full_path)
        return jsonify({"success": True, "message": "复制成功"})
    except Exception as e:
        return jsonify({"success": False, "message": f"复制失败: {str(e)}"}), 500

@story_bp.route('/api/upload-story', methods=['POST'])
@require_auth
@get_current_info
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
        
        filename = file.filename
        base, ext = os.path.splitext(filename)
        if ext.lower() != '.story':
            ext = '.story'
        target_filename = f"{base}{ext}"
        file_path = os.path.join(stories_path, target_filename)

        counter = 1
        while os.path.exists(file_path):
            target_filename = f"{base}_{counter}{ext}"
            file_path = os.path.join(stories_path, target_filename)
            counter += 1

        file.save(file_path)

        # 返回不带扩展名的相对路径（与文件树 path 一致）
        return jsonify({
            "success": True,
            "message": "上传成功",
            "filename": os.path.splitext(target_filename)[0]
        })
    except Exception as e:
        return jsonify({"success": False, "message": f"上传失败: {str(e)}"}), 500

@story_bp.route('/api/save-story', methods=['POST'])
@require_auth
@get_current_info
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
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(story_data, f, ensure_ascii=False, indent=2)
        
        return jsonify({"success": True, "message": "保存成功"})
    except Exception as e:
        return jsonify({"success": False, "message": f"保存失败: {str(e)}"}), 500

@story_bp.route('/api/file-content/<project_name>/<path:filename>')
@optional_auth
@get_current_info
def get_file_content(project_name, filename):
    """获取指定项目文件的内容"""
    try:
        user_id = request.current_user['user_id']
        stories_path = get_project_stories_path(user_id, project_name)
        file_path = os.path.join(stories_path, filename)
        if not file_path.endswith('.story'):
            file_path += '.story'
        
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return jsonify(data)
        else:
            return jsonify({"error": "文件不存在"}), 404
    except Exception as e:
        return jsonify({"error": f"读取文件失败: {str(e)}"}), 500

@story_bp.route('/api/file-content-txt/<project_name>/<path:filename>')
@optional_auth
@get_current_info
def get_txt_file_content(project_name, filename):
    """获取指定项目txt文件的内容"""
    try:
        user_id = request.current_user['user_id']
        stories_path = get_project_stories_path(user_id, project_name)
        file_path = os.path.join(stories_path, filename)
        if not file_path.endswith('.txt'):
            file_path += '.txt'
        
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                return jsonify(content)
        else:
            return jsonify({"error": "文件不存在"}), 404
    except Exception as e:
        return jsonify({"error": f"读取txt文件失败: {str(e)}"}), 500

@story_bp.route('/api/save-txt', methods=['POST'])
@require_auth
@get_current_info
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
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return jsonify({"success": True, "message": "保存成功"})
    except Exception as e:
        return jsonify({"success": False, "message": f"保存失败: {str(e)}"}), 500

@story_bp.route('/api/projects', methods=['GET'])
@optional_auth
@get_current_info
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
@get_current_info
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
            
        ensure_project_directory(user_id, project_name)
        ensure_project_stories_directory(user_id, project_name)
        ensure_project_worldview_and_character_settings(project_name)
        return jsonify({"success": True, "message": "项目创建成功"})
    except Exception as e:
        return jsonify({"success": False, "message": f"项目创建失败: {str(e)}"}), 500

@story_bp.route('/api/projects/<project_name>', methods=['DELETE'])
@require_auth
@get_current_info
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
@optional_auth
@get_current_info
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
@get_current_info
def save_worldview(project_name):
    """保存世界观内容到指定项目"""
    try:
        user_id = request.current_user['user_id']
        data = request.json
        content = data.get('content', '')
        
        worldview_path = get_project_worldview_path(user_id, project_name)
        
        ensure_project_directory(user_id, project_name)
        
        with open(worldview_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return jsonify({"success": True, "message": "保存成功"})
    except Exception as e:
        return jsonify({"success": False, "message": f"保存失败: {str(e)}"}), 500

@story_bp.route('/api/characters/<project_name>', methods=['GET'])
@optional_auth
@get_current_info
def get_characters(project_name):
    """获取指定项目的所有角色列表"""
    try:
        user_id = request.current_user['user_id']
        characters_path = get_project_characters_path(user_id, project_name)
        mapping_file = os.path.join(characters_path, 'chr.bind')

        if not os.path.exists(mapping_file):
            return jsonify([])

        with open(mapping_file, 'r', encoding='utf-8') as f:
            char_map = json.load(f)

        characters = [{'id': int(id), 'name': name} for id, name in char_map.items()]
        characters.sort(key=lambda x: x['id']) # 按ID排序
        
        return jsonify(characters)
    except Exception as e:
        return jsonify({"error": f"获取角色列表失败: {str(e)}"}), 500

@story_bp.route('/api/characters/<project_name>/<int:character_id>', methods=['GET'])
@optional_auth
@get_current_info
def get_character(project_name, character_id):
    """获取指定项目的指定角色内容"""
    try:
        user_id = request.current_user['user_id']
        characters_path = get_project_characters_path(user_id, project_name)
        character_file = os.path.join(characters_path, f"{character_id}.txt")
        
        if not os.path.exists(character_file):
            return jsonify({"error": "角色不存在"}), 404
            
        with open(character_file, 'r', encoding='utf-8') as f:
            content = f.read()
                
        return jsonify({
            "content": content
        })
    except Exception as e:
        return jsonify({"error": f"读取角色失败: {str(e)}"}), 500

@story_bp.route('/api/characters/<project_name>/<int:character_id>', methods=['POST'])
@require_auth
def save_character(project_name, character_id):
    """保存角色内容到指定项目"""
    try:
        user_id = request.current_user['user_id']
        data = request.json
        content = data.get('content', '')
        
        characters_path = get_project_characters_path(user_id, project_name)
        character_file = os.path.join(characters_path, f"{character_id}.txt")
        
        ensure_project_characters_directory(user_id, project_name)
        
        with open(character_file, 'w', encoding='utf-8') as f:
            f.write(content)
        
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
        
        characters_path = ensure_project_characters_directory(user_id, project_name)
        mapping_file = os.path.join(characters_path, 'chr.bind')

        char_map = {}
        if os.path.exists(mapping_file):
            with open(mapping_file, 'r', encoding='utf-8') as f:
                try:
                    char_map = json.load(f)
                except json.JSONDecodeError:
                    pass

        existing_ids = {int(k) for k in char_map.keys()}
        next_id = 0
        while next_id in existing_ids:
            next_id += 1
        
        char_map[str(next_id)] = name
        with open(mapping_file, 'w', encoding='utf-8') as f:
            json.dump(char_map, f, ensure_ascii=False, indent=2)

        character_file = os.path.join(characters_path, f"{next_id}.txt")
        with open(character_file, 'w', encoding='utf-8') as f:
            f.write(f"{name}\n\n在这里描述你的角色...")
            
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
        mapping_file = os.path.join(characters_path, 'chr.bind')
        character_file = os.path.join(characters_path, f"{character_id}.txt")

        if os.path.exists(mapping_file):
            with open(mapping_file, 'r', encoding='utf-8') as f:
                char_map = json.load(f)
            
            if str(character_id) in char_map:
                del char_map[str(character_id)]
            
            with open(mapping_file, 'w', encoding='utf-8') as f:
                json.dump(char_map, f, ensure_ascii=False, indent=2)

        if os.path.exists(character_file):
            os.remove(character_file)
            
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
        mapping_file = os.path.join(characters_path, 'chr.bind')
        character_file = os.path.join(characters_path, f"{character_id}.txt")
        
        if os.path.exists(mapping_file):
            with open(mapping_file, 'r', encoding='utf-8') as f:
                char_map = json.load(f)
            
            if str(character_id) in char_map:
                char_map[str(character_id)] = new_name
            
            with open(mapping_file, 'w', encoding='utf-8') as f:
                json.dump(char_map, f, ensure_ascii=False, indent=2)

        if os.path.exists(character_file):
            with open(character_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            if lines:
                lines = f"{new_name}\n"
            
            with open(character_file, 'w', encoding='utf-8') as f:
                f.writelines(lines)
            
        return jsonify({"success": True, "message": "角色重命名成功"})
    except Exception as e:
        return jsonify({"success": False, "message": f"角色重命名失败: {str(e)}"}), 500
# ============================================================================
# 设定管理 (原 lorebook.py)
# ============================================================================

@story_bp.route('/api/worldview/<project_name>', methods=['GET'])
@optional_auth
def get_worldview_content(project_name):
    """获取世界观内容"""
    try:
        user_id = request.current_user['user_id']
        ensure_project_worldview_and_character_settings(user_id, project_name)
        worldview_path = get_project_worldview_path(user_id, project_name)
        if not os.path.exists(worldview_path):
            return jsonify({'content': ''})
        with open(worldview_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return jsonify({'content': content})
    except Exception as e:
        return jsonify({'error': f'获取世界观失败: {e}'}), 500

@story_bp.route('/api/worldview', methods=['POST'])
@require_auth
def save_worldview_content():
    """保存世界观内容"""
    try:
        user_id = request.current_user['user_id']
        data = request.get_json()
        project_name = data.get('projectName')
        content = data.get('content', '')
        if not project_name:
            return jsonify({'success': False, 'message': '缺少项目名称'}), 400
        ensure_project_worldview_and_character_settings(user_id, project_name)
        worldview_path = get_project_worldview_path(user_id, project_name)
        with open(worldview_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return jsonify({'success': True, 'message': '世界观保存成功'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'保存世界观失败: {e}'}), 500

@story_bp.route('/api/character-settings/<project_name>', methods=['GET'])
@optional_auth
def get_character_settings_list(project_name):
    """获取所有角色设定"""
    try:
        user_id = request.current_user['user_id']
        characters_path = ensure_project_characters_directory(user_id, project_name)
        mapping_file = os.path.join(characters_path, 'chr.bind')
        
        if not os.path.exists(mapping_file):
            return jsonify([])
            
        with open(mapping_file, 'r', encoding='utf-8') as f:
            bindings = json.load(f)
        
        characters = []
        for char_id, name in bindings.items():
            char_file = os.path.join(characters_path, f"{char_id}.txt")
            content = ""
            if os.path.exists(char_file):
                with open(char_file, 'r', encoding='utf-8') as f:
                    content = f.read()
            characters.append({
                'id': int(char_id),
                'name': name,
                'content': content,
            })
        characters.sort(key=lambda x: x['id'])
        return jsonify(characters)
    except Exception as e:
        return jsonify({'error': f'获取角色设定失败: {e}'}), 500

@story_bp.route('/api/character-settings', methods=['POST'])
@require_auth
def create_new_character():
    """创建新角色"""
    try:
        user_id = request.current_user['user_id']
        data = request.get_json()
        project_name = data.get('projectName')
        character_name = data.get('name')
        
        if not project_name or not character_name:
            return jsonify({'success': False, 'message': '缺少项目名称或角色名称'}), 400
            
        characters_path = ensure_project_characters_directory(user_id, project_name)
        mapping_file = os.path.join(characters_path, 'chr.bind')
        
        bindings = {}
        if os.path.exists(mapping_file):
            with open(mapping_file, 'r', encoding='utf-8') as f:
                bindings = json.load(f)
        
        existing_ids = {int(k) for k in bindings.keys()}
        next_id = 0
        while next_id in existing_ids:
            next_id += 1
        
        initial_content = f"# {character_name}\n\n在这里描述你的角色..."
        char_file = os.path.join(characters_path, f"{next_id}.txt")
        with open(char_file, 'w', encoding='utf-8') as f:
            f.write(initial_content)
            
        bindings[str(next_id)] = character_name
        with open(mapping_file, 'w', encoding='utf-8') as f:
            json.dump(bindings, f, ensure_ascii=False, indent=2)
            
        return jsonify({
            'success': True,
            'message': '角色创建成功',
            'character': { 'id': next_id, 'name': character_name, 'content': initial_content }
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'创建角色失败: {e}'}), 500

@story_bp.route('/api/character-settings/save', methods=['POST'])
@require_auth
def save_character_content():
    """保存角色设定内容"""
    try:
        user_id = request.current_user['user_id']
        data = request.get_json()
        project_name = data.get('projectName')
        character_id = data.get('id')
        content = data.get('content', '')
        
        if not project_name or character_id is None:
            return jsonify({'success': False, 'message': '缺少项目名称或角色ID'}), 400
            
        characters_path = get_project_characters_path(user_id, project_name)
        char_file = os.path.join(characters_path, f"{character_id}.txt")
        
        # 移除文件存在性检查，如果文件不存在，'w'模式会自动创建
        with open(char_file, 'w', encoding='utf-8') as f:
            f.write(content)
            
        return jsonify({'success': True, 'message': '角色设定保存成功'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'保存角色设定失败: {e}'}), 500

@story_bp.route('/api/character-settings/rename', methods=['POST'])
@require_auth
def rename_character_setting():
    """重命名角色"""
    try:
        user_id = request.current_user['user_id']
        data = request.get_json()
        project_name = data.get('projectName')
        character_id = data.get('id')
        new_name = data.get('newName')
        
        if not project_name or character_id is None or not new_name:
            return jsonify({'success': False, 'message': '缺少项目名称、角色ID或新名称'}), 400
            
        characters_path = get_project_characters_path(user_id, project_name)
        mapping_file = os.path.join(characters_path, 'chr.bind')

        bindings = {}
        if os.path.exists(mapping_file):
            with open(mapping_file, 'r', encoding='utf-8') as f:
                bindings = json.load(f)

        if str(character_id) not in bindings:
            return jsonify({'success': False, 'message': '角色不存在'}), 404

        bindings[str(character_id)] = new_name
        with open(mapping_file, 'w', encoding='utf-8') as f:
            json.dump(bindings, f, ensure_ascii=False, indent=2)
            
        return jsonify({'success': True, 'message': '角色重命名成功'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'重命名角色失败: {e}'}), 500

@story_bp.route('/api/character-settings/delete', methods=['POST'])
@require_auth
def delete_character_setting():
    """删除角色"""
    try:
        user_id = request.current_user['user_id']
        data = request.get_json()
        project_name = data.get('projectName')
        character_id = data.get('id')
        
        if not project_name or character_id is None:
            return jsonify({'success': False, 'message': '缺少项目名称或角色ID'}), 400
            
        characters_path = get_project_characters_path(user_id, project_name)
        mapping_file = os.path.join(characters_path, 'chr.bind')
        char_file = os.path.join(characters_path, f"{character_id}.txt")
        
        if os.path.exists(char_file):
            os.remove(char_file)
        
        bindings = {}
        if os.path.exists(mapping_file):
            with open(mapping_file, 'r', encoding='utf-8') as f:
                bindings = json.load(f)
        
        if str(character_id) in bindings:
            del bindings[str(character_id)]
            with open(mapping_file, 'w', encoding='utf-8') as f:
                json.dump(bindings, f, ensure_ascii=False, indent=2)
            
        return jsonify({'success': True, 'message': '角色删除成功'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'删除角色失败: {e}'}), 500