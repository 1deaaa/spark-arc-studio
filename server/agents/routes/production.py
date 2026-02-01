"""
Production API - 剧本生成（单段/多段续写）

注意：为保持前端兼容性，保留旧版 /api/ai/single-node 和 /api/ai/multi-node 端点
"""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse, JSONResponse
from starlette.concurrency import run_in_threadpool
from sse_starlette.sse import EventSourceResponse
from typing import List, Dict, Any
import os
import json

from core.auth import get_current_user
from core.request_context import current_project_name, set_agent_context
from core.utils import (
    get_project_path, get_project_stories_path, strip_private_fields,
    ensure_project_characters_directory,
)

from agents import ScriptwriterAgent, CriticAgent, run_story_generation_workflow
from agents.agent_lorebook import get_all_characters, get_character_info
from agents.agent_style.utils import load_style_profile_from_file
from llm.llm_mgr import LLM_Manager

from .schemas import (
    SingleNodeRequest, MultiNodeRequest, FeedbackRequest, CriticReviewRequest,
    _load_worldview_and_roles, _load_worldview_and_characters,
)

production_router = APIRouter()
manager = LLM_Manager


# ==================== 旧版端点（前端兼容） ====================

@production_router.post('/api/ai/single-node')
async def single_node_writing(
    data: SingleNodeRequest,
    request: Request,
    user: dict = Depends(get_current_user)
):
    """单节点续写 - 流式响应（旧版端点，保持前端兼容）"""
    project_name = current_project_name.get() or data.projectName
    context = data.context
    length = data.length
    character_ids = data.character_ids
    user_id = str(user['user_id'])

    if not project_name:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="缺少项目名称")

    async def generate():
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
                except (json.JSONDecodeError, TypeError):
                    with open(roles_path, 'r', encoding='utf-8') as f:
                        roles = f.read()

            prompt = f"""我的世界观是：
"{worldview}"

你可能需要用到的角色设定：
"{roles}"

我当前的上下文是：
"{context}"

请根据以上信息，续写一句纯文本内容，续写长度约为 {length} 字。"""

            from langchain_core.messages import SystemMessage, HumanMessage
            messages = [
                SystemMessage(content="你是一个专业的剧本创作助手。你只输出纯文本的对话内容。"),
                HumanMessage(content=prompt)
            ]

            chat = manager.get_user_llm(user_id, agent_name="agent_scriptwriter")
            for chunk in chat.stream(messages):
                yield chunk.content
        except Exception as e:
            print(f"AI单节点续写流生成失败: {e}")
            raise

    return StreamingResponse(generate(), media_type='text/plain')


@production_router.post('/api/ai/multi-node')
async def multi_node_writing(
    data: MultiNodeRequest,
    user: dict = Depends(get_current_user)
):
    """多段续写 (Production Pipeline) - 旧版端点，保持前端兼容"""
    from story.arc_parser import parse_arc, serialize_to_arc
    
    project_name = current_project_name.get() or data.projectName
    context = data.context
    guidance = data.guidance
    character_ids = data.character_ids
    segment_count = data.segment_count
    current_file = data.current_file
    scene_name = data.scene_name
    after_node_id = data.after_node_id
    confirm_continue = data.confirm_continue
    user_id = str(user['user_id'])

    if not all([project_name, current_file, scene_name, after_node_id is not None]):
        return JSONResponse(status_code=400, content={"error": "缺少必要的参数"})

    try:
        project_path = get_project_path(user_id, project_name)
        worldview = ""
        worldview_path = os.path.join(project_path, '世界观.txt')
        if os.path.exists(worldview_path):
            with open(worldview_path, 'r', encoding='utf-8') as f:
                worldview = f.read()
        
        roles = ""
        chr_map = {}
        if character_ids:
            try:
                characters_path = ensure_project_characters_directory(user_id, project_name)
                bind_file = os.path.join(characters_path, 'chr.bind')
                
                if os.path.exists(bind_file):
                    with open(bind_file, 'r', encoding='utf-8') as f:
                        full_char_map = json.load(f)
                    
                    selected_roles_content = []
                    for cid in character_ids:
                        cid_str = str(cid)
                        if cid_str in full_char_map:
                            name = full_char_map[cid_str]
                            if int(cid) == -1:
                                name = "旁白"
                            chr_map[int(cid)] = name
                            char_file = os.path.join(characters_path, f"{cid}.txt")
                            if os.path.exists(char_file):
                                with open(char_file, 'r', encoding='utf-8') as cf:
                                    content = cf.read().strip()
                                    selected_roles_content.append(f"--- 角色: {name} (ID: {cid}) ---\n{content}")
                            else:
                                selected_roles_content.append(f"--- 角色: {name} (ID: {cid}) ---\n(暂无详细设定)")
                    
                    if selected_roles_content:
                        roles = "\n\n".join(selected_roles_content)
            except Exception as e:
                print(f"获取角色设定失败: {e}")

        missing_info = []
        if not worldview.strip():
            missing_info.append("世界观")
        if not roles.strip() and character_ids:
            missing_info.append("角色设定")
            
        if missing_info and not confirm_continue:
            return JSONResponse(
                status_code=409,
                content={
                    "error": "MISSING_INFO",
                    "message": f"检测到缺少以下信息：{', '.join(missing_info)}。这可能会影响生成质量。是否继续？",
                    "missing": missing_info
                }
            )

        author_id = f"{user_id}_{project_name}"
        style_profile = load_style_profile_from_file(author_id, user_id=user_id)

        # 以目标场景作为“权威上下文”，确保包含 scene/intro/thought/分支等完整信息。
        stories_path = get_project_stories_path(user_id, project_name)
        if not current_file.endswith('.arc'):
            current_file += '.arc'
        file_path = os.path.join(stories_path, current_file)
        if not os.path.exists(file_path):
            return JSONResponse(status_code=404, content={"error": f"目标文件不存在: {current_file}"})

        with open(file_path, 'r', encoding='utf-8') as f:
            arc_content = f.read()
        story_data = parse_arc(arc_content)
        strip_private_fields(story_data)
        target_scene = next((s for s in story_data if s.get('scene') == scene_name), None)
        if not target_scene:
            return JSONResponse(status_code=404, content={"error": f"场景 '{scene_name}' 未找到"})

        canonical_context = serialize_to_arc([target_scene]).strip()
        if context and str(context).strip() and str(context).strip() not in canonical_context:
            canonical_context = canonical_context + "\n\n" + "# 用户补充上下文\n" + str(context).strip()

        final_nodes, thought = await run_in_threadpool(
            run_story_generation_workflow,
            user_id=user_id,
            project_name=project_name,
            context=canonical_context,
            guidance=guidance,
            worldview=worldview,
            roles=roles,
            style_profile=style_profile,
            segment_count=segment_count,
            chr_map=chr_map,
            last_node_text=data.last_node_text
        )
        
        if not final_nodes:
            return JSONResponse(status_code=500, content={"error": "AI生成失败，未返回有效内容"})

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
        
        # 复用上面解析到的 story_data/target_scene/file_path

        def find_and_insert(nodes):
            if after_node_id == 0:
                for j, new_node in enumerate(final_nodes):
                    nodes.insert(j, new_node)
                return True
                
            for i, dia in enumerate(nodes):
                if dia.get('id') == after_node_id:
                    for j, new_node in enumerate(final_nodes):
                        nodes.insert(i + 1 + j, new_node)
                    return True
                if 'opt' in dia:
                    for opt in dia['opt']:
                        if 'dia' in opt:
                            if find_and_insert(opt['dia']):
                                return True
            return False

        # 如果是重写模式，清空场景对话
        if data.rewrite:
            target_scene['dia'] = []
            # 重写模式下直接插入新节点
            target_scene['dia'] = final_nodes
        else:
            if not find_and_insert(target_scene.get('dia', [])):
                return JSONResponse(status_code=404, content={"error": f"节点ID '{after_node_id}' 在场景中未找到"})


        if thought and not target_scene.get('thought'):
            target_scene['thought'] = thought

        new_arc_content = serialize_to_arc(story_data)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_arc_content)

        return {"success": True, "message": "续写成功并已插入剧本", "thought": thought}

    except Exception as e:
        print(f"AI多段续写失败: {e}")
        return JSONResponse(status_code=500, content={"error": f"AI生成或文件操作失败: {str(e)}"})


@production_router.post('/api/ai/critic')
async def run_critic_review(
    data: CriticReviewRequest,
    user: dict = Depends(get_current_user)
):
    """手动触发 Critic 评审（不参与自动工作流）"""
    project_name = current_project_name.get() or data.projectName
    if not project_name:
        return JSONResponse(status_code=400, content={"error": "缺少项目名称"})

    user_id = str(user['user_id'])
    info = _load_worldview_and_roles(user_id, project_name)
    author_id = f"{user_id}_{project_name}"
    style_profile = load_style_profile_from_file(author_id, user_id=user_id)

    critic = CriticAgent(user_id)
    score, status, feedback = await run_in_threadpool(
        critic.evaluate,
        script_nodes=data.script_nodes,
        context=data.context or "",
        guidance=data.guidance or "",
        worldview=info.get('worldview', ''),
        roles=info.get('roles', ''),
        style_profile=style_profile,
    )

    return {
        "success": True,
        "score": score,
        "status": status,
        "feedback": feedback,
    }


# ==================== 新版端点（SSE流式） ====================

@production_router.post('/api/production/single-generate/stream')
async def single_generate_stream(data: SingleNodeRequest, user: dict = Depends(get_current_user)):
    """单段续写（流式输出）- 新版 SSE 端点"""
    user_id = str(user['user_id'])
    project_name = current_project_name.get() or data.projectName
    if not project_name:
        return JSONResponse(status_code=400, content={'error': '缺少项目名称'})

    set_agent_context(user_id, project_name)
    
    wv = _load_worldview_and_roles(user_id, project_name)
    worldview = wv.get('worldview', '')
    roles = wv.get('roles', '')
    
    characters_text = ""
    if data.character_ids:
        char_infos = []
        for cid in data.character_ids:
            info = get_character_info(user_id, project_name, cid)
            if info:
                char_infos.append(f"- {info.get('name', '')}: {info.get('desc', '')}")
        if char_infos:
            characters_text = "\n".join(char_infos)

    agent = ScriptwriterAgent(user_id=user_id)

    async def generate():
        try:
            for chunk in agent.stream_single_node(
                context=data.context,
                worldview=worldview,
                roles=roles,
                characters=characters_text,
                length=data.length,
            ):
                yield {"event": "chunk", "data": json.dumps({"text": chunk}, ensure_ascii=False)}
            yield {"event": "done", "data": "{}"}
        except Exception as e:
            yield {"event": "error", "data": json.dumps({"error": str(e)}, ensure_ascii=False)}

    return EventSourceResponse(generate())


@production_router.post('/api/production/multi-generate/stream')
async def multi_generate_stream(data: MultiNodeRequest, user: dict = Depends(get_current_user)):
    """多段续写（流式输出）"""
    user_id = str(user['user_id'])
    project_name = current_project_name.get() or data.projectName
    if not project_name:
        return JSONResponse(status_code=400, content={'error': '缺少项目名称'})

    set_agent_context(user_id, project_name)
    
    wv = _load_worldview_and_characters(user_id, project_name)
    worldview = wv.get('worldview', '')
    characters = wv.get('characters', [])

    async def generate():
        try:
            async for event in run_story_generation_workflow(
                user_id=user_id,
                project_name=project_name,
                context=data.context,
                guidance=data.guidance,
                worldview=worldview,
                characters=characters,
                segment_count=data.segment_count,
                current_file=data.current_file,
                scene_name=data.scene_name,
                after_node_id=data.after_node_id,
                last_node_text=data.last_node_text,
                confirm_continue=data.confirm_continue,
            ):
                yield event
        except Exception as e:
            import traceback
            traceback.print_exc()
            yield {"event": "error", "data": json.dumps({"error": str(e)}, ensure_ascii=False)}

    return EventSourceResponse(generate())


@production_router.post('/api/production/feedback/stream')
async def feedback_stream(data: FeedbackRequest, user: dict = Depends(get_current_user)):
    """反馈/修改建议（流式输出）"""
    user_id = str(user['user_id'])
    project_name = current_project_name.get() or data.projectName
    if not project_name:
        return JSONResponse(status_code=400, content={'error': '缺少项目名称'})

    set_agent_context(user_id, project_name)
    
    wv = _load_worldview_and_roles(user_id, project_name)
    worldview = wv.get('worldview', '')
    roles = wv.get('roles', '')

    agent = ScriptwriterAgent(user_id=user_id)

    async def generate():
        try:
            for chunk in agent.stream_feedback(
                user_input=data.user_input,
                context=data.context,
                last_content=data.last_content,
                worldview=worldview,
                roles=roles,
            ):
                yield {"event": "chunk", "data": json.dumps({"text": chunk}, ensure_ascii=False)}
            yield {"event": "done", "data": "{}"}
        except Exception as e:
            yield {"event": "error", "data": json.dumps({"error": str(e)}, ensure_ascii=False)}

    return EventSourceResponse(generate())
