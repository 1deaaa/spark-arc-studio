from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional
import uuid
import os
import shutil

from core.auth import get_current_user
from core.models import UserInfoSession, ProjectVersion
from core.utils import get_project_path
from story.importer import import_project_stories_to_db

version_router = APIRouter()

SERVER_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHARES_DIR = os.path.join(SERVER_ROOT, 'shares_data')

def _get_shares_dir() -> str:
    os.makedirs(SHARES_DIR, exist_ok=True)
    return SHARES_DIR

class VersionCreate(BaseModel):
    versionName: str
    description: Optional[str] = ""

class VersionUpdate(BaseModel):
    versionName: Optional[str] = None
    description: Optional[str] = None
    is_shared: Optional[bool] = None

@version_router.get('/api/versions/{project_name}')
async def list_versions(project_name: str, user: dict = Depends(get_current_user)):
    """列出项目的所有版本"""
    user_id = str(user['user_id'])
    session = UserInfoSession()
    try:
        versions = session.query(ProjectVersion).filter_by(
            user_id=int(user_id),
            project_name=project_name
        ).order_by(ProjectVersion.created_at.desc()).all()
        
        return [
            {
                'id': item.id,
                'version_name': item.version_name,
                'description': item.description,
                'created_at': item.created_at.isoformat(),
                'is_shared': item.is_shared,
                'share_id': item.share_id
            }
            for item in versions
        ]
    finally:
        session.close()


@version_router.post('/api/versions/{project_name}')
async def create_version(project_name: str, data: VersionCreate, user: dict = Depends(get_current_user)):
    """为当前项目创建一个新版本快照"""
    user_id = str(user['user_id'])
    try:
        # 1. 先确保当前项目已同步到 stories.db
        import_project_stories_to_db(user_id, project_name, reset=True)
        
        project_path = get_project_path(user_id, project_name)
        db_path = os.path.join(project_path, 'stories.db')
        if not os.path.exists(db_path):
            return JSONResponse(status_code=404, content={'error': '项目数据库尚未生成'})

        # 2. 复制数据库到快照目录
        version_id = str(uuid.uuid4())
        snapshot_path = os.path.join(_get_shares_dir(), f'ver_{version_id}.db')
        shutil.copy2(db_path, snapshot_path)

        # 3. 记录到数据库
        session = UserInfoSession()
        try:
            version = ProjectVersion(
                id=version_id,
                user_id=int(user_id),
                project_name=project_name,
                version_name=data.versionName,
                description=data.description,
                snapshot_path=snapshot_path,
                is_shared=False
            )
            session.add(version)
            session.commit()
            return {'success': True, 'version_id': version_id}
        except Exception as exc:
            session.rollback()
            return JSONResponse(status_code=500, content={'error': str(exc)})
        finally:
            session.close()
    except Exception as exc:
        return JSONResponse(status_code=500, content={'error': f'创建版本失败: {exc}'})


@version_router.put('/api/versions/{version_id}')
async def update_version(version_id: str, data: VersionUpdate, user: dict = Depends(get_current_user)):
    """更新版本信息或分享状态"""
    user_id = str(user['user_id'])
    session = UserInfoSession()
    try:
        version = session.query(ProjectVersion).filter_by(id=version_id, user_id=int(user_id)).first()
        if not version:
            return JSONResponse(status_code=404, content={'error': '版本不存在'})
            
        if data.versionName is not None:
            version.version_name = data.versionName
        if data.description is not None:
            version.description = data.description
        if data.is_shared is not None:
            version.is_shared = data.is_shared
            if version.is_shared and not version.share_id:
                version.share_id = str(uuid.uuid4())
        
        session.commit()
        return {'success': True}
    except Exception as exc:
        session.rollback()
        return JSONResponse(status_code=500, content={'error': str(exc)})
    finally:
        session.close()


@version_router.delete('/api/versions/{version_id}')
async def delete_version(version_id: str, user: dict = Depends(get_current_user)):
    """删除版本及其快照文件"""
    user_id = str(user['user_id'])
    session = UserInfoSession()
    try:
        version = session.query(ProjectVersion).filter_by(id=version_id, user_id=int(user_id)).first()
        if not version:
            return JSONResponse(status_code=404, content={'error': '版本不存在'})
            
        snapshot_path = version.snapshot_path
        session.delete(version)
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


@version_router.post('/api/versions/{version_id}/restore')
async def restore_version(version_id: str, user: dict = Depends(get_current_user)):
    """从快照恢复版本到当前工作区 (stories.db)"""
    user_id = str(user['user_id'])
    session = UserInfoSession()
    try:
        version = session.query(ProjectVersion).filter_by(id=version_id, user_id=int(user_id)).first()
        if not version:
            return JSONResponse(status_code=404, content={'error': '版本不存在'})
            
        project_path = get_project_path(user_id, version.project_name)
        target_db_path = os.path.join(project_path, 'stories.db')
        
        if os.path.exists(version.snapshot_path):
            shutil.copy2(version.snapshot_path, target_db_path)
            return {'success': True, 'message': f'已成功恢复到版本: {version.version_name}'}
        else:
            return JSONResponse(status_code=404, content={'error': '快照文件已丢失'})
    except Exception as exc:
        return JSONResponse(status_code=500, content={'error': f'恢复版本失败: {exc}'})
    finally:
        session.close()