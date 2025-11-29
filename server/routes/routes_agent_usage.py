"""
Agent Usage Route - Agent 配置绑定 API
"""
import os
import json
from flask import Blueprint, request, jsonify
from core.auth import require_auth
from agents.registry import get_agent_registry

agent_usage_bp = Blueprint('agent_usage_bp', __name__)

# userdata 在 server/_userdata
USERDATA_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../_userdata'))


@agent_usage_bp.route('/api/agents/registry', methods=['GET'])
@require_auth
def get_registry():
    """返回所有可用 Agent 的注册信息"""
    return jsonify(get_agent_registry())


@agent_usage_bp.route('/api/agent-usage-bindings', methods=['GET', 'POST'])
@require_auth
def agent_usage_bindings():
    """获取或更新用户的 Agent 用途绑定配置"""
    user_id = str(request.current_user['user_id'])
    user_dir = os.path.join(USERDATA_ROOT, f'uid_{user_id}')
    os.makedirs(user_dir, exist_ok=True)
    usage_file = os.path.join(user_dir, 'agent_usage.json')

    if request.method == 'GET':
        if os.path.exists(usage_file):
            with open(usage_file, 'r', encoding='utf-8') as f:
                try:
                    data = json.load(f)
                except Exception:
                    data = {}
        else:
            data = {}
        return jsonify(data)

    if request.method == 'POST':
        try:
            data = request.json or {}
            with open(usage_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return jsonify({"success": True})
        except Exception as e:
            return jsonify({"error": str(e)}), 400
