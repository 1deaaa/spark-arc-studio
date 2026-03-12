"""Production API - ScriptWriter 统一执行接口。"""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse
from starlette.concurrency import run_in_threadpool
from typing import List, Dict, Any
import threading
import os
import json
import time

from core.auth import get_current_user
from core.request_context import current_project_name, set_agent_context
from core.utils import (
    get_project_path,
    get_project_stories_path,
    strip_private_fields,
    ensure_project_characters_directory,
)

from agents import ScriptwriterAgent, CriticAgent
from agents.agent_style.utils import load_style_profile_from_file
from llm.llm_mgr import LLM_Manager
from llm.llm_mgr.reasoning_compat import PrefixReasoningStreamParser

from .schemas import (
    CriticReviewRequest,
    ScriptwriterComposeRequest,
    ScriptwriterFeedbackRequest,
    _load_worldview_and_roles,
)
from .streaming_utils import iterate_sync_iterable_in_thread
from .stream_semantics import (
    semantic_event_data,
    merge_semantics,
    on_delta,
    on_cancelled,
    on_done,
    on_error,
    on_progress,
    on_start,
    on_stats,
)
from .execution_core import build_stats_payload

production_router = APIRouter()
manager = LLM_Manager


def build_scriptwriter_context_pack(
    user_id: str,
    project_name: str,
    operation: str,
    file_path: str = "",
    scene_name: str = "",
    node_id: int = 0,
    selected_character_ids: List[int] | None = None,
    guidance: str = "",
    segment_count: int = 3,
    last_node_text: str = "",
    context: str = "",
) -> Dict[str, Any]:
    from story.arc_parser import parse_arc, serialize_to_arc

    project_path = get_project_path(user_id, project_name)
    worldview = ""
    worldview_path = os.path.join(project_path, "世界观.txt")
    if os.path.exists(worldview_path):
        with open(worldview_path, "r", encoding="utf-8") as f:
            worldview = f.read()

    roles = ""
    chr_map: Dict[int, str] = {}
    characters_payload: List[Dict[str, Any]] = []
    selected_character_ids = selected_character_ids or []
    if selected_character_ids:
        characters_path = ensure_project_characters_directory(user_id, project_name)
        bind_file = os.path.join(characters_path, "chr.bind")
        if os.path.exists(bind_file):
            with open(bind_file, "r", encoding="utf-8") as f:
                full_char_map = json.load(f) or {}
            selected_roles_content = []
            for cid in selected_character_ids:
                cid_str = str(cid)
                if cid_str not in full_char_map:
                    continue
                name = full_char_map[cid_str]
                if int(cid) == -1:
                    name = "旁白"
                chr_map[int(cid)] = name
                char_file = os.path.join(characters_path, f"{cid}.txt")
                content = "(暂无详细设定)"
                if os.path.exists(char_file):
                    with open(char_file, "r", encoding="utf-8") as cf:
                        content = cf.read().strip() or content
                selected_roles_content.append(
                    f"--- 角色: {name} (ID: {cid}) ---\n{content}"
                )
                characters_payload.append(
                    {
                        "id": int(cid),
                        "name": name,
                        "desc": content,
                    }
                )
            if selected_roles_content:
                roles = "\n\n".join(selected_roles_content)

    story_data = []
    target_scene = None
    canonical_context = (context or "").strip()
    local_script = ""
    stories_path = get_project_stories_path(user_id, project_name)
    normalized_file_path = file_path or ""
    if normalized_file_path:
        if not normalized_file_path.endswith(".arc"):
            normalized_file_path += ".arc"
        absolute_file_path = os.path.join(stories_path, normalized_file_path)
        if os.path.exists(absolute_file_path):
            with open(absolute_file_path, "r", encoding="utf-8") as f:
                arc_content = f.read()
            story_data = parse_arc(arc_content)
            strip_private_fields(story_data)
            target_index = -1
            for i, s in enumerate(story_data):
                if s.get("scene") == scene_name:
                    target_scene = s
                    target_index = i
                    break
            if target_scene:
                context_scenes = story_data[: target_index + 1]
                canonical_context = serialize_to_arc(context_scenes).strip()
                local_script = serialize_to_arc([target_scene]).strip()
                if (
                    context
                    and str(context).strip()
                    and str(context).strip() not in canonical_context
                ):
                    canonical_context = (
                        canonical_context
                        + "\n\n# 用户补充上下文\n"
                        + str(context).strip()
                    )

    return {
        "project_meta": {
            "project_name": project_name,
            "file_path": normalized_file_path,
            "scene_name": scene_name,
            "node_id": node_id,
        },
        "worldview": worldview,
        "characters": characters_payload,
        "roles": roles,
        "chr_map": chr_map,
        "story_structure": {
            "operation": operation,
            "segment_count": segment_count,
            "guidance": guidance,
        },
        "local_script": local_script,
        "task_intent": {
            "operation": operation,
            "guidance": guidance,
            "last_node_text": last_node_text,
        },
        "context": canonical_context,
        "story_data": story_data,
        "target_scene": target_scene,
    }


def _clean_generated_nodes(final_nodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    allowed_fields = {"id", "chr", "txt", "opt", "optn", "dia", "act", "next"}

    def clean_node(node):
        if isinstance(node, dict):
            strip_private_fields(node)
            for key in list(node.keys()):
                if key not in allowed_fields:
                    del node[key]
            if "dia" in node:
                clean_nodes_list(node["dia"])
            if "opt" in node:
                clean_nodes_list(node["opt"])
        return node

    def clean_nodes_list(nodes):
        if isinstance(nodes, list):
            for i in range(len(nodes)):
                nodes[i] = clean_node(nodes[i])

    clean_nodes_list(final_nodes)
    return final_nodes


def _persist_generated_nodes(
    user_id: str,
    project_name: str,
    current_file: str,
    scene_name: str,
    after_node_id: int,
    final_nodes: List[Dict[str, Any]],
    rewrite: bool = False,
    thought: str = "",
) -> None:
    from story.arc_parser import parse_arc, serialize_to_arc

    stories_path = get_project_stories_path(user_id, project_name)
    normalized_file = (
        current_file if current_file.endswith(".arc") else f"{current_file}.arc"
    )
    file_path = os.path.join(stories_path, normalized_file)
    with open(file_path, "r", encoding="utf-8") as f:
        arc_content = f.read()
    story_data = parse_arc(arc_content)
    strip_private_fields(story_data)

    target_scene = None
    for s in story_data:
        if s.get("scene") == scene_name:
            target_scene = s
            break
    if not target_scene:
        raise FileNotFoundError(f"场景 '{scene_name}' 未找到")

    final_nodes = _clean_generated_nodes(final_nodes)

    def find_and_insert(nodes):
        if after_node_id == 0:
            for j, new_node in enumerate(final_nodes):
                nodes.insert(j, new_node)
            return True

        for i, dia in enumerate(nodes):
            if dia.get("id") == after_node_id:
                for j, new_node in enumerate(final_nodes):
                    nodes.insert(i + 1 + j, new_node)
                return True
            if "opt" in dia:
                for opt in dia["opt"]:
                    if "dia" in opt and find_and_insert(opt["dia"]):
                        return True
        return False

    if rewrite:
        target_scene["dia"] = final_nodes
    else:
        if not find_and_insert(target_scene.get("dia", [])):
            raise FileNotFoundError(f"节点ID '{after_node_id}' 在场景中未找到")

    if thought and not target_scene.get("thought"):
        target_scene["thought"] = thought

    new_arc_content = serialize_to_arc(story_data)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(new_arc_content)


@production_router.post("/api/ai/critic")
async def run_critic_review(
    data: CriticReviewRequest, user: dict = Depends(get_current_user)
):
    """手动触发 Critic 评审（不参与自动工作流）"""
    project_name = current_project_name.get() or data.projectName
    if not project_name:
        return JSONResponse(status_code=400, content={"error": "缺少项目名称"})

    user_id = str(user["user_id"])
    info = _load_worldview_and_roles(user_id, project_name)
    author_id = f"{user_id}_{project_name}"
    style_profile = load_style_profile_from_file(author_id, user_id=user_id)

    try:
        critic = CriticAgent(user_id)
    except ValueError as e:
        return JSONResponse(status_code=422, content={"error": str(e)})
    except Exception as e:
        return JSONResponse(
            status_code=500, content={"error": f"AI 服务初始化失败: {e}"}
        )
    score, status, feedback = await run_in_threadpool(
        critic.evaluate,
        script_nodes=data.script_nodes,
        context=data.context or "",
        guidance=data.guidance or "",
        worldview=info.get("worldview", ""),
        roles=info.get("roles", ""),
        style_profile=style_profile,
    )

    return {
        "success": True,
        "score": score,
        "status": status,
        "feedback": feedback,
    }


# ==================== 新版端点（SSE流式） ====================


@production_router.post("/api/scriptwriter/compose/stream")
async def scriptwriter_compose_stream(
    request: Request,
    data: ScriptwriterComposeRequest,
    user: dict = Depends(get_current_user),
):
    """ScriptWriter 统一执行流接口。"""
    from story.arc_parser import parse_arc_to_dialogues

    user_id = str(user["user_id"])
    project_name = current_project_name.get() or data.projectName
    if not project_name:
        return JSONResponse(status_code=400, content={"error": "缺少项目名称"})

    operation = (data.operation or "continue").strip()
    mode = (data.mode or "multi-node").strip()
    set_agent_context(user_id, project_name)

    context_pack = build_scriptwriter_context_pack(
        user_id=user_id,
        project_name=project_name,
        operation=operation,
        file_path=data.filePath,
        scene_name=data.sceneName,
        node_id=data.nodeId,
        selected_character_ids=data.selectedCharacterIds,
        guidance=data.guidance,
        segment_count=data.segmentCount,
        last_node_text=data.lastNodeText,
        context=data.context,
    )

    missing_info = []
    if operation in {"continue", "rewrite_scene"}:
        if not (context_pack.get("worldview") or "").strip():
            missing_info.append("世界观")
        if data.selectedCharacterIds and not (context_pack.get("roles") or "").strip():
            missing_info.append("角色设定")
        if missing_info and not data.confirmContinue:
            return JSONResponse(
                status_code=409,
                content={
                    "error": "MISSING_INFO",
                    "message": f"检测到缺少以下信息：{', '.join(missing_info)}。这可能会影响生成质量。是否继续？",
                    "missing": missing_info,
                },
            )

    author_id = f"{user_id}_{project_name}"
    style_profile = load_style_profile_from_file(author_id, user_id=user_id)

    try:
        agent = ScriptwriterAgent(user_id=user_id)
    except ValueError as e:
        return JSONResponse(status_code=422, content={"error": str(e)})
    except Exception as e:
        return JSONResponse(
            status_code=500, content={"error": f"AI 服务初始化失败: {e}"}
        )

    stop_event = threading.Event()

    async def generate():
        started_at = time.monotonic()
        total_chars = 0

        try:
            yield semantic_event_data(
                "progress",
                message="上下文准备完成",
                stage="context",
                **merge_semantics(
                    on_start("ScriptWriter 任务已启动"),
                    on_progress("上下文准备完成", stage="context"),
                ),
            )

            if operation == "bridge":
                exec_context = agent.build_context(
                    operation="bridge",
                    prev_scene=data.prevScene or {},
                    next_scene=data.nextScene or {},
                    worldview=context_pack.get("worldview") or "",
                    characters=context_pack.get("characters") or [],
                    pacing=data.pacing or "normal",
                    mood=data.mood or "",
                    guidance=data.guidance or "",
                    style_profile=style_profile,
                )
                async for chunk in iterate_sync_iterable_in_thread(
                    lambda: agent.execute(exec_context, stream=True),
                    request=request,
                    stop_event=stop_event,
                ):
                    if stop_event.is_set():
                        yield semantic_event_data(
                            "cancelled",
                            status="cancelled",
                            operation=operation,
                            mode=mode,
                            **on_cancelled("过渡生成已取消"),
                        )
                        return
                    if chunk.get("type") == "chunk":
                        total_chars = chunk.get("total_chars", total_chars)
                        elapsed = max(time.monotonic() - started_at, 0.001)
                        speed = round(total_chars / elapsed, 2)
                        text = chunk.get("content", "")
                        yield semantic_event_data(
                            "chunk",
                            text=text,
                            chars=total_chars,
                            elapsed=round(elapsed, 2),
                            speed=speed,
                            **merge_semantics(
                                on_delta(text),
                                on_stats(
                                    chars=total_chars,
                                    elapsed=round(elapsed, 2),
                                    speed=speed,
                                ),
                            ),
                        )
                    elif chunk.get("type") == "done":
                        elapsed = max(time.monotonic() - started_at, 0.001)
                        dialogues = parse_arc_to_dialogues(
                            chunk.get("transition_text", "") or ""
                        )
                        final_chars = chunk.get("total_chars", total_chars)
                        final_speed = round((final_chars or 0) / elapsed, 2)
                        yield semantic_event_data(
                            "done",
                            mode=mode,
                            operation=operation,
                            transition=chunk.get("transition_text", ""),
                            dialogues=dialogues,
                            summary=chunk.get("summary", ""),
                            chars=final_chars,
                            elapsed=round(elapsed, 2),
                            speed=final_speed,
                            **merge_semantics(
                                on_done("过渡生成完成"),
                                on_stats(
                                    chars=final_chars,
                                    elapsed=round(elapsed, 2),
                                    speed=final_speed,
                                ),
                            ),
                        )
                return

            if mode == "single-node":
                from langchain_core.messages import SystemMessage, HumanMessage

                prompt = f'''我的世界观是：\n"{context_pack.get("worldview", "")}"\n\n你可能需要用到的角色设定：\n"{context_pack.get("roles", "")}"\n\n我当前的上下文是：\n"{data.context or ""}"\n\n请根据以上信息，续写一句纯文本内容，续写长度约为 {data.length} 字。'''
                messages = [
                    SystemMessage(
                        content="你是一个专业的剧本创作助手。你只输出纯文本的对话内容。"
                    ),
                    HumanMessage(content=prompt),
                ]
                chat = manager.get_user_llm(user_id, agent_name="agent_scriptwriter")
                parser = PrefixReasoningStreamParser()
                async for model_chunk in iterate_sync_iterable_in_thread(
                    lambda: chat.stream(messages),
                    request=request,
                    stop_event=stop_event,
                ):
                    if stop_event.is_set():
                        yield semantic_event_data(
                            "cancelled",
                            status="cancelled",
                            operation=operation,
                            mode=mode,
                            **on_cancelled("单节点续写已取消"),
                        )
                        return
                    raw_text = getattr(model_chunk, "content", "") or ""
                    _, text = parser.push(raw_text)
                    if not text:
                        continue
                    total_chars += len(text)
                    elapsed = max(time.monotonic() - started_at, 0.001)
                    speed = round(total_chars / elapsed, 2)
                    yield semantic_event_data(
                        "chunk",
                        text=text,
                        chars=total_chars,
                        elapsed=round(elapsed, 2),
                        speed=speed,
                        **merge_semantics(
                            on_delta(text),
                            on_stats(
                                chars=total_chars,
                                elapsed=round(elapsed, 2),
                                speed=speed,
                            ),
                        ),
                    )
                _, trailing_text = parser.flush()
                if trailing_text:
                    total_chars += len(trailing_text)
                    elapsed = max(time.monotonic() - started_at, 0.001)
                    speed = round(total_chars / elapsed, 2)
                    yield semantic_event_data(
                        "chunk",
                        text=trailing_text,
                        chars=total_chars,
                        elapsed=round(elapsed, 2),
                        speed=speed,
                        **merge_semantics(
                            on_delta(trailing_text),
                            on_stats(
                                chars=total_chars,
                                elapsed=round(elapsed, 2),
                                speed=speed,
                            ),
                        ),
                    )
                elapsed = max(time.monotonic() - started_at, 0.001)
                final_speed = round(total_chars / elapsed, 2)
                yield semantic_event_data(
                    "done",
                    mode=mode,
                    operation=operation,
                    chars=total_chars,
                    elapsed=round(elapsed, 2),
                    speed=final_speed,
                    **merge_semantics(
                        on_done("单节点续写完成"),
                        on_stats(
                            chars=total_chars,
                            elapsed=round(elapsed, 2),
                            speed=final_speed,
                        ),
                    ),
                )
                return

            exec_context = agent.build_context(
                operation=operation,
                context=context_pack.get("context") or data.context or "",
                worldview=context_pack.get("worldview") or "",
                roles=context_pack.get("roles") or "",
                segment_count=data.segmentCount,
                guidance=data.guidance or "",
                style_profile=style_profile,
                chr_map=context_pack.get("chr_map") or None,
                last_node_text=data.lastNodeText or "",
                export_format=data.exportFormat or "arc",
            )

            full_arc_script = ""
            thought = ""
            async for chunk in iterate_sync_iterable_in_thread(
                lambda: agent.execute(exec_context, stream=True),
                request=request,
                stop_event=stop_event,
            ):
                if stop_event.is_set():
                    yield semantic_event_data(
                        "cancelled",
                        status="cancelled",
                        operation=operation,
                        mode=mode,
                        **on_cancelled("ScriptWriter 生成已取消"),
                    )
                    return
                if chunk.get("type") == "chunk":
                    total_chars = chunk.get("total_chars", total_chars)
                    elapsed = max(time.monotonic() - started_at, 0.001)
                    text = chunk.get("content", "")
                    speed = round(total_chars / elapsed, 2)
                    yield semantic_event_data(
                        "chunk",
                        text=text,
                        chars=total_chars,
                        elapsed=round(elapsed, 2),
                        speed=speed,
                        **merge_semantics(
                            on_delta(text),
                            on_stats(
                                chars=total_chars,
                                elapsed=round(elapsed, 2),
                                speed=speed,
                            ),
                        ),
                    )
                elif chunk.get("type") == "done":
                    full_arc_script = chunk.get("arc_script", "")
                    thought = chunk.get("thought", "")

            final_nodes = (
                parse_arc_to_dialogues(full_arc_script) if full_arc_script else []
            )
            if stop_event.is_set():
                yield semantic_event_data(
                    "cancelled",
                    status="cancelled",
                    operation=operation,
                    mode=mode,
                    **on_cancelled("ScriptWriter 生成已取消"),
                )
                return
            if mode != "single-node" and data.filePath and data.sceneName:
                _persist_generated_nodes(
                    user_id=user_id,
                    project_name=project_name,
                    current_file=data.filePath,
                    scene_name=data.sceneName,
                    after_node_id=data.nodeId,
                    final_nodes=final_nodes,
                    rewrite=(operation == "rewrite_scene" or data.rewrite),
                    thought=thought,
                )
            elapsed = max(time.monotonic() - started_at, 0.001)
            final_speed = round(total_chars / elapsed, 2)
            yield semantic_event_data(
                "done",
                mode=mode,
                operation=operation,
                thought=thought,
                chars=total_chars,
                elapsed=round(elapsed, 2),
                speed=final_speed,
                **merge_semantics(
                    on_done("ScriptWriter 生成完成"),
                    on_stats(
                        chars=total_chars, elapsed=round(elapsed, 2), speed=final_speed
                    ),
                ),
            )
        except Exception as e:
            if stop_event.is_set():
                yield semantic_event_data(
                    "cancelled",
                    status="cancelled",
                    operation=operation,
                    mode=mode,
                    **on_cancelled("ScriptWriter 生成已取消"),
                )
                return
            yield semantic_event_data("error", error=str(e), **on_error(str(e)))

    return EventSourceResponse(generate())


@production_router.post("/api/scriptwriter/feedback/stream")
async def scriptwriter_feedback_stream(
    request: Request,
    data: ScriptwriterFeedbackRequest,
    user: dict = Depends(get_current_user),
):
    """ScriptWriter 统一反馈流接口。"""
    user_id = str(user["user_id"])
    project_name = current_project_name.get() or data.projectName
    if not project_name:
        return JSONResponse(status_code=400, content={"error": "缺少项目名称"})

    set_agent_context(user_id, project_name)

    wv = _load_worldview_and_roles(user_id, project_name)
    worldview = wv.get("worldview", "")
    roles = wv.get("roles", "")

    try:
        agent = ScriptwriterAgent(user_id=user_id)
    except ValueError as e:
        return JSONResponse(status_code=422, content={"error": str(e)})
    except Exception as e:
        return JSONResponse(
            status_code=500, content={"error": f"AI 服务初始化失败: {e}"}
        )

    stop_event = threading.Event()

    async def generate():
        feedback_started_at = time.monotonic()
        total_chars = 0
        try:
            yield semantic_event_data(
                "progress",
                status="started",
                message="ScriptWriter 反馈任务已启动",
                stage="start",
                **merge_semantics(
                    on_start("ScriptWriter 反馈任务已启动"),
                    on_progress("正在准备反馈上下文...", stage="start"),
                ),
            )
            use_streaming_feedback = (
                data.user_input or ""
            ).strip().lower() != "__smoke_feedback__"

            if not use_streaming_feedback:
                chunk = await run_in_threadpool(
                    agent.feedback,
                    data.user_input,
                    data.context,
                    data.last_content,
                    worldview,
                    roles,
                )
                if stop_event.is_set():
                    yield semantic_event_data(
                        "cancelled",
                        status="cancelled",
                        **on_cancelled("反馈任务已取消"),
                    )
                    return
                total_chars += len(chunk or "")
                yield semantic_event_data(
                    "chunk",
                    text=chunk,
                    chars=total_chars,
                    **merge_semantics(
                        on_delta(chunk),
                        build_stats_payload(feedback_started_at, total_chars),
                    ),
                )
            else:
                async for chunk in iterate_sync_iterable_in_thread(
                    lambda: agent.stream_feedback(
                        user_input=data.user_input,
                        context=data.context,
                        last_content=data.last_content,
                        worldview=worldview,
                        roles=roles,
                    ),
                    request=request,
                    stop_event=stop_event,
                ):
                    if stop_event.is_set():
                        yield semantic_event_data(
                            "cancelled",
                            status="cancelled",
                            **on_cancelled("反馈任务已取消"),
                        )
                        return
                    total_chars += len(chunk or "")
                    yield semantic_event_data(
                        "chunk",
                        text=chunk,
                        chars=total_chars,
                        **merge_semantics(
                            on_delta(chunk),
                            build_stats_payload(feedback_started_at, total_chars),
                        ),
                    )
            if stop_event.is_set():
                yield semantic_event_data(
                    "cancelled",
                    status="cancelled",
                    **on_cancelled("反馈任务已取消"),
                )
                return
            yield semantic_event_data(
                "done",
                status="complete",
                chars=total_chars,
                **merge_semantics(
                    on_done("反馈任务已完成"),
                    build_stats_payload(feedback_started_at, total_chars),
                ),
            )
        except Exception as e:
            if stop_event.is_set():
                yield semantic_event_data(
                    "cancelled",
                    status="cancelled",
                    **on_cancelled("反馈任务已取消"),
                )
                return
            yield semantic_event_data(
                "error", status="error", error=str(e), **on_error(str(e))
            )

    return EventSourceResponse(generate())
