from functools import wraps
from flask import request, jsonify, session
from database import UserDatabase

# 初始化数据库
user_db = UserDatabase()

def require_auth(f):
    """装饰器：要求用户登录"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 检查会话令牌
        session_token = request.cookies.get('session_token')
        
        if not session_token:
            return jsonify({"success": False, "message": "需要登录", "require_login": True}), 401
        
        # 验证会话
        is_valid, user_info = user_db.verify_session(session_token)
        
        if not is_valid:
            return jsonify({"success": False, "message": "会话已过期，请重新登录", "require_login": True}), 401
        
        # 将用户信息添加到请求中
        request.current_user = user_info
        
        return f(*args, **kwargs)
    
    return decorated_function

def optional_auth(f):
    """装饰器：可选的用户认证"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 检查会话令牌
        session_token = request.cookies.get('session_token')
        
        request.current_user = None
        
        if session_token:
            # 验证会话
            is_valid, user_info = user_db.verify_session(session_token)
            
            if is_valid:
                request.current_user = user_info
        
        return f(*args, **kwargs)
    
    return decorated_function
