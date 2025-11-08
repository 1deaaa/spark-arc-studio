import os
import shutil

from flask import jsonify, request

from auth import require_auth, optional_auth
from request_context import get_current_info
from utils import (
    ensure_project_directory,
    ensure_project_stories_directory,
    ensure_project_worldview_and_character_settings,
    get_project_path,
    get_user_projects_root,
)

from . import story_bp
from .importer import import_project_stories_to_db


@story_bp.route('/api/projects', methods=['GET'])
@optional_auth
@get_current_info
def get_projects():
    """列出当前用户的所有项目"""
    try:
        user_id = request.current_user['user_id']
        projects_root = get_user_projects_root(user_id)
        if not os.path.exists(projects_root):
            os.makedirs(projects_root)
            return jsonify([])
        projects = [
            name
            for name in os.listdir(projects_root)
            if os.path.isdir(os.path.join(projects_root, name))
        ]
        return jsonify(sorted(projects))
    except Exception as exc:
        return jsonify({"success": False, "message": f"获取项目列表失败: {exc}"}), 500


@story_bp.route('/api/projects', methods=['POST'])
@require_auth
@get_current_info
def create_project():
    """创建新项目并初始化目录结构"""
    try:
        user_id = request.current_user['user_id']
        data = request.json or {}
        project_name = data.get('projectName')
        if not project_name:
            return jsonify({"success": False, "message": "项目名称不能为空"}), 400

        project_path = get_project_path(user_id, project_name)
        if os.path.exists(project_path):
            return jsonify({"success": False, "message": "项目已存在"}), 409

        ensure_project_directory(user_id, project_name)
        ensure_project_stories_directory(user_id, project_name)
        ensure_project_worldview_and_character_settings(user_id, project_name)
        return jsonify({"success": True, "message": "项目创建成功"})
    except Exception as exc:
        return jsonify({"success": False, "message": f"项目创建失败: {exc}"}), 500


@story_bp.route('/api/projects/<project_name>', methods=['DELETE'])
@require_auth
@get_current_info
def delete_project(project_name):
    """删除指定项目"""
    try:
        user_id = request.current_user['user_id']
        project_path = get_project_path(user_id, project_name)
        if not os.path.exists(project_path):
            return jsonify({"success": False, "message": "项目不存在"}), 404
        shutil.rmtree(project_path)
        return jsonify({"success": True, "message": "项目删除成功"})
    except Exception as exc:
        return jsonify({"success": False, "message": f"项目删除失败: {exc}"}), 500


@story_bp.route('/api/export-to-sqlite', methods=['POST'])
@require_auth
@get_current_info
def export_to_sqlite():
    """将当前项目的所有 .story 文件导出到 SQLite 数据库"""
    try:
        user_id = request.current_user['user_id']
        data = request.json or {}
        project_name = data.get('projectName')
        reset = data.get('reset', True)
        
        if not project_name:
            return jsonify({'success': False, 'message': '项目名不能为空'}), 400
        
        result = import_project_stories_to_db(
            user_id=user_id,
            project_name=project_name,
            reset=reset
        )
        
        return jsonify({
            'success': True,
            'db_path': result['db_path'],
            'chapters': result['chapters'],
            'scenes': result['scenes'],
            'message': f'成功导出 {result["chapters"]} 个章节，{result["scenes"]} 个场景'
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'导出失败: {str(e)}'}), 500


@story_bp.route('/api/action-bindings/<project_name>', methods=['GET'])
@optional_auth
@get_current_info
def get_action_bindings(project_name):
    """获取项目的行为函数绑定"""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from models import BindAct, StoryData
    
    try:
        user_id = request.current_user['user_id']
        project_path = get_project_path(user_id, project_name)
        db_path = os.path.join(project_path, 'stories.db')
        
        if not os.path.exists(db_path):
            return jsonify([])
        
        engine = create_engine(f'sqlite:///{db_path}', echo=False)
        Session = sessionmaker(bind=engine)
        session = Session()
        
        try:
            bindings = session.query(BindAct).all()
            result = [{
                'id': b.id,
                'act_type': b.act_type,
                'act_name': b.act_name,
                'func_name': b.func_name,
                'act_description': b.act_description,
                'act_args': b.act_args
            } for b in bindings]
            return jsonify(result)
        finally:
            session.close()
            engine.dispose()
    except Exception as e:
        return jsonify([])


@story_bp.route('/api/action-bindings/<project_name>', methods=['POST'])
@require_auth
@get_current_info
def save_action_bindings(project_name):
    """保存项目的行为函数绑定"""
    from sqlalchemy import create_engine, delete
    from sqlalchemy.orm import sessionmaker
    from models import BindAct, StoryData
    
    try:
        user_id = request.current_user['user_id']
        data = request.json or []
        
        project_path = ensure_project_directory(user_id, project_name)
        db_path = os.path.join(project_path, 'stories.db')
        
        engine = create_engine(f'sqlite:///{db_path}', echo=False)
        StoryData.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        session = Session()
        
        try:
            session.execute(delete(BindAct))
            
            for item in data:
                binding = BindAct(
                    act_type=item.get('act_type'),
                    act_name=item['act_name'],
                    func_name=item['func_name'],
                    act_description=item.get('act_description'),
                    act_args=item.get('act_args')
                )
                session.add(binding)
            
            session.commit()
            return jsonify({'success': True, 'message': '行为函数绑定保存成功'})
        except Exception as e:
            session.rollback()
            raise
        finally:
            session.close()
            engine.dispose()
    except Exception as e:
        return jsonify({'success': False, 'message': f'保存失败: {str(e)}'}), 500


@story_bp.route('/api/registries/<project_name>', methods=['GET'])
@optional_auth
@get_current_info
def get_registries(project_name):
    """获取项目的全局注册表"""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from models import Registry, StoryData
    
    try:
        user_id = request.current_user['user_id']
        project_path = get_project_path(user_id, project_name)
        db_path = os.path.join(project_path, 'stories.db')
        
        if not os.path.exists(db_path):
            return jsonify([])
        
        engine = create_engine(f'sqlite:///{db_path}', echo=False)
        Session = sessionmaker(bind=engine)
        session = Session()
        
        try:
            regs = session.query(Registry).all()
            result = [{
                'id': r.id,
                'name': r.name,
                'value': r.value
            } for r in regs]
            return jsonify(result)
        finally:
            session.close()
            engine.dispose()
    except Exception as e:
        return jsonify([])


@story_bp.route('/api/registries/<project_name>', methods=['POST'])
@require_auth
@get_current_info
def save_registries(project_name):
    """保存项目的全局注册表"""
    from sqlalchemy import create_engine, delete
    from sqlalchemy.orm import sessionmaker
    from models import Registry, StoryData
    
    try:
        user_id = request.current_user['user_id']
        data = request.json or []
        
        project_path = ensure_project_directory(user_id, project_name)
        db_path = os.path.join(project_path, 'stories.db')
        
        engine = create_engine(f'sqlite:///{db_path}', echo=False)
        StoryData.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        session = Session()
        
        try:
            session.execute(delete(Registry))
            
            for item in data:
                registry = Registry(
                    name=item['name'],
                    value=item['value']
                )
                session.add(registry)
            
            session.commit()
            return jsonify({'success': True, 'message': '注册表保存成功'})
        except Exception as e:
            session.rollback()
            raise
        finally:
            session.close()
            engine.dispose()
    except Exception as e:
        return jsonify({'success': False, 'message': f'保存失败: {str(e)}'}), 500
