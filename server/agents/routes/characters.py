"""
Characters API - 角色设定（统一接口）

统一使用 /api/characters 端点，支持 includeContent 参数按需加载内容。
"""

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from typing import Optional
import os
import re

from core.auth import get_current_user, get_optional_user
from core.character_store import (
    delete_character_record,
    next_character_id,
    read_character_records,
    upsert_character,
)
from core.character_relations import (
    create_character_relation,
    delete_character_relation,
    read_character_relations,
    remove_character_relations,
    update_character_relation,
)
from core.request_context import get_current_project_name, resolve_project_name
from core.utils import (
    ensure_project_characters_directory,
    get_project_stories_path,
    is_system_character_id,
)
from story.arc_parser import rename_speaker_markers_in_arc_text

from .schemas import (
    CharacterSettingsCreate, CharacterSettingsSave,
    CharacterSettingsRename, CharacterSettingsDelete,
    CharacterRelationCreate, CharacterRelationUpdate,
)

characters_router = APIRouter()


def _relation_error(exc: Exception) -> JSONResponse:
    status = 409 if "已经存在" in str(exc) else 400
    return JSONResponse(status_code=status, content={"error": str(exc)})


def _validate_arc_speaker_name(name: str) -> Optional[str]:
    """校验角色名能否安全放进 ARC 的 [角色名] 标记。"""
    value = str(name or "").strip()
    if not value:
        return "角色名不能为空"
    if any(ch in value for ch in "[]\r\n"):
        return "角色名不能包含方括号或换行"
    if value in {"旁白", "?"}:
        return "角色名不能使用系统保留说话人"
    if re.fullmatch(r"-?\d+", value):
        return "角色名不能是纯数字"
    return None


def _sync_story_speaker_marker_rename(user_id: str, project_name: str, old_name: str, new_name: str) -> int:
    """同步重命名 ARC 正文中的说话人标记行，只替换 [旧名] 行。"""
    old_name = str(old_name or "").strip()
    new_name = str(new_name or "").strip()
    if not old_name or not new_name or old_name == new_name:
        return 0

    stories_dir = get_project_stories_path(user_id, project_name)
    if not os.path.isdir(stories_dir):
        return 0

    changed_files = 0
    for root, _, files in os.walk(stories_dir):
        for filename in files:
            if not filename.endswith(".arc"):
                continue
            path = os.path.join(root, filename)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    text = f.read()
                updated, replacements = rename_speaker_markers_in_arc_text(text, old_name, new_name)
                if replacements > 0:
                    with open(path, "w", encoding="utf-8") as f:
                        f.write(updated)
                    changed_files += 1
            except Exception:
                continue
    return changed_files


# ==================== 统一接口 ====================

@characters_router.get('/api/characters')
async def get_characters(
    projectName: str = Query(None),
    includeContent: bool = Query(False, description="是否包含角色设定内容"),
    includeSystem: bool = Query(False, description="是否包含旁白、? 等系统保留角色"),
    user: dict = Depends(get_current_user),
):
    """
    获取项目的所有角色列表
    - 默认只返回 id, name, desc
    - includeContent=true 时额外返回 content（用于编辑器）
    """
    user_id = str(user['user_id'])
    project_name = resolve_project_name(get_current_project_name(), projectName)
    if not project_name:
        return JSONResponse(status_code=400, content={'error': '缺少项目名称'})

    ensure_project_characters_directory(user_id, project_name)
    chr_data = read_character_records(user_id, project_name)
    
    characters = []
    for chr_id, info in chr_data.items():
        if not includeSystem and is_system_character_id(chr_id):
            continue
        char = {
            'id': int(chr_id),
            'name': info['name'],
            'desc': ''
        }
        
        if includeContent:
            char['content'] = info['content']
        
        characters.append(char)
    
    return characters


@characters_router.get('/api/characters/{character_id}')
async def get_character_content(
    character_id: int,
    projectName: str = Query(None),
    user: dict = Depends(get_current_user),
):
    """获取单个角色的完整信息（含设定内容）"""
    user_id = str(user['user_id'])
    project_name = resolve_project_name(get_current_project_name(), projectName)
    if not project_name:
        return JSONResponse(status_code=400, content={'error': '缺少项目名称'})

    ensure_project_characters_directory(user_id, project_name)
    chr_data = read_character_records(user_id, project_name)
    chr_id = str(character_id)
    
    if chr_id not in chr_data:
        return JSONResponse(status_code=404, content={'error': '角色不存在'})
    
    name = chr_data[chr_id]['name']
    content = chr_data[chr_id]['content']
    
    return {
        'id': character_id,
        'name': name,
        'desc': '',
        'content': content
    }


@characters_router.post('/api/characters')
async def create_character(
    data: CharacterSettingsCreate,
    user: dict = Depends(get_current_user)
):
    """创建新角色"""
    user_id = str(user['user_id'])
    project_name = resolve_project_name(get_current_project_name(), data.projectName)
    if not project_name:
        return JSONResponse(status_code=400, content={'error': '缺少项目名称'})

    ensure_project_characters_directory(user_id, project_name)
    chr_data = read_character_records(user_id, project_name)
    new_id = next_character_id(chr_data)
    
    name = str(data.name or '新角色').strip()
    validation_error = _validate_arc_speaker_name(name)
    if validation_error:
        return JSONResponse(status_code=400, content={'error': validation_error})
    existing_names = {info['name'] for info in chr_data.values()}
    if name in existing_names:
        return JSONResponse(status_code=409, content={'error': '角色名已存在'})
    upsert_character(
        user_id,
        project_name,
        new_id,
        name=name,
        content=data.content if data.content is not None else f'# {name}\n\n在这里描述你的角色...',
    )
    
    return {'success': True, 'id': new_id, 'name': name}


@characters_router.put('/api/characters')
async def save_character(
    data: CharacterSettingsSave,
    user: dict = Depends(get_current_user)
):
    """保存角色设定内容"""
    user_id = str(user['user_id'])
    project_name = resolve_project_name(get_current_project_name(), data.projectName)
    if not project_name:
        return JSONResponse(status_code=400, content={'error': '缺少项目名称'})

    ensure_project_characters_directory(user_id, project_name)
    if is_system_character_id(data.id):
        return JSONResponse(status_code=403, content={'error': '系统保留角色不能编辑'})
    
    records = read_character_records(user_id, project_name)
    record = records.get(str(data.id))
    if record is None:
        return JSONResponse(status_code=404, content={'error': '角色不存在'})
    upsert_character(
        user_id,
        project_name,
        data.id,
        name=record['name'],
        content=data.content or '',
    )
    
    return {'success': True}


@characters_router.patch('/api/characters/rename')
async def rename_character(
    data: CharacterSettingsRename,
    user: dict = Depends(get_current_user)
):
    """重命名角色"""
    user_id = str(user['user_id'])
    project_name = resolve_project_name(get_current_project_name(), data.projectName)
    if not project_name:
        return JSONResponse(status_code=400, content={'error': '缺少项目名称'})

    ensure_project_characters_directory(user_id, project_name)
    chr_data = read_character_records(user_id, project_name)
    chr_id = str(data.id)
    if is_system_character_id(chr_id):
        return JSONResponse(status_code=403, content={'error': '系统保留角色不能重命名'})
    
    if chr_id not in chr_data:
        return JSONResponse(status_code=404, content={'error': '角色不存在'})
    
    new_name = str(data.newName or "").strip()
    validation_error = _validate_arc_speaker_name(new_name)
    if validation_error:
        return JSONResponse(status_code=400, content={'error': validation_error})
    existing_names = {
        info['name']
        for raw_id, info in chr_data.items()
        if str(raw_id) != chr_id
    }
    if new_name in existing_names:
        return JSONResponse(status_code=409, content={'error': '角色名已存在'})

    old_name = chr_data[chr_id]['name']
    upsert_character(
        user_id,
        project_name,
        chr_id,
        name=new_name,
        content=chr_data[chr_id]['content'],
    )
    updated_files = _sync_story_speaker_marker_rename(user_id, project_name, old_name, new_name)
    
    return {'success': True, 'updatedFiles': updated_files}


@characters_router.delete('/api/characters')
async def delete_character(
    id: int = Query(...),
    projectName: str = Query(None),
    user: dict = Depends(get_current_user),
):
    """删除角色"""
    user_id = str(user['user_id'])
    project_name = resolve_project_name(get_current_project_name(), projectName)
    if not project_name:
        return JSONResponse(status_code=400, content={'error': '缺少项目名称'})

    ensure_project_characters_directory(user_id, project_name)
    chr_id = str(id)
    if is_system_character_id(chr_id):
        return JSONResponse(status_code=403, content={'error': '系统保留角色不能删除'})
    
    delete_character_record(user_id, project_name, chr_id)
    remove_character_relations(user_id, project_name, chr_id)
    
    return {'success': True}


@characters_router.get('/api/character-relations')
async def get_character_relations(
    projectName: str = Query(None),
    user: dict = Depends(get_current_user),
):
    """读取项目中作者手动确认的角色关系。"""
    user_id = str(user['user_id'])
    project_name = resolve_project_name(get_current_project_name(), projectName)
    if not project_name:
        return JSONResponse(status_code=400, content={'error': '缺少项目名称'})
    records = read_character_records(user_id, project_name)
    valid_ids = set(records)
    return [
        item for item in read_character_relations(user_id, project_name)
        if item['source'] in valid_ids and item['target'] in valid_ids
    ]


@characters_router.post('/api/character-relations')
async def post_character_relation(
    data: CharacterRelationCreate,
    user: dict = Depends(get_current_user),
):
    """创建一条作者手动确认的角色关系。"""
    user_id = str(user['user_id'])
    project_name = resolve_project_name(get_current_project_name(), data.projectName)
    if not project_name:
        return JSONResponse(status_code=400, content={'error': '缺少项目名称'})
    try:
        item = create_character_relation(
            user_id, project_name, source=str(data.source), target=str(data.target),
            relation=data.relation, note=data.note,
        )
    except ValueError as exc:
        return _relation_error(exc)
    return {'success': True, 'relation': item}


@characters_router.put('/api/character-relations/{relation_id}')
async def put_character_relation(
    relation_id: str,
    data: CharacterRelationUpdate,
    user: dict = Depends(get_current_user),
):
    """更新一条作者手动确认的角色关系。"""
    user_id = str(user['user_id'])
    project_name = resolve_project_name(get_current_project_name(), data.projectName)
    if not project_name:
        return JSONResponse(status_code=400, content={'error': '缺少项目名称'})
    try:
        item = update_character_relation(
            user_id, project_name, relation_id, source=str(data.source), target=str(data.target),
            relation=data.relation, note=data.note,
        )
    except KeyError as exc:
        return JSONResponse(status_code=404, content={'error': str(exc)})
    except ValueError as exc:
        return _relation_error(exc)
    return {'success': True, 'relation': item}


@characters_router.delete('/api/character-relations/{relation_id}')
async def remove_character_relation(
    relation_id: str,
    projectName: str = Query(None),
    user: dict = Depends(get_current_user),
):
    """删除一条作者手动确认的角色关系。"""
    user_id = str(user['user_id'])
    project_name = resolve_project_name(get_current_project_name(), projectName)
    if not project_name:
        return JSONResponse(status_code=400, content={'error': '缺少项目名称'})
    if not delete_character_relation(user_id, project_name, relation_id):
        return JSONResponse(status_code=404, content={'error': '人工关系不存在'})
    return {'success': True}
