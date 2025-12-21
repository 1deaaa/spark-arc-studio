"""Story 路由模块 - FastAPI 版本

整合所有 story 相关的路由：
- 项目管理
- 文件操作
- 角色管理
- 蓝图管理
- 分享功能
"""

from fastapi import APIRouter, Depends, Request, UploadFile, File, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid
import os
import json
import shutil

from core.auth import get_current_user, get_optional_user
from core.utils import (
    ensure_project_directory,
    ensure_project_stories_directory,
    ensure_project_characters_directory,
    ensure_project_worldview_and_character_settings,
    get_project_path,
    get_project_stories_path,
    get_project_characters_path,
    get_project_synopsis_path,
    get_project_beats_path,
    get_user_projects_root,
    strip_private_fields,
)
from story.importer import import_project_stories_to_db
from core.models import UserInfoSession, Share, Story, BindChr, Registry
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# 创建主路由器
story_router = APIRouter()


def _get_shares_dir() -> str:
    os.makedirs(SHARES_DIR, exist_ok=True)
    return SHARES_DIR
SERVER_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHARES_DIR = os.path.join(SERVER_ROOT, 'shares_data')


# ==================== Pydantic Models ====================
class ProjectCreate(BaseModel):
    projectName: str


class FileOperation(BaseModel):
    projectName: str
    path: str
    type: Optional[str] = None
    sourcePath: Optional[str] = None
    targetPath: Optional[str] = None
    oldPath: Optional[str] = None
    newPath: Optional[str] = None


class StoryData(BaseModel):
    projectName: str
    filename: str
    data: Any


class CharacterCreate(BaseModel):
    name: str = "新角色"


class CharacterRename(BaseModel):
    name: str


class CharacterContent(BaseModel):
    content: str


class SaveOrder(BaseModel):
    projectName: str
    dirPath: str = ""
    order: List[str]


class ShareCreate(BaseModel):
    projectName: str
    title: str
    description: Optional[str] = ""
    is_shared: bool = False


class ShareUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    is_shared: Optional[bool] = None


# ==================== 项目管理 ====================
@story_router.get('/api/projects')
async def get_projects(user: Optional[dict] = Depends(get_optional_user)):
    """列出当前用户的所有项目"""
    try:
        if not user:
            return []
        user_id = str(user['user_id'])
        projects_root = get_user_projects_root(user_id)
        if not os.path.exists(projects_root):
            os.makedirs(projects_root)
            return []
        projects = [
            name for name in os.listdir(projects_root)
            if os.path.isdir(os.path.join(projects_root, name))
        ]
        return sorted(projects)
    except Exception as exc:
        return JSONResponse(status_code=500, content={"success": False, "message": f"获取项目列表失败: {exc}"})


@story_router.post('/api/projects')
async def create_project(data: ProjectCreate, user: dict = Depends(get_current_user)):
    """创建新项目并初始化目录结构"""
    try:
        user_id = str(user['user_id'])
        project_name = data.projectName
        if not project_name:
            return JSONResponse(status_code=400, content={"success": False, "message": "项目名称不能为空"})

        project_path = get_project_path(user_id, project_name)
        if os.path.exists(project_path):
            return JSONResponse(status_code=409, content={"success": False, "message": "项目已存在"})

        ensure_project_directory(user_id, project_name)
        ensure_project_stories_directory(user_id, project_name)
        ensure_project_worldview_and_character_settings(user_id, project_name)
        return {"success": True, "message": "项目创建成功"}
    except Exception as exc:
        return JSONResponse(status_code=500, content={"success": False, "message": f"项目创建失败: {exc}"})


@story_router.delete('/api/projects/{project_name}')
async def delete_project(project_name: str, user: dict = Depends(get_current_user)):
    """删除指定项目"""
    try:
        user_id = str(user['user_id'])
        project_path = get_project_path(user_id, project_name)
        if not os.path.exists(project_path):
            return JSONResponse(status_code=404, content={"success": False, "message": "项目不存在"})
        shutil.rmtree(project_path)
        return {"success": True, "message": "项目删除成功"}
    except Exception as exc:
        return JSONResponse(status_code=500, content={"success": False, "message": f"项目删除失败: {exc}"})


# ==================== 文件列表 ====================
@story_router.get('/api/story-files/{project_name}')
async def get_story_files(project_name: str, user: Optional[dict] = Depends(get_optional_user)):
    """返回用户项目 stories 目录下的文件树结构"""
    try:
        if not user:
            return []
        user_id = str(user['user_id'])
        stories_path = ensure_project_stories_directory(user_id, project_name)

        order_file = os.path.join(get_project_path(user_id, project_name), 'stories_order.json')
        order_map = {}
        if os.path.exists(order_file):
            try:
                with open(order_file, 'r', encoding='utf-8') as f:
                    order_map = json.load(f) or {}
            except Exception:
                order_map = {}

        def reorder_by_user_order(items_list, dir_rel_path):
            order = order_map.get(dir_rel_path or '')
            if not order or not isinstance(order, list):
                return items_list
            index_map = {name: idx for idx, name in enumerate(order)}
            def key_fn(entry):
                name = entry.get('name', '')
                return (0 if name in index_map else 1, index_map.get(name, 0))
            return sorted(items_list, key=key_fn)

        def scan_directory(path, relative_path=''):
            folders = []
            files = []
            if not os.path.exists(path):
                return []

            for item in os.listdir(path):
                if item.startswith('.'):
                    continue
                item_path = os.path.join(path, item)
                if os.path.isdir(item_path):
                    rel_dir = os.path.join(relative_path, item) if relative_path else item
                    web_dir = rel_dir.replace(os.sep, '/')
                    children = scan_directory(item_path, rel_dir)
                    folders.append({
                        'name': item,
                        'type': 'folder',
                        'path': web_dir,
                        'children': children,
                    })
                elif os.path.isfile(item_path) and (item.endswith('.story') or item.endswith('.arc')):
                    if item.endswith('.story'):
                        name = item[:-6]
                        file_type = 'story'
                    else:
                        name = item[:-4]
                        file_type = 'arc'
                    rel = os.path.join(relative_path, name) if relative_path else name
                    web_path = rel.replace(os.sep, '/')
                    scene_count = 0
                    try:
                        if file_type == 'story':
                            with open(item_path, 'r', encoding='utf-8') as f:
                                story_data = json.load(f)
                                if isinstance(story_data, list):
                                    scene_count = len(story_data)
                        else:
                            with open(item_path, 'r', encoding='utf-8') as f:
                                content = f.read()
                                scene_count = len([line for line in content.split('\n') if line.strip().startswith('# ')])
                    except Exception:
                        scene_count = 0
                    files.append({
                        'name': name,
                        'type': 'story',
                        'path': web_path,
                        'sceneCount': scene_count,
                        'format': file_type,
                    })

            folders_sorted = reorder_by_user_order(folders, relative_path)
            files_sorted = reorder_by_user_order(files, relative_path)
            return folders_sorted + files_sorted

        return scan_directory(stories_path)
    except Exception as exc:
        print(f"获取 JSON 文件列表失败: {exc}")
        return []


# ==================== 文件内容 ====================
@story_router.get('/api/file-content/{project_name}/{path:path}')
async def get_file_content(project_name: str, path: str, user: Optional[dict] = Depends(get_optional_user)):
    """获取 .story 或 .arc 文件的内容"""
    try:
        if not user:
            return JSONResponse(status_code=401, content={"error": "需要登录"})
        user_id = str(user['user_id'])
        stories_path = get_project_stories_path(user_id, project_name)
        
        file_path = os.path.join(stories_path, path)
        
        arc_path = file_path if file_path.endswith('.arc') else file_path + '.arc'
        if os.path.exists(arc_path):
            with open(arc_path, 'r', encoding='utf-8') as f:
                content = f.read()
            return content
        
        story_path = file_path if file_path.endswith('.story') else file_path + '.story'
        if os.path.exists(story_path):
            with open(story_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data
        
        return JSONResponse(status_code=404, content={"error": "文件不存在"})
    except Exception as exc:
        return JSONResponse(status_code=500, content={"error": f"读取文件失败: {exc}"})


@story_router.post('/api/save-story')
async def save_story(data: StoryData, user: dict = Depends(get_current_user)):
    """保存 stories 目录下的 .story 文件"""
    try:
        user_id = str(user['user_id'])
        project_name = data.projectName
        filename = data.filename
        story_data = data.data

        if not project_name:
            return JSONResponse(status_code=400, content={"success": False, "message": "缺少项目名称"})
        if not filename:
            return JSONResponse(status_code=400, content={"success": False, "message": "文件名不能为空"})

        stories_path = ensure_project_stories_directory(user_id, project_name)
        file_path = os.path.join(stories_path, filename)
        if not file_path.endswith('.story'):
            file_path += '.story'

        strip_private_fields(story_data)
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(story_data, f, ensure_ascii=False, indent=2)

        return {"success": True, "message": "保存成功"}
    except Exception as exc:
        return JSONResponse(status_code=500, content={"success": False, "message": f"保存失败: {exc}"})


# ==================== 文件操作 ====================
@story_router.post('/api/file-operations/create')
async def create_file_or_folder(data: FileOperation, user: dict = Depends(get_current_user)):
    """创建文件或文件夹"""
    try:
        user_id = str(user['user_id'])
        project_name = data.projectName
        if not project_name:
            return JSONResponse(status_code=400, content={"success": False, "message": "缺少项目名称"})

        stories_path = ensure_project_stories_directory(user_id, project_name)
        file_type = data.type
        file_path = os.path.join(stories_path, data.path)

        if file_type == 'folder':
            os.makedirs(file_path, exist_ok=True)
        else:
            if not file_path.endswith('.story') and not file_path.endswith('.txt'):
                file_path += '.story'
            if os.path.exists(file_path):
                return JSONResponse(status_code=409, content={"success": False, "message": f"文件 '{os.path.basename(file_path)}' 已存在"})
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            if file_path.endswith('.story'):
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump([], f, ensure_ascii=False, indent=2)
            elif file_path.endswith('.txt'):
                with open(file_path, 'w', encoding='utf-8') as f:
                    pass

        return {"success": True, "message": "创建成功"}
    except Exception as exc:
        return JSONResponse(status_code=500, content={"success": False, "message": f"创建失败: {exc}"})


@story_router.post('/api/file-operations/delete')
async def delete_file_or_folder(data: FileOperation, user: dict = Depends(get_current_user)):
    """删除文件或文件夹"""
    try:
        user_id = str(user['user_id'])
        project_name = data.projectName
        if not project_name:
            return JSONResponse(status_code=400, content={"success": False, "message": "缺少项目名称"})

        stories_path = ensure_project_stories_directory(user_id, project_name)
        file_path = os.path.join(stories_path, data.path)

        if os.path.isdir(file_path):
            shutil.rmtree(file_path)
            return {"success": True, "message": "删除成功"}

        # 尝试文件的 .story 或 .arc 扩展名
        if os.path.exists(file_path):
            os.remove(file_path)
            return {"success": True, "message": "删除成功"}

        arc_path = file_path if file_path.endswith('.arc') else file_path + '.arc'
        story_path = file_path if file_path.endswith('.story') else file_path + '.story'
        txt_path = file_path if file_path.endswith('.txt') else file_path + '.txt'

        if os.path.exists(arc_path):
            os.remove(arc_path)
            return {"success": True, "message": "删除成功"}
        if os.path.exists(story_path):
            os.remove(story_path)
            return {"success": True, "message": "删除成功"}
        if os.path.exists(txt_path):
            os.remove(txt_path)
            return {"success": True, "message": "删除成功"}

        return JSONResponse(status_code=404, content={"success": False, "message": "文件或文件夹不存在"})
    except Exception as exc:
        return JSONResponse(status_code=500, content={"success": False, "message": f"删除失败: {exc}"})


@story_router.post('/api/file-operations/move')
async def move_file_or_folder(data: FileOperation, user: dict = Depends(get_current_user)):
    """移动或移动重命名文件/文件夹"""
    try:
        user_id = str(user['user_id'])
        project_name = data.projectName
        source = data.sourcePath
        target = data.targetPath
        if not project_name or not source or not target:
            return JSONResponse(status_code=400, content={"success": False, "message": "缺少参数"})

        stories_path = ensure_project_stories_directory(user_id, project_name)
        source_path = os.path.join(stories_path, source)
        target_path = os.path.join(stories_path, target)

        target_dir = os.path.dirname(target_path)
        if target_dir:
            os.makedirs(target_dir, exist_ok=True)
        shutil.move(source_path, target_path)
        return {"success": True, "message": "移动成功"}
    except Exception as exc:
        return JSONResponse(status_code=500, content={"success": False, "message": f"移动失败: {exc}"})


@story_router.post('/api/file-operations/rename')
async def rename_file_or_folder(data: FileOperation, user: dict = Depends(get_current_user)):
    try:
        user_id = str(user['user_id'])
        project_name = data.projectName
        old_path = data.sourcePath or data.oldPath or data.path or getattr(data, 'source', None)
        new_path = data.targetPath or data.newPath or getattr(data, 'target', None)
        if not project_name or not old_path or not new_path:
            return JSONResponse(status_code=400, content={"success": False, "message": "缺少参数"})

        stories_path = ensure_project_stories_directory(user_id, project_name)
        source_path = os.path.join(stories_path, old_path)
        target_path = os.path.join(stories_path, new_path)
        target_dir = os.path.dirname(target_path)
        if target_dir:
            os.makedirs(target_dir, exist_ok=True)
        shutil.move(source_path, target_path)
        return {"success": True, "message": "重命名成功"}
    except Exception as exc:
        return JSONResponse(status_code=500, content={"success": False, "message": f"重命名失败: {exc}"})


@story_router.post('/api/file-operations/save-order')
async def save_stories_order(data: SaveOrder, user: dict = Depends(get_current_user)):
    try:
        user_id = str(user['user_id'])
        project_name = data.projectName
        dir_path = data.dirPath or ''
        order = data.order or []
        if not project_name:
            return JSONResponse(status_code=400, content={"success": False, "message": "缺少项目名称"})

        project_path = get_project_path(user_id, project_name)
        order_file = os.path.join(project_path, 'stories_order.json')
        orders = {}
        if os.path.exists(order_file):
            try:
                with open(order_file, 'r', encoding='utf-8') as f:
                    orders = json.load(f) or {}
            except Exception:
                orders = {}
        orders[dir_path or ''] = order
        with open(order_file, 'w', encoding='utf-8') as f:
            json.dump(orders, f, ensure_ascii=False, indent=2)
        return {"success": True, "message": "排序保存成功"}
    except Exception as exc:
        return JSONResponse(status_code=500, content={"success": False, "message": f"保存排序失败: {exc}"})


# ==================== 角色管理 ====================
@story_router.get('/api/characters/{project_name}')
async def get_characters(project_name: str, user: Optional[dict] = Depends(get_optional_user)):
    """获取项目的角色列表"""
    try:
        if not user:
            return []
        user_id = str(user['user_id'])
        characters_path = get_project_characters_path(user_id, project_name)
        mapping_file = os.path.join(characters_path, 'chr.bind')
        if not os.path.exists(mapping_file):
            return []
        with open(mapping_file, 'r', encoding='utf-8') as f:
            char_map = json.load(f)
        # 强制将id为-1的角色名字显示为"旁白"（用于前端显示）
        characters = []
        for cid, name in char_map.items():
            char_id = int(cid)
            # 对于id为-1的旁白角色，前端显示时使用"旁白"
            display_name = "旁白" if char_id == -1 else name
            characters.append({'id': char_id, 'name': display_name})
        characters.sort(key=lambda item: item['id'])
        return characters
    except Exception as exc:
        return JSONResponse(status_code=500, content={'error': f'获取角色列表失败: {exc}'})


@story_router.get('/api/characters/{project_name}/{character_id}')
async def get_character(project_name: str, character_id: int, user: Optional[dict] = Depends(get_optional_user)):
    """获取指定角色内容"""
    try:
        if not user:
            return JSONResponse(status_code=401, content={'error': '需要登录'})
        user_id = str(user['user_id'])
        characters_path = get_project_characters_path(user_id, project_name)
        character_file = os.path.join(characters_path, f"{character_id}.txt")
        if not os.path.exists(character_file):
            return JSONResponse(status_code=404, content={'error': '角色不存在'})
        with open(character_file, 'r', encoding='utf-8') as f:
            content = f.read()
        return {'content': content}
    except Exception as exc:
        return JSONResponse(status_code=500, content={'error': f'读取角色失败: {exc}'})


@story_router.post('/api/characters/{project_name}')
async def create_character(project_name: str, data: CharacterCreate, user: dict = Depends(get_current_user)):
    """创建新角色并返回其 ID"""
    try:
        user_id = str(user['user_id'])
        name = data.name
        characters_path = ensure_project_characters_directory(user_id, project_name)
        
        mapping_file = os.path.join(characters_path, 'chr.bind')
        char_map = {}
        if os.path.exists(mapping_file):
            with open(mapping_file, 'r', encoding='utf-8') as f:
                try:
                    char_map = json.load(f)
                except json.JSONDecodeError:
                    pass
        
        existing_ids = {int(k) for k in char_map.keys()}
        next_id = 0
        while next_id in existing_ids:
            next_id += 1
        
        char_map[str(next_id)] = name
        with open(mapping_file, 'w', encoding='utf-8') as f:
            json.dump(char_map, f, ensure_ascii=False, indent=2)
        
        character_file = os.path.join(characters_path, f"{next_id}.txt")
        with open(character_file, 'w', encoding='utf-8') as f:
            f.write(f"{name}\n\n在这里描述你的角色...")
        
        return {'success': True, 'message': '角色创建成功', 'id': next_id}
    except Exception as exc:
        return JSONResponse(status_code=500, content={'success': False, 'message': f'角色创建失败: {exc}'})


# ==================== 分享快照 ====================
@story_router.get('/api/shares')
async def list_shares(
    project_name: Optional[str] = Query(None),
    is_shared: Optional[bool] = Query(None),
    user: dict = Depends(get_current_user)
):
    user_id = str(user['user_id'])
    session = UserInfoSession()
    try:
        query = session.query(Share).filter_by(user_id=int(user_id))
        if project_name:
            query = query.filter_by(project_name=project_name)
        if is_shared is not None:
            query = query.filter_by(is_shared=is_shared)
        records = query.order_by(Share.created_at.desc()).all()
        return [
            {
                'id': item.id,
                'project_name': item.project_name,
                'title': item.title,
                'description': item.description,
                'is_shared': item.is_shared,
                'is_active': item.is_active,
                'created_at': item.created_at.isoformat() if item.created_at else None,
            }
            for item in records
        ]
    finally:
        session.close()


@story_router.post('/api/shares')
async def create_share(data: ShareCreate, user: dict = Depends(get_current_user)):
    user_id = str(user['user_id'])
    project_name = data.projectName
    if not project_name:
        return JSONResponse(status_code=400, content={'error': '缺少项目名'})

    try:
        import_project_stories_to_db(user_id, project_name, reset=True)
    except Exception as exc:
        return JSONResponse(status_code=500, content={'error': f'同步项目失败: {exc}'})

    project_path = get_project_path(user_id, project_name)
    db_path = os.path.join(project_path, 'stories.db')
    if not os.path.exists(db_path):
        return JSONResponse(status_code=404, content={'error': 'stories.db 不存在'})

    share_id = str(uuid.uuid4())
    snapshot_path = os.path.join(_get_shares_dir(), f'{share_id}.db')
    try:
        shutil.copy2(db_path, snapshot_path)
    except Exception as exc:
        return JSONResponse(status_code=500, content={'error': f'写入快照失败: {exc}'})

    session = UserInfoSession()
    try:
        share = Share(
            id=share_id,
            user_id=int(user_id),
            project_name=project_name,
            title=data.title,
            description=data.description,
            snapshot_path=snapshot_path,
            is_shared=data.is_shared,
            is_active=True,
        )
        session.add(share)
        session.commit()
        return {'success': True, 'share_id': share_id}
    except Exception as exc:
        session.rollback()
        return JSONResponse(status_code=500, content={'error': str(exc)})
    finally:
        session.close()


@story_router.put('/api/shares/{share_id}')
async def update_share(share_id: str, data: ShareUpdate, user: dict = Depends(get_current_user)):
    user_id = str(user['user_id'])
    session = UserInfoSession()
    try:
        share = session.query(Share).filter_by(id=share_id, user_id=int(user_id)).first()
        if not share:
            return JSONResponse(status_code=404, content={'error': '分享不存在'})
        if data.title is not None:
            share.title = data.title
        if data.description is not None:
            share.description = data.description
        if data.is_shared is not None:
            share.is_shared = data.is_shared
        session.commit()
        return {'success': True}
    except Exception as exc:
        session.rollback()
        return JSONResponse(status_code=500, content={'error': str(exc)})
    finally:
        session.close()


@story_router.delete('/api/shares/{share_id}')
async def delete_share(share_id: str, user: dict = Depends(get_current_user)):
    user_id = str(user['user_id'])
    session = UserInfoSession()
    try:
        share = session.query(Share).filter_by(id=share_id, user_id=int(user_id)).first()
        if not share:
            return JSONResponse(status_code=404, content={'error': '分享不存在'})
        snapshot_path = share.snapshot_path
        session.delete(share)
        session.commit()
        if snapshot_path and os.path.exists(snapshot_path):
            try:
                os.remove(snapshot_path)
            except OSError:
                pass
        return {'success': True}
    except Exception as exc:
        session.rollback()
        return JSONResponse(status_code=500, content={'error': str(exc)})
    finally:
        session.close()


@story_router.get('/api/play/{share_id}/info')
async def get_share_info(share_id: str):
    session = UserInfoSession()
    try:
        share = session.query(Share).filter_by(id=share_id, is_active=True, is_shared=True).first()
        if not share:
            return JSONResponse(status_code=404, content={'error': '分享不存在或未公开'})
        return {
            'title': share.title,
            'description': share.description,
            'created_at': share.created_at.isoformat() if share.created_at else None,
            'author': share.user.username if getattr(share, 'user', None) else 'unknown',
            'project_name': share.project_name,
        }
    finally:
        session.close()


@story_router.get('/api/play/{share_id}/data')
async def get_share_data(share_id: str):
    session = UserInfoSession()
    try:
        share = session.query(Share).filter_by(id=share_id, is_active=True, is_shared=True).first()
    finally:
        session.close()

    if not share or not share.snapshot_path or not os.path.exists(share.snapshot_path):
        return JSONResponse(status_code=404, content={'error': '分享不存在或数据缺失'})

    engine = create_engine(f'sqlite:///{share.snapshot_path}', echo=False)
    SnapshotSession = sessionmaker(bind=engine)
    snapshot_session = SnapshotSession()
    try:
        stories = snapshot_session.query(Story).order_by(Story.chapter, Story.progress, Story.id).all()
        characters = snapshot_session.query(BindChr).all()
        registry_items = snapshot_session.query(Registry).all()

        story_list = [
            {
                'id': item.id,
                'chapter': item.chapter,
                'scene_name': item.scene_name,
                'caption': item.caption,
                'dlg': item.dlg_json,
                'button_text': item.button_text,
                'conditions': item.conditions,
                'hidden': item.hiden,
            }
            for item in stories
        ]
        char_map = {c.chr_id: c.chr_name for c in characters}
        registry = {r.name: r.value for r in registry_items}
        return {
            'stories': story_list,
            'characters': char_map,
            'registry': registry,
        }
    except Exception as exc:
        return JSONResponse(status_code=500, content={'error': f'读取快照失败: {exc}'})
    finally:
        snapshot_session.close()
        engine.dispose()


# ==================== 蓝图、绑定、注册表 ====================
@story_router.get('/api/blueprint/{project_name}')
async def get_blueprint(project_name: str, user: dict = Depends(get_current_user)):
    user_id = str(user['user_id'])
    project_path = get_project_path(user_id, project_name)
    blueprint_path = os.path.join(project_path, 'blueprint.json')
    if os.path.exists(blueprint_path):
        with open(blueprint_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


@story_router.post('/api/blueprint/{project_name}')
async def save_blueprint(project_name: str, request: Request, user: dict = Depends(get_current_user)):
    user_id = str(user['user_id'])
    data = await request.json()
    project_path = get_project_path(user_id, project_name)
    blueprint_path = os.path.join(project_path, 'blueprint.json')
    try:
        with open(blueprint_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return {"success": True, "message": "蓝图已保存"}
    except Exception as exc:
        return JSONResponse(status_code=500, content={"success": False, "message": f"保存蓝图失败: {exc}"})


@story_router.get('/api/bindings/{project_name}')
async def get_bindings(project_name: str, user: dict = Depends(get_current_user)):
    user_id = str(user['user_id'])
    project_path = get_project_path(user_id, project_name)
    bindings_path = os.path.join(project_path, 'bindings.json')
    if os.path.exists(bindings_path):
        with open(bindings_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []


@story_router.post('/api/bindings/{project_name}')
async def save_bindings(project_name: str, request: Request, user: dict = Depends(get_current_user)):
    user_id = str(user['user_id'])
    data = await request.json()
    project_path = get_project_path(user_id, project_name)
    bindings_path = os.path.join(project_path, 'bindings.json')
    try:
        with open(bindings_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return {"success": True}
    except Exception as exc:
        return JSONResponse(status_code=500, content={"success": False, "message": str(exc)})


@story_router.get('/api/action-bindings/{project_name}')
async def get_action_bindings(project_name: str, user: dict = Depends(get_current_user)):
    user_id = str(user['user_id'])
    project_path = get_project_path(user_id, project_name)
    path = os.path.join(project_path, 'action_bindings.json')
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []


@story_router.post('/api/action-bindings/{project_name}')
async def save_action_bindings(project_name: str, request: Request, user: dict = Depends(get_current_user)):
    user_id = str(user['user_id'])
    data = await request.json()
    project_path = get_project_path(user_id, project_name)
    path = os.path.join(project_path, 'action_bindings.json')
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return {"success": True}
    except Exception as exc:
        return JSONResponse(status_code=500, content={"success": False, "message": str(exc)})


@story_router.get('/api/registries/{project_name}')
async def get_registries(project_name: str, user: dict = Depends(get_current_user)):
    user_id = str(user['user_id'])
    project_path = get_project_path(user_id, project_name)
    path = os.path.join(project_path, 'registries.json')
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []


@story_router.post('/api/registries/{project_name}')
async def save_registries(project_name: str, request: Request, user: dict = Depends(get_current_user)):
    user_id = str(user['user_id'])
    data = await request.json()
    project_path = get_project_path(user_id, project_name)
    path = os.path.join(project_path, 'registries.json')
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return {"success": True}
    except Exception as exc:
        return JSONResponse(status_code=500, content={"success": False, "message": str(exc)})


# ==================== 示例剧本 ====================
@story_router.get('/剧本示例.story')
async def get_dialogue_data(user: Optional[dict] = Depends(get_optional_user)):
    """读取示例剧本文件"""
    try:
        server_root = os.path.dirname(os.path.abspath(__file__))
        file_path = os.path.join(os.path.dirname(server_root), '剧本示例.story')
        
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data
        return ""
    except Exception as exc:
        print(f"加载剧本示例.story 出错: {exc}")
        return ""


@story_router.post('/save')
async def save_dialogue(request: Request, user: Optional[dict] = Depends(get_optional_user)):
    """保存示例剧本文件内容"""
    try:
        data = await request.json()
        server_root = os.path.dirname(os.path.abspath(__file__))
        file_path = os.path.join(os.path.dirname(server_root), '剧本示例.story')
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return {"success": True, "message": "保存成功"}
    except Exception as exc:
        return JSONResponse(status_code=500, content={"success": False, "message": f"保存失败: {exc}"})
