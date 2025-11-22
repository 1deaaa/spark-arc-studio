from flask import Blueprint, request, jsonify
from core.auth import require_auth
from core.request_context import get_current_info, current_user_id, current_project_name
from .showrunner import ShowrunnerAgent
import os
from core.utils import get_project_path
import json

structure_bp = Blueprint('structure_bp', __name__)

@structure_bp.route('/api/ai/beat-sheet', methods=['POST'])
@require_auth
@get_current_info
def generate_beat_sheet():
    """
    Showrunner Agent: Generate Beat Sheet.
    """
    data = request.json or {}
    context = data.get('context', '')
    guidance = data.get('guidance', '')
    
    user_id = current_user_id.get()
    project_name = current_project_name.get()

    if not project_name:
        return jsonify({"error": "Missing project name"}), 400

    try:
        project_path = get_project_path(user_id, project_name)
        
        # Load Worldview
        worldview = ""
        worldview_path = os.path.join(project_path, '世界观.txt')
        if os.path.exists(worldview_path):
            with open(worldview_path, 'r', encoding='utf-8') as f:
                worldview = f.read()

        # Load Roles
        roles = ""
        roles_path = os.path.join(project_path, '角色设定.txt')
        if os.path.exists(roles_path):
            try:
                with open(roles_path, 'r', encoding='utf-8') as f:
                    # Try to load as JSON first
                    all_roles = json.load(f)
                    if isinstance(all_roles, list):
                        roles = "\n".join([f"- {r.get('name', '')}: {r.get('settings', '')}" for r in all_roles])
            except:
                # Fallback to reading as text
                with open(roles_path, 'r', encoding='utf-8') as f:
                    roles = f.read()

        showrunner = ShowrunnerAgent(user_id)
        beat_sheet = showrunner.plan_scene(context, worldview, roles, guidance)
        
        return jsonify({"success": True, "beat_sheet": beat_sheet})

    except Exception as e:
        print(f"Error generating beat sheet: {e}")
        return jsonify({"error": str(e)}), 500
