import json
import os
import re
from typing import Dict, Any, List
from core.utils import get_project_stories_path, get_project_path
from story.file_naming import build_scene_story_filename, strip_story_filename_meta


def _load_project_outline(user_id: str, project_name: str) -> Dict[str, Any]:
    """读取项目 大纲.txt，解析失败返回空大纲。"""
    from story.outline_parser import parse_outline_markup
    path = os.path.join(get_project_path(user_id, project_name), "大纲.txt")
    if not os.path.exists(path):
        return {"nodes": []}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return parse_outline_markup(f.read())
    except Exception:
        return {"nodes": []}

def parse_scene_md(text: str) -> str:
    """
    清洗单个场景 .md 文件：移除 thought 块与 HTML 注释头。
    """
    # 移除 <!-- 注释 -->
    text = re.sub(r'<!--.*?-->', '', text, flags=re.DOTALL)
    # 移除 <conception>...</conception>
    text = re.sub(r'<conception>.*?</conception>', '', text, flags=re.DOTALL)
    # 移除可能存在的 @intro 开头的多行信息直到遇到空行或 #
    text = re.sub(r'@intro\s*.*?(?=\n\n|\n#|$)', '', text, flags=re.DOTALL)
    
    # 清理多余空行，保证最多两个连续换行
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

def get_novel_chapter_list(user_id: str, project_name: str, export_format: str = "md") -> List[Dict[str, Any]]:
    """
    返回章节+场景的目录树及具体内容，供前端阅读器或导出时聚合使用。
    """
    outline = _load_project_outline(user_id, project_name)
    stories_path = get_project_stories_path(user_id, project_name)
    
    chapter_nodes = [node for node in (outline.get("nodes", [])) if node.get("type") == "chapter"]
    
    toc = []
    
    for ch_idx, chapter in enumerate(chapter_nodes):
        chapter_num = chapter.get("chapter", ch_idx + 1)
        chapter_title = chapter.get("title", f"Chapter {chapter_num}")
        scenes = chapter.get("children", [])
        
        chapter_info = {
            "chapter_num": chapter_num,
            "title": chapter_title,
            "scenes": []
        }
        
        for s_idx, scene in enumerate(scenes):
            scene_title = scene.get("title", f"Scene {s_idx + 1}")
            filename = build_scene_story_filename(
                chapter_num,
                s_idx + 1,
                scene_title,
                file_format=export_format,
            )
            filepath = os.path.join(stories_path, filename)
            
            content = ""
            if os.path.exists(filepath):
                with open(filepath, "r", encoding="utf-8") as f:
                    raw_content = f.read()
                content = parse_scene_md(raw_content)
                
            chapter_info["scenes"].append({
                "scene_idx": s_idx,
                "title": scene_title,
                "content": content,
                "exists": os.path.exists(filepath),
                "filename": strip_story_filename_meta(filename)
            })
            
        toc.append(chapter_info)
        
    return toc

def aggregate_novel(user_id: str, project_name: str, export_format: str = "md") -> str:
    """
    按 大纲.txt 顺序聚合所有场景 .md 文件，返回完整 Markdown 文本。
    """
    toc = get_novel_chapter_list(user_id, project_name, export_format)
    
    full_text_blocks = []
    full_text_blocks.append(f"# {project_name}\n")
    
    for chapter in toc:
        has_content = any(s["exists"] and s["content"].strip() for s in chapter["scenes"])
        if not has_content:
            continue
            
        # 章节大标题
        full_text_blocks.append(f"## 第{chapter['chapter_num']}章 {chapter['title']}")
        
        for scene in chapter["scenes"]:
            if not scene["exists"] or not scene["content"].strip():
                continue
            
            # 场景正文（自带 # 场景名，如果是 AI 生成的话。为避免重复，可以直接使用清洗后的 content）
            full_text_blocks.append(scene["content"])
            
        full_text_blocks.append("")  # 章节末尾加空行
        
    return "\n\n".join(full_text_blocks).strip()
