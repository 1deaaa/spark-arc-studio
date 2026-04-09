"""
Auto-Write API - 自动化剧本撰写的异步批处理引擎。

════════════════════════════════════════════════════════════════════════
【架构定位：无人值守的长连接连续生成管道】

本文件不仅实现了与 `production.py` 类似的【业务语义流 (Stream Semantics)】标准 SSE 通信，
更进一步实现了一个复杂的状态机，用于控制**跨章节、多场景**的连续无人值守生成。

【工作流核心机制】
1. 状态落地：通过 `auto_write_state.py` 将当前运行游标（Chapter / Scene Index）实时落盘。
2. 线程隔离与心跳通信：长耗时的 AI 调用被推入子线程，通过 `queue.Queue` 与主协程通讯，主协程
   负责发送 Keep-Alive 心跳 (`: heartbeat\\n\\n`) 和定时打包的 progress 进度帧，防止前端或网关超时断连。
3. 状态帧约定：推送极为精细的语义帧：
   - chapter_start / scene_start / streaming
   - chapter_saved / scene_completed
   - paused / cancelled / complete / error
   这些帧使得前端组件能在不直接介入生成逻辑的前提下，完美渲染复杂的嵌套进度环。

作为项目内【工程化成熟度最高】的标准链路之一，本文件为未来添加其他后台自动批处理任务（如
自动大纲扩写、长篇风格修订）提供了最可靠的并发模板。
════════════════════════════════════════════════════════════════════════
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

from core.auth import get_current_user
from core.utils import get_project_path
from agents.agent_scriptwriter import ScriptwriterAgent
from .stream_semantics import (
    semantic_sse_data,
    merge_semantics,
    on_cancelled,
    on_done,
    on_error,
    on_progress,
    on_start,
    on_stats,
)
from .auto_write_state import (
    begin_auto_write_run,
    build_auto_write_state_payload,
    build_scene_output_filename,
    patch_auto_write_state,
)
from story.file_naming import strip_story_filename_meta
from .context_builder import (
    load_worldview,
    load_all_roles,
    load_full_outline,
    load_narrative_memory,
    build_scene_context,
)

auto_write_router = APIRouter()

# 全局存储运行中项目的 stop_event
_auto_write_stop_events: Dict[str, threading.Event] = {}


async def generate_script_stream(
    user_id: str,
    project_name: str,
    outline: Dict[str, Any],
    request: Request | None = None,
    mode: str = "chapter_by_chapter",  # "all" or "chapter_by_chapter"
    start_chapter_index: int = 0,
    start_scene_index: int = 0,  # 从该章内第 N 个场景开始（仅对起始章有效）
    context_strategy: str = "accumulate",
    export_format: str = "arc",
):
    """
    Generator function for SSE streaming of script generation progress.
    """

    stop_event = threading.Event()
    _auto_write_stop_events[project_name] = stop_event

    # 1. Initialize
    nodes = outline.get("nodes", [])
    stories_path = os.path.join(get_project_path(user_id, project_name), "stories")
    os.makedirs(stories_path, exist_ok=True)

    # Filter chapters (skip those before start_chapter_index)
    # Note: nodes can contain non-chapter items if the structure is complex,
    # but usually top-level nodes are chapters.
    chapter_nodes = [n for n in nodes if n.get("type") == "chapter"]
    current_chapter_index: int | None = None
    current_chapter_title = ""
    current_scene_index: int | None = None
    current_scene_title = ""
    generated_files: list[str] = []
    generated_scene_files: list[str] = []

    state = begin_auto_write_run(
        user_id,
        project_name,
        mode=mode,
        export_format=export_format,
        start_chapter_index=start_chapter_index,
        start_scene_index=start_scene_index,
        total_chapters=len(chapter_nodes),
        total_scenes=sum(len(ch.get("children") or []) for ch in chapter_nodes),
    )

    def update_state(status: str, **extra: Any) -> Dict[str, Any]:
        payload = {
            "status": status,
            "mode": mode,
            "exportFormat": export_format,
            "currentChapterIndex": current_chapter_index,
            "currentChapterTitle": current_chapter_title,
            "currentSceneIndex": current_scene_index,
            "currentSceneTitle": current_scene_title,
            "generatedFiles": generated_files,
            "generatedSceneFiles": generated_scene_files,
        }
        payload.update(extra)
        return patch_auto_write_state(
            user_id,
            project_name,
            **payload,
        )

    if start_chapter_index >= len(chapter_nodes):
        update_state(
            "complete",
            nextChapterIndex=len(chapter_nodes),
            availableResumeChapterIndex=None,
            availableRestartChapterIndex=None,
            completedAt=patch_auto_write_state(user_id, project_name).get("updatedAt", ""),
            lastError="",
        )
        yield semantic_sse_data(
            "complete",
            message="No more chapters to write.",
            **on_done("没有更多章节需要生成"),
        )
        return

    try:
        writer = ScriptwriterAgent(user_id)
    except ValueError as e:
        yield semantic_sse_data("error", message=str(e), **on_error(str(e)))
        return
    except Exception as e:
        message = f"AI 服务初始化失败: {e}"
        yield semantic_sse_data("error", message=message, **on_error(message))
        return

    yield semantic_sse_data(
        "started",
        **merge_semantics(
            on_start("自动撰写任务已启动"),
            on_progress("正在准备章节任务...", stage="prepare"),
        ),
    )

    # ── 预加载全量项目数据（一次性，无需在每个场景重复 IO）─────────────────
    worldview = load_worldview(user_id, project_name)
    roles, chr_map = load_all_roles(user_id, project_name)
    full_outline = load_full_outline(user_id, project_name)
    narrative_memory, _ = load_narrative_memory(user_id, project_name)

    # Context accumulation (简单片段积累，三圈记忆策略会在 build_scene_context 里处理跨章前文)
    chapters_processed = 0
    accumulated_context = ""

    for i in range(start_chapter_index, len(chapter_nodes)):
        if request is not None and await request.is_disconnected():
            stop_event.set()
            update_state(
                "interrupted",
                nextChapterIndex=current_chapter_index if current_chapter_index is not None else start_chapter_index,
                availableResumeChapterIndex=current_chapter_index if current_chapter_index is not None else start_chapter_index,
                availableRestartChapterIndex=current_chapter_index if current_chapter_index is not None else start_chapter_index,
                lastError="",
            )
            yield semantic_sse_data(
                "cancelled",
                message="自动撰写任务已取消",
                **on_cancelled("自动撰写任务已取消"),
            )
            return

        chapter = chapter_nodes[i]
        chapter_num = chapter.get("chapter", i + 1)
        chapter_title = chapter.get("title", f"Chapter {chapter_num}")
        scenes = chapter.get("children", [])
        current_chapter_index = i
        current_chapter_title = chapter_title
        current_scene_index = None
        current_scene_title = ""

        update_state(
            "running",
            nextChapterIndex=i,
            availableResumeChapterIndex=i,
            availableRestartChapterIndex=i,
            lastError="",
        )

        yield semantic_sse_data(
            "chapter_start",
            chapter_index=i,
            chapter_title=chapter_title,
            **on_progress(
                f"开始章节：{chapter_title}", stage="chapter_start", chapterIndex=i
            ),
        )

        # Determine existing content or start fresh?
        # For auto-write, we generally assume we are writing fresh or overwriting.

        # 第一章：如果有 start_scene_index，跳过小于它的场景
        effective_start_scene = start_scene_index if i == start_chapter_index else 0

        for scene_idx, scene in enumerate(scenes):
            if scene_idx < effective_start_scene:
                continue
            if request is not None and await request.is_disconnected():
                stop_event.set()
                update_state(
                    "interrupted",
                    nextChapterIndex=i,
                    availableResumeChapterIndex=i,
                    availableRestartChapterIndex=i,
                    lastError="",
                )
                yield semantic_sse_data(
                    "cancelled",
                    message="自动撰写任务已取消",
                    **on_cancelled("自动撰写任务已取消"),
                )
                return

            scene_title = scene.get("title", f"Scene {scene_idx + 1}")
            scene_desc = scene.get("description", "")
            key_dialogues = scene.get("key_dialogues", [])
            current_scene_index = scene_idx
            current_scene_title = scene_title
            
            # Prepare file path for this specific scene
            filename = build_scene_output_filename(chapter_num, chapter_title, scene_idx, scene_title, export_format)
            filepath = os.path.join(stories_path, filename)
            display_filename = strip_story_filename_meta(filename)
            
            scene_arc_content = []
            if export_format != "novel":
                scene_arc_content.append(f"<!-- 章节 {chapter_num}: {chapter_title} -->")
                if chapter.get("description"):
                    scene_arc_content.append(f"<!-- {chapter.get('description')} -->")
                scene_arc_content.append(f"<!-- 场景 {scene_idx + 1}: {scene_title} -->")
                scene_arc_content.append("")
            
            update_state(
                "running",
                nextChapterIndex=i,
                availableResumeChapterIndex=i,
                availableRestartChapterIndex=i,
                lastSavedFilename=filename if os.path.exists(filepath) else "",
            )
            dialogues_str = ""
            if key_dialogues:
                dialogues_str = "\n\n【关键对话/剧情方向】\n" + "\n".join(
                    [f"- {d}" for d in key_dialogues]
                )

            # Update User
            yield semantic_sse_data(
                "writing_scene",
                chapter_index=i,
                chapter_title=chapter_title,
                scene_index=scene_idx,
                scene_title=scene_title,
                **on_progress(
                    f"正在撰写：{chapter_title} - {scene_title}",
                    stage="scene_start",
                    chapterIndex=i,
                    sceneIndex=scene_idx,
                ),
            )

            # Construct Prompt Context
            # We provide:
            # 1. Overall Story Context (from Outline Summary + Accumulation)
            # 2. Current Chapter Goal
            # 3. Current Scene Goal

            # ── 用统一组装器构建三圈记忆前文 ───────────────────────────────────
            context_str = build_scene_context(
                user_id,
                project_name,
                current_chapter_index=i,
                current_scene_index=scene_idx,
            )

            scene_goal = f"""【当前场景任务】
场景名：{scene_title}
场景描述：{scene_desc}{dialogues_str}
当前章节目标：{chapter_title} — {chapter.get('description', '')}
请撰写本场景的完整剧本内容。
"""

            # ── Pre-flight 侦查阶段：按需懒加载远端伏笔场景 ───────────────────
            # 全量世界观/角色/梗概/节拍表已通过 Prompt 注入，无需读取工具；
            # 但如果大纲中提到了远端章节的具体伏笔细节，模型可通过
            # list_chapters / read_chapter_scene 按需取回历史场景原文，
            # 取回的内容追加进 context_str，再交给纯净的 write_script_stream。
            try:
                reference_text = writer.research_references(
                    scene_goal=scene_goal,
                    full_outline=full_outline,
                    user_id=user_id,
                    project_name=project_name,
                )
                if reference_text:
                    context_str = context_str + (
                        "\n\n### 【Pre-flight 主动查阅的远端场景参考】\n" + reference_text
                    )
            except Exception as preflight_err:
                # pre-flight 失败不影响正式写作，仅记录日志
                print(f"[AutoWrite] Pre-flight research_references 异常（已忽略）: {preflight_err}")

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
                            context=context_str,
                            worldview=worldview,
                            roles=roles,
                            full_outline=full_outline,
                            narrative_memory=narrative_memory,
                            chr_map=chr_map,
                            segment_count=0,
                            guidance=scene_goal,
                            export_format=export_format,
                        ):
                            if stop_event.is_set():
                                break
                            result_queue.put(event)
                        result_queue.put(None)  # 结束标记
                    except Exception as e:
                        result_queue.put({"type": "error", "message": str(e)})
                        result_queue.put(None)

                # 启动生成线程
                gen_thread = threading.Thread(target=run_stream_to_queue)
                gen_thread.start()

                # 异步消费队列，实时推送
                heartbeat_interval = 2.0  # 每2秒发一次心跳防止连接超时
                last_heartbeat = time.time()

                while True:
                    if request is not None and await request.is_disconnected():
                        stop_event.set()
                        update_state(
                            "interrupted",
                            nextChapterIndex=i,
                            availableResumeChapterIndex=i,
                            availableRestartChapterIndex=i,
                            lastSavedFilename=filename if os.path.exists(filepath) else "",
                            lastError="",
                        )
                        yield semantic_sse_data(
                            "cancelled",
                            message="自动撰写任务已取消",
                            **on_cancelled("自动撰写任务已取消"),
                        )
                        break

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

                    if event["type"] == "error":
                        raise Exception(event["message"])

                    if event["type"] == "chunk":
                        accumulated_content += event["content"]
                        total_chars = event["total_chars"]
                        current_time = time.time()
                        elapsed = current_time - start_time

                        # 每 0.5 秒推送一次进度更新
                        if current_time - last_progress_time >= 0.1:
                            speed = total_chars / elapsed if elapsed > 0 else 0
                            # 取累积内容的最后 30 个字符作为预览
                            preview = (
                                accumulated_content[-30:]
                                if len(accumulated_content) > 30
                                else accumulated_content
                            )

                            yield semantic_sse_data(
                                "streaming",
                                scene_title=scene_title,
                                preview=preview,
                                accumulated_content=accumulated_content,
                                total_chars=total_chars,
                                speed=round(speed, 1),
                                elapsed=round(elapsed, 1),
                                **merge_semantics(
                                    on_progress(
                                        f"正在撰写场景：{scene_title}",
                                        stage="streaming",
                                    ),
                                    on_stats(
                                        chars=total_chars,
                                        speed=round(speed, 1),
                                        elapsed=round(elapsed, 1),
                                        label=f"已撰写 {total_chars} 字 · {round(speed, 1)} 字/秒",
                                    ),
                                ),
                            )
                            last_progress_time = current_time

                    elif event["type"] == "done":
                        arc_text = event["arc_script"]
                        thought = event.get("thought", "")
                        total_chars = event["total_chars"]

                gen_thread.join()  # 确保线程结束
                if stop_event.is_set():
                    yield semantic_sse_data(
                        "cancelled",
                        message="自动撰写任务已取消",
                        **on_cancelled("自动撰写任务已取消"),
                    )
                    return

                # 清洗 AI 返回的内容，去掉它自己生成的 # 标题和 @intro 等格式
                if export_format == "arc":
                    try:
                        from story.arc_parser import (
                            parse_arc_to_dialogues,
                            _serialize_dialogues,
                        )

                        nodes = parse_arc_to_dialogues(arc_text)
                        if nodes:
                            clean_lines = _serialize_dialogues(nodes, {}, 0)
                            arc_text = "\n".join(clean_lines).strip()
                    except Exception as e:
                        print(f"Error cleaning arc text: {e}")

                elapsed = time.time() - start_time
                avg_speed = total_chars / elapsed if elapsed > 0 else 0

                # Append to scene file content
                if export_format == "novel":
                    scene_arc_content = [arc_text.strip()]
                else:
                    scene_arc_content.append(f"# {scene_title}")
                    if scene_desc:
                        scene_arc_content.append(f"@intro\n{scene_desc}")

                    if thought:
                        scene_arc_content.append(f"<conception>\n{thought.strip()}\n</conception>")

                    scene_arc_content.append("")
                    scene_arc_content.append(arc_text)
                    scene_arc_content.append("")

                # Update accumulation (full text to prevent context loss in long generation)
                accumulated_context += f"\n# {scene_title}\n{arc_text}\n"

                # Send completion with stats
                update_state(
                    "running",
                    nextChapterIndex=i,
                    availableResumeChapterIndex=i,
                    availableRestartChapterIndex=i,
                    lastSavedFilename=filename if os.path.exists(filepath) else "",
                    lastError="",
                )
                yield semantic_sse_data(
                    "scene_completed",
                    scene_title=scene_title,
                    preview=arc_text[:100] + "..." if len(arc_text) > 100 else arc_text,
                    total_chars=total_chars,
                    elapsed=round(elapsed, 1),
                    avg_speed=round(avg_speed, 1),
                    **merge_semantics(
                        on_progress(
                            f"场景完成：{scene_title}", stage="scene_completed"
                        ),
                        on_stats(
                            chars=total_chars,
                            speed=round(avg_speed, 1),
                            elapsed=round(elapsed, 1),
                            label=f"场景完成 · {total_chars} 字 · 平均 {round(avg_speed, 1)} 字/秒",
                        ),
                    ),
                )

            except Exception as e:
                print(f"Error writing scene {scene_title}: {e}")
                message = str(e)
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write("\n".join(scene_arc_content))
                if filename not in generated_scene_files:
                    generated_scene_files.append(filename)
                update_state(
                    "error",
                    nextChapterIndex=i,
                    availableResumeChapterIndex=i,
                    availableRestartChapterIndex=i,
                    lastSavedFilename=display_filename,
                    lastError=message,
                )
                yield semantic_sse_data("error", message=message, **on_error(message))
                return

            # Save file after each scene (progressive save)
            if stop_event.is_set():
                update_state(
                    "interrupted",
                    nextChapterIndex=i,
                    availableResumeChapterIndex=i,
                    availableRestartChapterIndex=i,
                    lastSavedFilename=filename if os.path.exists(filepath) else "",
                    lastError="",
                )
                yield semantic_sse_data(
                    "cancelled",
                    message="自动撰写任务已取消",
                    **on_cancelled("自动撰写任务已取消"),
                )
                return
            with open(filepath, "w", encoding="utf-8") as f:
                f.write("\n".join(scene_arc_content))
            
            if filename not in generated_scene_files:
                generated_scene_files.append(filename)
            
            update_state(
                "running",
                nextChapterIndex=i,
                availableResumeChapterIndex=i,
                availableRestartChapterIndex=i,
                lastSavedFilename=display_filename,
                generatedFiles=generated_scene_files,
                lastError="",
            )
            
            # Send progressive scene saved event to inform frontend about new scene file
            yield semantic_sse_data(
                "scene_saved",
                filename=display_filename,
                **on_progress(f"场景已保存：{display_filename}", stage="scene_saved"),
            )

        # Notify chapter saved (all scenes done)
        update_state(
            "running",
            lastCompletedChapterIndex=i,
            lastCompletedChapterTitle=chapter_title,
            nextChapterIndex=i + 1,
            availableResumeChapterIndex=i + 1,
            availableRestartChapterIndex=i,
            currentSceneIndex=None,
            currentSceneTitle="",
            lastError="",
        )
        yield semantic_sse_data(
            "chapter_saved",
            **on_progress(f"所有场景已完成：{chapter_title}", stage="chapter_saved"),
        )

        chapters_processed += 1

        # Check Mode
        if mode == "chapter_by_chapter":
            update_state(
                "chapter_paused",
                nextChapterIndex=i + 1,
                availableResumeChapterIndex=i + 1,
                availableRestartChapterIndex=i,
                currentSceneIndex=None,
                currentSceneTitle="",
                lastError="",
            )
            yield semantic_sse_data(
                "paused",
                next_chapter_index=i + 1,
                restart_chapter_index=i,
                **on_progress("当前章节已完成，任务暂停", stage="paused"),
            )
            return

    update_state(
        "complete",
        nextChapterIndex=len(chapter_nodes),
        availableResumeChapterIndex=None,
        availableRestartChapterIndex=None,
        currentSceneIndex=None,
        currentSceneTitle="",
        lastError="",
        completedAt=patch_auto_write_state(user_id, project_name).get("updatedAt", ""),
    )
    yield semantic_sse_data("complete", **on_done("全部自动撰写任务已完成"))


@auto_write_router.get("/api/outline/{project_name}/auto-write-state")
async def get_auto_write_state(
    project_name: str,
    export_format: str = "arc",
    user: dict = Depends(get_current_user),
):
    user_id = str(user["user_id"])
    outline_path = os.path.join(get_project_path(user_id, project_name), "outline.json")
    if not os.path.exists(outline_path):
        return {
            **build_auto_write_state_payload(user_id, project_name, {"nodes": []}, export_format=export_format),
            "outlineExists": False,
        }

    with open(outline_path, "r", encoding="utf-8") as f:
        outline = json.load(f)

    return {
        **build_auto_write_state_payload(
            user_id,
            project_name,
            outline,
            export_format=export_format,
        ),
        "outlineExists": True,
    }


@auto_write_router.post("/api/outline/{project_name}/auto-write-stream")
async def auto_write_stream(
    project_name: str, request: Request, user: dict = Depends(get_current_user)
):
    user_id = str(user["user_id"])
    if await request.is_disconnected():
        return StreamingResponse(iter(()), media_type="text/event-stream")
    data = await request.json() or {}
    mode = data.get("mode", "chapter_by_chapter")
    start_chapter_index = data.get("start_chapter_index", 0)
    start_scene_index = data.get("start_scene_index", 0)
    export_format = data.get("export_format", "arc")

    # Load Outline
    outline_path = os.path.join(get_project_path(user_id, project_name), "outline.json")
    if not os.path.exists(outline_path):
        return {"error": "Outline not found"}

    with open(outline_path, "r", encoding="utf-8") as f:
        outline = json.load(f)

    return StreamingResponse(
        generate_script_stream(
            user_id,
            project_name,
            outline,
            request,
            mode,
            start_chapter_index,
            start_scene_index,
            context_strategy="accumulate",
            export_format=export_format,
        ),
        media_type="text/event-stream",
    )


@auto_write_router.post("/api/outline/{project_name}/auto-write-pause")
async def auto_write_pause(
    project_name: str, user: dict = Depends(get_current_user)
):
    """
    前端点击终止/暂停触发，向正在运行的该项目生成引擎发送停止信号。
    """
    user_id = str(user["user_id"])
    
    # 向当前在内存中跑的任务发送停止信号
    if project_name in _auto_write_stop_events:
        _auto_write_stop_events[project_name].set()
    
    # 兜底：修改状态为中断（防止孤儿线程无法更新或早已消失）
    patch_auto_write_state(
        user_id, project_name, 
        status="interrupted", 
        lastError="用户已中断写作"
    )
    
    return {"success": True}
