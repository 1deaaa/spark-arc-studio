from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel
from typing import List, Optional, Any
import os
import json
import shutil
from urllib.parse import quote

from core.auth import get_current_user, get_optional_user
from core.request_context import normalize_project_name
from core.utils import (
    ensure_project_stories_directory,
    get_project_stories_path,
    get_project_path,
)
from story.arc_parser import serialize_to_arc
from story.file_naming import (
    build_display_story_path,
    build_story_filename,
    make_temp_story_filename,
    next_story_order,
    parse_story_filename,
    rebuild_story_filename,
    resolve_story_file_path,
    sanitize_story_display_name,
    story_sort_key,
    strip_story_filename_meta,
)
from story.importer import import_project_stories_to_db
from story.novel_parser import aggregate_novel, get_novel_chapter_list
from story.novel_submission_export import (
    NovelSubmissionExportError,
    generate_novel_submission_zip,
)

files_router = APIRouter()


def _split_story_filename(item: str) -> Optional[tuple[str, str]]:
    """返回故事文件的显示名与格式，仅识别 .arc / .md。"""
    parsed = parse_story_filename(item)
    if not parsed:
        return None
    return parsed['display_name'], parsed['format']


def _resolve_story_file_path(stories_path: str, path: str) -> tuple[Optional[str], Optional[str]]:
    """根据路径解析真实故事文件，兼容 .arc / .md。"""
    resolved_path, file_format, _ = resolve_story_file_path(stories_path, path)
    return resolved_path, file_format


def _batch_story_renames(rename_pairs: list[tuple[str, str]]) -> None:
    prepared = [(src, dst) for src, dst in rename_pairs if src != dst]
    if not prepared:
        return

    staged: dict[str, str] = {}
    for src, _ in prepared:
        temp_path = os.path.join(os.path.dirname(src), make_temp_story_filename(os.path.basename(src)))
        os.rename(src, temp_path)
        staged[src] = temp_path

    for src, dst in prepared:
        os.rename(staged[src], dst)

def _record_story_memory_after_story_save(
    *,
    user_id: str,
    project_name: str,
    stories_path: str,
    file_path: str,
    content: str,
    file_format: str,
) -> Any:
    """显式手动吸收入口：普通保存接口默认不调用。"""
    from agents.story_memory import enqueue_story_content_memory_write

    return enqueue_story_content_memory_write(
        user_id=user_id,
        project_name=project_name,
        stories_path=stories_path,
        file_path=file_path,
        content=content,
        file_format=file_format,
        label="手动保存显式吸收",
    )


class FileOperation(BaseModel):
    projectName: str
    path: str
    type: Optional[str] = None
    sourcePath: Optional[str] = None
    targetPath: Optional[str] = None
    oldPath: Optional[str] = None
    newPath: Optional[str] = None

class StoryData(BaseModel):
    projectName: str
    filename: str
    data: Any

class StoryMemoryAbsorbData(BaseModel):
    projectName: str
    filename: str

class SaveOrder(BaseModel):
    projectName: str
    dirPath: str = ""
    order: List[str]

class ExportRequest(BaseModel):
    projectName: str
    reset: bool = True

@files_router.get('/api/story-files/{project_name}')
async def get_story_files(
    project_name: str,
    format: Optional[str] = Query(None),
    user: Optional[dict] = Depends(get_optional_user),
):
    """返回用户项目 stories 目录下的文件树结构"""
    try:
        if not user:
            return []
        user_id = str(user['user_id'])
        stories_path = ensure_project_stories_directory(user_id, project_name)

        order_file = os.path.join(get_project_path(user_id, project_name), 'stories_order.json')
        order_map = {}
        if os.path.exists(order_file):
            try:
                with open(order_file, 'r', encoding='utf-8') as f:
                    order_map = json.load(f) or {}
            except Exception:
                order_map = {}

        def _extract_chapter_num(folder_name: str) -> int:
            """从文件夹名中提取章节号，支持多种格式：
            - '一 · 开端' -> 1, '二 · 相遇' -> 2（中文数字）
            - '第1章_开端' -> 1, '第02章_相遇' -> 2（第X章格式）
            - '01_开端' -> 1（纯数字开头）
            """
            import re
            # 中文数字映射
            cn_num_map = {
                '一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
                '六': 6, '七': 7, '八': 8, '九': 9, '十': 10,
                '十一': 11, '十二': 12, '十三': 13, '十四': 14, '十五': 15,
                '十六': 16, '十七': 17, '十八': 18, '十九': 19, '二十': 20,
            }
            # 匹配「中文数字 · 标题」格式，如「一 · 开端」
            match = re.match(r'^([一二三四五六七八九十]+)\s*[·•]\s*', folder_name)
            if match:
                cn_num = match.group(1)
                if cn_num in cn_num_map:
                    return cn_num_map[cn_num]
            # 匹配 "第X章" 或 "第XX章" 格式
            match = re.search(r'第(\d+)章', folder_name)
            if match:
                return int(match.group(1))
            # 匹配纯数字开头的格式，如 "01_开端"
            match = re.match(r'^(\d+)', folder_name)
            if match:
                return int(match.group(1))
            return 999999  # 无法识别的放最后

        def reorder_by_user_order(items_list, dir_rel_path):
            order = order_map.get(dir_rel_path or '')
            if not order or not isinstance(order, list):
                # 没有用户自定义顺序时，按章节号排序文件夹
                def default_key_fn(entry):
                    if entry.get('type') == 'folder':
                        return (_extract_chapter_num(entry.get('name', '')), entry.get('name', '').lower())
                    return (999999, entry.get('name', '').lower())
                return sorted(items_list, key=default_key_fn)
            index_map = {name: idx for idx, name in enumerate(order)}
            def key_fn(entry):
                name = entry.get('name', '')
                return (0 if name in index_map else 1, index_map.get(name, 0))
            return sorted(items_list, key=key_fn)

        normalized_filter = (format or '').strip().lower()
        if normalized_filter not in {'arc', 'novel'}:
            normalized_filter = ''

        def scan_directory(path, relative_path=''):
            folders = []
            files = []
            if not os.path.exists(path):
                return []

            for item in os.listdir(path):
                if item.startswith('.'):
                    continue
                item_path = os.path.join(path, item)
                if os.path.isdir(item_path):
                    rel_dir = os.path.join(relative_path, item) if relative_path else item
                    web_dir = rel_dir.replace(os.sep, '/')
                    children = scan_directory(item_path, rel_dir)
                    folders.append({
                        'name': item,
                        'type': 'folder',
                        'path': web_dir,
                        'children': children,
                    })
                elif os.path.isfile(item_path):
                    parsed = parse_story_filename(item)
                    if not parsed:
                        continue
                    name = parsed['display_name']
                    file_type = parsed['format']
                    if normalized_filter and file_type != normalized_filter:
                        continue
                    web_path = build_display_story_path(relative_path, item)
                    scene_count = 0
                    if file_type == 'arc':
                        try:
                            with open(item_path, 'r', encoding='utf-8') as f:
                                content = f.read()
                                scene_count = len([line for line in content.split('\n') if line.strip().startswith('# ')])
                        except Exception:
                            scene_count = 0
                    files.append({
                        'name': name,
                        'type': 'story',
                        'path': web_path,
                        'sceneCount': scene_count,
                        'format': file_type,
                        'filename': strip_story_filename_meta(item),
                        'meta': parsed['meta'],
                        'sortKey': story_sort_key(os.path.join(relative_path, item) if relative_path else item),
                    })

            folders_sorted = reorder_by_user_order(folders, relative_path)
            files_sorted = sorted(files, key=lambda entry: entry.get('sortKey') or story_sort_key(entry.get('filename', '')))
            return folders_sorted + files_sorted

        return scan_directory(stories_path)
    except Exception as exc:
        print(f"Failed to get JSON file list: {exc}")
        return []


@files_router.get('/api/file-content/{project_name}/{path:path}')
async def get_file_content(project_name: str, path: str, user: Optional[dict] = Depends(get_optional_user)):
    """获取故事文件内容，兼容 .arc 与 .md。"""
    try:
        if not user:
            return JSONResponse(status_code=401, content={"error": "需要登录"})
        user_id = str(user['user_id'])
        stories_path = get_project_stories_path(user_id, project_name)

        resolved_path, file_format = _resolve_story_file_path(stories_path, path)
        if resolved_path:
            with open(resolved_path, 'r', encoding='utf-8') as f:
                content = f.read()
            rel_dir = os.path.dirname(os.path.relpath(resolved_path, stories_path))
            return {
                "content": content,
                "format": file_format,
                "path": build_display_story_path('' if rel_dir == '.' else rel_dir, os.path.basename(resolved_path)),
            }

        return JSONResponse(status_code=404, content={"error": "文件不存在"})
    except Exception as exc:
        return JSONResponse(status_code=500, content={"error": f"读取文件失败: {exc}"})


@files_router.post('/api/save-story')
async def save_story(data: StoryData, user: dict = Depends(get_current_user)):
    """保存 stories 目录下的故事文件，兼容 .arc 与 .md。"""
    try:
        user_id = str(user['user_id'])
        project_name = normalize_project_name(data.projectName)
        filename = data.filename
        story_data = data.data

        if not project_name:
            return JSONResponse(status_code=400, content={"success": False, "message": "缺少项目名称"})
        if not filename:
            return JSONResponse(status_code=400, content={"success": False, "message": "文件名不能为空"})

        stories_path = ensure_project_stories_directory(user_id, project_name)

        normalized_filename = str(filename).replace('\\', '/').strip('/')
        file_ext = os.path.splitext(normalized_filename)[1].lower()
        if file_ext not in {'.arc', '.md'}:
            normalized_filename += '.arc'
            file_ext = '.arc'

        resolved_existing_path, _, _ = resolve_story_file_path(stories_path, normalized_filename)
        if resolved_existing_path:
            file_path = resolved_existing_path
        else:
            rel_dir = os.path.dirname(normalized_filename)
            display_name = sanitize_story_display_name(os.path.splitext(os.path.basename(normalized_filename))[0])
            file_path = os.path.join(
                stories_path,
                rel_dir,
                build_story_filename(
                    display_name,
                    file_format='novel' if file_ext == '.md' else 'arc',
                    order=next_story_order(stories_path, rel_dir),
                    free=True,
                ),
            )
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        if file_ext == '.md':
            content = story_data if isinstance(story_data, str) else str(story_data or '')
        else:
            # 确保数据以 ARC 文本格式保存
            if isinstance(story_data, (list, dict)):
                # 如果是结构化数据，序列化为 ARC 格式
                if isinstance(story_data, dict):
                    story_data = [story_data]
                content = serialize_to_arc(story_data)
            else:
                # 已经是字符串
                content = str(story_data)
            
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)

        return {"success": True, "message": "保存成功"}
    except Exception as exc:
        return JSONResponse(status_code=500, content={"success": False, "message": f"保存失败: {exc}"})


@files_router.post('/api/story-memory/absorb-story')
async def absorb_story_memory(data: StoryMemoryAbsorbData, user: dict = Depends(get_current_user)):
    """显式把指定故事文件提交到 StoryMemory 后台吸收队列。"""
    try:
        user_id = str(user['user_id'])
        project_name = normalize_project_name(data.projectName)
        filename = str(data.filename or '').replace('\\', '/').strip('/')

        if not project_name:
            return JSONResponse(status_code=400, content={"success": False, "message": "缺少项目名称"})
        if not filename:
            return JSONResponse(status_code=400, content={"success": False, "message": "文件名不能为空"})

        stories_path = ensure_project_stories_directory(user_id, project_name)
        file_path, file_format = _resolve_story_file_path(stories_path, filename)
        if not file_path or not file_format:
            return JSONResponse(status_code=404, content={"success": False, "message": "文件不存在"})

        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        future = _record_story_memory_after_story_save(
            user_id=user_id,
            project_name=project_name,
            stories_path=stories_path,
            file_path=file_path,
            content=content,
            file_format=file_format,
        )

        return {
            "success": True,
            "queued": future is not None,
            "message": "已提交记忆吸收任务",
        }
    except Exception as exc:
        return JSONResponse(status_code=500, content={"success": False, "message": f"提交记忆吸收失败: {exc}"})


@files_router.post('/api/file-operations/create')
async def create_file_or_folder(data: FileOperation, user: dict = Depends(get_current_user)):
    """创建文件或文件夹"""
    try:
        user_id = str(user['user_id'])
        project_name = normalize_project_name(data.projectName)
        if not project_name:
            return JSONResponse(status_code=400, content={"success": False, "message": "缺少项目名称"})

        stories_path = ensure_project_stories_directory(user_id, project_name)
        file_type = data.type
        normalized_path = str(data.path or '').replace('\\', '/').strip('/')
        file_path = os.path.join(stories_path, normalized_path)

        if file_type == 'folder':
            if os.path.exists(file_path):
                return JSONResponse(status_code=409, content={"success": False, "message": f"分卷 '{os.path.basename(file_path)}' 已存在"})
            os.makedirs(file_path, exist_ok=True)
        else:
            file_ext = os.path.splitext(file_path)[1].lower()
            if file_ext not in {'.arc', '.txt', '.md'}:
                file_ext = '.arc'
                file_path += '.arc'
            if file_ext in {'.arc', '.md'}:
                rel_dir = os.path.dirname(normalized_path)
                display_name = sanitize_story_display_name(os.path.splitext(os.path.basename(normalized_path))[0])
                file_path = os.path.join(
                    stories_path,
                    rel_dir,
                    build_story_filename(
                        display_name,
                        file_format='novel' if file_ext == '.md' else 'arc',
                        order=next_story_order(stories_path, rel_dir),
                        free=True,
                    ),
                )
            if os.path.exists(file_path):
                return JSONResponse(status_code=409, content={"success": False, "message": f"文件 '{os.path.basename(file_path)}' 已存在"})
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            if file_path.endswith('.arc'):
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write("# 新场景\n\n[-1]\n在这里开始你的创作...")
            elif file_path.endswith('.md'):
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write("# 新章节\n\n在这里开始你的小说创作……")
            elif file_path.endswith('.txt'):
                with open(file_path, 'w', encoding='utf-8') as f:
                    pass

        return {"success": True, "message": "创建成功"}
    except Exception as exc:
        return JSONResponse(status_code=500, content={"success": False, "message": f"创建失败: {exc}"})


@files_router.post('/api/file-operations/delete')
async def delete_file_or_folder(data: FileOperation, user: dict = Depends(get_current_user)):
    """删除文件或文件夹"""
    try:
        user_id = str(user['user_id'])
        project_name = normalize_project_name(data.projectName)
        if not project_name:
            return JSONResponse(status_code=400, content={"success": False, "message": "缺少项目名称"})

        stories_path = ensure_project_stories_directory(user_id, project_name)
        normalized_path = str(data.path or '').replace('\\', '/').strip('/')
        file_path = os.path.join(stories_path, normalized_path)
        if os.path.isdir(file_path):
            shutil.rmtree(file_path)
            return {"success": True, "message": "删除成功"}

        resolved_story_path, _, _ = resolve_story_file_path(stories_path, normalized_path)
        if resolved_story_path and os.path.exists(resolved_story_path):
            os.remove(resolved_story_path)
            return {"success": True, "message": "删除成功"}
        txt_path = file_path if file_path.endswith('.txt') else file_path + '.txt'
        if os.path.exists(txt_path):
            os.remove(txt_path)
            return {"success": True, "message": "删除成功"}

        return JSONResponse(status_code=404, content={"success": False, "message": "文件或文件夹不存在"})
    except Exception as exc:
        return JSONResponse(status_code=500, content={"success": False, "message": f"删除失败: {exc}"})


def _extract_chapter_number(dir_rel_path: str, stories_path: str) -> Optional[int]:
    import re
    cleaned_dir = str(dir_rel_path).replace('\\', '/').strip('/')
    if not cleaned_dir:
        return None
    
    # 1. 尝试从最内层文件夹名中直接匹配首个连续数字
    folder_name = os.path.basename(cleaned_dir)
    match = re.search(r'(\d+)', folder_name)
    if match:
        return int(match.group(1))
        
    # 2. 兜底：扫描同级所有文件夹，找到自己在其中的排序索引 + 1
    parent_dir = os.path.dirname(cleaned_dir)
    parent_abs_path = os.path.join(stories_path, parent_dir)
    if not os.path.exists(parent_abs_path) or not os.path.isdir(parent_abs_path):
        return None
        
    try:
        subdirs = []
        for item in os.listdir(parent_abs_path):
            if item.startswith('.'):
                continue
            if os.path.isdir(os.path.join(parent_abs_path, item)):
                subdirs.append(item)
        subdirs.sort() # 按默认排序
        if folder_name in subdirs:
            return subdirs.index(folder_name) + 1
    except Exception:
        pass
    return None


@files_router.post('/api/file-operations/move')
async def move_file_or_folder(data: FileOperation, user: dict = Depends(get_current_user)):
    """移动或移动重命名文件/文件夹"""
    try:
        user_id = str(user['user_id'])
        project_name = normalize_project_name(data.projectName)
        source = data.sourcePath
        target = data.targetPath
        if not project_name or not source or not target:
            return JSONResponse(status_code=400, content={"success": False, "message": "缺少参数"})

        stories_path = ensure_project_stories_directory(user_id, project_name)
        source_path = os.path.join(stories_path, source)
        target_path = os.path.join(stories_path, target)

        if os.path.isdir(source_path):
            target_dir = os.path.dirname(target_path)
            if target_dir:
                os.makedirs(target_dir, exist_ok=True)
            shutil.move(source_path, target_path)
            return {"success": True, "message": "移动成功"}

        resolved_source_path, _, parsed = resolve_story_file_path(stories_path, source)
        if resolved_source_path and parsed:
            target_dir_rel = os.path.dirname(str(target).replace('\\', '/').strip('/'))
            target_display_name = sanitize_story_display_name(os.path.splitext(os.path.basename(target))[0])
            
            # 动态计算并纠正移动后的目标章节号
            target_chapter_num = _extract_chapter_number(target_dir_rel, stories_path)
            
            final_target_path = os.path.join(
                stories_path,
                target_dir_rel,
                rebuild_story_filename(
                    os.path.basename(resolved_source_path),
                    display_name=target_display_name,
                    chapter_num=target_chapter_num
                ),
            )
            os.makedirs(os.path.dirname(final_target_path), exist_ok=True)
            shutil.move(resolved_source_path, final_target_path)
            return {"success": True, "message": "移动成功"}

        target_dir = os.path.dirname(target_path)
        if target_dir:
            os.makedirs(target_dir, exist_ok=True)
        shutil.move(source_path, target_path)
        return {"success": True, "message": "移动成功"}
    except Exception as exc:
        return JSONResponse(status_code=500, content={"success": False, "message": f"移动失败: {exc}"})


@files_router.post('/api/file-operations/rename')
async def rename_file_or_folder(data: FileOperation, user: dict = Depends(get_current_user)):
    try:
        user_id = str(user['user_id'])
        project_name = normalize_project_name(data.projectName)
        old_path = data.sourcePath or data.oldPath or data.path or getattr(data, 'source', None)
        new_path = data.targetPath or data.newPath or getattr(data, 'target', None)
        if not project_name or not old_path or not new_path:
            return JSONResponse(status_code=400, content={"success": False, "message": "缺少参数"})

        stories_path = ensure_project_stories_directory(user_id, project_name)
        source_path = os.path.join(stories_path, old_path)
        target_path = os.path.join(stories_path, new_path)
        if os.path.isdir(source_path):
            target_dir = os.path.dirname(target_path)
            if target_dir:
                os.makedirs(target_dir, exist_ok=True)
            shutil.move(source_path, target_path)
            return {"success": True, "message": "重命名成功"}

        resolved_source_path, _, parsed = resolve_story_file_path(stories_path, old_path)
        if resolved_source_path and parsed:
            target_dir_rel = os.path.dirname(str(new_path).replace('\\', '/').strip('/'))
            target_display_name = sanitize_story_display_name(os.path.splitext(os.path.basename(new_path))[0])
            final_target_path = os.path.join(
                stories_path,
                target_dir_rel,
                rebuild_story_filename(os.path.basename(resolved_source_path), display_name=target_display_name),
            )
            os.makedirs(os.path.dirname(final_target_path), exist_ok=True)
            shutil.move(resolved_source_path, final_target_path)
            return {"success": True, "message": "重命名成功"}

        target_dir = os.path.dirname(target_path)
        if target_dir:
            os.makedirs(target_dir, exist_ok=True)
        shutil.move(source_path, target_path)
        return {"success": True, "message": "重命名成功"}
    except Exception as exc:
        return JSONResponse(status_code=500, content={"success": False, "message": f"重命名失败: {exc}"})


@files_router.post('/api/file-operations/save-order')
async def save_stories_order(data: SaveOrder, user: dict = Depends(get_current_user)):
    try:
        user_id = str(user['user_id'])
        project_name = normalize_project_name(data.projectName)
        dir_path = data.dirPath or ''
        order = data.order or []
        if not project_name:
            return JSONResponse(status_code=400, content={"success": False, "message": "缺少项目名称"})

        project_path = get_project_path(user_id, project_name)
        order_file = os.path.join(project_path, 'stories_order.json')
        stories_path = ensure_project_stories_directory(user_id, project_name)
        dir_abs_path = os.path.join(stories_path, dir_path)

        folder_names = []
        rename_pairs: list[tuple[str, str]] = []
        if os.path.isdir(dir_abs_path):
            story_map = {}
            for item in os.listdir(dir_abs_path):
                item_abs = os.path.join(dir_abs_path, item)
                if os.path.isdir(item_abs):
                    folder_names.append(item)
                    continue
                parsed = parse_story_filename(item)
                if parsed:
                    story_map[parsed['display_name']] = item_abs

            next_order_value = 1
            for display_name in order:
                source_abs_path = story_map.get(display_name)
                if not source_abs_path:
                    continue
                target_abs_path = os.path.join(
                    dir_abs_path,
                    rebuild_story_filename(os.path.basename(source_abs_path), order=next_order_value),
                )
                rename_pairs.append((source_abs_path, target_abs_path))
                next_order_value += 1

            _batch_story_renames(rename_pairs)

        orders = {}
        if os.path.exists(order_file):
            try:
                with open(order_file, 'r', encoding='utf-8') as f:
                    orders = json.load(f) or {}
            except Exception:
                orders = {}
        folder_order = [name for name in order if name in folder_names]
        if folder_order:
            orders[dir_path or ''] = folder_order
        else:
            orders.pop(dir_path or '', None)
        with open(order_file, 'w', encoding='utf-8') as f:
            json.dump(orders, f, ensure_ascii=False, indent=2)
        return {"success": True, "message": "排序保存成功"}
    except Exception as exc:
        return JSONResponse(status_code=500, content={"success": False, "message": f"保存排序失败: {exc}"})


@files_router.post('/api/export-to-sqlite')
async def export_to_sqlite(data: ExportRequest, user: dict = Depends(get_current_user)):
    """将项目剧本导出为 SQLite 数据库"""
    try:
        user_id = str(user['user_id'])
        project_name = normalize_project_name(data.projectName)
        reset = data.reset
        
        if not project_name:
            return JSONResponse(status_code=400, content={"success": False, "message": "项目名称不能为空"})
            
        result = import_project_stories_to_db(user_id, project_name, reset=reset)
        return {"success": True, "message": "导出成功", "result": result}
    except Exception as exc:
        return JSONResponse(status_code=500, content={"success": False, "message": f"导出失败: {exc}"})


@files_router.post('/api/export-to-sqlite/download')
async def export_and_download_sqlite(data: ExportRequest, user: dict = Depends(get_current_user)):
    """将项目剧本导出为 SQLite 数据库并返回文件供下载"""
    from fastapi.responses import FileResponse
    
    try:
        user_id = str(user['user_id'])
        project_name = normalize_project_name(data.projectName)
        reset = data.reset
        
        if not project_name:
            return JSONResponse(status_code=400, content={"success": False, "message": "项目名称不能为空"})
            
        result = import_project_stories_to_db(user_id, project_name, reset=reset)
        db_path = result.get('db_path')
        
        if not db_path or not os.path.exists(db_path):
            return JSONResponse(status_code=500, content={"success": False, "message": "数据库文件生成失败"})
        
        # 返回文件供下载
        filename = f"{project_name}_stories.db"
        return FileResponse(
            path=db_path,
            media_type='application/x-sqlite3',
            filename=filename,
            headers={
                "X-Chapters": str(result.get('chapters', 0)),
                "X-Scenes": str(result.get('scenes', 0)),
            }
        )
    except Exception as exc:
        return JSONResponse(status_code=500, content={"success": False, "message": f"导出失败: {exc}"})


@files_router.get('/api/story-novel/{project_name}/toc')
async def get_novel_toc(project_name: str, user: dict = Depends(get_current_user)):
    """获取当前项目小说的章节目录（TOC）"""
    try:
        user_id = str(user['user_id'])
        toc = get_novel_chapter_list(user_id, project_name, export_format="md")
        return {"success": True, "toc": toc}
    except Exception as exc:
        return JSONResponse(status_code=500, content={"success": False, "message": f"获取小说目录失败: {exc}"})


@files_router.get('/api/story-novel/{project_name}/export')
async def export_novel_markdown(project_name: str, user: dict = Depends(get_current_user)):
    """聚合该项目下所有的场景 Markdown，返回完整的小说文本供下载"""
    try:
        user_id = str(user['user_id'])
        full_markdown = aggregate_novel(user_id, project_name, export_format="md")
        
        # 将聚合结果写入临时文件以便下载
        project_path = get_project_path(user_id, project_name)
        export_dir = os.path.join(project_path, "exports")
        os.makedirs(export_dir, exist_ok=True)
        export_file = os.path.join(export_dir, f"{project_name}_novel.md")
        
        with open(export_file, "w", encoding="utf-8") as f:
            f.write(full_markdown)

        from fastapi.responses import FileResponse
        return FileResponse(
            path=export_file,
            media_type='text/markdown',
            filename=f"{project_name}_novel.md"
        )
    except Exception as exc:
        return JSONResponse(status_code=500, content={"success": False, "message": f"导出小说失败: {exc}"})


@files_router.get('/api/story-novel/{project_name}/submission-export')
async def export_novel_submission_package(
    project_name: str,
    platform: str = Query(..., description="投稿平台标识"),
    user: dict = Depends(get_current_user),
):
    """导出面向小说平台作者后台的投稿 zip 包。"""
    try:
        user_id = str(user['user_id'])
        normalized_project_name = normalize_project_name(project_name)
        if not normalized_project_name:
            return JSONResponse(status_code=400, content={"success": False, "message": "项目名称不能为空"})

        toc = get_novel_chapter_list(user_id, normalized_project_name, export_format="md")
        package = generate_novel_submission_zip(normalized_project_name, toc, platform)
        encoded_filename = quote(package.filename, safe="")
        return Response(
            content=package.content,
            media_type="application/zip",
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}",
                "X-Novel-Submission-Platform": package.platform.key,
                "X-Novel-Submission-Chapters": str(package.chapter_count),
            },
        )
    except NovelSubmissionExportError as exc:
        return JSONResponse(status_code=400, content={"success": False, "message": str(exc)})
    except Exception as exc:
        return JSONResponse(status_code=500, content={"success": False, "message": f"导出投稿包失败: {exc}"})
