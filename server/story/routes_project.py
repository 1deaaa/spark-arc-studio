from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional
import os
import shutil

from core.auth import get_current_user, get_optional_user
from core.utils import (
    ensure_project_directory,
    ensure_project_stories_directory,
    ensure_project_worldview_and_character_settings,
    get_project_path,
    get_project_stories_path,
    get_user_projects_root,
)

project_router = APIRouter()

class ProjectCreate(BaseModel):
    projectName: str

@project_router.get('/api/projects')
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


@project_router.post('/api/projects')
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

        # 复制示例剧本.arc
        try:
            server_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            template_path = os.path.join(server_root, 'ARC剧本实例.arc')
            if os.path.exists(template_path):
                target_path = os.path.join(get_project_stories_path(user_id, project_name), '示例剧本.arc')
                shutil.copy2(template_path, target_path)
        except Exception as e:
            print(f"复制示例剧本失败: {e}")

        return {"success": True, "message": "项目创建成功"}
    except Exception as exc:
        return JSONResponse(status_code=500, content={"success": False, "message": f"项目创建失败: {exc}"})


@project_router.delete('/api/projects/{project_name}')
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