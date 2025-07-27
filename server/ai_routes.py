from flask import Blueprint, request, Response, jsonify
from auth import require_auth
from openai import OpenAI
import os
from utils import get_project_path

ai_bp = Blueprint('ai_bp', __name__)

MODEL = "qwen-plus"

client = OpenAI(
    api_key="sk-c1cf2eb1c1a846e3b3f729ff656cc5a2",
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
)

@ai_bp.route('/api/continue_writing', methods=['POST'])
@require_auth
def continue_writing():
    """AI续写 - 流式响应"""
    data = request.json
    text = data.get('text', '')
    project_name = data.get('projectName')
    user_id = request.current_user['user_id']

    if not text or not project_name:
        return Response("文本或项目名称不能为空", status=400)

    def generate():
        try:
            # 读取世界观和角色设定文件
            project_path = get_project_path(user_id, project_name)
            worldview_path = os.path.join(project_path, '世界观.txt')
            roles_path = os.path.join(project_path, '角色设定.txt')

            worldview = ""
            if os.path.exists(worldview_path):
                with open(worldview_path, 'r', encoding='utf-8') as f:
                    worldview = f.read()
            
            roles = ""
            if os.path.exists(roles_path):
                with open(roles_path, 'r', encoding='utf-8') as f:
                    roles = f.read()

            messages = [
                {"role": "system", "content": "你是一个专业的剧本续写助手。"},
                {"role": "system", "content": f"世界观:\n{worldview}"},
                {"role": "system", "content": f"角色设定:\n{roles}"},
                {"role": "user", "content": f"请根据以下内容续写：\n\n{text}"}
            ]

            completion = client.chat.completions.create(
                model=MODEL,
                messages=messages,
                stream=True
            )

            for chunk in completion:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            print(f"AI续写流生成失败: {e}")
            yield " [续写失败] "

    return Response(generate(), mimetype='text/plain')