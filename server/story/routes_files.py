from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Optional, Any
import os
import json
import shutil

from core.auth import get_current_user, get_optional_user
from core.utils import (
    ensure_project_stories_directory,
    get_project_stories_path,
    get_project_path,
)
from story.arc_parser import serialize_to_arc
from story.importer import import_project_stories_to_db
from story.novel_parser import aggregate_novel, get_novel_chapter_list

files_router = APIRouter()


def _split_story_filename(item: str) -> Optional[tuple[str, str]]:
    """返回故事文件的显示名与格式，仅识别 .arc / .md。"""
    if item.endswith('.arc'):
        return item[:-4], 'arc'
    if item.endswith('.md'):
        return item[:-3], 'novel'
    return None


def _resolve_story_file_path(stories_path: str, path: str) -> tuple[Optional[str], Optional[str]]:
    """根据路径解析真实故事文件，兼容 .arc / .md。"""
    file_path = os.path.join(stories_path, path)
    candidates: list[str] = []

    if os.path.splitext(file_path)[1].lower() in {'.arc', '.md'}:
        candidates.append(file_path)
    else:
        candidates.append(file_path + '.arc')
        candidates.append(file_path + '.md')

    for candidate in candidates:
        if os.path.exists(candidate):
            ext = os.path.splitext(candidate)[1].lower()
            return candidate, ('novel' if ext == '.md' else 'arc')

    return None, None

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

class SaveOrder(BaseModel):
    projectName: str
    dirPath: str = ""
    order: List[str]

class ExportRequest(BaseModel):
    projectName: str
    reset: bool = True

@files_router.get('/api/story-files/{project_name}')
async def get_story_files(project_name: str, user: Optional[dict] = Depends(get_optional_user)):
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

        def reorder_by_user_order(items_list, dir_rel_path):
            order = order_map.get(dir_rel_path or '')
            if not order or not isinstance(order, list):
                return items_list
            index_map = {name: idx for idx, name in enumerate(order)}
            def key_fn(entry):
                name = entry.get('name', '')
                return (0 if name in index_map else 1, index_map.get(name, 0))
            return sorted(items_list, key=key_fn)

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
                    split_result = _split_story_filename(item)
                    if not split_result:
                        continue
                    name, file_type = split_result
                    rel_name = item if file_type == 'novel' else name
                    rel = os.path.join(relative_path, rel_name) if relative_path else rel_name
                    web_path = rel.replace(os.sep, '/')
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
                    })

            folders_sorted = reorder_by_user_order(folders, relative_path)
            files_sorted = reorder_by_user_order(files, relative_path)
            return folders_sorted + files_sorted

        return scan_directory(stories_path)
    except Exception as exc:
        print(f"获取 JSON 文件列表失败: {exc}")
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
            return {
                "content": content,
                "format": file_format,
                "path": os.path.relpath(resolved_path, stories_path).replace(os.sep, '/'),
            }

        return JSONResponse(status_code=404, content={"error": "文件不存在"})
    except Exception as exc:
        return JSONResponse(status_code=500, content={"error": f"读取文件失败: {exc}"})


@files_router.post('/api/save-story')
async def save_story(data: StoryData, user: dict = Depends(get_current_user)):
    """保存 stories 目录下的故事文件，兼容 .arc 与 .md。"""
    try:
        user_id = str(user['user_id'])
        project_name = data.projectName
        filename = data.filename
        story_data = data.data

        if not project_name:
            return JSONResponse(status_code=400, content={"success": False, "message": "缺少项目名称"})
        if not filename:
            return JSONResponse(status_code=400, content={"success": False, "message": "文件名不能为空"})

        stories_path = ensure_project_stories_directory(user_id, project_name)

        normalized_filename = str(filename)
        file_ext = os.path.splitext(normalized_filename)[1].lower()
        if file_ext not in {'.arc', '.md'}:
            normalized_filename += '.arc'
            file_ext = '.arc'

        file_path = os.path.join(stories_path, normalized_filename)
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


@files_router.post('/api/file-operations/create')
async def create_file_or_folder(data: FileOperation, user: dict = Depends(get_current_user)):
    """创建文件或文件夹"""
    try:
        user_id = str(user['user_id'])
        project_name = data.projectName
        if not project_name:
            return JSONResponse(status_code=400, content={"success": False, "message": "缺少项目名称"})

        stories_path = ensure_project_stories_directory(user_id, project_name)
        file_type = data.type
        file_path = os.path.join(stories_path, data.path)

        if file_type == 'folder':
            os.makedirs(file_path, exist_ok=True)
        else:
            if not file_path.endswith('.arc') and not file_path.endswith('.txt') and not file_path.endswith('.md'):
                file_path += '.arc'
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
        project_name = data.projectName
        if not project_name:
            return JSONResponse(status_code=400, content={"success": False, "message": "缺少项目名称"})

        stories_path = ensure_project_stories_directory(user_id, project_name)
        file_path = os.path.join(stories_path, data.path)
        if os.path.isdir(file_path):
            shutil.rmtree(file_path)
            return {"success": True, "message": "删除成功"}

        # 尝试直接删除给定路径
        if os.path.exists(file_path):
            os.remove(file_path)
            return {"success": True, "message": "删除成功"}

        arc_path = file_path if file_path.endswith('.arc') else file_path + '.arc'
        md_path = file_path if file_path.endswith('.md') else file_path + '.md'
        txt_path = file_path if file_path.endswith('.txt') else file_path + '.txt'

        if os.path.exists(arc_path):
            os.remove(arc_path)
            return {"success": True, "message": "删除成功"}
        if os.path.exists(md_path):
            os.remove(md_path)
            return {"success": True, "message": "删除成功"}
        if os.path.exists(txt_path):
            os.remove(txt_path)
            return {"success": True, "message": "删除成功"}

        return JSONResponse(status_code=404, content={"success": False, "message": "文件或文件夹不存在"})
    except Exception as exc:
        return JSONResponse(status_code=500, content={"success": False, "message": f"删除失败: {exc}"})


@files_router.post('/api/file-operations/move')
async def move_file_or_folder(data: FileOperation, user: dict = Depends(get_current_user)):
    """移动或移动重命名文件/文件夹"""
    try:
        user_id = str(user['user_id'])
        project_name = data.projectName
        source = data.sourcePath
        target = data.targetPath
        if not project_name or not source or not target:
            return JSONResponse(status_code=400, content={"success": False, "message": "缺少参数"})

        stories_path = ensure_project_stories_directory(user_id, project_name)
        source_path = os.path.join(stories_path, source)
        target_path = os.path.join(stories_path, target)

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
        project_name = data.projectName
        old_path = data.sourcePath or data.oldPath or data.path or getattr(data, 'source', None)
        new_path = data.targetPath or data.newPath or getattr(data, 'target', None)
        if not project_name or not old_path or not new_path:
            return JSONResponse(status_code=400, content={"success": False, "message": "缺少参数"})

        stories_path = ensure_project_stories_directory(user_id, project_name)
        source_path = os.path.join(stories_path, old_path)
        target_path = os.path.join(stories_path, new_path)
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
        project_name = data.projectName
        dir_path = data.dirPath or ''
        order = data.order or []
        if not project_name:
            return JSONResponse(status_code=400, content={"success": False, "message": "缺少项目名称"})

        project_path = get_project_path(user_id, project_name)
        order_file = os.path.join(project_path, 'stories_order.json')
        orders = {}
        if os.path.exists(order_file):
            try:
                with open(order_file, 'r', encoding='utf-8') as f:
                    orders = json.load(f) or {}
            except Exception:
                orders = {}
        orders[dir_path or ''] = order
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
        project_name = data.projectName
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
        project_name = data.projectName
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
