from flask import Blueprint, request, Response
from auth import require_auth
import time

ai_bp = Blueprint('ai_bp', __name__)

@ai_bp.route('/api/continue_writing', methods=['POST'])
@require_auth
def continue_writing():
    """AI续写 - 流式响应"""
    data = request.json
    text = data.get('text', '')

    if not text:
        return Response("文本不能为空", status=400)

    def generate():
        try:
            # 在这里调用你的AI模型
            # 为简单起见，我们模拟一个流式响应
            continued_text = " 这是AI模拟的流式续写内容。"
            for char in continued_text:
                yield char
                time.sleep(0.05)
        except Exception as e:
            print(f"AI续写流生成失败: {e}")
            # 可以在这里yield一个错误信息
            yield " [续写失败] "

    return Response(generate(), mimetype='text/plain')