from flask import Blueprint, request, Response, jsonify
from auth import require_auth
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage
import os
from utils import get_project_path, get_project_stories_path, get_project_worldview_path, get_project_characters_path, ensure_project_characters_directory
import json
from llm_mgr import AIManager
from request_context import get_current_info, current_user_id, current_project_name, set_agent_context
from agent_lorebook import get_all_characters, get_character_info

ai_bp = Blueprint('ai_bp', __name__)

# 统一的 LLM 管理器（支持用户级 API Key 与平台/模型配置）
manager = AIManager()

def _extract_json_array(text: str) -> str:
    """从可能包含 Markdown 代码块的文本中提取 JSON 数组字符串。"""
    if not text:
        return "[]"
    s = text.strip()
    # 去除```包裹
    if s.startswith("```"):
        # 形如 ```json\n...\n```
        first = s.find("\n")
        if first != -1:
            s = s[first+1:]
        if s.endswith("```"):
            s = s[:-3]
        s = s.strip()
    # 裁剪到第一个 '[' 与最后一个 ']'
    l = s.find('[')
    r = s.rfind(']')
    if l != -1 and r != -1 and r > l:
        return s[l:r+1]
    return s

@ai_bp.route('/api/ai/single-node', methods=['POST'])
@require_auth
@get_current_info
def single_node_writing():
    """单节点续写 - 流式响应"""
    data = request.get_json(silent=True) or {}
    project_name = current_project_name.get() or data.get('projectName')
    context = data.get('context') or ''
    length = data.get('length', 100)
    # 注意：前端需要传递当前节点相关的角色ID，这里暂时假设为 all
    character_ids = data.get('character_ids', [])
    user_id = current_user_id.get() or request.current_user['user_id']

    if not project_name:
        return Response("缺少项目名称", status=400)

    def generate():
        try:
            project_path = get_project_path(user_id, project_name)
            
            # 读取世界观
            worldview = ""
            worldview_path = os.path.join(project_path, '世界观.txt')
            if os.path.exists(worldview_path):
                with open(worldview_path, 'r', encoding='utf-8') as f:
                    worldview = f.read()

            # 读取和筛选角色设定
            roles = ""
            roles_path = os.path.join(project_path, '角色设定.txt')
            if os.path.exists(roles_path) and character_ids:
                try:
                    with open(roles_path, 'r', encoding='utf-8') as f:
                        all_roles = json.load(f)
                        # 确保 all_roles 是一个列表
                        if isinstance(all_roles, list):
                            # 根据 character_ids 筛选
                            selected_roles = [role for role in all_roles if str(role.get('id')) in map(str, character_ids)]
                            if selected_roles:
                                roles = "\n".join([f"- {r.get('name', '')}: {r.get('settings', '')}" for r in selected_roles])
                except (json.JSONDecodeError, TypeError) as e:
                    print(f"无法解析角色设定文件: {e}")
                    # 作为后备，读取纯文本
                    with open(roles_path, 'r', encoding='utf-8') as f:
                        roles = f.read()

            # 构建 Prompt
            prompt = f"""我的世界观是：
"{worldview}"

你可能需要用到的角色设定：
"{roles}"

我当前的上下文是：
"{context}"

请根据以上信息，续写一句纯文本内容，续写长度约为 {length} 字。"""

            messages = [
                SystemMessage(content="你是一个专业的剧本创作助手。你只输出纯文本的对话内容。"),
                HumanMessage(content=prompt)
            ]

            chat = manager.get_user_llm(user_id, streaming=True, temperature=0.7)
            for chunk in chat.stream(messages):
                yield chunk.content
        except Exception as e:
            print(f"AI单节点续写流生成失败: {e}")
            yield " [续写失败] "

    return Response(generate(), mimetype='text/plain')

@ai_bp.route('/api/ai/multi-node', methods=['POST'])
@require_auth
@get_current_info
def multi_node_writing():
    """多段续写"""
    data = request.json
    project_name = current_project_name.get() or data.get('projectName')
    context = data.get('context', '')
    guidance = data.get('guidance', '')
    character_ids = data.get('character_ids', [])
    segment_count = data.get('segment_count', 3)
    current_file = data.get('current_file')
    scene_name = data.get('scene_name')
    after_node_id = data.get('after_node_id')
    user_id = current_user_id.get() or request.current_user['user_id']

    if not all([project_name, context, current_file, scene_name, after_node_id is not None]):
        return jsonify({"error": "缺少必要的参数"}), 400

    try:
        # ... (省略AI调用前的准备代码，与之前相同) ...
        project_path = get_project_path(user_id, project_name)
        worldview = ""
        worldview_path = os.path.join(project_path, '世界观.txt')
        if os.path.exists(worldview_path):
            with open(worldview_path, 'r', encoding='utf-8') as f:
                worldview = f.read()
        roles = ""
        roles_path = os.path.join(project_path, '角色设定.txt')
        if os.path.exists(roles_path) and character_ids:
            try:
                with open(roles_path, 'r', encoding='utf-8') as f:
                    all_roles = json.load(f)
                    if isinstance(all_roles, list):
                        selected_roles = [role for role in all_roles if str(role.get('id')) in map(str, character_ids)]
                        if selected_roles:
                            roles = "\n".join([f"- {r.get('name', '')}: {r.get('settings', '')}" for r in selected_roles])
            except (json.JSONDecodeError, TypeError) as e:
                print(f"无法解析角色设定文件: {e}")
                with open(roles_path, 'r', encoding='utf-8') as f:
                    roles = f.read()
        example_format = ""
        example_path = os.path.join(os.path.dirname(__file__), '剧本示例.story')
        if os.path.exists(example_path):
            with open(example_path, 'r', encoding='utf-8') as f:
                example_format = f.read()
        system_prompt = f"""你是一个专业的剧本创作助手。你只能续写 "基础的对话节点"。你必须严格遵守用户提供的 "剧本示例.txt" 文件中的格式规范生成剧情脚本，并只返回一个JSON数组，不要包含任何其他解释性文字或markdown标记。
        
剧本示例格式:
```json
{example_format}
```
"""
        user_prompt = f"""我的世界观是：
"{worldview}"
你可能需要用到的角色设定：
"{roles}"
我当前的上下文是：
"{context}"
请根据以上信息，以及以下发展指导：
"{guidance}"
严格按照 "剧本示例格式" 续写一段连续的剧情脚本。特别注意：这段续写必须包含 {segment_count} 段连续的 "基础对话节点"。"""
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]
        
        # 非流式调用
        non_streaming_chat = manager.get_user_llm(user_id, streaming=False, temperature=0.7)
        completion = non_streaming_chat.invoke(messages)
        generated_text = completion.content
        
        # 清理并解析AI返回的JSON
        json_str = _extract_json_array(generated_text)
        new_nodes = json.loads(json_str)

        # --- 文件插入逻辑 ---
        stories_path = get_project_stories_path(user_id, project_name)
        file_path = os.path.join(stories_path, current_file)
        if not file_path.endswith('.story'):
            file_path += '.story'

        if not os.path.exists(file_path):
            return jsonify({"error": "目标文件不存在"}), 404

        with open(file_path, 'r+', encoding='utf-8') as f:
            story_data = json.load(f)
            
            # 找到目标场景
            target_scene = next((s for s in story_data if s.get('scene') == scene_name), None)
            if not target_scene:
                return jsonify({"error": f"场景 '{scene_name}' 未找到"}), 404

            # 找到要插入位置的节点索引
            # 注意：这里假设节点ID在场景内是唯一的
            target_index = -1
            for i, dia in enumerate(target_scene.get('dia', [])):
                if dia.get('id') == after_node_id:
                    target_index = i
                    break
            
            if target_index == -1:
                return jsonify({"error": f"节点ID '{after_node_id}' 在场景中未找到"}), 404

            # 插入新节点
            for node in reversed(new_nodes):
                target_scene['dia'].insert(target_index + 1, node)

            # 写回文件
            f.seek(0)
            f.truncate()
            json.dump(story_data, f, ensure_ascii=False, indent=2)

        return jsonify({"success": True, "message": "续写成功并已插入剧本"})

    except json.JSONDecodeError:
        return jsonify({"error": "AI返回的内容无法解析为JSON，请重试"}), 500
    except Exception as e:
        print(f"AI多段续写失败: {e}")
        return jsonify({"error": f"AI生成或文件操作失败: {str(e)}"}), 500


@ai_bp.route('/api/ai/configs', methods=['GET'])
@require_auth
def get_ai_configs():
    """返回可用平台/模型与用户当前选择和密钥存在性。"""
    try:
        user_id = str(request.current_user['user_id'])
        configs = manager.get_available_models()
        user_cfg = manager.get_config(user_id)
        # 首次访问时若无配置，保存默认配置，保证前端切换后能持久化
        if not user_cfg:
            try:
                from llm_mgr import default_platform as _def_pf, default_model as _def_md
                manager.save_config(user_id, _def_pf, _def_md)
                user_cfg = manager.get_config(user_id)
            except Exception:
                user_cfg = None
        result = {
            "platforms": {k: {"models": list(v.get("models", {}).keys())} for k, v in configs.items()},
            "user": {
                "selected_platform": getattr(user_cfg, 'selected_platform', None),
                "selected_model": getattr(user_cfg, 'selected_model', None),
            }
        }
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": f"获取配置失败: {e}"}), 500


@ai_bp.route('/api/ai/config', methods=['POST'])
@require_auth
def set_ai_config():
    data = request.json or {}
    platform = data.get('platform')
    model = data.get('model')
    if not platform or not model:
        return jsonify({"error": "缺少 platform 或 model"}), 400
    try:
        user_id = str(request.current_user['user_id'])
        manager.save_config(user_id, platform, model)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@ai_bp.route('/api/ai/apikey', methods=['POST'])
@require_auth
def set_ai_api_key():
    data = request.json or {}
    platform = data.get('platform')
    api_key = data.get('apiKey')
    if not platform or not api_key:
        return jsonify({"error": "缺少 platform 或 apiKey"}), 400
    try:
        user_id = str(request.current_user['user_id'])
        manager.set_api_key(user_id, platform, api_key)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@ai_bp.route('/api/ai/agent-chat', methods=['POST'])
@require_auth
@get_current_info
def agent_chat():
    """
    一个通用的 Agent 调用入口点。
    它会从请求中提取用户和项目信息，设置上下文，
    然后可以执行任何需要这些上下文的 Agent 任务。
    """
    data = request.json or {}
    project_name = current_project_name.get() or data.get('projectName')
    user_query = data.get('query') # 用户发来的问题或指令

    if not project_name or not user_query:
        return jsonify({"error": "缺少 projectName 或 query"}), 400

    user_id = current_user_id.get() or str(request.current_user['user_id'])

    # --- 关键步骤：设置 Agent 工具的上下文 ---
    set_agent_context(str(user_id), str(project_name))

    # --- 在这里，您可以构建并运行您的 LangChain Agent ---
    # 下面是一个模拟，直接调用工具函数来验证上下文是否有效
    try:
        # 模拟 Agent 使用工具
        all_chars = get_all_characters()
        
        # 假设我们想获取第一个角色的信息
        first_char_info = ""
        if all_chars and "错误" not in all_chars[0]:
            first_char_info = get_character_info(all_chars[0])

        # 在实际应用中，这里会是 agent.run(user_query) 的结果
        response_data = {
            "message": "Agent 上下文设置成功，工具调用结果如下",
            "user_query": user_query,
            "tool_results": {
                "all_characters": all_chars,
                "first_character_info": first_char_info
            }
        }
        return jsonify(response_data)

    except Exception as e:
        print(f"Agent 执行出错: {e}")
        return jsonify({"error": f"Agent 执行失败: {e}"}), 500

## 生成角色接口已迁移至 agent_lorebook.py