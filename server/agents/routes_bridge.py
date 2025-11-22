from flask import Blueprint, request, jsonify
from core.auth import require_auth
from agents.bridge import BridgeAgent

bridge_bp = Blueprint('bridge', __name__, url_prefix='/api/bridge')

@bridge_bp.route('/generate', methods=['POST'])
@require_auth
def generate_transition():
    data = request.json
    prev_text = data.get('prevText', '')
    next_text = data.get('nextText', '')
    context = data.get('context', '')
    
    user_id = request.current_user
    agent = BridgeAgent(user_id)
    
    result = agent.bridge_scenes(prev_text, next_text, context)
    return jsonify({'success': True, 'transition': result})
