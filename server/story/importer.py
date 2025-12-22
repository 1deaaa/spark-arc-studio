import copy
import json
import os
import re

from sqlalchemy import create_engine, delete, select, func
from sqlalchemy.orm import sessionmaker

from core.models import Story, StoryData
from core.utils import (
    ensure_project_directory,
    ensure_project_stories_directory,
)
from .scene_loader import load_story_file


def _extract_chapter_from_filename(rel_path: str) -> int:
    """根据文件名推断章节序号，保持导入顺序稳定。"""
    filename = os.path.basename(rel_path)
    filename_no_ext = os.path.splitext(filename)[0]

    patterns = [
        r'^(\d+)[_\-\s]',
        r'[Cc]hapter[_\s]*(\d+)',
        r'第(\d+)[章节回]',
    ]

    for pat in patterns:
        match = re.search(pat, filename_no_ext)
        if match:
            return int(match.group(1))

    return 900 + (abs(hash(filename_no_ext)) % 99)


def import_project_stories_to_db(user_id: str, project_name: str, *, reset: bool = True) -> dict:
    """将项目 stories 目录导入独立的 SQLite 数据库。"""
    from core.models import BindChr

    project_root = ensure_project_directory(user_id, project_name)
    stories_dir = ensure_project_stories_directory(user_id, project_name)
    db_path = os.path.join(project_root, 'stories.db')

    engine = create_engine(f'sqlite:///{db_path}', echo=False, future=True)
    StoryData.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False, future=True)

    story_files = []
    for root, _, files in os.walk(stories_dir):
        for file_name in files:
            if not file_name.endswith('.arc'):
                continue
            full_path = os.path.join(root, file_name)
            rel_path = os.path.relpath(full_path, stories_dir)
            chapter_num = _extract_chapter_from_filename(rel_path)
            story_files.append((chapter_num, rel_path))

    story_files.sort(key=lambda item: item[0])

    session = Session()
    imported = 0
    seen_chapters = set()
    progress_counter = 0.0

    try:
        if reset:
            session.execute(delete(Story))
        else:
            result = session.execute(select(func.max(Story.progress)))
            max_progress = result.scalar()
            if max_progress is not None:
                progress_counter = float(max_progress)

        for chapter_num, rel_path in story_files:
            file_path = os.path.join(stories_dir, rel_path)
            scene_models = load_story_file(file_path)
            if not scene_models:
                continue

            default_scene_name = os.path.splitext(os.path.basename(rel_path))[0]

            for scene_model in scene_models:
                caption = scene_model.caption or ''
                scene_name = scene_model.name or default_scene_name

                progress_counter += 1.0
                dlg_payload = scene_model.to_dict().get('dia', [])

                seen_chapters.add(chapter_num)

                story_row = Story(
                    chapter=int(chapter_num),
                    scene_name=str(scene_name),
                    button_text=scene_model.button_text,
                    progress=progress_counter,
                    caption=str(caption),
                    conditions=copy.deepcopy(scene_model.conditions) if scene_model.conditions is not None else None,
                    dlg_json=dlg_payload,
                    hiden=scene_model.hidden,
                )
                session.add(story_row)
                imported += 1

        session.commit()

        chr_bind_path = os.path.join(project_root, 'chr', 'chr.bind')
        if os.path.exists(chr_bind_path):
            try:
                with open(chr_bind_path, 'r', encoding='utf-8') as handle:
                    chr_bindings = json.load(handle) or {}

                session.execute(delete(BindChr))

                for chr_id_str, chr_name in chr_bindings.items():
                    try:
                        chr_id_int = int(chr_id_str)
                        session.add(BindChr(chr_id=chr_id_int, chr_name=chr_name))
                    except (ValueError, TypeError):
                        continue

                session.commit()
            except Exception as exc:
                print(f"Warning: 同步角色绑定失败: {exc}")

    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
        engine.dispose()

    return {
        'db_path': db_path,
        'chapters': len(seen_chapters),
        'scenes': imported,
    }
