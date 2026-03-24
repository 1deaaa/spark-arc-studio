"""
Characters API - 角色设定（统一接口）

统一使用 /api/characters 端点，支持 includeContent 参数按需加载内容。
兼容读取历史 .txt 文件，写入统一使用 .md 格式。
"""

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from typing import Optional
import os
import json

from core.auth import get_current_user, get_optional_user
from core.request_context import get_current_project_name, resolve_project_name
from core.utils import ensure_project_characters_directory

from .schemas import (
    CharacterSettingsCreate, CharacterSettingsSave,
    CharacterSettingsRename, CharacterSettingsDelete,
)

characters_router = APIRouter()


# ==================== 辅助函数 ====================

def _read_character_content(chr_dir: str, char_id: str) -> str:
    """
    兼容读取角色内容：优先 .md，降级 .txt
    读取 .txt 时自动解析 "名字\\n\\n内容" 格式
    """
    md_file = os.path.join(chr_dir, f'{char_id}.md')
    txt_file = os.path.join(chr_dir, f'{char_id}.txt')
    
    if os.path.exists(md_file):
        with open(md_file, 'r', encoding='utf-8') as f:
            return f.read()
    
    if os.path.exists(txt_file):
        with open(txt_file, 'r', encoding='utf-8') as f:
            text = f.read()
        # 旧格式: 名字\n\n内容
        parts = text.split('\n', 2)
        if len(parts) >= 3:
            return parts[2]
        elif len(parts) == 2:
            return parts[1]
        else:
            return parts[0] if parts else ''
    
    return ''


def _write_character_content(chr_dir: str, char_id: str, content: str):
    """
    统一写入角色内容到 .md 文件
    如果存在旧的 .txt 文件，自动删除（完成迁移）
    """
    md_file = os.path.join(chr_dir, f'{char_id}.md')
    txt_file = os.path.join(chr_dir, f'{char_id}.txt')
    
    with open(md_file, 'w', encoding='utf-8') as f:
        f.write(content)
    
    # 迁移：删除旧 .txt 文件
    if os.path.exists(txt_file):
        try:
            os.remove(txt_file)
        except Exception:
            pass


def _delete_character_files(chr_dir: str, char_id: str):
    """删除角色的所有相关文件（.md 和 .txt）"""
    for ext in ('.md', '.txt'):
        file_path = os.path.join(chr_dir, f'{char_id}{ext}')
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass


def _load_bind_file(bind_file: str) -> dict:
    """加载 chr.bind 文件，返回 dict"""
    if not os.path.exists(bind_file):
        return {}
    try:
        with open(bind_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_bind_file(bind_file: str, data: dict):
    """保存 chr.bind 文件"""
    with open(bind_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _normalize_bind_entry(entry) -> dict:
    """将 bind 条目统一为 dict 格式 {name, desc}"""
    if isinstance(entry, dict):
        return {'name': entry.get('name', ''), 'desc': entry.get('desc', '')}
    else:
        return {'name': str(entry), 'desc': ''}


# ==================== 统一接口 ====================

@characters_router.get('/api/characters')
async def get_characters(
    projectName: str = Query(None),
    includeContent: bool = Query(False, description="是否包含角色设定内容"),
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

    chr_dir = ensure_project_characters_directory(user_id, project_name)
    bind_file = os.path.join(chr_dir, 'chr.bind')
    
    chr_data = _load_bind_file(bind_file)
    
    characters = []
    for chr_id, info in chr_data.items():
        entry = _normalize_bind_entry(info)
        char = {
            'id': int(chr_id),
            'name': entry['name'],
            'desc': entry['desc']
        }
        
        if includeContent:
            char['content'] = _read_character_content(chr_dir, chr_id)
        
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

    chr_dir = ensure_project_characters_directory(user_id, project_name)
    bind_file = os.path.join(chr_dir, 'chr.bind')
    
    chr_data = _load_bind_file(bind_file)
    chr_id = str(character_id)
    
    if chr_id not in chr_data:
        return JSONResponse(status_code=404, content={'error': '角色不存在'})
    
    entry = _normalize_bind_entry(chr_data[chr_id])
    content = _read_character_content(chr_dir, chr_id)
    
    return {
        'id': character_id,
        'name': entry['name'],
        'desc': entry['desc'],
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

    chr_dir = ensure_project_characters_directory(user_id, project_name)
    bind_file = os.path.join(chr_dir, 'chr.bind')
    
    chr_data = _load_bind_file(bind_file)
    
    # 生成新 ID（找最大值 + 1）
    existing_ids = [int(k) for k in chr_data.keys()] if chr_data else []
    new_id = max(existing_ids, default=-1) + 1
    
    name = data.name or '新角色'
    chr_data[str(new_id)] = {'name': name, 'desc': ''}
    
    _save_bind_file(bind_file, chr_data)
    
    # 创建角色设定文件（.md）
    _write_character_content(chr_dir, str(new_id), f'# {name}\n\n在这里描述你的角色...')
    
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

    chr_dir = ensure_project_characters_directory(user_id, project_name)
    
    _write_character_content(chr_dir, str(data.id), data.content or '')
    
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

    chr_dir = ensure_project_characters_directory(user_id, project_name)
    bind_file = os.path.join(chr_dir, 'chr.bind')
    
    chr_data = _load_bind_file(bind_file)
    chr_id = str(data.id)
    
    if chr_id not in chr_data:
        return JSONResponse(status_code=404, content={'error': '角色不存在'})
    
    entry = _normalize_bind_entry(chr_data[chr_id])
    entry['name'] = data.newName
    chr_data[chr_id] = entry
    
    _save_bind_file(bind_file, chr_data)
    
    return {'success': True}


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

    chr_dir = ensure_project_characters_directory(user_id, project_name)
    bind_file = os.path.join(chr_dir, 'chr.bind')
    chr_id = str(id)
    
    # 从 bind 文件中删除
    chr_data = _load_bind_file(bind_file)
    if chr_id in chr_data:
        del chr_data[chr_id]
        _save_bind_file(bind_file, chr_data)
    
    # 删除设定文件（.md 和 .txt）
    _delete_character_files(chr_dir, chr_id)
    
    return {'success': True}
