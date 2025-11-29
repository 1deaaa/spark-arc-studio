"""
Bridge Route - 场景过渡 API
"""
from flask import Blueprint, request, jsonify
from core.auth import require_auth
from core.request_context import get_current_info, current_user_id, current_project_name
from core.utils import get_project_path
from agents import BridgeAgent
import os
import json

bridge_bp = Blueprint('bridge', __name__, url_prefix='/api/bridge')


def _load_worldview_and_characters(user_id, project_name):
    """加载世界观和角色信息"""
    worldview = ""
    characters = []
    
    project_path = get_project_path(user_id, project_name)
    
    # 加载世界观
    worldview_path = os.path.join(project_path, 'worldview.txt')
    if os.path.exists(worldview_path):
        with open(worldview_path, 'r', encoding='utf-8') as f:
            worldview = f.read()
    
    # 加载角色绑定
    chr_bind_path = os.path.join(project_path, 'chr', 'chr.bind')
    if os.path.exists(chr_bind_path):
        with open(chr_bind_path, 'r', encoding='utf-8') as f:
            chr_data = json.load(f)
            # 转换为角色列表
            for chr_id, chr_info in chr_data.items():
                if isinstance(chr_info, dict):
                    characters.append({
                        'id': int(chr_id),
                        'name': chr_info.get('name', ''),
                        'desc': chr_info.get('desc', '')
                    })
                else:
                    # 简单格式: id -> name
                    characters.append({
                        'id': int(chr_id),
                        'name': str(chr_info),
                        'desc': ''
                    })
    
    return worldview, characters


@bridge_bp.route('/generate', methods=['POST'])
@require_auth
@get_current_info
def generate_transition():
    """
    生成两个场景之间的过渡对话
    
    请求体：
    {
        "prevScene": { "scene": "...", "cap": "...", "dia": [...] },
        "nextScene": { "scene": "...", "cap": "...", "dia": [...] },
        "pacing": "slow|normal|fast",
        "mood": "目标氛围",
        "guidance": "用户指导文本",
        "characters": [{"id": 1, "name": "..."}]  // 可选，覆盖自动加载
    }
    """
    data = request.json or {}
    
    prev_scene = data.get('prevScene', {})
    next_scene = data.get('nextScene', {})
    pacing = data.get('pacing', 'normal')
    mood = data.get('mood', '')
    guidance = data.get('guidance', '')
    
    user_id = current_user_id.get()
    project_name = current_project_name.get()
    
    if not project_name:
        return jsonify({'success': False, 'error': '缺少项目名称'}), 400
    
    # 加载世界观和角色
    worldview, characters = _load_worldview_and_characters(user_id, project_name)
    
    # 允许请求中覆盖角色
    if data.get('characters'):
        characters = data['characters']
    
    agent = BridgeAgent(user_id)
    
    result = agent.bridge_scenes(
        prev_scene=prev_scene,
        next_scene=next_scene,
        worldview=worldview,
        characters=characters,
        pacing=pacing,
        mood=mood,
        guidance=guidance
    )
    
    return jsonify({'success': True, **result})


@bridge_bp.route('/preview', methods=['POST'])
@require_auth
@get_current_info
def preview_transition():
    """
    快速预览过渡（不加载完整世界观）
    用于对话编辑器中的实时预览
    """
    data = request.json or {}
    
    prev_text = data.get('prevText', '')
    next_text = data.get('nextText', '')
    guidance = data.get('guidance', '')
    
    user_id = current_user_id.get()
    
    # 构建简单场景对象
    prev_scene = {'scene': '上一场景', 'cap': '', 'dia': [{'txt': prev_text}]}
    next_scene = {'scene': '下一场景', 'cap': '', 'dia': [{'txt': next_text}]}
    
    agent = BridgeAgent(user_id)
    
    result = agent.bridge_scenes(
        prev_scene=prev_scene,
        next_scene=next_scene,
        guidance=guidance
    )
    
    return jsonify({'success': True, **result})
