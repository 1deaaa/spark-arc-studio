"""
Characters API - 角色设定

注意：为保持前端兼容性，保留旧版 /api/character-settings/* 端点
"""

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from typing import Optional
import os
import json

from core.auth import get_current_user, get_optional_user
from core.request_context import current_project_name
from core.utils import (
    get_project_path,
    ensure_project_characters_directory,
)

from .schemas import (
    CharacterSettingsCreate, CharacterSettingsSave,
    CharacterSettingsRename, CharacterSettingsDelete,
)

characters_router = APIRouter()


# ==================== 旧版端点（前端兼容） ====================

@characters_router.get('/api/character-settings/{project_name}')
async def get_character_settings(project_name: str, user: Optional[dict] = Depends(get_optional_user)):
    """获取角色设定列表（旧版端点）"""
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
                        parts = text.split('\n', 2)
                        content = parts[2] if len(parts) >= 3 else (parts[1] if len(parts) == 2 else parts[0])
                result.append({'id': int(cid), 'name': name if isinstance(name, str) else name.get('name', ''), 'content': content})
            except Exception:
                continue
        return result
    except Exception as exc:
        return JSONResponse(status_code=500, content={'error': f'获取角色设定失败: {exc}'})


@characters_router.post('/api/character-settings')
async def create_character_setting(data: CharacterSettingsCreate, user: dict = Depends(get_current_user)):
    """创建新角色（旧版端点）"""
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

        char_file = os.path.join(characters_path, f"{next_id}.txt")
        with open(char_file, 'w', encoding='utf-8') as f:
            f.write(f"{name}\n\n在这里描述你的角色...")

        return {'success': True, 'id': next_id}
    except Exception as exc:
        return JSONResponse(status_code=500, content={'success': False, 'message': str(exc)})


@characters_router.post('/api/character-settings/save')
async def save_character_setting(data: CharacterSettingsSave, user: dict = Depends(get_current_user)):
    """保存角色设定内容（旧版端点）"""
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
        char_file = os.path.join(characters_path, f"{char_id}.txt")
        if os.path.exists(char_file):
            try:
                with open(char_file, 'r', encoding='utf-8') as f:
                    lines = f.read().split('\n', 1)
                    if lines:
                        name = lines[0]
            except Exception:
                pass
        with open(char_file, 'w', encoding='utf-8') as f:
            f.write(f"{name}\n\n{content}")
        return {'success': True}
    except Exception as exc:
        return JSONResponse(status_code=500, content={'success': False, 'message': str(exc)})


@characters_router.post('/api/character-settings/rename')
async def rename_character_setting(data: CharacterSettingsRename, user: dict = Depends(get_current_user)):
    """重命名角色（旧版端点）"""
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


@characters_router.post('/api/character-settings/delete')
async def delete_character_setting(data: CharacterSettingsDelete, user: dict = Depends(get_current_user)):
    """删除角色（旧版端点）"""
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
        char_file = os.path.join(characters_path, f"{char_id}.txt")
        if os.path.exists(char_file):
            os.remove(char_file)
        return {'success': True}
    except Exception as exc:
        return JSONResponse(status_code=500, content={'success': False, 'message': str(exc)})


# ==================== 新版端点 ====================

@characters_router.get('/api/characters')
async def get_characters(
    projectName: str = Query(None),
    user: dict = Depends(get_current_user),
):
    """获取项目的所有角色列表（新版端点）"""
    user_id = str(user['user_id'])
    project_name = current_project_name.get() or projectName
    if not project_name:
        return JSONResponse(status_code=400, content={'error': '缺少项目名称'})

    chr_dir = ensure_project_characters_directory(user_id, project_name)
    bind_file = os.path.join(chr_dir, 'chr.bind')
    
    characters = []
    if os.path.exists(bind_file):
        with open(bind_file, 'r', encoding='utf-8') as f:
            chr_data = json.load(f)
            for chr_id, info in chr_data.items():
                if isinstance(info, dict):
                    characters.append({
                        'id': int(chr_id),
                        'name': info.get('name', ''),
                        'desc': info.get('desc', '')
                    })
                else:
                    characters.append({
                        'id': int(chr_id),
                        'name': str(info),
                        'desc': ''
                    })
    
    return {'success': True, 'characters': characters}




@characters_router.post('/api/characters')
async def create_character(data: CharacterSettingsCreate, user: dict = Depends(get_current_user)):
    """创建新角色"""
    user_id = str(user['user_id'])
    project_name = current_project_name.get() or data.projectName
    if not project_name:
        return JSONResponse(status_code=400, content={'error': '缺少项目名称'})

    chr_dir = ensure_project_characters_directory(user_id, project_name)
    bind_file = os.path.join(chr_dir, 'chr.bind')
    
    chr_data = {}
    if os.path.exists(bind_file):
        with open(bind_file, 'r', encoding='utf-8') as f:
            chr_data = json.load(f)
    
    # 生成新 ID
    max_id = max([int(k) for k in chr_data.keys()], default=0)
    new_id = max_id + 1
    
    chr_data[str(new_id)] = {
        'name': data.name,
        'desc': ''
    }
    
    with open(bind_file, 'w', encoding='utf-8') as f:
        json.dump(chr_data, f, ensure_ascii=False, indent=2)
    
    # 创建角色设定文件
    chr_file = os.path.join(chr_dir, f'{new_id}.md')
    with open(chr_file, 'w', encoding='utf-8') as f:
        f.write(f'# {data.name}\n\n')
    
    return {'success': True, 'id': new_id, 'name': data.name}


@characters_router.put('/api/characters')
async def save_character(data: CharacterSettingsSave, user: dict = Depends(get_current_user)):
    """保存角色设定内容"""
    user_id = str(user['user_id'])
    project_name = current_project_name.get() or data.projectName
    if not project_name:
        return JSONResponse(status_code=400, content={'error': '缺少项目名称'})

    chr_dir = ensure_project_characters_directory(user_id, project_name)
    chr_file = os.path.join(chr_dir, f'{data.id}.md')
    
    with open(chr_file, 'w', encoding='utf-8') as f:
        f.write(data.content)
    
    return {'success': True}


@characters_router.patch('/api/characters/rename')
async def rename_character(data: CharacterSettingsRename, user: dict = Depends(get_current_user)):
    """重命名角色"""
    user_id = str(user['user_id'])
    project_name = current_project_name.get() or data.projectName
    if not project_name:
        return JSONResponse(status_code=400, content={'error': '缺少项目名称'})

    chr_dir = ensure_project_characters_directory(user_id, project_name)
    bind_file = os.path.join(chr_dir, 'chr.bind')
    
    if not os.path.exists(bind_file):
        return JSONResponse(status_code=404, content={'error': '角色不存在'})
    
    with open(bind_file, 'r', encoding='utf-8') as f:
        chr_data = json.load(f)
    
    chr_id = str(data.id)
    if chr_id not in chr_data:
        return JSONResponse(status_code=404, content={'error': '角色不存在'})
    
    if isinstance(chr_data[chr_id], dict):
        chr_data[chr_id]['name'] = data.newName
    else:
        chr_data[chr_id] = {'name': data.newName, 'desc': ''}
    
    with open(bind_file, 'w', encoding='utf-8') as f:
        json.dump(chr_data, f, ensure_ascii=False, indent=2)
    
    return {'success': True}


@characters_router.delete('/api/characters')
async def delete_character(
    id: int = Query(...),
    projectName: str = Query(None),
    user: dict = Depends(get_current_user),
):
    """删除角色"""
    user_id = str(user['user_id'])
    project_name = current_project_name.get() or projectName
    if not project_name:
        return JSONResponse(status_code=400, content={'error': '缺少项目名称'})

    chr_dir = ensure_project_characters_directory(user_id, project_name)
    bind_file = os.path.join(chr_dir, 'chr.bind')
    chr_file = os.path.join(chr_dir, f'{id}.md')
    
    # 从 bind 文件中删除
    if os.path.exists(bind_file):
        with open(bind_file, 'r', encoding='utf-8') as f:
            chr_data = json.load(f)
        
        if str(id) in chr_data:
            del chr_data[str(id)]
            with open(bind_file, 'w', encoding='utf-8') as f:
                json.dump(chr_data, f, ensure_ascii=False, indent=2)
    
    # 删除设定文件
    if os.path.exists(chr_file):
        os.remove(chr_file)
    
    return {'success': True}


@characters_router.get('/api/characters/{character_id}')
async def get_character_content(
    character_id: int,
    projectName: str = Query(None),
    user: dict = Depends(get_current_user),
):
    """获取角色设定内容"""
    user_id = str(user['user_id'])
    project_name = current_project_name.get() or projectName
    if not project_name:
        return JSONResponse(status_code=400, content={'error': '缺少项目名称'})

    chr_dir = ensure_project_characters_directory(user_id, project_name)
    chr_file = os.path.join(chr_dir, f'{character_id}.md')
    
    content = ''
    if os.path.exists(chr_file):
        with open(chr_file, 'r', encoding='utf-8') as f:
            content = f.read()
    
    return {'success': True, 'content': content}


@characters_router.get('/api/characters/{project_name}')
async def get_characters_by_path(
    project_name: str,
    user: dict = Depends(get_current_user),
):
    """获取项目的所有角色列表（兼容路径参数）"""
    return await get_characters(projectName=project_name, user=user)
