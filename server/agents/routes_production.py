from flask import Blueprint, request, Response, jsonify
from core.auth import require_auth
from langchain_core.messages import HumanMessage, SystemMessage
import os
import json
from core.utils import (
    get_project_path,
    get_project_stories_path,
    strip_private_fields,
)
from llm.llm_mgr import LLM_Manager
from core.request_context import get_current_info, current_user_id, current_project_name, set_agent_context
from .agent_lorebook import get_all_characters, get_character_info
from .showrunner import ShowrunnerAgent
from .scriptwriter import ScriptwriterAgent
from .state_keeper import StateKeeper
from .critic import CriticAgent
from .gatekeeper import GatekeeperAgent
from .mirror import MirrorAgent
from .bridge import BridgeAgent

# Renamed blueprint to reflect its new role
production_bp = Blueprint('production_bp', __name__)

manager = LLM_Manager

def _extract_json_array(text: str) -> str:
    """从可能包含 Markdown 代码块的文本中提取 JSON 数组字符串。"""
    if not text:
        return "[]"
    s = text.strip()
    if s.startswith("```"):
        first = s.find("\n")
        if first != -1:
            s = s[first+1:]
        if s.endswith("```"):
            s = s[:-3]
        s = s.strip()
    l = s.find('[')
    r = s.rfind(']')
    if l != -1 and r != -1 and r > l:
        return s[l:r+1]
    return s

@production_bp.route('/api/ai/single-node', methods=['POST'])
@require_auth
@get_current_info
def single_node_writing():
    """单节点续写 - 流式响应 (Legacy/Quick Mode)"""
    data = request.get_json(silent=True) or {}
    project_name = current_project_name.get() or data.get('projectName')
    context = data.get('context') or ''
    length = data.get('length', 100)
    character_ids = data.get('character_ids', [])
    user_id = current_user_id.get() or request.current_user['user_id']

    if not project_name:
        return Response("缺少项目名称", status=400)

    def generate():
        try:
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

            chat = manager.get_user_llm(user_id)
            for chunk in chat.stream(messages):
                yield chunk.content
        except Exception as e:
            print(f"AI单节点续写流生成失败: {e}")
            yield " [续写失败] "

    return Response(generate(), mimetype='text/plain')

@production_bp.route('/api/ai/multi-node', methods=['POST'])
@require_auth
@get_current_info
def multi_node_writing():
    """
    多段续写 (Production Pipeline Entry Point)
    Executes: Showrunner -> Scriptwriter -> Critic -> StateKeeper
    """
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
    
    # Optional: Handle rewrite instruction from feedback loop
    is_rewrite = data.get('is_rewrite', False)

    if not all([project_name, context, current_file, scene_name, after_node_id is not None]):
        return jsonify({"error": "缺少必要的参数"}), 400

    try:
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

        # --- Agent Pipeline Execution ---
        
        # 0. State Keeper: Get Context & Constraints
        state_keeper = StateKeeper(user_id, project_name)
        pov_constraints = state_keeper.get_pov_constraints()
        world_state = state_keeper.get_world_state_context()
        
        # Combine context
        full_context_prompt = f"{context}\n\n{world_state}"
        full_guidance = f"{guidance}\n\n{pov_constraints}"

        # 1. Showrunner: Plan the scene
        showrunner = ShowrunnerAgent(user_id)
        beat_sheet = showrunner.plan_scene(full_context_prompt, worldview, roles, full_guidance)
        print(f"[Agent Pipeline] Beat Sheet generated: {beat_sheet.get('summary', 'No summary')}")

        # 2. Scriptwriter & Critic Loop (Max 2 retries)
        scriptwriter = ScriptwriterAgent(user_id)
        critic = CriticAgent(user_id)
        
        max_retries = 2
        current_try = 0
        final_nodes = []
        
        feedback_history = ""

        while current_try <= max_retries:
            print(f"[Agent Pipeline] Writing Draft {current_try + 1}...")
            
            current_guidance = full_guidance
            if feedback_history:
                current_guidance += f"\n\n[CRITICAL FEEDBACK FROM EDITOR]: {feedback_history}"

            new_nodes, thought_process = scriptwriter.write_script(
                full_context_prompt, 
                worldview, 
                roles, 
                beat_sheet, 
                segment_count,
                feedback=feedback_history
            )
            
            if not new_nodes:
                print("[Agent Pipeline] Scriptwriter failed to generate nodes.")
                break

            # 3. Critic: Evaluate
            score, status, feedback = critic.evaluate(new_nodes, full_context_prompt, beat_sheet)
            print(f"[Agent Pipeline] Critic Score: {score} ({status})")
            
            if status == "APPROVE" or score >= 80:
                final_nodes = new_nodes
                print("[Agent Pipeline] Draft Approved!")
                break
            else:
                print(f"[Agent Pipeline] Draft Rejected. Feedback: {feedback}")
                feedback_history = feedback
                current_try += 1
        
        if not final_nodes and new_nodes:
            print("[Agent Pipeline] Max retries reached. Using last draft.")
            final_nodes = new_nodes

        # 4. State Keeper: Update State (Async-like)
        if final_nodes:
            print("[Agent Pipeline] Updating World State...")
            state_keeper.analyze_and_update(final_nodes)

        # --- 数据清理 ---
        allowed_fields = {'id', 'chr', 'txt', 'opt', 'optn', 'dia', 'act', 'next'}
        def clean_node(node):
            if isinstance(node, dict):
                strip_private_fields(node)
                for key in list(node.keys()):
                    if key not in allowed_fields:
                        del node[key]
                if 'dia' in node:
                    clean_nodes_list(node['dia'])
                if 'opt' in node:
                    clean_nodes_list(node['opt'])
            return node
        
        def clean_nodes_list(nodes):
            if isinstance(nodes, list):
                for i in range(len(nodes)):
                    nodes[i] = clean_node(nodes[i])

        strip_private_fields(final_nodes)
        clean_nodes_list(final_nodes)
        
        # --- 文件插入逻辑 ---
        stories_path = get_project_stories_path(user_id, project_name)
        file_path = os.path.join(stories_path, current_file)
        if not file_path.endswith('.story'):
            file_path += '.story'

        if not os.path.exists(file_path):
            return jsonify({"error": "目标文件不存在"}), 404

        with open(file_path, 'r+', encoding='utf-8') as f:
            story_data = json.load(f)
            strip_private_fields(story_data)
            
            target_scene = next((s for s in story_data if s.get('scene') == scene_name), None)
            if not target_scene:
                return jsonify({"error": f"场景 '{scene_name}' 未找到"}), 404

            target_index = -1
            for i, dia in enumerate(target_scene.get('dia', [])):
                if dia.get('id') == after_node_id:
                    target_index = i
                    break
            
            if target_index == -1:
                return jsonify({"error": f"节点ID '{after_node_id}' 在场景中未找到"}), 404

            for node in reversed(final_nodes):
                target_scene['dia'].insert(target_index + 1, node)

            f.seek(0)
            f.truncate()
            strip_private_fields(story_data)
            json.dump(story_data, f, ensure_ascii=False, indent=2)

        return jsonify({"success": True, "message": "续写成功并已插入剧本"})

    except json.JSONDecodeError:
        return jsonify({"error": "AI返回的内容无法解析为JSON，请重试"}), 500
    except Exception as e:
        print(f"AI多段续写失败: {e}")
        return jsonify({"error": f"AI生成或文件操作失败: {str(e)}"}), 500

@production_bp.route('/api/ai/feedback-loop', methods=['POST'])
@require_auth
@get_current_info
def feedback_loop():
    """
    Handles the Feedback Loop: Gatekeeper -> Mirror -> (Rewrite or Next).
    """
    data = request.json or {}
    user_input = data.get('user_input', '')
    project_name = current_project_name.get()
    user_id = current_user_id.get()
    
    context = data.get('context', '')
    last_generated_content = data.get('last_content', '')
    
    if not user_input:
        return jsonify({"action": "NONE"})

    # 1. Gatekeeper: Decide Intent
    gatekeeper = GatekeeperAgent(user_id)
    intent = gatekeeper.route_request(user_input)
    print(f"[Feedback Loop] User Intent: {intent}")

    if intent == "NEXT":
        return jsonify({"action": "NEXT_PHASE", "message": "Proceeding to next scene."})

    elif intent == "MODIFY":
        # 2. Mirror: Analyze Feedback
        mirror = MirrorAgent(user_id, project_name)
        analysis = mirror.analyze_feedback(last_generated_content, user_input)
        
        instruction = analysis.get("rewrite_instruction", user_input)
        print(f"[Feedback Loop] Rewrite Instruction: {instruction}")
        
        return jsonify({
            "action": "REWRITE", 
            "instruction": instruction,
            "analysis": analysis
        })

    return jsonify({"action": "NONE"})

@production_bp.route('/api/ai/agent-chat', methods=['POST'])
@require_auth
@get_current_info
def agent_chat():
    """
    Generic Agent Chat Endpoint.
    """
    data = request.json or {}
    project_name = current_project_name.get() or data.get('projectName')
    user_query = data.get('query')

    if not project_name or not user_query:
        return jsonify({"error": "缺少 projectName 或 query"}), 400

    user_id = current_user_id.get() or str(request.current_user['user_id'])
    set_agent_context(str(user_id), str(project_name))

    try:
        all_chars = get_all_characters()
        first_char_info = ""
        if all_chars and "错误" not in all_chars[0]:
            first_char_info = get_character_info(all_chars[0])

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
