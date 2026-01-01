"""
Characters API - 角色设定
"""

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
import os
import json

from core.auth import get_current_user
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


@characters_router.get('/api/characters')
async def get_characters(
    projectName: str = Query(None),
    user: dict = Depends(get_current_user),
):
    """获取项目的所有角色列表"""
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
