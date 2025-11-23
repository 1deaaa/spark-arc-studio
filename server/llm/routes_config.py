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

@llm_config_bp.route('/api/ai/platform', methods=['POST', 'DELETE', 'PUT'])
@require_auth
def manage_platform():
    """管理平台：添加、删除、重命名"""
    user_id = str(request.current_user['user_id'])
    
    if request.method == 'POST':
        # 添加平台
        data = request.json or {}
        name = data.get('name')
        base_url = data.get('base_url')
        api_key = data.get('api_key')
        
        if not name or not base_url:
            return jsonify({"error": "name 和 base_url 必填"}), 400
            
        try:
            plat = manager.add_platform(name, base_url, api_key, user_id)
            return jsonify({"success": True, "id": plat.id})
        except Exception as e:
            return jsonify({"error": str(e)}), 400
            
    elif request.method == 'DELETE':
        # 删除平台
        platform_id = request.args.get('id')
        if not platform_id:
            return jsonify({"error": "缺少 id 参数"}), 400
            
        try:
            manager.delete_platform(user_id, int(platform_id))
            return jsonify({"success": True})
        except Exception as e:
            return jsonify({"error": str(e)}), 400
            
    elif request.method == 'PUT':
        # 更新平台信息（重命名 + 修改 URL）
        data = request.json or {}
        platform_id = data.get('id')
        new_name = data.get('name')
        new_base_url = data.get('base_url')
        
        if not platform_id or not new_name:
            return jsonify({"error": "id 和 name 必填"}), 400
            
        try:
            # 如果提供了 base_url，则调用 update_platform_details
            if new_base_url:
                manager.update_platform_details(user_id, int(platform_id), new_name, new_base_url)
            else:
                # 兼容旧的重命名逻辑（虽然前端也会更新，但保持健壮性）
                # 注意：llm_mgr.py 中我们替换了 rename_platform 为 update_platform_details
                # 如果没有 base_url，我们需要先获取当前的 base_url 或者报错
                # 为了简单起见，前端应该总是发送 base_url。
                # 但如果必须兼容，我们可以让 update_platform_details 处理 base_url=None 的情况？
                # 不，刚才的修改强制要求 base_url。
                # 所以这里如果没传 base_url，我们应该报错，或者假设前端会传。
                # 鉴于这是内部 API，我们要求前端必须传 base_url。
                return jsonify({"error": "base_url 必填"}), 400
                
            return jsonify({"success": True})
        except Exception as e:
            return jsonify({"error": str(e)}), 400

@llm_config_bp.route('/api/ai/model', methods=['POST', 'DELETE', 'PUT'])
@require_auth
def manage_model():
    """管理模型：添加、删除、更新"""
    user_id = str(request.current_user['user_id'])
    
    if request.method == 'POST':
        # 添加模型
        data = request.json or {}
        platform_id = data.get('platform_id')
        model_name = data.get('model_name')
        display_name = data.get('display_name')
        extra_body = data.get('extra_body')
        
        if not all([platform_id, model_name, display_name]):
            return jsonify({"error": "platform_id, model_name, display_name 必填"}), 400
            
        try:
            model = manager.add_model(int(platform_id), model_name, display_name, user_id, extra_body)
            return jsonify({"success": True, "id": model.id})
        except Exception as e:
            return jsonify({"error": str(e)}), 400
            
    elif request.method == 'DELETE':
        # 删除模型
        model_id = request.args.get('id')
        if not model_id:
            return jsonify({"error": "缺少 id 参数"}), 400
            
        try:
            manager.delete_model(user_id, int(model_id))
            return jsonify({"success": True})
        except Exception as e:
            return jsonify({"error": str(e)}), 400
            
    elif request.method == 'PUT':
        # 更新模型
        data = request.json or {}
        model_id = data.get('id')
        display_name = data.get('display_name')
        extra_body = data.get('extra_body')
        
        if not model_id:
            return jsonify({"error": "id 必填"}), 400
            
        try:
            manager.update_model(user_id, int(model_id), display_name, extra_body)
            return jsonify({"success": True})
        except Exception as e:
            return jsonify({"error": str(e)}), 400

