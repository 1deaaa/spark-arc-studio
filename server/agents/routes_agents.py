"""Agents 路由模块 - FastAPI 版本

整合所有 agents 相关的路由：
- 剧本生成 (Production)
- 场景过渡 (Bridge)
- 风格分析 (Style)
- 剧情结构 (Structure)
- 大纲管理 (Outline)
- Agent 配置 (Usage)
- 世界观与角色生成 (Lorebook)
- 灵感生成 (Setup)
"""

from fastapi import APIRouter, Depends, Request, HTTPException, Response, UploadFile, File, Query
from fastapi.responses import StreamingResponse, JSONResponse
from sse_starlette.sse import EventSourceResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
import os
import json
import shutil
import tempfile

from core.auth import get_current_user, get_optional_user
from core.request_context import current_user_id, current_project_name, set_agent_context
from core.utils import (
    get_project_path,
    get_project_stories_path,
    get_project_worldview_path,
    get_project_synopsis_path,
    get_project_beats_path,
    get_project_lorebook_path,
    ensure_project_characters_directory,
    ensure_project_worldview_and_character_settings,
    ensure_project_directory,
    strip_private_fields,
)
from llm.llm_mgr import LLM_Manager

# 导入 Agents
from agents import (
    ShowrunnerAgent,
    ScriptwriterAgent,
    CriticAgent,
    FeedbackJudgeAgent,
    MirrorAgent,
    run_story_generation_workflow,
)
from agents.agent_lorebook import get_all_characters, get_character_info, WorldviewAgent
from agents.agent_style.workflow import save_style_profile
from agents.agent_style.utils import extract_text_from_epub, load_style_profile_from_file
from agents.setup_agents import MuseAgent

# 创建主路由器
agents_router = APIRouter()
manager = LLM_Manager


# ==================== Pydantic Models ====================
class SingleNodeRequest(BaseModel):
    projectName: Optional[str] = None
    context: str = ""
    length: int = 100
    character_ids: List[int] = []


class MultiNodeRequest(BaseModel):
    projectName: Optional[str] = None
    context: str = ""
    guidance: str = ""
    character_ids: List[int] = []
    segment_count: int = 3
    current_file: str
    scene_name: str
    after_node_id: int
    confirm_continue: bool = False


class FeedbackRequest(BaseModel):
    user_input: str = ""
    projectName: Optional[str] = None
    context: str = ""
    last_content: str = ""


class CriticReviewRequest(BaseModel):
    projectName: Optional[str] = None
    context: str = ""
    guidance: str = ""
    script_nodes: List[Dict[str, Any]]


class AgentChatRequest(BaseModel):
    projectName: Optional[str] = None
    query: str


class BridgeRequest(BaseModel):
    projectName: Optional[str] = None
    prev_scene_content: str
    next_scene_content: str
    guidance: str = ""


class StyleAnalysisRequest(BaseModel):
    projectName: Optional[str] = None
    text: str
    author_name: str = "Unknown"


class StructureRequest(BaseModel):
    projectName: Optional[str] = None
    content: str


class OutlineRequest(BaseModel):
    projectName: Optional[str] = None
    outline: Dict[str, Any]


class LorebookRequest(BaseModel):
    projectName: Optional[str] = None
    fileName: str
    content: str


class WorldviewRequest(BaseModel):
    projectName: Optional[str] = None
    content: str


class MuseRequest(BaseModel):
    inspiration: str


class SynopsisRequest(BaseModel):
    projectName: Optional[str] = None
    logline: str
    guidance: str = ""


class BeatSheetRequest(BaseModel):
    projectName: Optional[str] = None
    synopsis: str
    guidance: str = ""


class WorldviewGenerateRequest(BaseModel):
    seed: str
    projectName: Optional[str] = None


class SynopsisSaveRequest(BaseModel):
    projectName: str
    synopsis: Dict[str, Any]


class BeatSheetSaveRequest(BaseModel):
    projectName: str
    beatSheet: Dict[str, Any]


# ==================== 辅助函数 ====================
def _load_worldview_and_roles(user_id: str, project_name: Optional[str]) -> Dict[str, str]:
    if not project_name:
        return {"worldview": "", "roles": ""}
    project_path = get_project_path(user_id, project_name)

    worldview = ""
    worldview_path = os.path.join(project_path, '世界观.txt')
    if os.path.exists(worldview_path):
        with open(worldview_path, 'r', encoding='utf-8') as f:
            worldview = f.read()

    roles = ""
    roles_path = os.path.join(project_path, '角色设定.txt')
    if os.path.exists(roles_path):
        try:
            with open(roles_path, 'r', encoding='utf-8') as f:
                all_roles = json.load(f)
                if isinstance(all_roles, list):
                    roles = "\n".join([f"- {r.get('name', '')}: {r.get('settings', '')}" for r in all_roles])
        except Exception:
            with open(roles_path, 'r', encoding='utf-8') as f:
                roles = f.read()

    return {"worldview": worldview, "roles": roles}


def _get_history_dir(user_id: str, project_name: str) -> str:
    return os.path.join(get_project_path(user_id, project_name), 'history')


def _ensure_history_dir(user_id: str, project_name: str) -> str:
    history_dir = _get_history_dir(user_id, project_name)
    os.makedirs(history_dir, exist_ok=True)
    return history_dir


def _save_outline_to_history(user_id: str, project_name: str, outline: Dict[str, Any]) -> None:
    history_dir = _ensure_history_dir(user_id, project_name)
    history_file = os.path.join(history_dir, 'outline_history.json')

    history: List[Dict[str, Any]] = []
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
    history = history[:20]

    with open(history_file, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def _save_muse_history(user_id: str, project_name: str, input_text: str, output_text: str) -> None:
    try:
        history_dir = _ensure_history_dir(user_id, project_name)
        history_file = os.path.join(history_dir, 'muse_history.json')
        history: List[Dict[str, Any]] = []
        if os.path.exists(history_file):
            with open(history_file, 'r', encoding='utf-8') as f:
                history = json.load(f)
        entry = {
            "id": len(history) + 1,
            "timestamp": datetime.now().isoformat(),
            "input": input_text,
            "output": output_text
        }
        history.insert(0, entry)
        history = history[:50]
        with open(history_file, 'w', encoding='utf-8') as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except Exception as exc:
        print(f"Error saving muse history: {exc}")


def _load_worldview_and_characters(user_id: str, project_name: str) -> Dict[str, Any]:
    worldview = ""
    characters: List[Dict[str, Any]] = []
    project_path = get_project_path(user_id, project_name)

    worldview_path = os.path.join(project_path, 'worldview.txt')
    if os.path.exists(worldview_path):
        with open(worldview_path, 'r', encoding='utf-8') as f:
            worldview = f.read()

    chr_bind_path = os.path.join(project_path, 'chr', 'chr.bind')
    if os.path.exists(chr_bind_path):
        with open(chr_bind_path, 'r', encoding='utf-8') as f:
            chr_data = json.load(f)
            for chr_id, info in chr_data.items():
                if isinstance(info, dict):
                    characters.append({'id': int(chr_id), 'name': info.get('name', ''), 'desc': info.get('desc', '')})
                else:
                    characters.append({'id': int(chr_id), 'name': str(info), 'desc': ''})

    return {"worldview": worldview, "characters": characters}


# ==================== Character Settings (角色设定 API) ====================
class CharacterSettingsCreate(BaseModel):
    projectName: Optional[str] = None
    name: str = "新角色"


class CharacterSettingsSave(BaseModel):
    projectName: Optional[str] = None
    id: int
    content: str = ""


class CharacterSettingsRename(BaseModel):
    projectName: Optional[str] = None
    id: int
    newName: str


class CharacterSettingsDelete(BaseModel):
    projectName: Optional[str] = None
    id: int


@agents_router.get('/api/character-settings/{project_name}')
async def get_character_settings(project_name: str, user: Optional[dict] = Depends(get_optional_user)):
    try:
        if not user:
            return []
        user_id = str(user['user_id'])
        characters_path = ensure_project_characters_directory(user_id, project_name)
        bind_file = os.path.join(characters_path, 'chr.bind')
        mapping = {}
        if os.path.exists(bind_file):
            try:
                with open(bind_file, 'r', encoding='utf-8') as f:
                    mapping = json.load(f) or {}
            except Exception:
                mapping = {}

        result = []
        for cid, name in mapping.items():
            try:
                file_path = os.path.join(characters_path, f"{cid}.txt")
                content = ''
                if os.path.exists(file_path):
                    with open(file_path, 'r', encoding='utf-8') as f:
                        text = f.read()
                        # strip name line if included
                        parts = text.split('\n', 2)
                        content = parts[2] if len(parts) >= 3 else (parts[1] if len(parts) == 2 else parts[0])
                result.append({'id': int(cid), 'name': name if isinstance(name, str) else name.get('name', ''), 'content': content})
            except Exception:
                continue
        return result
    except Exception as exc:
        return JSONResponse(status_code=500, content={'error': f'获取角色设定失败: {exc}'})


@agents_router.post('/api/character-settings')
async def create_character_setting(data: CharacterSettingsCreate, user: dict = Depends(get_current_user)):
    try:
        user_id = str(user['user_id'])
        project_name = data.projectName
        name = data.name or '新角色'
        characters_path = ensure_project_characters_directory(user_id, project_name)
        bind_file = os.path.join(characters_path, 'chr.bind')
        mapping = {}
        if os.path.exists(bind_file):
            try:
                with open(bind_file, 'r', encoding='utf-8') as f:
                    mapping = json.load(f) or {}
            except Exception:
                mapping = {}
        existing_ids = {int(k) for k in mapping.keys()} if mapping else set()
        next_id = 0
        while next_id in existing_ids:
            next_id += 1
        mapping[str(next_id)] = name
        with open(bind_file, 'w', encoding='utf-8') as f:
            json.dump(mapping, f, ensure_ascii=False, indent=2)

        # Write template file
        char_file = os.path.join(characters_path, f"{next_id}.txt")
        with open(char_file, 'w', encoding='utf-8') as f:
            f.write(f"{name}\n\n在这里描述你的角色...")

        return {'success': True, 'id': next_id}
    except Exception as exc:
        return JSONResponse(status_code=500, content={'success': False, 'message': str(exc)})


@agents_router.post('/api/character-settings/save')
async def save_character_setting(data: CharacterSettingsSave, user: dict = Depends(get_current_user)):
    try:
        user_id = str(user['user_id'])
        project_name = data.projectName
        char_id = str(data.id)
        content = data.content or ''
        characters_path = ensure_project_characters_directory(user_id, project_name)
        bind_file = os.path.join(characters_path, 'chr.bind')
        name = ''
        if os.path.exists(bind_file):
            try:
                with open(bind_file, 'r', encoding='utf-8') as f:
                    mapping = json.load(f) or {}
                    val = mapping.get(char_id)
                    name = val if isinstance(val, str) else val.get('name', '')
            except Exception:
                name = ''
        # If name unavailable, try to get from file
        char_file = os.path.join(characters_path, f"{char_id}.txt")
        if os.path.exists(char_file):
            try:
                with open(char_file, 'r', encoding='utf-8') as f:
                    lines = f.read().split('\n', 1)
                    if lines:
                        name = lines[0]
            except Exception:
                pass
        # save content with name at top
        with open(char_file, 'w', encoding='utf-8') as f:
            f.write(f"{name}\n\n{content}")
        return {'success': True}
    except Exception as exc:
        return JSONResponse(status_code=500, content={'success': False, 'message': str(exc)})


@agents_router.post('/api/character-settings/rename')
async def rename_character_setting(data: CharacterSettingsRename, user: dict = Depends(get_current_user)):
    try:
        user_id = str(user['user_id'])
        project_name = data.projectName
        char_id = str(data.id)
        new_name = data.newName
        characters_path = ensure_project_characters_directory(user_id, project_name)
        bind_file = os.path.join(characters_path, 'chr.bind')
        mapping = {}
        if os.path.exists(bind_file):
            try:
                with open(bind_file, 'r', encoding='utf-8') as f:
                    mapping = json.load(f) or {}
            except Exception:
                mapping = {}
        if char_id not in mapping:
            return JSONResponse(status_code=404, content={'success': False, 'message': '角色不存在'})
        mapping[char_id] = new_name
        with open(bind_file, 'w', encoding='utf-8') as f:
            json.dump(mapping, f, ensure_ascii=False, indent=2)
        # Also update character file's first line
        char_file = os.path.join(characters_path, f"{char_id}.txt")
        if os.path.exists(char_file):
            try:
                with open(char_file, 'r', encoding='utf-8') as f:
                    old = f.read()
                parts = old.split('\n', 2)
                body = parts[2] if len(parts) >= 3 else (parts[1] if len(parts) == 2 else '')
                with open(char_file, 'w', encoding='utf-8') as f:
                    f.write(f"{new_name}\n\n{body}")
            except Exception:
                pass
        return {'success': True}
    except Exception as exc:
        return JSONResponse(status_code=500, content={'success': False, 'message': str(exc)})


@agents_router.post('/api/character-settings/delete')
async def delete_character_setting(data: CharacterSettingsDelete, user: dict = Depends(get_current_user)):
    try:
        user_id = str(user['user_id'])
        project_name = data.projectName
        char_id = str(data.id)
        characters_path = ensure_project_characters_directory(user_id, project_name)
        bind_file = os.path.join(characters_path, 'chr.bind')
        mapping = {}
        if os.path.exists(bind_file):
            try:
                with open(bind_file, 'r', encoding='utf-8') as f:
                    mapping = json.load(f) or {}
            except Exception:
                mapping = {}
        if char_id in mapping:
            mapping.pop(char_id, None)
            with open(bind_file, 'w', encoding='utf-8') as f:
                json.dump(mapping, f, ensure_ascii=False, indent=2)
        # remove file
        char_file = os.path.join(characters_path, f"{char_id}.txt")
        if os.path.exists(char_file):
            os.remove(char_file)
        return {'success': True}
    except Exception as exc:
        return JSONResponse(status_code=500, content={'success': False, 'message': str(exc)})


def _write_worldview(user_id: str, project_name: str, content: str) -> None:
    ensure_project_worldview_and_character_settings(user_id, project_name)
    worldview_path = get_project_worldview_path(user_id, project_name)
    ensure_project_directory(user_id, project_name)
    with open(worldview_path, 'w', encoding='utf-8') as f:
        f.write(content)


def _run_bridge_agent(
    user_id: str,
    prev_scene: Dict[str, Any],
    next_scene: Dict[str, Any],
    worldview: str = "",
    characters: Optional[List[Dict[str, Any]]] = None,
    pacing: str = "normal",
    mood: str = "",
    guidance: str = "",
    style_profile: object = None,
) -> Dict[str, Any]:
    writer = ScriptwriterAgent(user_id)
    return writer.bridge_scenes(
        prev_scene=prev_scene,
        next_scene=next_scene,
        worldview=worldview,
        characters=characters or [],
        pacing=pacing,
        mood=mood,
        guidance=guidance,
        style_profile=style_profile,
    )


def _generate_story_json_content(chapter_num: int, chapter_title: str, chapter_desc: str, scenes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    import uuid
    story_data = []
    
    if not scenes:
        # Create a default scene for the chapter
        story_data.append({
            "id": str(uuid.uuid4()),
            "scene": chapter_title,
            "cap": chapter_title,
            "intro": chapter_desc if chapter_desc else "",
            "dia": [
                {
                    "id": 1,
                    "chr": -1,
                    "txt": "场景内容待填写..."
                }
            ]
        })
        return story_data

    for idx, scene in enumerate(scenes):
        scene_title = scene.get('title', f'场景 {idx + 1}')
        scene_desc = scene.get('description', '场景内容待填写...')
        
        story_data.append({
            "id": str(uuid.uuid4()),
            "scene": scene_title,
            "cap": scene_title,
            "intro": scene_desc if scene_desc else "",
            "dia": [
                {
                    "id": 1,
                    "chr": -1,
                    "txt": "场景内容待填写..."
                }
            ]
        })
        
    return story_data


def _generate_arc_content(chapter_num: int, chapter_title: str, chapter_desc: str, scenes: List[Dict[str, Any]]) -> str:
    lines: List[str] = []
    lines.append(f"<!-- 章节 {chapter_num}: {chapter_title} -->")
    lines.append(f"<!-- {chapter_desc} -->")
    lines.append("")

    if not scenes:
        lines.append(f"# {chapter_title}")
        lines.append(f"@cap {chapter_title}")
        if chapter_desc:
            lines.append("@intro")
            lines.extend([l for l in str(chapter_desc).split('\n') if l.strip()])
        lines.append("")
        lines.append("(旁白)")
        lines.append("场景内容待填写...")
        lines.append("")
        return '\n'.join(lines)

    for idx, scene in enumerate(scenes):
        scene_title = scene.get('title', f'场景 {idx + 1}')
        scene_desc = scene.get('description', '场景内容待填写...')
        lines.append(f"# {scene_title}")
        lines.append(f"@cap {scene_title}")
        if scene_desc:
            lines.append("@intro")
            lines.extend([l for l in str(scene_desc).split('\n') if l.strip()])
        lines.append("")
        lines.append("(旁白)")
        lines.append("场景内容待填写...")
        lines.append("")
        if idx < len(scenes) - 1:
            lines.append("")

    return '\n'.join(lines)


# ==================== Production (执笔编剧) ====================
@agents_router.post('/api/ai/single-node')
async def single_node_writing(
    data: SingleNodeRequest,
    request: Request,
    user: dict = Depends(get_current_user)
):
    """单节点续写 - 流式响应"""
    project_name = current_project_name.get() or data.projectName
    context = data.context
    length = data.length
    character_ids = data.character_ids
    user_id = str(user['user_id'])

    if not project_name:
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


@agents_router.post('/api/ai/multi-node')
async def multi_node_writing(
    data: MultiNodeRequest,
    user: dict = Depends(get_current_user)
):
    """多段续写 (Production Pipeline)"""
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

    if not all([project_name, context, current_file, scene_name, after_node_id is not None]):
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
                from core.utils import get_project_characters_path
                characters_path = get_project_characters_path(user_id, project_name)
                bind_file = os.path.join(characters_path, 'chr.bind')
                
                if os.path.exists(bind_file):
                    with open(bind_file, 'r', encoding='utf-8') as f:
                        full_char_map = json.load(f)
                    
                    selected_roles_content = []
                    for cid in character_ids:
                        cid_str = str(cid)
                        if cid_str in full_char_map:
                            name = full_char_map[cid_str]
                            # 强制将id为-1的角色名字显示为"旁白"
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
        style_profile = load_style_profile_from_file(author_id)

        final_nodes, thought = run_story_generation_workflow(
            user_id=user_id,
            project_name=project_name,
            context=context,
            guidance=guidance,
            worldview=worldview,
            roles=roles,
            style_profile=style_profile,
            segment_count=segment_count,
            chr_map=chr_map
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
        
        stories_path = get_project_stories_path(user_id, project_name)
        file_path = os.path.join(stories_path, current_file)
        if not file_path.endswith('.story'):
            file_path += '.story'

        if not os.path.exists(file_path):
            return JSONResponse(status_code=404, content={"error": "目标文件不存在"})

        with open(file_path, 'r+', encoding='utf-8') as f:
            story_data = json.load(f)
            strip_private_fields(story_data)
            
            target_scene = next((s for s in story_data if s.get('scene') == scene_name), None)
            if not target_scene:
                return JSONResponse(status_code=404, content={"error": f"场景 '{scene_name}' 未找到"})

            target_index = -1
            for i, dia in enumerate(target_scene.get('dia', [])):
                if dia.get('id') == after_node_id:
                    target_index = i
                    break
            
            if target_index == -1:
                return JSONResponse(status_code=404, content={"error": f"节点ID '{after_node_id}' 在场景中未找到"})

            for node in reversed(final_nodes):
                target_scene['dia'].insert(target_index + 1, node)

            f.seek(0)
            f.truncate()
            strip_private_fields(story_data)
            json.dump(story_data, f, ensure_ascii=False, indent=2)

        return {"success": True, "message": "续写成功并已插入剧本", "thought": thought}

    except Exception as e:
        print(f"AI多段续写失败: {e}")
        return JSONResponse(status_code=500, content={"error": f"AI生成或文件操作失败: {str(e)}"})


# ==================== Critic (手动评审) ====================
@agents_router.post('/api/ai/critic')
async def run_critic_review(
    data: CriticReviewRequest,
    user: dict = Depends(get_current_user)
):
    """手动触发 Critic 评审（不参与自动工作流）。"""
    project_name = current_project_name.get() or data.projectName
    if not project_name:
        return JSONResponse(status_code=400, content={"error": "缺少项目名称"})

    user_id = str(user['user_id'])
    info = _load_worldview_and_roles(user_id, project_name)
    author_id = f"{user_id}_{project_name}"
    style_profile = load_style_profile_from_file(author_id)

    critic = CriticAgent(user_id)
    score, status, feedback = critic.evaluate(
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


# ==================== Bridge (场景衔接) ====================
@agents_router.post('/api/ai/bridge')
async def generate_bridge(
    data: BridgeRequest,
    user: dict = Depends(get_current_user)
):
    """简化场景过渡接口 (保留与旧前端兼容)。"""
    project_name = current_project_name.get() or data.projectName
    if not project_name:
        return JSONResponse(status_code=400, content={"error": "缺少项目名称"})

    user_id = str(user['user_id'])
    prev_scene = {'scene': '上一场景', 'cap': '', 'dia': [{'txt': data.prev_scene_content}]}
    next_scene = {'scene': '下一场景', 'cap': '', 'dia': [{'txt': data.next_scene_content}]}
    bridge_ctx = _load_worldview_and_roles(user_id, project_name)
    author_id = f"{user_id}_{project_name}"
    style_profile = load_style_profile_from_file(author_id)

    try:
        result = _run_bridge_agent(
            user_id=user_id,
            prev_scene=prev_scene,
            next_scene=next_scene,
            worldview=bridge_ctx.get('worldview', ''),
            guidance=data.guidance,
            style_profile=style_profile,
        )
        return {"success": True, **result}
    except Exception as exc:
        return JSONResponse(status_code=500, content={"error": f"生成过渡失败: {exc}"})


@agents_router.post('/api/bridge/generate')
async def bridge_generate(request: Request, user: dict = Depends(get_current_user)):
    """完整场景结构的过渡生成 (与 Flask 版接口保持一致)。"""
    data = await request.json()
    prev_scene = data.get('prevScene') or {}
    next_scene = data.get('nextScene') or {}
    pacing = data.get('pacing', 'normal')
    mood = data.get('mood', '')
    guidance = data.get('guidance', '')
    project_name = current_project_name.get() or data.get('projectName') or data.get('project_name')

    user_id = str(user['user_id'])
    if not project_name:
        return JSONResponse(status_code=400, content={'error': '缺少项目名称'})

    meta = _load_worldview_and_characters(user_id, project_name)
    characters = data.get('characters') or meta['characters']
    author_id = f"{user_id}_{project_name}"
    style_profile = load_style_profile_from_file(author_id)

    try:
        result = _run_bridge_agent(
            user_id=user_id,
            prev_scene=prev_scene,
            next_scene=next_scene,
            worldview=meta['worldview'],
            characters=characters,
            pacing=pacing,
            mood=mood,
            guidance=guidance,
            style_profile=style_profile,
        )
        return {'success': True, **result}
    except Exception as exc:
        return JSONResponse(status_code=500, content={'error': str(exc)})


@agents_router.post('/api/bridge/preview')
async def bridge_preview(request: Request, user: dict = Depends(get_current_user)):
    """实时预览过渡内容 (无需完整项目数据)。"""
    data = await request.json()
    prev_text = data.get('prevText', '')
    next_text = data.get('nextText', '')
    guidance = data.get('guidance', '')
    user_id = str(user['user_id'])

    prev_scene = {'scene': '上一场景', 'cap': '', 'dia': [{'txt': prev_text}]}
    next_scene = {'scene': '下一场景', 'cap': '', 'dia': [{'txt': next_text}]}

    try:
        result = _run_bridge_agent(user_id, prev_scene, next_scene, guidance=guidance)
        return {'success': True, **result}
    except Exception as exc:
        return JSONResponse(status_code=500, content={'error': str(exc)})


# ==================== Style (风格分析) ====================
@agents_router.post('/api/ai/style-analyze')
async def analyze_style(
    request: Request,
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user)
):
    user_id = str(user['user_id'])
    project_name = current_project_name.get()
    if not project_name:
        form = await request.form()
        project_name = form.get('projectName') or form.get('project_name')
    if not project_name:
        return JSONResponse(status_code=400, content={'error': '缺少项目名称'})

    suffix = os.path.splitext(file.filename or '')[1].lower()
    if suffix not in {'.epub', '.txt'}:
        return JSONResponse(status_code=400, content={'error': '仅支持 .epub 或 .txt 文件'})

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp_path = tmp.name
            file.file.seek(0)
            shutil.copyfileobj(file.file, tmp)

        if suffix == '.epub':
            chapters = extract_text_from_epub(tmp_path, merge_short_chapters=True, min_chunk_size=3000)
        else:
            with open(tmp_path, 'r', encoding='utf-8') as f:
                text = f.read()
            chapters = [text[i:i+5000] for i in range(0, len(text), 5000)]

        if not chapters:
            return JSONResponse(status_code=400, content={'error': '无法从文件中提取文本'})

        author_id = f"{user_id}_{project_name}" if project_name else f"{user_id}_default"
        style_profile = save_style_profile(
            author_id=author_id,
            chapter_texts=chapters,
            force_regenerate=True,
            interactive=False,
            parallel=True,
            user_id=user_id
        )

        if style_profile:
            return {'success': True, 'style_profile': style_profile}
        return JSONResponse(status_code=500, content={'error': '风格分析失败'})
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


@agents_router.get('/api/ai/style-profile')
async def get_style_profile(user: dict = Depends(get_current_user)):
    user_id = str(user['user_id'])
    project_name = current_project_name.get()
    if not project_name:
        return JSONResponse(status_code=400, content={'success': False, 'message': '缺少项目名称'})

    author_id = f"{user_id}_{project_name}"
    profile = load_style_profile_from_file(author_id)
    if profile:
        return {'success': True, 'style_profile': profile}
    return JSONResponse(status_code=404, content={'success': False, 'message': '未找到风格分析结果'})


# ==================== Structure (剧情结构) ====================
@agents_router.post('/api/ai/synopsis')
async def generate_synopsis_ai(data: SynopsisRequest, user: dict = Depends(get_current_user)):
    """生成故事梗概 (Synopsis)"""
    project_name = current_project_name.get() or data.projectName
    if not project_name:
        return JSONResponse(status_code=400, content={'error': '缺少项目名称'})

    user_id = str(user['user_id'])
    info = _load_worldview_and_roles(user_id, project_name)
    try:
        showrunner = ShowrunnerAgent(user_id)
        synopsis = showrunner.generate_synopsis(
            logline=data.logline,
            worldview=info['worldview'],
            roles=info['roles'],
            guidance=data.guidance
        )
        return {'success': True, 'synopsis': synopsis}
    except Exception as exc:
        return JSONResponse(status_code=500, content={'error': str(exc)})


@agents_router.get('/api/synopsis/{project_name}')
async def get_synopsis(project_name: str, user: dict = Depends(get_current_user)):
    user_id = str(user['user_id'])
    synopsis_path = os.path.join(get_project_path(user_id, project_name), 'synopsis.json')
    if os.path.exists(synopsis_path):
        with open(synopsis_path, 'r', encoding='utf-8') as f:
            return {'success': True, 'synopsis': json.load(f)}
    return {'success': True, 'synopsis': None}


@agents_router.post('/api/synopsis')
async def save_synopsis(data: SynopsisSaveRequest, user: dict = Depends(get_current_user)):
    user_id = str(user['user_id'])
    project_name = data.projectName
    synopsis_path = os.path.join(get_project_path(user_id, project_name), 'synopsis.json')
    try:
        with open(synopsis_path, 'w', encoding='utf-8') as f:
            json.dump(data.synopsis, f, ensure_ascii=False, indent=2)
        return {'success': True}
    except Exception as exc:
        return JSONResponse(status_code=500, content={'error': str(exc)})


@agents_router.post('/api/ai/beat-sheet')
async def generate_beat_sheet_ai(data: BeatSheetRequest, user: dict = Depends(get_current_user)):
    """生成节拍表 (Beat Sheet)"""
    project_name = current_project_name.get() or data.projectName
    if not project_name:
        return JSONResponse(status_code=400, content={'error': '缺少项目名称'})

    user_id = str(user['user_id'])
    info = _load_worldview_and_roles(user_id, project_name)
    try:
        showrunner = ShowrunnerAgent(user_id)
        beat_sheet = showrunner.generate_beat_sheet(
            synopsis=data.synopsis,
            worldview=info['worldview'],
            roles=info['roles'],
            guidance=data.guidance
        )
        return {'success': True, 'beat_sheet': beat_sheet}
    except Exception as exc:
        return JSONResponse(status_code=500, content={'error': str(exc)})


@agents_router.get('/api/beat-sheet/{project_name}')
async def get_beat_sheet(project_name: str, user: dict = Depends(get_current_user)):
    user_id = str(user['user_id'])
    beats_path = os.path.join(get_project_path(user_id, project_name), 'beats.json')
    if os.path.exists(beats_path):
        with open(beats_path, 'r', encoding='utf-8') as f:
            return {'success': True, 'beat_sheet': json.load(f)}
    return {'success': True, 'beat_sheet': None}


@agents_router.post('/api/beat-sheet')
async def save_beat_sheet(data: BeatSheetSaveRequest, user: dict = Depends(get_current_user)):
    user_id = str(user['user_id'])
    project_name = data.projectName
    beats_path = os.path.join(get_project_path(user_id, project_name), 'beats.json')
    try:
        with open(beats_path, 'w', encoding='utf-8') as f:
            json.dump(data.beatSheet, f, ensure_ascii=False, indent=2)
        return {'success': True}
    except Exception as exc:
        return JSONResponse(status_code=500, content={'error': str(exc)})


@agents_router.post('/api/ai/outline')
async def generate_outline_ai(request: Request, user: dict = Depends(get_current_user)):
    data = await request.json() or {}
    context = data.get('context', '')
    guidance = data.get('guidance', '')
    chapter_count = data.get('chapterCount', 5)
    beat_sheet = data.get('beatSheet', '')
    save_to_project = data.get('saveToProject', True)
    save_to_history = data.get('saveToHistory', True)

    user_id = str(user['user_id'])
    project_name = current_project_name.get()
    if not project_name:
        return JSONResponse(status_code=400, content={'error': '缺少项目名称'})

    info = _load_worldview_and_roles(user_id, project_name)
    try:
        showrunner = ShowrunnerAgent(user_id)
        outline = showrunner.generate_outline(
            context=context,
            worldview=info['worldview'],
            roles=info['roles'],
            guidance=guidance,
            chapter_count=chapter_count,
            beat_sheet=beat_sheet
        )
        outline['updatedAt'] = datetime.now().isoformat()
        outline['generatedAt'] = datetime.now().isoformat()

        if save_to_project:
            outline_path = os.path.join(get_project_path(user_id, project_name), 'outline.json')
            with open(outline_path, 'w', encoding='utf-8') as f:
                json.dump(outline, f, ensure_ascii=False, indent=2)

        if save_to_history:
            _save_outline_to_history(user_id, project_name, outline)

        return {'success': True, 'outline': outline}
    except Exception as exc:
        return JSONResponse(status_code=500, content={'error': str(exc)})


# ==================== Lorebook (设定专家) ====================
@agents_router.get('/api/worldview/{project_name}')
async def get_worldview(project_name: str, user: Optional[dict] = Depends(get_optional_user)):
    """读取指定项目的世界观文本"""
    try:
        if not user:
            return {"content": ""}
        user_id = str(user['user_id'])
        ensure_project_worldview_and_character_settings(user_id, project_name)
        worldview_path = get_project_worldview_path(user_id, project_name)
        if not os.path.exists(worldview_path):
            return {'content': ''}
        with open(worldview_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return {'content': content}
    except Exception as exc:
        return JSONResponse(status_code=500, content={'error': f'读取世界观失败: {exc}'})


@agents_router.post('/api/worldview')
async def save_worldview_content(data: WorldviewRequest, user: dict = Depends(get_current_user)):
    """保存世界观内容"""
    try:
        user_id = str(user['user_id'])
        project_name = data.projectName
        content = data.content
        if not project_name:
            return JSONResponse(status_code=400, content={'success': False, 'message': '缺少项目名称'})
        
        ensure_project_worldview_and_character_settings(user_id, project_name)
        worldview_path = get_project_worldview_path(user_id, project_name)
        ensure_project_directory(user_id, project_name)
        with open(worldview_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return {'success': True, 'message': '世界观保存成功'}
    except Exception as exc:
        return JSONResponse(status_code=500, content={'success': False, 'message': f'保存世界观失败: {exc}'})


@agents_router.post('/api/worldview/{project_name}')
async def save_worldview_by_path(
    project_name: str,
    data: WorldviewRequest,
    user: dict = Depends(get_current_user)
):
    user_id = str(user['user_id'])
    try:
        _write_worldview(user_id, project_name, data.content)
        return {'success': True, 'message': '世界观保存成功'}
    except Exception as exc:
        return JSONResponse(status_code=500, content={'success': False, 'message': str(exc)})


@agents_router.post('/api/ai/worldview/generate')
async def generate_worldview(data: WorldviewGenerateRequest, user: dict = Depends(get_current_user)):
    user_id = str(user['user_id'])
    project_name = current_project_name.get() or data.projectName
    if not project_name or not data.seed:
        return JSONResponse(status_code=400, content={'error': '缺少项目名称或 seed'})

    agent = WorldviewAgent(user_id)
    author_id = f"{user_id}_{project_name}"
    style_profile = load_style_profile_from_file(author_id)

    async def streamer():
        full_text = []
        try:
            for chunk in agent.build_worldview(data.seed, style_profile=style_profile):
                full_text.append(chunk)
                yield chunk
        except Exception:
            raise
        else:
            if full_text:
                _write_worldview(user_id, project_name, ''.join(full_text))

    return StreamingResponse(streamer(), media_type='text/plain')


@agents_router.get('/api/lorebooks/{project_name}/{file_name}')
async def get_lorebook_file(
    project_name: str,
    file_name: str,
    user: dict = Depends(get_current_user)
):
    user_id = str(user['user_id'])
    lorebook_path = get_project_lorebook_path(user_id, project_name, file_name)
    if not os.path.exists(lorebook_path):
        return {'content': ''}
    with open(lorebook_path, 'r', encoding='utf-8') as f:
        content = f.read()
    return {'content': content}


@agents_router.post('/api/lorebooks')
async def save_lorebook_file(data: LorebookRequest, user: dict = Depends(get_current_user)):
    project_name = data.projectName
    file_name = data.fileName
    if not project_name or not file_name:
        return JSONResponse(status_code=400, content={'error': '缺少项目或文件名'})
    user_id = str(user['user_id'])
    lorebook_path = get_project_lorebook_path(user_id, project_name, file_name)
    try:
        with open(lorebook_path, 'w', encoding='utf-8') as f:
            f.write(data.content)
        return {'success': True}
    except Exception as exc:
        return JSONResponse(status_code=500, content={'error': str(exc)})


@agents_router.get('/api/ai/gen-characters/stream')
async def gen_characters_stream(
    request: Request,
    projectName: str,
    count: int = 1,
    prompt: str = "",
    user: dict = Depends(get_current_user)
):
    """SSE 流式生成角色"""
    user_id = str(user['user_id'])
    
    if count < 1 or count > 8:
        return JSONResponse(status_code=400, content={"error": "生成数量需在 1-8 之间"})

    async def event_generator():
        try:
            # 读取世界观
            worldview_path = get_project_worldview_path(user_id, projectName)
            worldview = ''
            if os.path.exists(worldview_path):
                with open(worldview_path, 'r', encoding='utf-8') as f:
                    worldview = f.read()
            
            # 角色目录与绑定
            characters_path = ensure_project_characters_directory(user_id, projectName)
            bind_path = os.path.join(characters_path, 'chr.bind')
            
            # 加载已有角色
            mapping = {}
            if os.path.exists(bind_path):
                try:
                    with open(bind_path, 'r', encoding='utf-8') as f:
                        mapping = json.load(f) or {}
                except Exception:
                    mapping = {}
            
            existing_ids = {int(k) for k in mapping.keys()}
            
            # 构造已有角色文本块
            lines = []
            for cid, name in mapping.items():
                try:
                    char_file = os.path.join(characters_path, f"{cid}.txt")
                    content = ''
                    if os.path.exists(char_file):
                        with open(char_file, 'r', encoding='utf-8') as f:
                            text = f.read()
                            parts = text.split('\n', 2)
                            content = parts[2] if len(parts) >= 3 else text
                    content = (content or '').strip()
                    if len(content) > 400:
                        content = content[:400] + '…'
                    lines.append(f"- {name}: {content}")
                except Exception:
                    continue
            existing_block = "\n".join(lines) if lines else ''

            created_count = 0
            
            for _ in range(count):
                # 分配新ID
                char_id = 0
                while char_id in existing_ids:
                    char_id += 1
                existing_ids.add(char_id)
                
                mapping[str(char_id)] = "生成中..."
                with open(bind_path, 'w', encoding='utf-8') as f:
                    json.dump(mapping, f, ensure_ascii=False, indent=2)

                system = (
                    "你是一个资深设定师，负责根据世界观与已有角色生成新的角色。**严禁**使用网文常见角色名字。\n"
                    "你的输出必须严格遵循以下格式，不要附加任何说明或Markdown：\n"
                    "第一行是角色名，然后是一个空行，然后是角色设定内容。\n"
                    "例如："
                    "角色名\n\n"
                    "这是角色的详细设定..."
                )
                user_prompt = f"""
世界观：\n{worldview}

已有角色（供参考，避免角色重复！）：
{existing_block}

请在不重复已有角色的前提下，生成一个新角色：
- 角色名：不超过8个中文字符；
- 角色设定：200-400字，描述性格、动机、矛盾、与世界观的关系。
{f"额外要求：{prompt}" if prompt else ""}
"""
                from langchain_core.messages import SystemMessage, HumanMessage
                messages = [SystemMessage(content=system), HumanMessage(content=user_prompt)]
                llm = manager.get_user_llm(user_id, agent_name="agent_lorebook")

                buffer = ""
                name_sent = False
                final_name = "新角色"
                final_content = ""

                yield {
                    "event": "character-start",
                    "data": json.dumps({"id": char_id, "name": ""}, ensure_ascii=False)
                }

                for chunk in llm.stream(messages):
                    if not chunk or not getattr(chunk, 'content', None):
                        continue
                    
                    buffer += chunk.content
                    
                    if not name_sent:
                        separator_pos = buffer.find('\n\n')
                        if separator_pos != -1:
                            name = buffer[:separator_pos].strip()
                            if name:
                                final_name = name
                                yield {
                                    "event": "character-streamed",
                                    "data": json.dumps({"id": char_id, "name": final_name}, ensure_ascii=False)
                                }
                                name_sent = True
                    
                    yield {
                        "event": "character-delta",
                        "data": json.dumps({"id": char_id, "delta": chunk.content}, ensure_ascii=False)
                    }

                separator_pos = buffer.find('\n\n')
                if separator_pos != -1:
                    final_name = buffer[:separator_pos].strip() or "新角色"
                    final_content = buffer[separator_pos + 2:].strip()
                else:
                    final_content = buffer.strip()

                mapping[str(char_id)] = final_name
                with open(bind_path, 'w', encoding='utf-8') as f:
                    json.dump(mapping, f, ensure_ascii=False, indent=2)
                
                char_file = os.path.join(characters_path, f"{char_id}.txt")
                with open(char_file, 'w', encoding='utf-8') as f:
                    f.write(f"{final_name}\n\n{final_content}")

                yield {
                    "event": "character-end",
                    "data": json.dumps({"id": char_id, "name": final_name, "content": final_content}, ensure_ascii=False)
                }
                created_count += 1
                
                snippet = final_content if len(final_content) <= 400 else final_content[:400] + '…'
                existing_block += f"\n- {final_name}: {snippet}"

            yield {
                "event": "done",
                "data": json.dumps({"count": created_count}, ensure_ascii=False)
            }

        except Exception as e:
            print(f"AI 生成角色(SSE)失败: {e}")
            yield {
                "event": "error",
                "data": json.dumps({"message": f"生成失败: {e}"}, ensure_ascii=False)
            }

    return EventSourceResponse(event_generator())


# ==================== Setup (创意助手 Muse) ====================
@agents_router.post('/api/ai/muse')
async def muse_inspiration(
    data: MuseRequest,
    user: dict = Depends(get_current_user)
):
    """灵感种子: 灵感扩展 (流式响应)"""
    raw_input = data.inspiration
    user_id = str(user['user_id'])
    project_name = current_project_name.get()

    if not raw_input:
        return JSONResponse(status_code=400, content={"error": "Missing inspiration input"})

    muse = MuseAgent(user_id)
    
    async def generate():
        output_collector = []
        try:
            for chunk in muse.expand_inspiration(raw_input):
                output_collector.append(chunk)
                yield chunk
        except Exception as e:
            print(f"Muse Agent 灵感扩展失败: {e}")
            raise
        finally:
            if project_name and output_collector:
                full_output = ''.join(output_collector)
                _save_muse_history(user_id, project_name, raw_input, full_output)

    return StreamingResponse(generate(), media_type='text/plain')


# ==================== Outline (大纲管理) ====================
@agents_router.get('/api/outline/{project_name}')
async def get_outline(project_name: str, user: dict = Depends(get_current_user)):
    user_id = str(user['user_id'])
    outline_path = os.path.join(get_project_path(user_id, project_name), 'outline.json')
    try:
        if os.path.exists(outline_path):
            with open(outline_path, 'r', encoding='utf-8') as f:
                outline = json.load(f)
            return {'success': True, 'outline': outline}
        return {
            'success': True,
            'outline': {
                'title': '新故事大纲',
                'nodes': [],
                'updatedAt': None
            }
        }
    except Exception as exc:
        return JSONResponse(status_code=500, content={'success': False, 'error': str(exc)})


@agents_router.post('/api/outline/{project_name}')
async def save_outline(project_name: str, request: Request, user: dict = Depends(get_current_user)):
    user_id = str(user['user_id'])
    data = await request.json()
    outline = data.get('outline', {})
    save_to_history = data.get('saveToHistory', False)
    outline['updatedAt'] = datetime.now().isoformat()

    outline_path = os.path.join(get_project_path(user_id, project_name), 'outline.json')
    try:
        with open(outline_path, 'w', encoding='utf-8') as f:
            json.dump(outline, f, ensure_ascii=False, indent=2)
        if save_to_history:
            _save_outline_to_history(user_id, project_name, outline)
        return {'success': True, 'message': '大纲已保存'}
    except Exception as exc:
        return JSONResponse(status_code=500, content={'success': False, 'error': str(exc)})


@agents_router.get('/api/history/muse/{project_name}')
async def get_muse_history(project_name: str, user: dict = Depends(get_current_user)):
    user_id = str(user['user_id'])
    history_file = os.path.join(_get_history_dir(user_id, project_name), 'muse_history.json')
    if os.path.exists(history_file):
        with open(history_file, 'r', encoding='utf-8') as f:
            history = json.load(f)
        return {'success': True, 'history': history}
    return {'success': True, 'history': []}


@agents_router.post('/api/history/muse/{project_name}')
async def save_muse_history(project_name: str, request: Request, user: dict = Depends(get_current_user)):
    user_id = str(user['user_id'])
    data = await request.json()
    input_text = data.get('input', '')
    output_text = data.get('output', '')
    _save_muse_history(user_id, project_name, input_text, output_text)
    history_file = os.path.join(_get_history_dir(user_id, project_name), 'muse_history.json')
    with open(history_file, 'r', encoding='utf-8') as f:
        history = json.load(f)
    return {'success': True, 'entry': history[0] if history else {}}


@agents_router.delete('/api/history/muse/{project_name}/{entry_id}')
async def delete_muse_history(project_name: str, entry_id: int, user: dict = Depends(get_current_user)):
    user_id = str(user['user_id'])
    history_file = os.path.join(_get_history_dir(user_id, project_name), 'muse_history.json')
    if not os.path.exists(history_file):
        return JSONResponse(status_code=404, content={'success': False, 'error': '历史记录不存在'})
    with open(history_file, 'r', encoding='utf-8') as f:
        history = json.load(f)
    history = [h for h in history if h.get('id') != entry_id]
    with open(history_file, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
    return {'success': True}


@agents_router.get('/api/history/outline/{project_name}')
async def get_outline_history(project_name: str, user: dict = Depends(get_current_user)):
    user_id = str(user['user_id'])
    history_file = os.path.join(_get_history_dir(user_id, project_name), 'outline_history.json')
    if os.path.exists(history_file):
        with open(history_file, 'r', encoding='utf-8') as f:
            history = json.load(f)
        return {'success': True, 'history': history}
    return {'success': True, 'history': []}


@agents_router.post('/api/history/outline/{project_name}')
async def save_outline_history(project_name: str, request: Request, user: dict = Depends(get_current_user)):
    user_id = str(user['user_id'])
    data = await request.json()
    outline = data.get('outline', {})
    _save_outline_to_history(user_id, project_name, outline)
    return {'success': True}


@agents_router.delete('/api/history/outline/{project_name}/{entry_id}')
async def delete_outline_history(project_name: str, entry_id: int, user: dict = Depends(get_current_user)):
    user_id = str(user['user_id'])
    history_file = os.path.join(_get_history_dir(user_id, project_name), 'outline_history.json')
    if not os.path.exists(history_file):
        return JSONResponse(status_code=404, content={'success': False, 'error': '历史记录不存在'})
    with open(history_file, 'r', encoding='utf-8') as f:
        history = json.load(f)
    history = [h for h in history if h.get('id') != entry_id]
    with open(history_file, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
    return {'success': True}


@agents_router.post('/api/history/outline/{project_name}/{entry_id}/restore')
async def restore_outline_from_history(project_name: str, entry_id: int, user: dict = Depends(get_current_user)):
    user_id = str(user['user_id'])
    history_file = os.path.join(_get_history_dir(user_id, project_name), 'outline_history.json')
    if not os.path.exists(history_file):
        return JSONResponse(status_code=404, content={'success': False, 'error': '历史记录不存在'})
    with open(history_file, 'r', encoding='utf-8') as f:
        history = json.load(f)
    entry = next((h for h in history if h.get('id') == entry_id), None)
    if not entry:
        return JSONResponse(status_code=404, content={'success': False, 'error': '记录不存在'})
    outline = entry.get('outline', {})
    outline['updatedAt'] = datetime.now().isoformat()
    outline_path = os.path.join(get_project_path(user_id, project_name), 'outline.json')
    with open(outline_path, 'w', encoding='utf-8') as f:
        json.dump(outline, f, ensure_ascii=False, indent=2)
    return {'success': True, 'outline': outline}


@agents_router.post('/api/outline/{project_name}/export-to-files')
async def export_outline_to_files(
    project_name: str, 
    request: Request,
    user: dict = Depends(get_current_user)
):
    user_id = str(user['user_id'])
    data = await request.json() or {}
    overwrite = data.get('overwrite', False)
    check_only = data.get('check_only', False)

    outline_path = os.path.join(get_project_path(user_id, project_name), 'outline.json')
    if not os.path.exists(outline_path):
        return JSONResponse(status_code=404, content={'success': False, 'error': '大纲不存在'})

    with open(outline_path, 'r', encoding='utf-8') as f:
        outline = json.load(f)

    nodes = outline.get('nodes', [])
    if not nodes:
        return JSONResponse(status_code=400, content={'success': False, 'error': '大纲为空'})

    stories_path = os.path.join(get_project_path(user_id, project_name), 'stories')
    os.makedirs(stories_path, exist_ok=True)

    # First pass: Identify files to be created
    files_to_create = []
    existing_files = []

    for chapter in nodes:
        if chapter.get('type') != 'chapter':
            continue
        chapter_num = chapter.get('chapter', 1)
        chapter_title = chapter.get('title', f'第{chapter_num}章')
        safe_title = chapter_title.replace(':', '').replace('：', '').replace('/', '_').replace('\\', '_')
        filename = f"{safe_title}.arc"
        filepath = os.path.join(stories_path, filename)
        
        if os.path.exists(filepath):
            existing_files.append(filename)
        
        files_to_create.append({
            'chapter': chapter,
            'filename': filename,  # Will be converted to .arc in the creation step
            'filepath': filepath   # Will be converted to .arc in the creation step
        })

    if check_only:
        return {'success': True, 'existing': existing_files}

    if existing_files and not overwrite:
        return JSONResponse(
            status_code=409, 
            content={
                'success': False, 
                'error': 'CONFLICT', 
                'message': '检测到同名文件已存在',
                'existing': existing_files
            }
        )

    # Second pass: Create files
    created_files = []
    for item in files_to_create:
        chapter = item['chapter']
        filepath = item['filepath']
        filename = item['filename']
        
        chapter_num = chapter.get('chapter', 1)
        chapter_title = chapter.get('title', f'第{chapter_num}章')
        chapter_desc = chapter.get('description', '')
        children = chapter.get('children', [])
        
        # Generate .arc format content
        arc_content = _generate_arc_content(chapter_num, chapter_title, chapter_desc, children)
        
        # Change extension to .arc
        arc_filepath = filepath.replace('.story', '.arc')
        arc_filename = filename.replace('.story', '.arc')
        
        with open(arc_filepath, 'w', encoding='utf-8') as f:
            f.write(arc_content)
            
        created_files.append({
            'chapter': chapter_num,
            'title': chapter_title,
            'filename': arc_filename,
            'sceneCount': len(children)
        })

    return {'success': True, 'files': created_files, 'message': f'成功导出 {len(created_files)} 个 .arc 格式章节文件'}


# ==================== Agent Usage (配置绑定) ====================
@agents_router.get('/api/agents/registry')
async def get_registry(user: dict = Depends(get_current_user)):
    """返回所有可用 Agent 的注册信息"""
    from agents.registry import get_agent_registry
    return get_agent_registry()
