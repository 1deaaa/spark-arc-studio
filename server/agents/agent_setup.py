from flask import Blueprint, request, Response, jsonify
from core.auth import require_auth
from core.request_context import get_current_info, current_user_id, current_project_name
from .setup_agents import MuseAgent
import os
from core.utils import get_project_path

setup_bp = Blueprint('setup_bp', __name__)

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

    if not raw_input:
        return jsonify({"error": "Missing inspiration input"}), 400

    muse = MuseAgent(user_id)
    
    def generate():
        try:
            for chunk in muse.expand_inspiration(raw_input):
                yield chunk
        except Exception as e:
            yield f"Error: {str(e)}"

    return Response(generate(), mimetype='text/plain')
