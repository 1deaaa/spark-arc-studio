"""
Auto-Write API - 自动化剧本撰写
"""

import json
import os
import asyncio
import time
import queue
import threading
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
            
            try:
                # 使用队列实现真正的实时流式推送
                arc_text = ""
                thought = ""
                start_time = time.time()
                total_chars = 0
                last_progress_time = start_time
                accumulated_content = ""
                
                # 创建队列用于线程间通信
                result_queue = queue.Queue()
                
                def run_stream_to_queue():
                    """在线程中运行生成器，将结果放入队列"""
                    try:
                        for event in writer.write_script_stream(
                            context=current_context,
                            worldview="（请基于当前项目世界观）",
                            roles="（请根据场景描述推断角色）",
                            segment_count=0,
                            guidance=scene_goal
                        ):
                            result_queue.put(event)
                        result_queue.put(None)  # 结束标记
                    except Exception as e:
                        result_queue.put({'type': 'error', 'message': str(e)})
                        result_queue.put(None)
                
                # 启动生成线程
                gen_thread = threading.Thread(target=run_stream_to_queue)
                gen_thread.start()
                
                # 异步消费队列，实时推送
                heartbeat_interval = 2.0  # 每2秒发一次心跳防止连接超时
                last_heartbeat = time.time()
                
                while True:
                    # 非阻塞检查队列
                    try:
                        event = result_queue.get_nowait()
                    except queue.Empty:
                        # 发送心跳保持连接
                        current_time = time.time()
                        if current_time - last_heartbeat >= heartbeat_interval:
                            yield f": heartbeat\n\n"  # SSE 注释格式，客户端会忽略
                            last_heartbeat = current_time
                        await asyncio.sleep(0.05)  # 更短的检查间隔
                        continue
                    
                    if event is None:  # 结束标记
                        break
                    
                    if event['type'] == 'error':
                        raise Exception(event['message'])
                    
                    if event['type'] == 'chunk':
                        accumulated_content += event['content']
                        total_chars = event['total_chars']
                        current_time = time.time()
                        elapsed = current_time - start_time
                        
                        # 每 0.5 秒推送一次进度更新
                        if current_time - last_progress_time >= 0.5:
                            speed = total_chars / elapsed if elapsed > 0 else 0
                            # 取累积内容的最后 30 个字符作为预览
                            preview = accumulated_content[-30:] if len(accumulated_content) > 30 else accumulated_content
                            
                            yield f"data: {json.dumps({
                                'status': 'streaming',
                                'scene_title': scene_title,
                                'preview': preview,
                                'total_chars': total_chars,
                                'speed': round(speed, 1),
                                'elapsed': round(elapsed, 1)
                            }, ensure_ascii=False)}\n\n"
                            last_progress_time = current_time
                            
                    elif event['type'] == 'done':
                        arc_text = event['arc_script']
                        thought = event.get('thought', '')
                        total_chars = event['total_chars']
                
                gen_thread.join()  # 确保线程结束
                
                elapsed = time.time() - start_time
                avg_speed = total_chars / elapsed if elapsed > 0 else 0
                
                # Append to file content
                full_arc_content.append(f"# {scene_title}")
                if scene_desc:
                    full_arc_content.append(f"@intro\n{scene_desc}")
                full_arc_content.append("")
                full_arc_content.append(arc_text)
                full_arc_content.append("")
                
                # Update accumulation (naive)
                accumulated_context += f"\n(场景 {scene_title} 完成)\n"
                
                # Send completion with stats
                yield f"data: {json.dumps({
                    'status': 'scene_completed',
                    'scene_title': scene_title,
                    'preview': arc_text[:100] + '...' if len(arc_text) > 100 else arc_text,
                    'total_chars': total_chars,
                    'elapsed': round(elapsed, 1),
                    'avg_speed': round(avg_speed, 1)
                }, ensure_ascii=False)}\n\n"
                
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
