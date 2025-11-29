import os
import uuid
import shutil
from datetime import datetime
from flask import Blueprint, request, jsonify, send_file
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from core.auth import require_auth, optional_auth
from core.request_context import get_current_info
from core.models import UserInfoSession, Share, Story, BindChr, BindAct, Registry, StoryData
from core.utils import get_project_path, get_user_projects_root
from ..importer import import_project_stories_to_db

shares_bp = Blueprint('shares_bp', __name__)

SHARES_DIR = 'shares_data'

def get_shares_dir():
    if not os.path.exists(SHARES_DIR):
        os.makedirs(SHARES_DIR)
    return SHARES_DIR

@shares_bp.route('/api/shares', methods=['GET'])
@require_auth
@get_current_info
def list_shares():
    """
    List shares/versions. 
    Optional query params: 
    - project_name: filter by project
    - is_shared: 'true' or 'false' to filter by shared status
    """
    user_id = request.current_user['user_id']
    project_name = request.args.get('project_name')
    is_shared_param = request.args.get('is_shared')

    session = UserInfoSession()
    try:
        query = session.query(Share).filter_by(user_id=user_id)
        
        if project_name:
            query = query.filter_by(project_name=project_name)
        
        if is_shared_param is not None:
            is_shared_bool = is_shared_param.lower() == 'true'
            query = query.filter_by(is_shared=is_shared_bool)

        shares = query.order_by(Share.created_at.desc()).all()
        return jsonify([{
            'id': share.id,
            'project_name': share.project_name,
            'title': share.title,
            'description': share.description,
            'created_at': share.created_at.isoformat(),
            'is_active': share.is_active,
            'is_shared': share.is_shared
        } for share in shares])
    finally:
        session.close()

@shares_bp.route('/api/shares', methods=['POST'])
@require_auth
@get_current_info
def create_share():
    """Create a new snapshot (version) of a project"""
    user_id = request.current_user['user_id']
    data = request.json or {}
    project_name = data.get('projectName')
    title = data.get('title')
    description = data.get('description', '')
    is_shared = data.get('is_shared', False)

    if not project_name or not title:
        return jsonify({'error': 'Missing required fields'}), 400

    # 1. Ensure project DB is up to date
    try:
        import_project_stories_to_db(user_id, project_name, reset=True)
    except Exception as e:
        return jsonify({'error': f'Failed to export project: {str(e)}'}), 500

    # 2. Copy DB to shares folder
    project_path = get_project_path(user_id, project_name)
    source_db = os.path.join(project_path, 'stories.db')
    
    if not os.path.exists(source_db):
        return jsonify({'error': 'Project database not found'}), 404

    share_id = str(uuid.uuid4())
    shares_dir = get_shares_dir()
    target_db_name = f"{share_id}.db"
    target_db_path = os.path.join(shares_dir, target_db_name)

    try:
        shutil.copy2(source_db, target_db_path)
    except Exception as e:
        return jsonify({'error': f'Failed to create snapshot: {str(e)}'}), 500

    # 3. Create Share record
    session = UserInfoSession()
    try:
        new_share = Share(
            id=share_id,
            user_id=user_id,
            project_name=project_name,
            title=title,
            description=description,
            snapshot_path=target_db_path,
            is_active=True,
            is_shared=is_shared
        )
        session.add(new_share)
        session.commit()
        return jsonify({'success': True, 'share_id': share_id})
    except Exception as e:
        session.rollback()
        return jsonify({'error': f'Database error: {str(e)}'}), 500
    finally:
        session.close()

@shares_bp.route('/api/shares/<share_id>', methods=['PUT'])
@require_auth
@get_current_info
def update_share(share_id):
    """Update a share/version (title, description, is_shared)"""
    user_id = request.current_user['user_id']
    data = request.json or {}
    
    session = UserInfoSession()
    try:
        share = session.query(Share).filter_by(id=share_id, user_id=user_id).first()
        if not share:
            return jsonify({'error': 'Share not found'}), 404
            
        if 'title' in data:
            share.title = data['title']
        if 'description' in data:
            share.description = data['description']
        if 'is_shared' in data:
            share.is_shared = data['is_shared']
            
        session.commit()
        return jsonify({'success': True})
    except Exception as e:
        session.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()

@shares_bp.route('/api/shares/<share_id>', methods=['DELETE'])
@require_auth
@get_current_info
def delete_share(share_id):
    """Delete a share"""
    user_id = request.current_user['user_id']
    session = UserInfoSession()
    try:
        share = session.query(Share).filter_by(id=share_id, user_id=user_id).first()
        if not share:
            return jsonify({'error': 'Share not found'}), 404

        # Delete file
        if share.snapshot_path and os.path.exists(share.snapshot_path):
            try:
                os.remove(share.snapshot_path)
            except:
                pass # Ignore file deletion errors

        session.delete(share)
        session.commit()
        return jsonify({'success': True})
    finally:
        session.close()

# --- Public Player Routes ---

@shares_bp.route('/api/play/<share_id>/info', methods=['GET'])
def get_share_info(share_id):
    """Get public info for a share"""
    session = UserInfoSession()
    try:
        share = session.query(Share).filter_by(id=share_id, is_active=True, is_shared=True).first()
        if not share:
            return jsonify({'error': 'Share not found or inactive'}), 404
        
        return jsonify({
            'title': share.title,
            'description': share.description,
            'created_at': share.created_at.isoformat(),
            'author': share.user.username if share.user else 'Unknown'
        })
    finally:
        session.close()

@shares_bp.route('/api/play/<share_id>/data', methods=['GET'])
def get_share_data(share_id):
    """Get full story data from the snapshot DB"""
    session = UserInfoSession()
    share = None
    try:
        share = session.query(Share).filter_by(id=share_id, is_active=True, is_shared=True).first()
    finally:
        session.close()

    if not share or not os.path.exists(share.snapshot_path):
        return jsonify({'error': 'Share data not available'}), 404

    # Read from snapshot DB
    db_path = share.snapshot_path
    engine = create_engine(f'sqlite:///{db_path}', echo=False)
    Session = sessionmaker(bind=engine)
    db_session = Session()

    try:
        # Fetch Stories
        stories = db_session.query(Story).order_by(Story.chapter, Story.progress, Story.id).all()
        story_data = []
        for s in stories:
            story_data.append({
                'id': s.id,
                'chapter': s.chapter,
                'scene_name': s.scene_name,
                'caption': s.caption,
                'dlg': s.dlg_json,
                'button_text': s.button_text,
                'conditions': s.conditions,
                'hidden': s.hiden
            })

        # Fetch Characters
        chars = db_session.query(BindChr).all()
        char_map = {c.chr_id: c.chr_name for c in chars}

        # Fetch Registry (Global vars)
        regs = db_session.query(Registry).all()
        registry = {r.name: r.value for r in regs}

        return jsonify({
            'stories': story_data,
            'characters': char_map,
            'registry': registry
        })
    except Exception as e:
        return jsonify({'error': f'Failed to read story data: {str(e)}'}), 500
    finally:
        db_session.close()
        engine.dispose()
