from flask import Blueprint, request, Response, jsonify
from auth import require_auth
from openai import OpenAI
import os
from utils import get_project_path, get_project_stories_path
import json

ai_bp = Blueprint('ai_bp', __name__)

MODEL = "qwen-plus"

client = OpenAI(
    api_key="sk-c1cf2eb1c1a846e3b3f729ff656cc5a2",
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
)

@ai_bp.route('/api/ai/single-node', methods=['POST'])
@require_auth
def single_node_writing():
    """单节点续写 - 流式响应"""
    data = request.json
    project_name = data.get('projectName')
    context = data.get('context', '')
    length = data.get('length', 100)
    # 注意：前端需要传递当前节点相关的角色ID，这里暂时假设为 all
    character_ids = data.get('character_ids', [])
    user_id = request.current_user['user_id']

    if not project_name or not context:
        return Response("项目名称或上下文不能为空", status=400)

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
            if os.path.exists(roles_path):
                with open(roles_path, 'r', encoding='utf-8') as f:
                    # 这里简化处理，实际应根据 character_ids 筛选
                    roles = f.read()

            # 构建 Prompt
            prompt = f"""我的世界观是：
"{worldview}"

你可能需要用到的角色设定：
"{roles}"

我当前的上下文是：
"{context}"

请根据以上信息，续写一段纯文本对话内容，续写长度约为 {length} 字。"""

            messages = [
                {"role": "system", "content": "你是一个专业的剧本创作助手。你只输出纯文本的对话内容。"},
                {"role": "user", "content": prompt}
            ]

            completion = client.chat.completions.create(
                model=MODEL,
                messages=messages,
                stream=True
            )

            for chunk in completion:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            print(f"AI单节点续写流生成失败: {e}")
            yield " [续写失败] "

    return Response(generate(), mimetype='text/plain')

@ai_bp.route('/api/ai/multi-node', methods=['POST'])
@require_auth
def multi_node_writing():
    """多段续写"""
    data = request.json
    project_name = data.get('projectName')
    context = data.get('context', '')
    guidance = data.get('guidance', '')
    character_ids = data.get('character_ids', [])
    segment_count = data.get('segment_count', 3)
    current_file = data.get('current_file')
    scene_name = data.get('scene_name')
    after_node_id = data.get('after_node_id')
    user_id = request.current_user['user_id']

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
        if os.path.exists(roles_path):
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
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        completion = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            stream=False
        )
        generated_text = completion.choices[0].message.content
        
        # 清理并解析AI返回的JSON
        json_str = generated_text
        if "```json" in json_str:
            json_str = json_str.split("```json")[1].split("```")[0]
        
        json_str = json_str.strip()
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