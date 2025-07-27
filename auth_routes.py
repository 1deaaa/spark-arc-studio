from flask import Blueprint, jsonify, request, make_response, send_from_directory
from auth import user_db, require_auth
from utils import ensure_user_directory
import shutil
import os

auth_bp = Blueprint('auth_bp', __name__)

@auth_bp.route('/api/register', methods=['POST'])
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
                os.makedirs(sample_folder, exist_ok=True)                  # 复制根目录下的剧本示例.story到用户stories目录
                source_script_path = os.path.join('.', '剧本示例.story')
                if os.path.exists(source_script_path):
                    target_script_path = os.path.join(stories_path, '剧本示例.story')
                    shutil.copy2(source_script_path, target_script_path)
                    print(f"已为用户 {user_id} 复制剧本示例.story")
                else:
                    print(f"警告: 根目录下的剧本示例.story不存在，无法复制")
            except Exception as e:
                print(f"创建示例文件失败: {e}")
            
            return jsonify({"success": True, "message": "注册成功！请登录"})
        else:
            return jsonify({"success": False, "message": result}), 400
            
    except Exception as e:
        return jsonify({"success": False, "message": f"注册失败: {str(e)}"}), 500

@auth_bp.route('/api/login', methods=['POST'])
def login():
    """用户登录"""
    try:
        data = request.json
        username = data.get('username', '').strip()
        password = data.get('password', '')
        
        if not username or not password:
            return jsonify({"success": False, "message": "请输入用户名和密码"}), 400
        
        # 验证用户
        success, result = user_db.verify_user(username, password)
        
        if success:
            # 创建会话
            session_token = user_db.create_session(result)
            
            if session_token:
                response = make_response(jsonify({"success": True, "message": "登录成功"}))
                response.set_cookie('session_token', session_token, 
                                  max_age=7*24*60*60,  # 7天
                                  httponly=True, 
                                  secure=False)  # 开发环境设为False
                return response
            else:
                return jsonify({"success": False, "message": "创建会话失败"}), 500
        else:
            return jsonify({"success": False, "message": result}), 401
            
    except Exception as e:
        return jsonify({"success": False, "message": f"登录失败: {str(e)}"}), 500

@auth_bp.route('/api/logout', methods=['POST'])
def logout():
    """用户登出"""
    session_token = request.cookies.get('session_token')
    
    if session_token:
        user_db.logout_user(session_token)
    
    response = make_response(jsonify({"success": True, "message": "已登出"}))
    response.set_cookie('session_token', '', expires=0)
    return response

@auth_bp.route('/api/user/info')
@require_auth
def get_user_info():
    """获取当前用户信息"""
    user_info = user_db.get_user_info(request.current_user['user_id'])
    if user_info:
        return jsonify({"success": True, "user": user_info})
    else:
        return jsonify({"success": False, "message": "获取用户信息失败"}), 500

@auth_bp.route('/login.html')
def login_page():
    """登录页面"""
    return send_from_directory('.', 'login.html')