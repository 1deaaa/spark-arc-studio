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


# ==================== 大纲导出到文件 API ====================

@outline_bp.route('/api/outline/<project_name>/export-to-files', methods=['POST'])
@require_auth
@get_current_info
def export_outline_to_files(project_name):
    """
    将大纲导出为 .arc 格式文件到项目的 stories 目录
    每个章节导出为一个独立的 .arc 文件，包含该章节的所有场景标题
    """
    try:
        user_id = current_user_id.get()
        project_path = get_project_path(user_id, project_name)
        outline_path = os.path.join(project_path, 'outline.json')
        
        if not os.path.exists(outline_path):
            return jsonify({"success": False, "error": "大纲不存在，请先生成大纲"}), 404
        
        with open(outline_path, 'r', encoding='utf-8') as f:
            outline = json.load(f)
        
        nodes = outline.get('nodes', [])
        if not nodes:
            return jsonify({"success": False, "error": "大纲为空，没有可导出的章节"}), 400
        
        # 确保 stories 目录存在
        stories_path = os.path.join(project_path, 'stories')
        os.makedirs(stories_path, exist_ok=True)
        
        created_files = []
        
        for chapter_node in nodes:
            if chapter_node.get('type') != 'chapter':
                continue
            
            chapter_num = chapter_node.get('chapter', 1)
            chapter_title = chapter_node.get('title', f'第{chapter_num}章')
            chapter_desc = chapter_node.get('description', '')
            children = chapter_node.get('children', [])
            
            # 生成 .arc 文件内容
            arc_content = _generate_arc_content(chapter_num, chapter_title, chapter_desc, children)
            
            # 文件名格式：第X章_标题.arc
            # 清理标题中的特殊字符
            safe_title = chapter_title.replace(':', '').replace('：', '').replace('/', '_').replace('\\', '_')
            filename = f"{safe_title}.arc"
            filepath = os.path.join(stories_path, filename)
            
            # 如果文件已存在，添加数字后缀
            counter = 1
            base_filename = filename[:-4]  # 去掉 .arc
            while os.path.exists(filepath):
                filename = f"{base_filename}_{counter}.arc"
                filepath = os.path.join(stories_path, filename)
                counter += 1
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(arc_content)
            
            created_files.append({
                "chapter": chapter_num,
                "title": chapter_title,
                "filename": filename,
                "sceneCount": len(children)
            })
        
        return jsonify({
            "success": True,
            "message": f"成功导出 {len(created_files)} 个章节文件",
            "files": created_files
        })
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


def _generate_arc_content(chapter_num: int, chapter_title: str, chapter_desc: str, scenes: list) -> str:
    """
    生成 .arc 格式的章节内容
    
    格式参考：
    # 场景标题
    @cap 章节名/任务名
    
    (旁白)
    描述文本...
    """
    lines = []
    
    # 添加章节头部注释
    lines.append(f"<!-- 章节 {chapter_num}: {chapter_title} -->")
    lines.append(f"<!-- {chapter_desc} -->")
    lines.append("")
    
    if not scenes:
        # 如果没有场景，创建一个默认场景
        lines.append(f"# {chapter_title}")
        lines.append(f"@cap {chapter_title}")
        lines.append("")
        lines.append("(旁白)")
        lines.append(chapter_desc if chapter_desc else "场景内容待填写...")
        lines.append("")
    else:
        # 为每个场景生成内容
        for i, scene in enumerate(scenes):
            scene_title = scene.get('title', f'场景 {i+1}')
            scene_desc = scene.get('description', '')
            
            lines.append(f"# {scene_title}")
            lines.append(f"@cap {scene_title}")
            lines.append("")
            
            if scene_desc:
                lines.append("(旁白)")
                lines.append(scene_desc)
            else:
                lines.append("(旁白)")
                lines.append("场景内容待填写...")
            
            lines.append("")
            
            # 如果不是最后一个场景，添加分隔
            if i < len(scenes) - 1:
                lines.append("")
    
    return '\n'.join(lines)