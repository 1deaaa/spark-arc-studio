from flask import Blueprint, request, jsonify
from core.auth import require_auth
from core.request_context import get_current_info, current_user_id, current_project_name
from .showrunner import ShowrunnerAgent
import os
from core.utils import get_project_path
import json
from datetime import datetime

structure_bp = Blueprint('structure_bp', __name__)


def _load_worldview_and_roles(user_id, project_name):
    """加载世界观和角色设定"""
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
                all_roles = json.load(f)
                if isinstance(all_roles, list):
                    roles = "\n".join([f"- {r.get('name', '')}: {r.get('settings', '')}" for r in all_roles])
        except:
            with open(roles_path, 'r', encoding='utf-8') as f:
                roles = f.read()
    
    return worldview, roles


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
        worldview, roles = _load_worldview_and_roles(user_id, project_name)

        showrunner = ShowrunnerAgent(user_id)
        beat_sheet = showrunner.plan_scene(context, worldview, roles, guidance)
        
        return jsonify({"success": True, "beat_sheet": beat_sheet})

    except Exception as e:
        print(f"Error generating beat sheet: {e}")
        return jsonify({"error": str(e)}), 500


@structure_bp.route('/api/ai/outline', methods=['POST'])
@require_auth
@get_current_info
def generate_outline():
    """
    Showrunner Agent: Generate Story Outline (树状结构).
    """
    data = request.json or {}
    context = data.get('context', '')
    guidance = data.get('guidance', '')
    save_to_project = data.get('saveToProject', True)
    save_to_history = data.get('saveToHistory', True)
    
    user_id = current_user_id.get()
    project_name = current_project_name.get()

    if not project_name:
        return jsonify({"error": "Missing project name"}), 400

    try:
        worldview, roles = _load_worldview_and_roles(user_id, project_name)

        showrunner = ShowrunnerAgent(user_id)
        outline = showrunner.generate_outline(context, worldview, roles, guidance)
        
        # 添加时间戳
        outline['updatedAt'] = datetime.now().isoformat()
        outline['generatedAt'] = datetime.now().isoformat()
        
        # 保存到项目
        if save_to_project:
            project_path = get_project_path(user_id, project_name)
            outline_path = os.path.join(project_path, 'outline.json')
            with open(outline_path, 'w', encoding='utf-8') as f:
                json.dump(outline, f, ensure_ascii=False, indent=2)
        
        # 保存到历史
        if save_to_history:
            _save_outline_to_history(user_id, project_name, outline)
        
        return jsonify({"success": True, "outline": outline})

    except Exception as e:
        print(f"Error generating outline: {e}")
        return jsonify({"error": str(e)}), 500


def _save_outline_to_history(user_id, project_name, outline):
    """保存大纲到历史记录"""
    project_path = get_project_path(user_id, project_name)
    history_dir = os.path.join(project_path, 'history')
    os.makedirs(history_dir, exist_ok=True)
    
    history_file = os.path.join(history_dir, 'outline_history.json')
    
    history = []
    if os.path.exists(history_file):
        with open(history_file, 'r', encoding='utf-8') as f:
            history = json.load(f)
    
    entry = {
        "id": len(history) + 1,
        "timestamp": datetime.now().isoformat(),
        "title": outline.get('title', '未命名大纲'),
        "nodeCount": len(outline.get('nodes', [])),
        "outline": outline
    }
    history.insert(0, entry)
    history = history[:20]  # 保留最近20条
    
    with open(history_file, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
