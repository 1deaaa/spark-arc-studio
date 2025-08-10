from flask import Flask, send_from_directory, request
import os
import json
from auth import optional_auth

# 导入蓝图
from auth import auth_bp
from story_routes import story_bp
from ai import ai_bp
from server.lorebook import settings_bp

# 获取client目录的绝对路径
current_dir = os.path.dirname(os.path.abspath(__file__))
client_dir = os.path.join(os.path.dirname(current_dir), 'clinet')

app = Flask(__name__, static_folder=client_dir, static_url_path='')
app.secret_key = 'your-secret-key-change-this-in-production'

# 注册蓝图
app.register_blueprint(auth_bp)
app.register_blueprint(story_bp)
app.register_blueprint(ai_bp)
app.register_blueprint(settings_bp)

@app.route('/')
@optional_auth
def index():
    """提供主页"""
    # 如果用户未登录，重定向到登录页面
    if not request.current_user:
        return send_from_directory(client_dir, 'login.html')
    return send_from_directory(client_dir, 'index.html')

if __name__ == '__main__':
    # 检查剧本示例.story是否存在，不存在则创建默认文件
    default_story_path = os.path.join('.', '剧本示例.story')
    if not os.path.exists(default_story_path):
        try:
            with open(default_story_path, 'w', encoding='utf-8') as f:
                json.dump("", f, ensure_ascii=False, indent=2)
            print("已创建默认的剧本示例.story文件")
        except Exception as e:
            print(f"创建默认剧本示例.story失败: {e}")
    
    # 直接启动Flask开发服务器
    app.run(host='0.0.0.0', port=5000, debug=True)
