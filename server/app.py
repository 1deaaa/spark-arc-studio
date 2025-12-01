from flask import Flask, send_from_directory, request
import os
import json
from core.auth import optional_auth

# 导入蓝图
from core.auth import auth_bp
from story import story_bp
from story.routes.routes_shares import shares_bp

# Agent 相关路由 - 从 agents/routes/ 目录导入
from agents.routes import (
    bridge_bp,
    style_bp,
    structure_bp,
    production_bp,
    outline_bp,
    agent_usage_bp,
)

# 其他 Agent 蓝图
from agents.agent_lorebook import lorebook_bp
from agents.agent_setup import setup_bp

# LLM 配置路由
from llm.routes.routes_config import llm_config_bp

# 获取client/dist目录的绝对路径
current_dir = os.path.dirname(os.path.abspath(__file__))
# 指向前端客户端的构建输出目录
dist_dir = os.path.join(os.path.dirname(current_dir), 'client', 'dist')

app = Flask(__name__, static_folder=dist_dir, static_url_path='')
app.secret_key = 'your-secret-key-change-this-in-production'

# 注册蓝图
app.register_blueprint(auth_bp)
app.register_blueprint(story_bp)
app.register_blueprint(production_bp)
app.register_blueprint(lorebook_bp)
app.register_blueprint(setup_bp)
app.register_blueprint(structure_bp)
app.register_blueprint(style_bp)
app.register_blueprint(bridge_bp)
app.register_blueprint(agent_usage_bp)
app.register_blueprint(outline_bp)
app.register_blueprint(llm_config_bp)
app.register_blueprint(shares_bp)

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_spa(path):
    """服务单页应用 (SPA)"""
    # 检查请求的路径是否是静态文件
    if path != "" and os.path.exists(os.path.join(app.static_folder, path)):
        return send_from_directory(app.static_folder, path)
    else:
        # 否则，提供SPA的主入口 index.html
        return send_from_directory(app.static_folder, 'index.html')

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

    import uvicorn
    # 使用 Uvicorn 运行 ASGI 应用, 启用热重载
    # 第一个 "app" 是指文件名 app.py，第二个 "app" 是指 Flask app 对象
    uvicorn.run("app:app", host='0.0.0.0', port=6688, reload=True)
