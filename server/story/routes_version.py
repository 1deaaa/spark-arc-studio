from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional
import uuid
import os
import shutil
import re
from datetime import datetime, timezone

from core.auth import get_current_user
from core.compliance_features import is_force_public_share_review_effective
from core.models import UserInfoSession, ProjectVersion
from core.utils import get_project_path
from core.system_settings import get_disable_public_share
from story.public_share_review import (
    PublicShareReviewRejectedError,
    ensure_public_share_allowed,
)
from story.importer import import_project_stories_to_db
from story.novel_parser import aggregate_novel
from story.presentation_manifest import copy_presentation_snapshot, remove_presentation_snapshot

version_router = APIRouter()

SERVER_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHARES_DIR = os.path.join(SERVER_ROOT, 'shares_data')

def _get_shares_dir() -> str:
    os.makedirs(SHARES_DIR, exist_ok=True)
    return SHARES_DIR


FORMAT_MARKER_RE = re.compile(r'^\[\[format:(script|novel)\]\]\n?', re.IGNORECASE)
DIRECTORY_MARKER_RE = re.compile(r'^\[\[directory:(full|progressive)\]\]\n?', re.IGNORECASE)
PREVIEW_VERSION_PREFIX = '__preview__'


def _normalize_content_format(value: Optional[str]) -> str:
    return 'novel' if str(value or '').strip().lower() == 'novel' else 'script'


def _encode_version_description(
    description: Optional[str],
    content_format: str,
    show_full_directory: bool = True,
) -> str:
    desc = str(description or '')
    stripped = FORMAT_MARKER_RE.sub('', desc)
    stripped = DIRECTORY_MARKER_RE.sub('', stripped).strip()
    directory_mode = 'full' if show_full_directory else 'progressive'
    return (
        f"[[format:{_normalize_content_format(content_format)}]]\n"
        f"[[directory:{directory_mode}]]\n"
        f"{stripped}"
    ).strip()


def _decode_version_description(description: Optional[str]) -> tuple[str, str]:
    raw = str(description or '')
    match = FORMAT_MARKER_RE.match(raw)
    content_format = _normalize_content_format(match.group(1) if match else 'script')
    clean_description = FORMAT_MARKER_RE.sub('', raw, count=1)
    clean_description = DIRECTORY_MARKER_RE.sub('', clean_description, count=1).strip()
    return clean_description, content_format


def _decode_version_show_full_directory(description: Optional[str]) -> bool:
    raw = FORMAT_MARKER_RE.sub('', str(description or ''), count=1)
    match = DIRECTORY_MARKER_RE.match(raw)
    return not match or match.group(1).lower() == 'full'


def _is_preview_version(version_name: Optional[str]) -> bool:
    return str(version_name or '').startswith(PREVIEW_VERSION_PREFIX)


def _build_preview_version_name() -> str:
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')
    return f'{PREVIEW_VERSION_PREFIX}{stamp}'


def _create_snapshot_for_format(user_id: str, project_name: str, content_format: str, version_id: str):
    if content_format == 'novel':
        snapshot_path = os.path.join(_get_shares_dir(), f'ver_{version_id}.md')
        try:
            with open(snapshot_path, 'w', encoding='utf-8') as f:
                f.write(aggregate_novel(user_id, project_name, export_format='md'))
        except Exception:
            if os.path.exists(snapshot_path):
                try:
                    os.remove(snapshot_path)
                except OSError:
                    pass
            remove_presentation_snapshot(snapshot_path)
            raise
        return snapshot_path, None

    import_project_stories_to_db(user_id, project_name, reset=True)

    project_path = get_project_path(user_id, project_name)
    db_path = os.path.join(project_path, 'stories.db')
    if not os.path.exists(db_path):
        return None, JSONResponse(status_code=404, content={'error': '项目数据库尚未生成'})

    snapshot_path = os.path.join(_get_shares_dir(), f'ver_{version_id}.db')
    try:
        shutil.copy2(db_path, snapshot_path)
        copy_presentation_snapshot(user_id, project_name, snapshot_path)
    except Exception:
        if os.path.exists(snapshot_path):
            try:
                os.remove(snapshot_path)
            except OSError:
                pass
        remove_presentation_snapshot(snapshot_path)
        raise
    return snapshot_path, None

class VersionCreate(BaseModel):
    versionName: str
    description: Optional[str] = ""
    contentFormat: Optional[str] = 'script'
    showFullDirectory: bool = True

class VersionUpdate(BaseModel):
    versionName: Optional[str] = None
    description: Optional[str] = None
    is_shared: Optional[bool] = None
    showFullDirectory: Optional[bool] = None


class VersionPreviewCreate(BaseModel):
    contentFormat: Optional[str] = 'script'

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

        visible_versions = [item for item in versions if not _is_preview_version(item.version_name)]
        
        return [
            {
                'id': item.id,
                'version_name': item.version_name,
                'description': _decode_version_description(item.description)[0],
                'content_format': _decode_version_description(item.description)[1],
                'show_full_directory': _decode_version_show_full_directory(item.description),
                'created_at': item.created_at.isoformat(),
                'is_shared': item.is_shared,
                'share_id': item.share_id
            }
            for item in visible_versions
        ]
    finally:
        session.close()


@version_router.post('/api/versions/{project_name}')
async def create_version(project_name: str, data: VersionCreate, user: dict = Depends(get_current_user)):
    """为当前项目创建一个新版本快照"""
    user_id = str(user['user_id'])
    try:
        version_id = str(uuid.uuid4())
        content_format = _normalize_content_format(data.contentFormat)

        snapshot_path, error_response = _create_snapshot_for_format(user_id, project_name, content_format, version_id)
        if error_response:
            return error_response

        # 3. 记录到数据库
        session = UserInfoSession()
        try:
            version = ProjectVersion(
                id=version_id,
                user_id=int(user_id),
                project_name=project_name,
                version_name=data.versionName,
                description=_encode_version_description(
                    data.description,
                    content_format,
                    data.showFullDirectory,
                ),
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


@version_router.post('/api/versions/{project_name}/preview')
async def create_preview_version(project_name: str, data: VersionPreviewCreate, user: dict = Depends(get_current_user)):
    """创建仅用于试玩的临时快照，不进入版本列表。"""
    user_id = str(user['user_id'])
    try:
        version_id = str(uuid.uuid4())
        content_format = _normalize_content_format(data.contentFormat)
        snapshot_path, error_response = _create_snapshot_for_format(user_id, project_name, content_format, version_id)
        if error_response:
            return error_response

        session = UserInfoSession()
        try:
            version = ProjectVersion(
                id=version_id,
                user_id=int(user_id),
                project_name=project_name,
                version_name=_build_preview_version_name(),
                description=_encode_version_description('临时试玩快照', content_format),
                snapshot_path=snapshot_path,
                is_shared=False,
                share_id=None,
            )
            session.add(version)
            session.commit()
            return {'success': True, 'version_id': version_id}
        except Exception as exc:
            session.rollback()
            if snapshot_path and os.path.exists(snapshot_path):
                try:
                    os.remove(snapshot_path)
                except OSError:
                    pass
            remove_presentation_snapshot(snapshot_path)
            return JSONResponse(status_code=500, content={'error': str(exc)})
        finally:
            session.close()
    except Exception as exc:
        return JSONResponse(status_code=500, content={'error': f'创建试玩快照失败: {exc}'})


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
            _, current_format = _decode_version_description(version.description)
            show_full_directory = _decode_version_show_full_directory(version.description)
            version.description = _encode_version_description(
                data.description,
                current_format,
                show_full_directory,
            )
        if data.showFullDirectory is not None:
            current_description, current_format = _decode_version_description(version.description)
            version.description = _encode_version_description(
                current_description,
                current_format,
                data.showFullDirectory,
            )
        if data.is_shared is not None:
            if data.is_shared and get_disable_public_share():
                return JSONResponse(status_code=403, content={'error': '管理员已禁用公开分享'})
            if data.is_shared and not version.is_shared and is_force_public_share_review_effective():
                try:
                    content_format = _decode_version_description(version.description)[1]
                    ensure_public_share_allowed(user_id, version.project_name, content_format)
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
            version.is_shared = data.is_shared
            if version.is_shared and not version.share_id:
                version.share_id = str(uuid.uuid4())
        
        session.commit()
        return {'success': True, 'share_id': version.share_id}
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
        remove_presentation_snapshot(snapshot_path)
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
        _, content_format = _decode_version_description(version.description)
        if content_format == 'novel':
            return JSONResponse(status_code=400, content={'error': '当前版本为小说快照，暂不支持一键恢复到工作区'})
            
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


@version_router.get('/api/versions/{version_id}/download')
async def download_version_snapshot(version_id: str, user: dict = Depends(get_current_user)):
    from fastapi.responses import FileResponse

    user_id = str(user['user_id'])
    session = UserInfoSession()
    try:
        version = session.query(ProjectVersion).filter_by(id=version_id, user_id=int(user_id)).first()
        if not version:
            return JSONResponse(status_code=404, content={'error': '版本不存在'})

        if not version.snapshot_path or not os.path.exists(version.snapshot_path):
            return JSONResponse(status_code=404, content={'error': '版本快照不存在'})

        _, content_format = _decode_version_description(version.description)
        safe_name = version.version_name.replace('/', '_').replace('\\', '_')
        if content_format == 'novel':
            return FileResponse(
                path=version.snapshot_path,
                media_type='text/markdown',
                filename=f'{safe_name}.md',
            )

        return FileResponse(
            path=version.snapshot_path,
            media_type='application/x-sqlite3',
            filename=f'{safe_name}.db',
        )
    finally:
        session.close()
