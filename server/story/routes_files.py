import json
import os
import shutil

from flask import jsonify, request

from core.auth import require_auth, optional_auth
from core.request_context import get_current_info
from core.utils import (
    ensure_project_stories_directory,
    get_project_path,
    get_project_stories_path,
    strip_private_fields,
)

from . import story_bp


@story_bp.route('/api/story-files/<project_name>')
@optional_auth
@get_current_info
def get_story_files(project_name):
    """返回用户项目 stories 目录下的文件树结构"""
    try:
        user_id = request.current_user['user_id']
        stories_path = ensure_project_stories_directory(user_id, project_name)

        order_file = os.path.join(get_project_path(user_id, project_name), 'stories_order.json')
        order_map = {}
        if os.path.exists(order_file):
            try:
                with open(order_file, 'r', encoding='utf-8') as f:
                    order_map = json.load(f) or {}
            except Exception:
                order_map = {}

        def reorder_by_user_order(items_list, dir_rel_path):
            order = order_map.get(dir_rel_path or '')
            if not order or not isinstance(order, list):
                return items_list
            index_map = {name: idx for idx, name in enumerate(order)}

            def key_fn(entry):
                name = entry.get('name', '')
                return (0 if name in index_map else 1, index_map.get(name, 0))

            return sorted(items_list, key=key_fn)

        def scan_directory(path, relative_path=''):
            folders = []
            files = []
            if not os.path.exists(path):
                return []

            for item in os.listdir(path):
                if item.startswith('.'):
                    continue
                item_path = os.path.join(path, item)
                if os.path.isdir(item_path):
                    rel_dir = os.path.join(relative_path, item) if relative_path else item
                    web_dir = rel_dir.replace(os.sep, '/')
                    children = scan_directory(item_path, rel_dir)
                    folders.append({
                        'name': item,
                        'type': 'folder',
                        'path': web_dir,
                        'children': children,
                    })
                elif os.path.isfile(item_path) and (item.endswith('.story') or item.endswith('.arc')):
                    # 支持 .story 和 .arc 两种格式
                    if item.endswith('.story'):
                        name = item[:-6]
                        file_type = 'story'
                    else:
                        name = item[:-4]
                        file_type = 'arc'
                    rel = os.path.join(relative_path, name) if relative_path else name
                    web_path = rel.replace(os.sep, '/')
                    scene_count = 0
                    try:
                        if file_type == 'story':
                            with open(item_path, 'r', encoding='utf-8') as f:
                                story_data = json.load(f)
                                if isinstance(story_data, list):
                                    scene_count = len(story_data)
                        else:
                            # .arc 格式：统计 # 开头的场景数
                            with open(item_path, 'r', encoding='utf-8') as f:
                                content = f.read()
                                scene_count = len([line for line in content.split('\n') if line.strip().startswith('# ')])
                    except Exception:
                        scene_count = 0
                    files.append({
                        'name': name,
                        'type': 'story',  # 统一用 story 类型以便前端兼容
                        'path': web_path,
                        'sceneCount': scene_count,
                        'format': file_type,  # 新增：标记实际格式
                    })

            folders_sorted = reorder_by_user_order(folders, relative_path)
            files_sorted = reorder_by_user_order(files, relative_path)
            return folders_sorted + files_sorted

        return jsonify(scan_directory(stories_path))
    except Exception as exc:
        print(f"获取 JSON 文件列表失败: {exc}")
        return jsonify([])


@story_bp.route('/api/file-operations/save-order', methods=['POST'])
@require_auth
@get_current_info
def save_stories_order():
    """保存 stories 子目录的用户自定义顺序"""
    try:
        user_id = request.current_user['user_id']
        data = request.json or {}
        project_name = data.get('projectName')
        dir_path = (data.get('dirPath') or '').strip('/\\')
        order = data.get('order', [])
        if not project_name:
            return jsonify({"success": False, "message": "缺少项目名称"}), 400
        if not isinstance(order, list):
            return jsonify({"success": False, "message": "order 必须是数组"}), 400

        stories_path = ensure_project_stories_directory(user_id, project_name)
        target_dir = os.path.join(stories_path, dir_path) if dir_path else stories_path
        if not os.path.isdir(target_dir):
            return jsonify({"success": False, "message": "目录不存在"}), 404

        order_file = os.path.join(get_project_path(user_id, project_name), 'stories_order.json')
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
    except Exception as exc:
        return jsonify({"success": False, "message": f"保存排序失败: {exc}"}), 500


@story_bp.route('/api/file-operations/move', methods=['POST'])
@require_auth
@get_current_info
def move_file():
    """移动文件或文件夹"""
    try:
        user_id = request.current_user['user_id']
        data = request.json or {}
        project_name = data.get('projectName')
        if not project_name:
            return jsonify({"success": False, "message": "缺少项目名称"}), 400

        stories_path = get_project_stories_path(user_id, project_name)
        source_path = os.path.join(stories_path, data['sourcePath'])
        target_path = os.path.join(stories_path, data['targetPath'])

        if not os.path.exists(source_path) and not os.path.isdir(source_path):
            story_source_path = source_path + '.story'
            if os.path.exists(story_source_path):
                source_path = story_source_path
                if not target_path.endswith('.story'):
                    target_path = target_path + '.story'

        if not os.path.exists(source_path):
            return jsonify({"success": False, "message": f"源文件不存在: {source_path}"}), 404

        target_dir = os.path.dirname(target_path)
        if target_dir and not os.path.exists(target_dir):
            os.makedirs(target_dir, exist_ok=True)

        shutil.move(source_path, target_path)
        return jsonify({"success": True, "message": "文件移动成功"})
    except Exception as exc:
        return jsonify({"success": False, "message": f"文件移动失败: {exc}"}), 500


@story_bp.route('/api/file-operations/create', methods=['POST'])
@require_auth
@get_current_info
def create_file_or_folder():
    """创建文件或文件夹"""
    try:
        user_id = request.current_user['user_id']
        data = request.json or {}
        project_name = data.get('projectName')
        if not project_name:
            return jsonify({"success": False, "message": "缺少项目名称"}), 400

        stories_path = ensure_project_stories_directory(user_id, project_name)
        file_type = data['type']
        file_path = os.path.join(stories_path, data['path'])

        if file_type == 'folder':
            os.makedirs(file_path, exist_ok=True)
        else:
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
                    pass
            else:
                return jsonify({"success": False, "message": "不支持的文件类型"}), 400

        return jsonify({"success": True, "message": "创建成功"})
    except Exception as exc:
        return jsonify({"success": False, "message": f"创建失败: {exc}"}), 500


@story_bp.route('/api/file-operations/delete', methods=['POST'])
@require_auth
@get_current_info
def delete_file_or_folder():
    """删除文件或文件夹"""
    try:
        user_id = request.current_user['user_id']
        data = request.json or {}
        project_name = data.get('projectName')
        if not project_name:
            return jsonify({"success": False, "message": "缺少项目名称"}), 400

        stories_path = get_project_stories_path(user_id, project_name)
        file_path = os.path.join(stories_path, data['path'])

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
    except Exception as exc:
        return jsonify({"success": False, "message": f"删除失败: {exc}"}), 500


@story_bp.route('/api/file-operations/rename', methods=['POST'])
@require_auth
@get_current_info
def rename_file_or_folder():
    """重命名文件或文件夹"""
    try:
        user_id = request.current_user['user_id']
        data = request.json or {}
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

        if not os.path.exists(old_path) and not os.path.isdir(old_path):
            story_old_path = old_path + '.story'
            if os.path.exists(story_old_path):
                old_path = story_old_path
                if not new_path.endswith('.story'):
                    new_path = new_path + '.story'

        if os.path.exists(new_path):
            return jsonify({"success": False, "message": "目标已存在"}), 409

        new_dir = os.path.dirname(new_path)
        if new_dir and not os.path.exists(new_dir):
            os.makedirs(new_dir, exist_ok=True)

        os.rename(old_path, new_path)
        return jsonify({"success": True, "message": "重命名成功"})
    except Exception as exc:
        return jsonify({"success": False, "message": f"重命名失败: {exc}"}), 500


@story_bp.route('/api/file-operations/copy', methods=['POST'])
@require_auth
@get_current_info
def copy_file():
    """复制文件或文件夹"""
    try:
        user_id = request.current_user['user_id']
        data = request.json or {}
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
            os.makedirs(target_dir, exist_ok=True)

        if os.path.isdir(source_full_path):
            shutil.copytree(source_full_path, target_full_path)
        else:
            shutil.copy2(source_full_path, target_full_path)
        return jsonify({"success": True, "message": "复制成功"})
    except Exception as exc:
        return jsonify({"success": False, "message": f"复制失败: {exc}"}), 500


@story_bp.route('/api/upload-story', methods=['POST'])
@require_auth
@get_current_info
def upload_story():
    """上传 .story 文件到项目"""
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

        base, ext = os.path.splitext(file.filename)
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
        return jsonify({
            "success": True,
            "message": "上传成功",
            "filename": os.path.splitext(target_filename)[0],
        })
    except Exception as exc:
        return jsonify({"success": False, "message": f"上传失败: {exc}"}), 500


@story_bp.route('/api/save-story', methods=['POST'])
@require_auth
@get_current_info
def save_story():
    """保存 stories 目录下的 .story 文件"""
    try:
        user_id = request.current_user['user_id']
        data = request.json or {}
        project_name = data.get('projectName')
        filename = data.get('filename')
        story_data = data.get('data')

        if not project_name:
            return jsonify({"success": False, "message": "缺少项目名称"}), 400
        if not filename:
            return jsonify({"success": False, "message": "文件名不能为空"}), 400
        if story_data is None:
            return jsonify({"success": False, "message": "数据不能为空"}), 400

        stories_path = ensure_project_stories_directory(user_id, project_name)
        file_path = os.path.join(stories_path, filename)
        if not file_path.endswith('.story'):
            file_path += '.story'

        strip_private_fields(story_data)
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(story_data, f, ensure_ascii=False, indent=2)

        return jsonify({"success": True, "message": "保存成功"})
    except Exception as exc:
        return jsonify({"success": False, "message": f"保存失败: {exc}"}), 500


@story_bp.route('/api/file-content/<project_name>/<path:filename>')
@optional_auth
@get_current_info
def get_file_content(project_name, filename):
    """获取 .story 或 .arc 文件的内容"""
    try:
        user_id = request.current_user['user_id']
        stories_path = get_project_stories_path(user_id, project_name)
        
        # 支持 .arc 和 .story 两种格式
        file_path = os.path.join(stories_path, filename)
        
        # 尝试 .arc 文件
        arc_path = file_path if file_path.endswith('.arc') else file_path + '.arc'
        if os.path.exists(arc_path):
            with open(arc_path, 'r', encoding='utf-8') as f:
                content = f.read()
            # 返回纯文本内容作为 JSON 字符串，前端可以通过 detectFormat 判断
            return jsonify(content)
        
        # 尝试 .story 文件 (JSON 格式)
        story_path = file_path if file_path.endswith('.story') else file_path + '.story'
        if os.path.exists(story_path):
            with open(story_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return jsonify(data)
        
        return jsonify({"error": "文件不存在"}), 404
    except Exception as exc:
        return jsonify({"error": f"读取文件失败: {exc}"}), 500


@story_bp.route('/api/file-content-txt/<project_name>/<path:filename>')
@optional_auth
@get_current_info
def get_txt_file_content(project_name, filename):
    """获取 .txt 文件内容"""
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
        return jsonify({"error": "文件不存在"}), 404
    except Exception as exc:
        return jsonify({"error": f"读取txt文件失败: {exc}"}), 500


@story_bp.route('/api/save-txt', methods=['POST'])
@require_auth
@get_current_info
def save_txt_file():
    """保存 stories 目录下的 .txt 文件"""
    try:
        user_id = request.current_user['user_id']
        data = request.json or {}
        project_name = data.get('projectName')
        filename = data.get('filename')
        content = data.get('content', '')

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
    except Exception as exc:
        return jsonify({"success": False, "message": f"保存失败: {exc}"}), 500
