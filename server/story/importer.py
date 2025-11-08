import copy
import json
import os
import re

from sqlalchemy import create_engine, delete
from sqlalchemy.orm import sessionmaker

from models import Story, StoryData
from utils import (
    ensure_project_directory,
    ensure_project_stories_directory,
    strip_private_fields,
)


def _extract_chapter_from_filename(rel_path: str) -> int:
    """从文件名提取章节号
    
    支持格式：
    - 01_序章.story → 1
    - Chapter_02.story → 2
    - 第3章.story → 3
    - scene.story → 900+ (无编号则按文件名哈希排到最后)
    """
    filename = os.path.basename(rel_path)
    filename_no_ext = os.path.splitext(filename)[0]
    
    patterns = [
        r'^(\d+)[_\-\s]',          # 01_序章、02-初遇
        r'[Cc]hapter[_\s]*(\d+)',  # Chapter_02
        r'第(\d+)[章节回]',          # 第3章
    ]
    
    for pat in patterns:
        m = re.search(pat, filename_no_ext)
        if m:
            return int(m.group(1))
    
    # 无编号文件用文件名哈希（保证排序稳定性）
    return 900 + (abs(hash(filename_no_ext)) % 99)


def import_project_stories_to_db(user_id: str, project_name: str, *, reset: bool = True) -> dict:
    """将项目 stories 目录内的 .story 文件导入到该项目的独立 SQLite 数据库。"""
    from models import BindChr
    
    project_root = ensure_project_directory(user_id, project_name)
    stories_dir = ensure_project_stories_directory(user_id, project_name)
    db_path = os.path.join(project_root, 'stories.db')

    engine = create_engine(f'sqlite:///{db_path}', echo=False, future=True)
    StoryData.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False, future=True)

    # 收集所有文件并提取章节号
    story_files = []
    for root, _, files in os.walk(stories_dir):
        for file_name in files:
            if file_name.endswith('.story'):
                full_path = os.path.join(root, file_name)
                rel_path = os.path.relpath(full_path, stories_dir)
                chapter_num = _extract_chapter_from_filename(rel_path)
                story_files.append((chapter_num, rel_path))

    # 按章节号排序（一个文件 = 一章）
    story_files.sort(key=lambda x: x[0])

    session = Session()
    imported = 0
    seen_chapters = set()
    try:
        if reset:
            session.execute(delete(Story))

        for chapter_num, rel_path in story_files:
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

                # 记录实际出现的章节
                seen_chapters.add(chapter_num)

                story_row = Story(
                    chapter=int(chapter_num),
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
        
        # 🆕 同步角色绑定：从 chr/chr.bind 读取并写入 binding_chr 表
        chr_bind_path = os.path.join(project_root, 'chr', 'chr.bind')
        if os.path.exists(chr_bind_path):
            try:
                with open(chr_bind_path, 'r', encoding='utf-8') as f:
                    chr_bindings = json.load(f) or {}
                
                # 清空旧绑定
                session.execute(delete(BindChr))
                
                # 插入新绑定
                for chr_id_str, chr_name in chr_bindings.items():
                    try:
                        chr_id_int = int(chr_id_str)
                        binding = BindChr(chr_id=chr_id_int, chr_name=chr_name)
                        session.add(binding)
                    except (ValueError, TypeError):
                        continue
                
                session.commit()
            except Exception as e:
                # 角色绑定失败不影响主流程
                print(f"Warning: 同步角色绑定失败: {e}")
        
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
