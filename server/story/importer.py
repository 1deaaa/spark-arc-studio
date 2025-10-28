import copy
import json
import os

from sqlalchemy import create_engine, delete
from sqlalchemy.orm import sessionmaker

from models import Story, StoryData
from utils import (
    ensure_project_directory,
    ensure_project_stories_directory,
    strip_private_fields,
)


def import_project_stories_to_db(user_id: str, project_name: str, *, reset: bool = True) -> dict:
    """将项目 stories 目录内的 .story 文件导入到该项目的独立 SQLite 数据库。"""
    project_root = ensure_project_directory(user_id, project_name)
    stories_dir = ensure_project_stories_directory(user_id, project_name)
    db_path = os.path.join(project_root, 'stories.db')

    engine = create_engine(f'sqlite:///{db_path}', echo=False, future=True)
    StoryData.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False, future=True)

    story_files = []
    for root, _, files in os.walk(stories_dir):
        for file_name in files:
            if file_name.endswith('.story'):
                full_path = os.path.join(root, file_name)
                rel_path = os.path.relpath(full_path, stories_dir)
                story_files.append(rel_path)

    story_files.sort()

    session = Session()
    imported = 0
    try:
        if reset:
            session.execute(delete(Story))

        for chapter_index, rel_path in enumerate(story_files, start=1):
            file_path = os.path.join(stories_dir, rel_path)
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = json.load(f)
            except (json.JSONDecodeError, OSError):
                continue
            if not isinstance(content, list):
                continue

            for scene in content:
                if not isinstance(scene, dict):
                    continue

                scene_copy = copy.deepcopy(scene)
                strip_private_fields(scene_copy)

                caption = scene_copy.get('cap') or ''
                if not isinstance(caption, str):
                    caption = str(caption)

                progress_raw = scene_copy.get('pgrs', 0)
                try:
                    progress_value = float(progress_raw)
                except (TypeError, ValueError):
                    progress_value = 0.0

                conditions = scene_copy.get('conditions')
                if conditions is None:
                    conditions = scene_copy.get('cond')
                if isinstance(conditions, (dict, list)):
                    conditions = strip_private_fields(copy.deepcopy(conditions))
                else:
                    conditions = None

                button_text = (
                    scene_copy.get('button_text')
                    or scene_copy.get('buttonText')
                    or scene_copy.get('btn')
                    or scene_copy.get('button')
                )

                scene_name = scene_copy.get('scene')
                if not scene_name:
                    scene_name = os.path.splitext(os.path.basename(rel_path))[0]
                if not isinstance(scene_name, str):
                    scene_name = str(scene_name)

                dlg_payload = scene_copy.get('dia') or []
                dlg_payload = strip_private_fields(copy.deepcopy(dlg_payload))

                hidden_flag = None
                if 'hiden' in scene_copy:
                    hidden_flag = bool(scene_copy.get('hiden'))
                elif 'hidden' in scene_copy:
                    hidden_flag = bool(scene_copy.get('hidden'))

                story_row = Story(
                    chapter=int(chapter_index),
                    scene_name=scene_name,
                    button_text=button_text,
                    progress=progress_value,
                    caption=caption,
                    conditions=conditions,
                    dlg_json=dlg_payload,
                    hiden=hidden_flag,
                )
                session.add(story_row)
                imported += 1

        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
        engine.dispose()

    return {
        'db_path': db_path,
        'chapters': len(story_files),
        'scenes': imported,
    }
