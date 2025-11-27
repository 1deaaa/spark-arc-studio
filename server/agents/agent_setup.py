from flask import Blueprint, request, Response, jsonify
from core.auth import require_auth
from core.request_context import get_current_info, current_user_id, current_project_name
from .setup_agents import MuseAgent
import os
import json
from datetime import datetime
from core.utils import get_project_path

setup_bp = Blueprint('setup_bp', __name__)


def _save_muse_to_history(user_id, project_name, input_text, output_text):
    """保存灵感到历史记录"""
    try:
        project_path = get_project_path(user_id, project_name)
        history_dir = os.path.join(project_path, 'history')
        os.makedirs(history_dir, exist_ok=True)
        
        history_file = os.path.join(history_dir, 'muse_history.json')
        
        history = []
        if os.path.exists(history_file):
            with open(history_file, 'r', encoding='utf-8') as f:
                history = json.load(f)
        
        entry = {
            "id": len(history) + 1,
            "timestamp": datetime.now().isoformat(),
            "input": input_text,
            "output": output_text
        }
        history.insert(0, entry)
        history = history[:50]  # 保留最近50条
        
        with open(history_file, 'w', encoding='utf-8') as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error saving muse history: {e}")


@setup_bp.route('/api/ai/muse', methods=['POST'])
@require_auth
@get_current_info
def muse_inspiration():
    """
    Muse Agent: Expands raw inspiration.
    Streamed response.
    """
    data = request.json or {}
    raw_input = data.get('inspiration', '')
    user_id = current_user_id.get()
    project_name = current_project_name.get()

    if not raw_input:
        return jsonify({"error": "Missing inspiration input"}), 400

    muse = MuseAgent(user_id)
    
    # 用于收集完整输出
    output_collector = []
    
    def generate():
        try:
            for chunk in muse.expand_inspiration(raw_input):
                output_collector.append(chunk)
                yield chunk
        except Exception as e:
            yield f"Error: {str(e)}"
        finally:
            # 流式传输完成后保存到历史
            if project_name and output_collector:
                full_output = ''.join(output_collector)
                _save_muse_to_history(user_id, project_name, raw_input, full_output)

    return Response(generate(), mimetype='text/plain')
