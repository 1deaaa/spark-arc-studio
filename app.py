from flask import Flask, send_from_directory, jsonify, request
import os
import json
import shutil

app = Flask(__name__, static_folder='.', static_url_path='')

@app.route('/')
def index():
    """提供主页"""
    return send_from_directory('.', 'index.html')

@app.route('/对话.json')
def get_dialogue_data():
    """获取对话数据，优先从文件读取，文件不存在则返回默认数据"""
    try:
        # 尝试读取文件
        file_path = os.path.join(os.path.dirname(__file__), '对话.json')
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return jsonify(data)
        else:
            print("对话.json 文件不存在，返回默认数据")
            return jsonify("")
    except Exception as e:
        print(f"加载对话.json 出错: {e}")
        return jsonify("")

@app.route('/save', methods=['POST'])
def save_dialogue():
    """保存对话数据到文件"""
    from flask import request
    try:
        data = request.json
        with open('对话.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return jsonify({"success": True, "message": "保存成功"})
    except Exception as e:
        return jsonify({"success": False, "message": f"保存失败: {str(e)}"}), 500

@app.route('/api/json-files')
def get_json_files():
    """获取stories文件夹下所有JSON文件的文件树结构"""
    try:
        def scan_directory(path, relative_path=""):
            """递归扫描目录，构建文件树"""
            items = []
            if not os.path.exists(path):
                return items
                
            for item in sorted(os.listdir(path), key=str.lower):  # 按首字母排序
                item_path = os.path.join(path, item)
                if os.path.isfile(item_path) and item.endswith('.json'):
                    # JSON文件，去掉.json后缀
                    name = item[:-5]  # 去掉.json后缀
                    items.append({
                        'name': name,
                        'type': 'json',
                        'path': os.path.join(relative_path, item) if relative_path else item
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
        
        # 确保stories文件夹存在
        stories_path = './stories'
        if not os.path.exists(stories_path):
            os.makedirs(stories_path)
        
        # 扫描stories目录，返回其内容（不显示stories文件夹本身）
        file_tree = scan_directory(stories_path)
        return jsonify(file_tree)
    except Exception as e:
        print(f"获取JSON文件列表失败: {e}")
        return jsonify([])

@app.route('/api/file-operations/move', methods=['POST'])
def move_file():
    """移动文件或文件夹"""
    try:
        data = request.json
        source_path = os.path.join('./stories', data['sourcePath'])
        target_path = os.path.join('./stories', data['targetPath'])
        
        print(f"移动文件请求:")
        print(f"  源路径: {data['sourcePath']}")
        print(f"  目标路径: {data['targetPath']}")
        print(f"  完整源路径: {source_path}")
        print(f"  完整目标路径: {target_path}")
        print(f"  源文件是否存在: {os.path.exists(source_path)}")
        
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

@app.route('/api/file-operations/create', methods=['POST'])
def create_file_or_folder():
    """创建文件或文件夹"""
    try:
        data = request.json
        file_type = data['type']  # 'file' 或 'folder'
        file_path = os.path.join('./stories', data['path'])
        
        if file_type == 'folder':
            os.makedirs(file_path, exist_ok=True)
        else:  # file
            # 确保目录存在
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            # 创建空的JSON文件
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump([], f, ensure_ascii=False, indent=2)
        
        return jsonify({"success": True, "message": "创建成功"})
    except Exception as e:
        return jsonify({"success": False, "message": f"创建失败: {str(e)}"}), 500

@app.route('/api/file-operations/delete', methods=['POST'])
def delete_file_or_folder():
    """删除文件或文件夹"""
    try:
        data = request.json
        file_path = os.path.join('./stories', data['path'])
        
        if os.path.isdir(file_path):
            shutil.rmtree(file_path)
        else:
            os.remove(file_path)
        
        return jsonify({"success": True, "message": "删除成功"})
    except Exception as e:
        return jsonify({"success": False, "message": f"删除失败: {str(e)}"}), 500

@app.route('/api/file-operations/rename', methods=['POST'])
def rename_file_or_folder():
    """重命名文件或文件夹"""
    try:
        data = request.json
        old_path = os.path.join('./stories', data['oldPath'])
        new_path = os.path.join('./stories', data['newPath'])
        
        os.rename(old_path, new_path)
        
        return jsonify({"success": True, "message": "重命名成功"})
    except Exception as e:
        return jsonify({"success": False, "message": f"重命名失败: {str(e)}"}), 500

@app.route('/api/file-operations/copy', methods=['POST'])
def copy_file():
    """复制文件或文件夹"""
    try:
        data = request.json
        source_path = data.get('sourcePath')
        target_path = data.get('targetPath')
        
        if not source_path or not target_path:
            return jsonify({"success": False, "message": "源路径和目标路径不能为空"}), 400
        
        source_full_path = os.path.join('./stories', source_path)
        target_full_path = os.path.join('./stories', target_path)
        
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

@app.route('/api/file-content/<path:filename>')
def get_file_content(filename):
    """获取指定文件的内容"""
    try:
        print(f"请求文件内容: {filename}")
        file_path = os.path.join('./stories', filename)
        if not file_path.endswith('.json'):
            file_path += '.json'
        
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

if __name__ == '__main__':
    # 检查对话.json是否存在，不存在则创建默认文件
    if not os.path.exists('对话.json'):
        try:
            with open('对话.json', 'w', encoding='utf-8') as f:
                json.dump("", f, ensure_ascii=False, indent=2)
            print("已创建默认的对话.json文件")
        except Exception as e:
            print(f"创建默认对话.json失败: {e}")
    
    # 启动服务器
    print("服务器启动在 http://127.0.0.1:5000")
    print("请在浏览器中访问此地址来使用对话编辑器")
    app.run(debug=True)