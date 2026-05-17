from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional
import uuid
import os
import shutil

from core.auth import get_current_user, user_db
from core.compliance_features import is_force_public_share_review_effective
from core.request_context import normalize_project_name
from core.models import UserInfoSession, Share, ProjectVersion, Story, BindChr, Registry
from core.utils import get_project_path
from core.system_settings import get_disable_public_share
from story.public_share_review import (
    PublicShareReviewRejectedError,
    ensure_public_share_allowed,
)
from story.importer import import_project_stories_to_db
from story.routes_version import _decode_version_description
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

share_router = APIRouter()

SERVER_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHARES_DIR = os.path.join(SERVER_ROOT, 'shares_data')

def _get_shares_dir() -> str:
    os.makedirs(SHARES_DIR, exist_ok=True)
    return SHARES_DIR


def _get_optional_current_user(request: Request):
    token = request.headers.get('X-Session-Token') or request.cookies.get('session_token')
    if not token:
        return None

    ok, info = user_db.verify_session(token)
    return info if ok else None


def _is_owner(owner_user_id: int, current_user: Optional[dict]) -> bool:
    return bool(current_user and str(current_user.get('user_id')) == str(owner_user_id))


def _can_access_share(share: Share, current_user: Optional[dict]) -> bool:
    if share.is_shared and not get_disable_public_share():
        return True
    return _is_owner(share.user_id, current_user)


def _can_access_version(version: ProjectVersion, current_user: Optional[dict]) -> bool:
    if version.is_shared and not get_disable_public_share():
        return True
    return _is_owner(version.user_id, current_user)

class ShareCreate(BaseModel):
    projectName: str
    title: str
    description: Optional[str] = ""
    is_shared: bool = False

class ShareUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    is_shared: Optional[bool] = None

@share_router.get('/api/shares')
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


@share_router.post('/api/shares')
async def create_share(data: ShareCreate, user: dict = Depends(get_current_user)):
    user_id = str(user['user_id'])
    project_name = normalize_project_name(data.projectName)
    if not project_name:
        return JSONResponse(status_code=400, content={'error': '缺少项目名'})

    if data.is_shared and get_disable_public_share():
        return JSONResponse(status_code=403, content={'error': '管理员已禁用公开分享'})

    if data.is_shared and is_force_public_share_review_effective():
        try:
            ensure_public_share_allowed(user_id, project_name, 'script')
        except PublicShareReviewRejectedError as exc:
            return JSONResponse(
                status_code=403,
                content={
                    'error': f'公开前审核未通过：{exc.result.reason}',
                    'review': {
                        'decision': exc.result.decision,
                        'reason': exc.result.reason,
                        'risk_tags': exc.result.risk_tags,
                        'evidence': exc.result.evidence,
                        'rejected_chunk_index': exc.result.rejected_chunk_index,
                        'total_chunks': exc.result.total_chunks,
                    },
                },
            )
        except Exception as exc:
            return JSONResponse(status_code=503, content={'error': f'公开前审核失败：{exc}'})

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


@share_router.put('/api/shares/{share_id}')
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
            if data.is_shared and get_disable_public_share():
                return JSONResponse(status_code=403, content={'error': '管理员已禁用公开分享'})
            if data.is_shared and not share.is_shared and is_force_public_share_review_effective():
                try:
                    ensure_public_share_allowed(user_id, share.project_name, 'script')
                except PublicShareReviewRejectedError as exc:
                    return JSONResponse(
                        status_code=403,
                        content={
                            'error': f'公开前审核未通过：{exc.result.reason}',
                            'review': {
                                'decision': exc.result.decision,
                                'reason': exc.result.reason,
                                'risk_tags': exc.result.risk_tags,
                                'evidence': exc.result.evidence,
                                'rejected_chunk_index': exc.result.rejected_chunk_index,
                                'total_chunks': exc.result.total_chunks,
                            },
                        },
                    )
                except Exception as exc:
                    return JSONResponse(status_code=503, content={'error': f'公开前审核失败：{exc}'})
            share.is_shared = data.is_shared
        session.commit()
        return {'success': True}
    except Exception as exc:
        session.rollback()
        return JSONResponse(status_code=500, content={'error': str(exc)})
    finally:
        session.close()


@share_router.delete('/api/shares/{share_id}')
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


@share_router.get('/api/play/{share_id}/info')
async def get_share_info(share_id: str, request: Request):
    session = UserInfoSession()
    try:
        current_user = _get_optional_current_user(request)
        share = session.query(Share).filter_by(id=share_id, is_active=True).first()
        if not share:
            return JSONResponse(status_code=404, content={'error': '分享不存在'})
        if not _can_access_share(share, current_user):
            if get_disable_public_share() and share.is_shared:
                return JSONResponse(status_code=403, content={'error': '管理员已禁用公开分享'})
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


@share_router.get('/api/play/{share_id}/data')
async def get_share_data(share_id: str, request: Request):
    session = UserInfoSession()
    try:
        current_user = _get_optional_current_user(request)
        share = session.query(Share).filter_by(id=share_id, is_active=True).first()
        if share and not _can_access_share(share, current_user):
            if get_disable_public_share() and share.is_shared:
                return JSONResponse(status_code=403, content={'error': '管理员已禁用公开分享'})
            return JSONResponse(status_code=404, content={'error': '分享不存在或未公开'})
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
                'guide': item.guide,
                'intro': item.intro,
                'dlg': item.dlg_json,
                'button_text': item.button_text,
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


@share_router.get('/api/play/v/{share_id}/info')
async def get_version_share_info(share_id: str, request: Request):
    """获取分享版本的元数据"""
    session = UserInfoSession()
    try:
        current_user = _get_optional_current_user(request)
        # 支持通过 share_id 或 version_id (UUID) 获取数据，但私有版本仅允许作者本人访问
        version = session.query(ProjectVersion).filter(
            (ProjectVersion.share_id == share_id) | (ProjectVersion.id == share_id)
        ).first()

        if not version:
            return JSONResponse(status_code=404, content={'error': '分享不存在'})
        if not _can_access_version(version, current_user):
            if get_disable_public_share() and version.is_shared:
                return JSONResponse(status_code=403, content={'error': '管理员已禁用公开分享'})
            return JSONResponse(status_code=404, content={'error': '分享不存在'})
        description, content_format = _decode_version_description(version.description)
        return {
            'title': version.version_name,
            'description': description,
            'created_at': version.created_at.isoformat(),
            'author': version.user.username if getattr(version, 'user', None) else 'unknown',
            'project_name': version.project_name,
            'content_format': content_format,
        }
    finally:
        session.close()


@share_router.get('/api/play/v/{share_id}/data')
async def get_version_share_data(share_id: str, request: Request):
    """获取分享版本的数据内容"""
    session = UserInfoSession()
    try:
        current_user = _get_optional_current_user(request)
        # 支持通过 share_id 或 version_id (UUID) 获取数据，但私有版本仅允许作者本人访问
        version = session.query(ProjectVersion).filter(
            (ProjectVersion.share_id == share_id) | (ProjectVersion.id == share_id)
        ).first()

        if not version:
            return JSONResponse(status_code=404, content={'error': '分享数据不存在'})

        if not _can_access_version(version, current_user):
            if get_disable_public_share() and version.is_shared:
                return JSONResponse(status_code=403, content={'error': '管理员已禁用公开分享'})
            return JSONResponse(status_code=404, content={'error': '分享数据不存在'})

        if not version.snapshot_path or not os.path.exists(version.snapshot_path):
            return JSONResponse(status_code=404, content={'error': '分享数据不存在'})

        snapshot_path = version.snapshot_path
        _, content_format = _decode_version_description(version.description)
    finally:
        session.close()

    if content_format == 'novel':
        try:
            with open(snapshot_path, 'r', encoding='utf-8') as f:
                content = f.read()
            return {
                'format': 'novel',
                'content': content,
            }
        except Exception as exc:
            return JSONResponse(status_code=500, content={'error': f'读取小说快照失败: {exc}'})

    engine = create_engine(f'sqlite:///{snapshot_path}', echo=False)
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
                'guide': item.guide,
                'intro': item.intro,
                'dlg': item.dlg_json,
                'button_text': item.button_text,
                'hidden': item.hiden,
            }
            for item in stories
        ]
        char_map = {c.chr_id: c.chr_name for c in characters}
        registry = {r.name: r.value for r in registry_items}
        return {
            'format': 'script',
            'stories': story_list,
            'characters': char_map,
            'registry': registry,
        }
    except Exception as exc:
        return JSONResponse(status_code=500, content={'error': f'读取快照失败: {exc}'})
    finally:
        snapshot_session.close()
        engine.dispose()
