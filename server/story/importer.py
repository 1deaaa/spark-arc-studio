import copy
import json
import os

from sqlalchemy import create_engine, delete, select, func
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from core.models import Story, StoryData
from core.utils import (
    ensure_project_directory,
    ensure_project_stories_directory,
)
from .file_naming import parse_story_filename, story_sort_key
from .project_files import _coerce_character_name
from .scene_loader import load_story_file


def _collect_char_ids_from_dialogues(dialogues: list, collected: set):
    """递归收集可导出的隐藏角色绑定 ID。"""
    for d in dialogues:
        if isinstance(d.character, int):
            collected.add(d.character)
        for opt in d.options:
            _collect_char_ids_from_dialogues(opt.dialogues, collected)


def _load_json_list(path: str) -> list:
    """读取项目级 JSON 列表配置，异常时回退为空列表。"""
    if not os.path.exists(path):
        return []
    try:
        with open(path, 'r', encoding='utf-8') as handle:
            data = json.load(handle)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _normalize_json_object(value) -> dict:
    """确保行为参数示例写入数据库时始终是对象。"""
    return value if isinstance(value, dict) else {}


def _normalize_registry_value(value) -> list:
    """注册表值统一写成 JSON 数组，便于 Unity 端做占位符和枚举选择。"""
    if isinstance(value, list):
        return value
    if value is None:
        return []
    return [value]


def _load_chr_bindings(project_root: str) -> dict:
    """读取项目角色绑定，供 ARC 说话人名反查隐藏 ID。"""
    chr_bind_path = os.path.join(project_root, 'chr', 'chr.bind')
    if not os.path.exists(chr_bind_path):
        return {}
    try:
        with open(chr_bind_path, 'r', encoding='utf-8') as handle:
            data = json.load(handle) or {}
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _chr_map_from_bindings(chr_bindings: dict) -> dict[int, str]:
    """把 chr.bind 整理成解析器可用的 ``{id: name}``。"""
    result: dict[int, str] = {}
    for raw_id, raw_value in (chr_bindings or {}).items():
        try:
            cid = int(raw_id)
        except (TypeError, ValueError):
            continue
        name = _coerce_character_name(raw_value)
        if name:
            result[cid] = name
    return result


def import_project_stories_to_db(user_id: str, project_name: str, *, reset: bool = True) -> dict:
    """将项目 stories 目录导入独立的 SQLite 数据库。"""
    from core.models import BindAct, BindChr, Character, Registry

    project_root = ensure_project_directory(user_id, project_name)
    stories_dir = ensure_project_stories_directory(user_id, project_name)
    db_path = os.path.join(project_root, 'stories.db')
    chr_bindings = _load_chr_bindings(project_root)
    chr_map_for_parse = _chr_map_from_bindings(chr_bindings)

    # 使用 NullPool 确保连接用完后立即真正关闭，避免 Windows 上 SQLite 文件锁残留
    # 导致后续的 shutil.copy2 快照复制失败（第一次创建分享/版本必定失败的根因）
    engine = create_engine(f'sqlite:///{db_path}', echo=False, future=True, poolclass=NullPool)
    StoryData.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False, future=True)

    story_files = []
    for root, _, files in os.walk(stories_dir):
        for file_name in files:
            if not file_name.endswith('.arc'):
                continue
            full_path = os.path.join(root, file_name)
            rel_path = os.path.relpath(full_path, stories_dir)
            parsed = parse_story_filename(file_name)
            if not parsed:
                continue
            story_files.append((story_sort_key(rel_path), rel_path, parsed))

    story_files.sort(key=lambda item: item[0])

    session = Session()
    imported = 0
    seen_chapters = set()
    progress_counter = 0.0
    
    # 收集所有出现的角色ID
    seen_char_ids = set()

    try:
        if reset:
            session.execute(delete(Story))
            session.execute(delete(Character))
            session.execute(delete(BindAct))
            session.execute(delete(Registry))
        else:
            result = session.execute(select(func.max(Story.progress)))
            max_progress = result.scalar()
            if max_progress is not None:
                progress_counter = float(max_progress)

        for _, rel_path, parsed in story_files:
            file_path = os.path.join(stories_dir, rel_path)
            scene_models = load_story_file(file_path, chr_map=chr_map_for_parse)
            if not scene_models:
                continue
            chapter_num = parsed.get('chapter_num') or 999
            
            # 收集角色ID
            for scene_model in scene_models:
                _collect_char_ids_from_dialogues(scene_model.dialogues, seen_char_ids)

            default_scene_name = parsed.get('display_name') or os.path.splitext(os.path.basename(rel_path))[0]

            for scene_model in scene_models:
                guide = scene_model.guide or ''
                scene_name = scene_model.name or default_scene_name

                progress_counter += 1.0
                dlg_payload = scene_model.to_dict().get('dia', [])

                seen_chapters.add(chapter_num)

                story_row = Story(
                    chapter=int(chapter_num),
                    scene_name=str(scene_name),
                    button_text=scene_model.button_text,
                    progress=progress_counter,
                    guide=str(guide),
                    conditions=copy.deepcopy(scene_model.conditions) if scene_model.conditions is not None else None,
                    effects=copy.deepcopy(scene_model.effects) if scene_model.effects is not None else None,
                    trigger_event=scene_model.trigger_event,
                    priority=scene_model.priority,
                    once_key=scene_model.once_key,
                    intro=scene_model.intro or None,
                    dlg_json=dlg_payload,
                    hiden=scene_model.hidden,
                )
                session.add(story_row)
                imported += 1

        # 处理角色数据
        # 1. 兼容旧表 BindChr
        try:
            session.execute(delete(BindChr))
            for chr_id_str, raw_value in chr_bindings.items():
                try:
                    chr_id_int = int(chr_id_str)
                    chr_name = _coerce_character_name(raw_value)
                    if not chr_name:
                        continue
                    session.add(BindChr(chr_id=chr_id_int, chr_name=chr_name))
                except (ValueError, TypeError):
                    continue
        except Exception as exc:
            print(f"Warning: Failed to sync character binding (BindChr): {exc}")

        # 2. 填充新表 Character
        try:
            # 始终重建 Character 表以确保最新
            session.execute(delete(Character))
            
            # 合并 ARC 中扫描到的 ID 和绑定文件中的 ID
            bound_ids = {int(k) for k in chr_bindings.keys() if k.lstrip('-').isdigit()}
            all_ids = seen_char_ids.union(bound_ids)
            
            for cid in all_ids:
                # 优先使用绑定文件中的名字（兼容 dict 与 string 两种格式）
                raw = chr_bindings.get(str(cid))
                name = _coerce_character_name(raw) if raw else None
                if not name:
                    if cid == -1:
                        name = "旁白"
                    else:
                        name = f"角色{cid}"
                
                session.add(Character(character_id=cid, name=name))
                
        except Exception as exc:
             print(f"Warning: Failed to populate Character table: {exc}")

        # 3. 同步 Unity 行为函数绑定
        try:
            session.execute(delete(BindAct))
            action_bindings = _load_json_list(os.path.join(project_root, 'action_bindings.json'))
            for item in action_bindings:
                if not isinstance(item, dict):
                    continue
                act_name = str(item.get('act_name') or '').strip()
                func_name = str(item.get('func_name') or '').strip()
                if not act_name or not func_name:
                    continue
                session.add(BindAct(
                    act_name=act_name,
                    func_name=func_name,
                    act_type=(str(item.get('act_type')).strip() if item.get('act_type') is not None else None),
                    act_description=(str(item.get('act_description')).strip() if item.get('act_description') is not None else None),
                    act_args=copy.deepcopy(_normalize_json_object(item.get('act_args'))),
                ))
        except Exception as exc:
            print(f"Warning: Failed to sync action bindings (BindAct): {exc}")

        # 4. 同步 Unity 全局注册表
        try:
            session.execute(delete(Registry))
            registries = _load_json_list(os.path.join(project_root, 'registries.json'))
            for item in registries:
                if not isinstance(item, dict):
                    continue
                name = str(item.get('name') or '').strip()
                if not name:
                    continue
                session.add(Registry(
                    name=name,
                    value=copy.deepcopy(_normalize_registry_value(item.get('value'))),
                ))
        except Exception as exc:
            print(f"Warning: Failed to sync registries (Registry): {exc}")

        session.commit()

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
