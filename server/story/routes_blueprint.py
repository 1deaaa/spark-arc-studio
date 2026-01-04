from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
import os
import json

from core.auth import get_current_user
from core.utils import get_project_path

blueprint_router = APIRouter()

@blueprint_router.get('/api/blueprint/{project_name}')
async def get_blueprint(project_name: str, user: dict = Depends(get_current_user)):
    user_id = str(user['user_id'])
    project_path = get_project_path(user_id, project_name)
    blueprint_path = os.path.join(project_path, 'blueprint.json')
    if os.path.exists(blueprint_path):
        with open(blueprint_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


@blueprint_router.post('/api/blueprint/{project_name}')
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


@blueprint_router.get('/api/bindings/{project_name}')
async def get_bindings(project_name: str, user: dict = Depends(get_current_user)):
    user_id = str(user['user_id'])
    project_path = get_project_path(user_id, project_name)
    bindings_path = os.path.join(project_path, 'bindings.json')
    if os.path.exists(bindings_path):
        with open(bindings_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []


@blueprint_router.post('/api/bindings/{project_name}')
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


@blueprint_router.get('/api/action-bindings/{project_name}')
async def get_action_bindings(project_name: str, user: dict = Depends(get_current_user)):
    user_id = str(user['user_id'])
    project_path = get_project_path(user_id, project_name)
    path = os.path.join(project_path, 'action_bindings.json')
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []


@blueprint_router.post('/api/action-bindings/{project_name}')
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


@blueprint_router.get('/api/registries/{project_name}')
async def get_registries(project_name: str, user: dict = Depends(get_current_user)):
    user_id = str(user['user_id'])
    project_path = get_project_path(user_id, project_name)
    path = os.path.join(project_path, 'registries.json')
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []


@blueprint_router.post('/api/registries/{project_name}')
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