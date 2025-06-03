from flask import Flask, send_from_directory, jsonify, request, make_response
import os
import json
import shutil
from auth import require_auth, optional_auth, user_db

app = Flask(__name__, static_folder='.', static_url_path='')
app.secret_key = 'your-secret-key-change-this-in-production'

def get_user_stories_path(user_id):
    """获取用户专属的stories路径"""
    return f'./uid_{user_id}/stories'

def ensure_user_directory(user_id):
    """确保用户目录存在"""
    user_path = f'./uid_{user_id}'
    stories_path = get_user_stories_path(user_id)
    
    if not os.path.exists(user_path):
        os.makedirs(user_path)
    
    if not os.path.exists(stories_path):
        os.makedirs(stories_path)
    
    return stories_path

@app.route('/')
@optional_auth
def index():
    """提供主页"""
    # 如果用户未登录，重定向到登录页面
    if not request.current_user:
        return send_from_directory('.', 'login.html')
    return send_from_directory('.', 'index.html')

# 认证相关路由
@app.route('/api/register', methods=['POST'])
def register():
    """用户注册"""
    try:
        data = request.json
        username = data.get('username', '').strip()
        password = data.get('password', '')
          # 基本验证
        if not username or not password:
            return jsonify({"success": False, "message": "请填写用户名和密码"}), 400
        
        if len(username) < 3:
            return jsonify({"success": False, "message": "用户名至少需要3个字符"}), 400
        
        if len(password) < 6:
            return jsonify({"success": False, "message": "密码至少需要6个字符"}), 400
        
        # 创建用户（不再需要邮箱）
        success, result = user_db.create_user(username, password)
        
        if success:
            # 为新用户创建目录和示例文件
            user_id = result  # result是用户ID
            stories_path = ensure_user_directory(user_id)
            
            # 创建示例文件夹和文件
            try:
                sample_folder = os.path.join(stories_path, '示例文件夹')
                os.makedirs(sample_folder, exist_ok=True)
                
                # 复制根目录下的剧本示例.json到用户stories目录
                source_script_path = './剧本示例.json'
                if os.path.exists(source_script_path):
                    target_script_path = os.path.join(stories_path, '剧本示例.json')
                    shutil.copy2(source_script_path, target_script_path)
                    print(f"已为用户 {user_id} 复制剧本示例.json")
                else:
                    print(f"警告: 根目录下的剧本示例.json不存在，无法复制")
                
                # 创建示例故事文件
                sample_story_path = os.path.join(sample_folder, '示例故事.json')
                with open(sample_story_path, 'w', encoding='utf-8') as f:
                    json.dump([], f, ensure_ascii=False, indent=2)
                
                # 创建根目录下的新建故事文件
                new_story_path = os.path.join(stories_path, '新建故事.json')
                with open(new_story_path, 'w', encoding='utf-8') as f:
                    json.dump([], f, ensure_ascii=False, indent=2)
                    
                print(f"为用户 {user_id} 创建了完整的示例文件结构")
            except Exception as e:
                print(f"创建示例文件失败: {e}")
            
            return jsonify({"success": True, "message": "注册成功！请登录"})
        else:
            return jsonify({"success": False, "message": result}), 400
            
    except Exception as e:
        return jsonify({"success": False, "message": f"注册失败: {str(e)}"}), 500

@app.route('/api/login', methods=['POST'])
def login():
    """用户登录"""
    try:
        data = request.json
        username = data.get('username', '').strip()
        password = data.get('password', '')
        remember_me = data.get('rememberMe', False)
        
        if not username or not password:
            return jsonify({"success": False, "message": "请输入用户名和密码"}), 400
        
        # 验证用户
        success, result = user_db.verify_user(username, password)
        
        if success:
            # 根据"记住我"选项决定会话时长
            if remember_me:
                # 记住我：30天
                session_days = 30
                max_age = 30*24*60*60
            else:
                # 普通登录：7天
                session_days = 7
                max_age = 7*24*60*60
            
            # 创建会话
            session_token = user_db.create_session(result, session_days)
            
            if session_token:
                response = make_response(jsonify({"success": True, "message": "登录成功"}))
                response.set_cookie('session_token', session_token, 
                                  max_age=max_age,
                                  httponly=True, 
                                  secure=False)  # 开发环境设为False
                return response
            else:
                return jsonify({"success": False, "message": "创建会话失败"}), 500
        else:
            return jsonify({"success": False, "message": result}), 401
            
    except Exception as e:
        return jsonify({"success": False, "message": f"登录失败: {str(e)}"}), 500

@app.route('/api/logout', methods=['POST'])
def logout():
    """用户登出"""
    session_token = request.cookies.get('session_token')
    
    if session_token:
        user_db.logout_user(session_token)
    
    response = make_response(jsonify({"success": True, "message": "已登出"}))
    response.set_cookie('session_token', '', expires=0)
    return response

@app.route('/api/user/info')
@require_auth
def get_user_info():
    """获取当前用户信息"""
    user_info = user_db.get_user_info(request.current_user['user_id'])
    if user_info:
        return jsonify({"success": True, "user": user_info})
    else:
        return jsonify({"success": False, "message": "获取用户信息失败"}), 500

@app.route('/login.html')
def login_page():
    """登录页面"""
    return send_from_directory('.', 'login.html')

@app.route('/剧本示例.json')
@require_auth
def get_dialogue_data():
    """获取对话数据，优先从文件读取，文件不存在则返回默认数据"""
    try:
        # 尝试读取文件
        file_path = os.path.join(os.path.dirname(__file__), '剧本示例.json')
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return jsonify(data)
        else:
            print("剧本示例.json 文件不存在，返回默认数据")
            return jsonify("")
    except Exception as e:
        print(f"加载剧本示例.json 出错: {e}")
        return jsonify("")

@app.route('/save', methods=['POST'])
@require_auth
def save_dialogue():
    """保存对话数据到文件"""
    from flask import request
    try:
        data = request.json
        with open('剧本示例.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return jsonify({"success": True, "message": "保存成功"})
    except Exception as e:
        return jsonify({"success": False, "message": f"保存失败: {str(e)}"}), 500

@app.route('/api/json-files')
@require_auth
def get_json_files():
    """获取用户专属stories文件夹下所有JSON文件的文件树结构"""
    try:
        user_id = request.current_user['user_id']
        stories_path = ensure_user_directory(user_id)
        
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
        
        # 扫描用户的stories目录，返回其内容
        file_tree = scan_directory(stories_path)
        return jsonify(file_tree)
    except Exception as e:
        print(f"获取JSON文件列表失败: {e}")
        return jsonify([])

@app.route('/api/file-operations/move', methods=['POST'])
@require_auth
def move_file():
    """移动文件或文件夹"""
    try:
        user_id = request.current_user['user_id']
        stories_path = get_user_stories_path(user_id)
        
        data = request.json
        source_path = os.path.join(stories_path, data['sourcePath'])
        target_path = os.path.join(stories_path, data['targetPath'])
        
        print(f"移动文件请求:")
        print(f"  用户ID: {user_id}")
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
@require_auth
def create_file_or_folder():
    """创建文件或文件夹"""
    try:
        user_id = request.current_user['user_id']
        stories_path = get_user_stories_path(user_id)
        
        data = request.json
        file_type = data['type']  # 'file' 或 'folder'
        file_path = os.path.join(stories_path, data['path'])
        
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
@require_auth
def delete_file_or_folder():
    """删除文件或文件夹"""
    try:
        user_id = request.current_user['user_id']
        stories_path = get_user_stories_path(user_id)
        
        data = request.json
        file_path = os.path.join(stories_path, data['path'])
        
        if os.path.isdir(file_path):
            shutil.rmtree(file_path)
        else:
            os.remove(file_path)
        
        return jsonify({"success": True, "message": "删除成功"})
    except Exception as e:
        return jsonify({"success": False, "message": f"删除失败: {str(e)}"}), 500

@app.route('/api/file-operations/rename', methods=['POST'])
@require_auth
def rename_file_or_folder():
    """重命名文件或文件夹"""
    try:
        user_id = request.current_user['user_id']
        stories_path = get_user_stories_path(user_id)
        
        data = request.json
        old_path = os.path.join(stories_path, data['oldPath'])
        new_path = os.path.join(stories_path, data['newPath'])
        
        os.rename(old_path, new_path)
        
        return jsonify({"success": True, "message": "重命名成功"})
    except Exception as e:
        return jsonify({"success": False, "message": f"重命名失败: {str(e)}"}), 500

@app.route('/api/file-operations/copy', methods=['POST'])
@require_auth
def copy_file():
    """复制文件或文件夹"""
    try:
        user_id = request.current_user['user_id']
        stories_path = get_user_stories_path(user_id)
        
        data = request.json
        source_path = data.get('sourcePath')
        target_path = data.get('targetPath')
        
        if not source_path or not target_path:
            return jsonify({"success": False, "message": "源路径和目标路径不能为空"}), 400
        
        source_full_path = os.path.join(stories_path, source_path)
        target_full_path = os.path.join(stories_path, target_path)
        
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

@app.route('/api/upload-story', methods=['POST'])
@require_auth
def upload_story():
    """上传故事文件到用户专属stories目录"""
    try:
        user_id = request.current_user['user_id']
        stories_dir = ensure_user_directory(user_id)
        
        if 'file' not in request.files:
            return jsonify({"success": False, "message": "没有文件"}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({"success": False, "message": "没有选择文件"}), 400
        
        if not file.filename.endswith('.json'):
            return jsonify({"success": False, "message": "只支持JSON文件"}), 400
        
        # 保存文件
        filename = file.filename
        file_path = os.path.join(stories_dir, filename)
        
        # 如果文件已存在，生成新的文件名
        base_name = os.path.splitext(filename)[0]
        counter = 1
        while os.path.exists(file_path):
            new_filename = f"{base_name}_{counter}.json"
            file_path = os.path.join(stories_dir, new_filename)
            filename = new_filename
            counter += 1
        
        file.save(file_path)
        
        # 返回不带.json后缀的文件名（用于前端识别）
        return jsonify({
            "success": True, 
            "message": "上传成功",
            "filename": os.path.splitext(filename)[0]
        })
    except Exception as e:
        return jsonify({"success": False, "message": f"上传失败: {str(e)}"}), 500

@app.route('/api/save-story', methods=['POST'])
@require_auth
def save_story():
    """保存故事数据到指定文件"""
    try:
        user_id = request.current_user['user_id']
        stories_dir = ensure_user_directory(user_id)
        
        data = request.json
        filename = data.get('filename')
        story_data = data.get('data')
        
        if not filename:
            return jsonify({"success": False, "message": "文件名不能为空"}), 400
        
        if not story_data:
            return jsonify({"success": False, "message": "数据不能为空"}), 400
        
        # 构建文件路径
        file_path = os.path.join(stories_dir, filename)
        if not file_path.endswith('.json'):
            file_path += '.json'
        
        # 保存文件
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(story_data, f, ensure_ascii=False, indent=2)
        
        return jsonify({"success": True, "message": "保存成功"})
    except Exception as e:
        return jsonify({"success": False, "message": f"保存失败: {str(e)}"}), 500

@app.route('/api/file-content/<path:filename>')
@require_auth
def get_file_content(filename):
    """获取指定文件的内容"""
    try:
        user_id = request.current_user['user_id']
        stories_path = get_user_stories_path(user_id)
        
        print(f"请求文件内容: {filename} (用户ID: {user_id})")
        file_path = os.path.join(stories_path, filename)
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
    # 检查剧本示例.json是否存在，不存在则创建默认文件
    if not os.path.exists('剧本示例.json'):
        try:
            with open('剧本示例.json', 'w', encoding='utf-8') as f:
                json.dump("", f, ensure_ascii=False, indent=2)
            print("已创建默认的剧本示例.json文件")
        except Exception as e:
            print(f"创建默认剧本示例.json失败: {e}")
    
    # 启动服务器
    print("服务器启动在 http://127.0.0.1:5000")
    print("请在浏览器中访问此地址来使用对话编辑器")
    app.run(debug=True)