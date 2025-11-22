from flask import Blueprint, request, jsonify
from core.auth import require_auth
from .llm_mgr import LLM_Manager

llm_config_bp = Blueprint('llm_config_bp', __name__)
manager = LLM_Manager

@llm_config_bp.route('/api/ai/user-platforms-models', methods=['GET'])
@require_auth
def get_user_platforms_and_models():
    """获取用户所有可用平台及对应的模型列表。"""
    try:
        user_id = str(request.current_user['user_id'])
        data = manager.get_platform_models(user_id)
        return jsonify(data)
    except Exception as e:
        print(f"获取用户平台模型列表失败: {e}")
        return jsonify({"error": str(e)}), 500

@llm_config_bp.route('/api/ai/user-selection', methods=['GET', 'POST'])
@require_auth
def handle_user_selection():
    """获取或更新用户的AI模型选择。"""
    user_id = str(request.current_user['user_id'])
    if request.method == 'GET':
        try:
            usage_key = request.args.get('usage_key')
            selection = manager.get_user_selection_detail(user_id, usage_key=usage_key)
            return jsonify(selection)
        except Exception as e:
            print(f"获取用户选择失败: {e}")
            return jsonify({"error": str(e)}), 500
    
    if request.method == 'POST':
        data = request.json or {}
        platform_id = data.get('platform_id')
        model_id = data.get('model_id')
        usage_key = data.get('usage_key')
        if not all([platform_id, model_id]):
            return jsonify({"error": "缺少 platform_id 或 model_id"}), 400
        try:
            success = manager.save_user_selection(
                user_id,
                int(platform_id),
                int(model_id),
                usage_key=usage_key,
            )
            if success:
                return jsonify({"success": True})
            else:
                return jsonify({"error": "保存失败"}), 400
        except Exception as e:
            print(f"保存用户选择失败: {e}")
            return jsonify({"error": str(e)}), 400

@llm_config_bp.route('/api/ai/user-selection/usage', methods=['POST'])
@require_auth
def create_user_selection_usage():
    """创建一个新的选中模型用途，可绑定任意现有模型。"""
    user_id = str(request.current_user['user_id'])
    data = request.json or {}
    usage_key = data.get('usage_key')
    usage_label = data.get('usage_label')
    platform_id = data.get('platform_id')
    model_id = data.get('model_id')

    if not usage_key:
        return jsonify({"error": "缺少 usage_key"}), 400

    try:
        platform_id_int = int(platform_id) if platform_id is not None else None
    except (TypeError, ValueError):
        return jsonify({"error": "platform_id 必须是整数"}), 400

    try:
        model_id_int = int(model_id) if model_id is not None else None
    except (TypeError, ValueError):
        return jsonify({"error": "model_id 必须是整数"}), 400

    try:
        detail = manager.create_user_usage_slot(
            user_id,
            usage_key,
            usage_label=usage_label,
            platform_id=platform_id_int,
            model_id=model_id_int,
        )
        return jsonify(detail)
    except Exception as e:
        print(f"创建选中模型用途失败: {e}")
        return jsonify({"error": str(e)}), 400

@llm_config_bp.route('/api/ai/platform-config', methods=['POST'])
@require_auth
def update_platform_config():
    """更新用户平台的配置，如 API Key。"""
    user_id = str(request.current_user['user_id'])
    data = request.json
    platform_id = data.get('platform_id')
    api_key = data.get('api_key')
    
    if platform_id is None:
        return jsonify({"error": "缺少 platform_id"}), 400
    
    try:
        success = manager.update_platform_config(user_id, int(platform_id), api_key)
        if success:
            return jsonify({"success": True})
        else:
            return jsonify({"success": True, "message": "No changes applied"})
    except Exception as e:
        print(f"更新平台配置失败: {e}")
        return jsonify({"error": str(e)}), 400
