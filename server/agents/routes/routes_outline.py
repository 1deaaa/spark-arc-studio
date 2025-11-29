"""
Outline Route - 大纲和历史记录管理 API

文件结构：
- {project}/outline.json - 当前大纲
- {project}/history/muse_history.json - 灵感历史
- {project}/history/outline_history.json - 大纲历史
"""
import os
import json
from datetime import datetime
from flask import Blueprint, request, jsonify
from core.auth import require_auth
from core.request_context import get_current_info, current_user_id, current_project_name
from core.utils import get_project_path

outline_bp = Blueprint('outline_bp', __name__)


def get_history_dir(user_id, project_name):
    """获取历史记录目录"""
    return os.path.join(get_project_path(user_id, project_name), 'history')


def ensure_history_dir(user_id, project_name):
    """确保历史记录目录存在"""
    history_dir = get_history_dir(user_id, project_name)
    os.makedirs(history_dir, exist_ok=True)
    return history_dir


# ==================== 大纲 API ====================

@outline_bp.route('/api/outline/<project_name>', methods=['GET'])
@require_auth
@get_current_info
def get_outline(project_name):
    """获取当前大纲"""
    try:
        user_id = current_user_id.get()
        project_path = get_project_path(user_id, project_name)
        outline_path = os.path.join(project_path, 'outline.json')
        
        if os.path.exists(outline_path):
            with open(outline_path, 'r', encoding='utf-8') as f:
                outline = json.load(f)
            return jsonify({"success": True, "outline": outline})
        
        # 返回空大纲模板
        return jsonify({
            "success": True,
            "outline": {
                "title": "新故事大纲",
                "nodes": [],
                "updatedAt": None
            }
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@outline_bp.route('/api/outline/<project_name>', methods=['POST'])
@require_auth
@get_current_info
def save_outline(project_name):
    """保存大纲"""
    try:
        user_id = current_user_id.get()
        project_path = get_project_path(user_id, project_name)
        outline_path = os.path.join(project_path, 'outline.json')
        
        data = request.json or {}
        outline = data.get('outline', {})
        save_to_history = data.get('saveToHistory', False)
        
        # 添加更新时间
        outline['updatedAt'] = datetime.now().isoformat()
        
        # 保存当前大纲
        with open(outline_path, 'w', encoding='utf-8') as f:
            json.dump(outline, f, ensure_ascii=False, indent=2)
        
        # 如果需要，同时保存到历史记录
        if save_to_history:
            _save_to_outline_history(user_id, project_name, outline)
        
        return jsonify({"success": True, "message": "大纲已保存"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ==================== 灵感历史 API ====================

@outline_bp.route('/api/history/muse/<project_name>', methods=['GET'])
@require_auth
@get_current_info
def get_muse_history(project_name):
    """获取灵感历史列表"""
    try:
        user_id = current_user_id.get()
        history_dir = get_history_dir(user_id, project_name)
        history_file = os.path.join(history_dir, 'muse_history.json')
        
        if os.path.exists(history_file):
            with open(history_file, 'r', encoding='utf-8') as f:
                history = json.load(f)
            return jsonify({"success": True, "history": history})
        
        return jsonify({"success": True, "history": []})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@outline_bp.route('/api/history/muse/<project_name>', methods=['POST'])
@require_auth
@get_current_info
def save_muse_history(project_name):
    """保存灵感到历史"""
    try:
        user_id = current_user_id.get()
        history_dir = ensure_history_dir(user_id, project_name)
        history_file = os.path.join(history_dir, 'muse_history.json')
        
        data = request.json or {}
        input_text = data.get('input', '')
        output_text = data.get('output', '')
        
        # 加载现有历史
        history = []
        if os.path.exists(history_file):
            with open(history_file, 'r', encoding='utf-8') as f:
                history = json.load(f)
        
        # 添加新记录
        entry = {
            "id": len(history) + 1,
            "timestamp": datetime.now().isoformat(),
            "input": input_text,
            "output": output_text
        }
        history.insert(0, entry)  # 最新的在前面
        
        # 限制历史数量（最多保留50条）
        history = history[:50]
        
        # 保存
        with open(history_file, 'w', encoding='utf-8') as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
        
        return jsonify({"success": True, "entry": entry})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@outline_bp.route('/api/history/muse/<project_name>/<int:entry_id>', methods=['DELETE'])
@require_auth
@get_current_info
def delete_muse_history(project_name, entry_id):
    """删除单条灵感历史"""
    try:
        user_id = current_user_id.get()
        history_dir = get_history_dir(user_id, project_name)
        history_file = os.path.join(history_dir, 'muse_history.json')
        
        if not os.path.exists(history_file):
            return jsonify({"success": False, "error": "历史记录不存在"}), 404
        
        with open(history_file, 'r', encoding='utf-8') as f:
            history = json.load(f)
        
        history = [h for h in history if h.get('id') != entry_id]
        
        with open(history_file, 'w', encoding='utf-8') as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
        
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ==================== 大纲历史 API ====================

@outline_bp.route('/api/history/outline/<project_name>', methods=['GET'])
@require_auth
@get_current_info
def get_outline_history(project_name):
    """获取大纲历史列表"""
    try:
        user_id = current_user_id.get()
        history_dir = get_history_dir(user_id, project_name)
        history_file = os.path.join(history_dir, 'outline_history.json')
        
        if os.path.exists(history_file):
            with open(history_file, 'r', encoding='utf-8') as f:
                history = json.load(f)
            return jsonify({"success": True, "history": history})
        
        return jsonify({"success": True, "history": []})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


def _save_to_outline_history(user_id, project_name, outline):
    """内部函数：保存大纲到历史"""
    history_dir = ensure_history_dir(user_id, project_name)
    history_file = os.path.join(history_dir, 'outline_history.json')
    
    # 加载现有历史
    history = []
    if os.path.exists(history_file):
        with open(history_file, 'r', encoding='utf-8') as f:
            history = json.load(f)
    
    # 添加新记录（包含完整大纲数据）
    entry = {
        "id": len(history) + 1,
        "timestamp": datetime.now().isoformat(),
        "title": outline.get('title', '未命名大纲'),
        "nodeCount": len(outline.get('nodes', [])),
        "outline": outline  # 完整大纲数据
    }
    history.insert(0, entry)
    
    # 限制历史数量（最多保留20条大纲）
    history = history[:20]
    
    # 保存
    with open(history_file, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


@outline_bp.route('/api/history/outline/<project_name>', methods=['POST'])
@require_auth
@get_current_info
def save_outline_history(project_name):
    """手动保存大纲到历史"""
    try:
        user_id = current_user_id.get()
        data = request.json or {}
        outline = data.get('outline', {})
        
        _save_to_outline_history(user_id, project_name, outline)
        
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@outline_bp.route('/api/history/outline/<project_name>/<int:entry_id>', methods=['DELETE'])
@require_auth
@get_current_info
def delete_outline_history(project_name, entry_id):
    """删除单条大纲历史"""
    try:
        user_id = current_user_id.get()
        history_dir = get_history_dir(user_id, project_name)
        history_file = os.path.join(history_dir, 'outline_history.json')
        
        if not os.path.exists(history_file):
            return jsonify({"success": False, "error": "历史记录不存在"}), 404
        
        with open(history_file, 'r', encoding='utf-8') as f:
            history = json.load(f)
        
        history = [h for h in history if h.get('id') != entry_id]
        
        with open(history_file, 'w', encoding='utf-8') as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
        
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@outline_bp.route('/api/history/outline/<project_name>/<int:entry_id>/restore', methods=['POST'])
@require_auth
@get_current_info
def restore_outline_from_history(project_name, entry_id):
    """从历史恢复大纲"""
    try:
        user_id = current_user_id.get()
        history_dir = get_history_dir(user_id, project_name)
        history_file = os.path.join(history_dir, 'outline_history.json')
        
        if not os.path.exists(history_file):
            return jsonify({"success": False, "error": "历史记录不存在"}), 404
        
        with open(history_file, 'r', encoding='utf-8') as f:
            history = json.load(f)
        
        # 找到对应的历史记录
        entry = next((h for h in history if h.get('id') == entry_id), None)
        if not entry:
            return jsonify({"success": False, "error": "记录不存在"}), 404
        
        outline = entry.get('outline', {})
        
        # 更新时间戳
        outline['updatedAt'] = datetime.now().isoformat()
        
        # 保存为当前大纲
        project_path = get_project_path(user_id, project_name)
        outline_path = os.path.join(project_path, 'outline.json')
        with open(outline_path, 'w', encoding='utf-8') as f:
            json.dump(outline, f, ensure_ascii=False, indent=2)
        
        return jsonify({"success": True, "outline": outline})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500