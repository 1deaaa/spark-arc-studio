"""
Auto-Write API - 自动化剧本撰写
"""

import json
import os
import asyncio
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from datetime import datetime

from core.auth import get_current_user
from core.utils import get_project_path
from agents.agent_scriptwriter import ScriptwriterAgent

auto_write_router = APIRouter()

async def generate_script_stream(
    user_id: str,
    project_name: str,
    outline: Dict[str, Any],
    mode: str = "chapter_by_chapter", # "all" or "chapter_by_chapter"
    start_chapter_index: int = 0,
    context_strategy: str = "accumulate"
):
    """
    Generator function for SSE streaming of script generation progress.
    """
    
    # 1. Initialize
    nodes = outline.get('nodes', [])
    stories_path = os.path.join(get_project_path(user_id, project_name), 'stories')
    os.makedirs(stories_path, exist_ok=True)
    
    # Filter chapters (skip those before start_chapter_index)
    # Note: nodes can contain non-chapter items if the structure is complex, 
    # but usually top-level nodes are chapters.
    chapter_nodes = [n for n in nodes if n.get('type') == 'chapter']
    
    if start_chapter_index >= len(chapter_nodes):
        yield f"data: {json.dumps({'status': 'complete', 'message': 'No more chapters to write.'})}\n\n"
        return

    writer = ScriptwriterAgent(user_id)
    
    # Context accumulation (simple version: just keep track of what happened)
    # In a real accumulating strategy, we might want to read previous summaries.
    accumulated_context = outline.get('summary', '') or "无前文。"
    
    chapters_processed = 0
    
    for i in range(start_chapter_index, len(chapter_nodes)):
        chapter = chapter_nodes[i]
        chapter_num = chapter.get('chapter', i + 1)
        chapter_title = chapter.get('title', f'Chapter {chapter_num}')
        scenes = chapter.get('children', [])
        
        yield f"data: {json.dumps({'status': 'chapter_start', 'chapter_index': i, 'chapter_title': chapter_title})}\n\n"
        
        # Prepare file path
        safe_title = chapter_title.replace(':', '').replace('：', '').replace('/', '_').replace('\\', '_')
        filename = f"{safe_title}.arc"
        filepath = os.path.join(stories_path, filename)
        
        # Determine existing content or start fresh?
        # For auto-write, we generally assume we are writing fresh or overwriting.
        # But maybe we want to support appending? For now: Overwrite/Create New.
        
        full_arc_content = []
        full_arc_content.append(f"<!-- 章节 {chapter_num}: {chapter_title} -->")
        if chapter.get('description'):
            full_arc_content.append(f"<!-- {chapter.get('description')} -->")
        full_arc_content.append("")
        
        for scene_idx, scene in enumerate(scenes):
            scene_title = scene.get('title', f'Scene {scene_idx + 1}')
            scene_desc = scene.get('description', '')
            
            # Update User
            yield f"data: {json.dumps({
                'status': 'writing_scene', 
                'chapter_index': i,
                'chapter_title': chapter_title,
                'scene_index': scene_idx,
                'scene_title': scene_title
            })}\n\n"
            
            # Construct Prompt Context
            # We provide:
            # 1. Overall Story Context (from Outline Summary + Accumulation)
            # 2. Current Chapter Goal
            # 3. Current Scene Goal
            
            current_context = f"""
【全局概要】
{outline.get('summary', '')}

【当前前文状况】
{accumulated_context[-2000:]} 

【当前章节目标】
{chapter_title}: {chapter.get('description', '')}
"""
            
            scene_goal = f"""
【当前场景任务】
场景名：{scene_title}
场景描述：{scene_desc}
请撰写本场景的完整剧本内容。
"""
            
            # Call Agent (Sync call wrapped in thread or async if supported)
            # agent_scriptwriter.py's write_script is synchronous LLM invoke usually, 
            # unless we use async invoke. The ScriptwriterAgent uses self.llm.invoke.
            # We should try to run it in a thread to not block the event loop? 
            # Or just await if langchain supports it. 
            # ScriptwriterAgent.write_script is currently sync.
            # We will use `asyncio.to_thread` for safety.
            
            try:
                # We need to construct roles map if available, currently mostly empty or from project
                # We'll pass minimal needed
                arc_text, thought = await asyncio.to_thread(
                    writer.write_script,
                    context=current_context,
                    worldview="（请基于当前项目世界观）",
                    roles="（请根据场景描述推断角色）",
                    segment_count=0, # 0 means full scene
                    guidance=scene_goal
                )
                
                # Append to file content
                full_arc_content.append(f"# {scene_title}")
                if scene_desc:
                    full_arc_content.append(f"@intro\n{scene_desc}")
                full_arc_content.append("")
                full_arc_content.append(arc_text)
                full_arc_content.append("")
                
                # Update accumulation (naive)
                accumulated_context += f"\n(场景 {scene_title} 完成)\n"
                
                # Send chunk update (optional, maybe just 'scene_completed')
                yield f"data: {json.dumps({
                    'status': 'scene_completed',
                    'scene_title': scene_title,
                    'preview': arc_text[:100] + '...'
                })}\n\n"
                
            except Exception as e:
                print(f"Error writing scene {scene_title}: {e}")
                yield f"data: {json.dumps({'status': 'error', 'message': str(e)})}\n\n"
                # Continue or break? Let's break current scene
                full_arc_content.append(f"# {scene_title} (Generation Failed)")
                full_arc_content.append(f"Error: {str(e)}")
        
        # Save Chapter File
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write('\n'.join(full_arc_content))
            
        yield f"data: {json.dumps({'status': 'chapter_saved', 'filename': filename})}\n\n"
        
        chapters_processed += 1
        
        # Check Mode
        if mode == "chapter_by_chapter":
            yield f"data: {json.dumps({'status': 'paused', 'next_chapter_index': i + 1})}\n\n"
            return

    yield f"data: {json.dumps({'status': 'complete'})}\n\n"


@auto_write_router.post('/api/outline/{project_name}/auto-write-stream')
async def auto_write_stream(
    project_name: str, 
    request: Request,
    user: dict = Depends(get_current_user)
):
    user_id = str(user['user_id'])
    data = await request.json() or {}
    mode = data.get('mode', 'chapter_by_chapter')
    start_chapter_index = data.get('start_chapter_index', 0)
    
    # Load Outline
    outline_path = os.path.join(get_project_path(user_id, project_name), 'outline.json')
    if not os.path.exists(outline_path):
        return {"error": "Outline not found"}
        
    with open(outline_path, 'r', encoding='utf-8') as f:
        outline = json.load(f)
        
    return StreamingResponse(
        generate_script_stream(user_id, project_name, outline, mode, start_chapter_index),
        media_type="text/event-stream"
    )
