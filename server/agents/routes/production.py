"""
Production API - 正片/剧本生成的长耗时业务流接口。

════════════════════════════════════════════════════════════════════════
【架构定位：业务语义流 (Stream Semantics) 的标准实现】

本模块承载了 ScriptWriter (剧本家) 的核心长耗时生成任务（包括单章续写、桥接生成、推流等）。
与 chat.py 中使用的 NDJSON 对话流不同，本文件严格遵循 `stream_semantics.py` 定义的【业务语义流】协议。

【流控链路核心特征】
1. SSE 标准：使用 `EventSourceResponse` 向前端推送标准的 Server-Sent Events 事件。
2. 异步协程转换：通过 `iterate_sync_iterable_in_thread` 将同步的 LLM 阻塞调用转化为全异步可中断的流。
3. 状态帧切面：强制使用 `semantic_event_data` 包装器，向前端精确推送生命周期语义帧：
   - on_start: "任务已启动"
   - on_progress: 报告生成阶段 (如 context, streaming, scene_completed)
   - on_delta: 细粒度的文本块打字机输出
   - on_stats: 统计耗时与生成速率
   - on_done / on_error / on_cancelled: 任务终态处理
4. 中断控制：借助 `threading.Event()` 实现响应 `await request.is_disconnected()` 的流平滑取消。

这种模式实现了【后端的无状态流式推演】与前端【声明式 UI】的彻底解耦，是系统中同步转异步
长耗时任务的基准参考实现。
════════════════════════════════════════════════════════════════════════
"""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse
from starlette.concurrency import run_in_threadpool
from typing import List, Dict, Any
import threading
import asyncio
import os
import json
import time

from core.auth import get_current_user
from core.request_context import get_current_project_name, resolve_project_name, set_agent_context
from core.utils import (
    get_project_path,
    get_project_stories_path,
    strip_private_fields,
    ensure_project_characters_directory,
)

from agents import ScriptwriterAgent, CriticAgent
from agents.agent_style.utils import load_project_style_profile
from agents.context_budget import prepare_specialized_prompt_messages_with_budget
from agents.language_policy import prepend_prompt_language_policy
from core.project_settings import get_project_story_tags
from llm.agen_matchbox import matchbox
from llm.agen_matchbox.reasoning_compat import (
    PrefixReasoningStreamParser,
    extract_raw_text_content_from_message,
)

from .schemas import (
    CriticReviewRequest,
    ScriptwriterComposeRequest,
    ScriptwriterFeedbackRequest,
)
from agents.project_context import (
    build_scriptwriter_context,
    build_story_tags_hint,
    format_outline_scene_contract,
    load_all_roles,
    load_outline_data,
    load_project_context_bundle,
    resolve_outline_scene_contract,
)
from .streaming_utils import iterate_sync_iterable_in_thread
from agents.stream_semantics import (
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


def build_scriptwriter_context_pack(
    user_id: str,
    project_name: str,
    operation: str,
    file_path: str = "",
    scene_name: str = "",
    node_id: int = 0,
    selected_character_ids: List[int] | None = None,  # 保留参数兼容性，但不再限制角色范围
    guidance: str = "",
    segment_count: int = 3,
    last_node_text: str = "",
    context: str = "",
) -> Dict[str, Any]:
    """
    ScriptWriter 上下文包组装器（生产端）。

    改造说明：
    - 使用统一的 context_builder 加载全量世界观、全量角色设定、完整大纲、叙事记忆。
    - 废弃仅传选中角色的旧逻辑（selected_character_ids 参数保留以兼容旧接口调用，但不再过滤角色）。
    - arc 文件解析和前文序列化逻辑保留（生产端需要精确的 target_scene 和 local_script）。
    """
    from story.arc_parser import parse_arc, serialize_to_arc
    from story.arc_safety import sanitize_arc_for_project_ai_context

    def clean_arc(value: str) -> str:
        return sanitize_arc_for_project_ai_context(value, user_id, project_name)

    # ── 全量加载：世界观 / 所有角色 / 完整大纲 / 叙事记忆 ──────────────
    from agents.project_context import load_worldview, load_all_roles, load_full_outline, load_narrative_memory

    worldview = load_worldview(user_id, project_name)
    roles, chr_map = load_all_roles(user_id, project_name)
    full_outline = load_full_outline(user_id, project_name)
    outline_data = load_outline_data(user_id, project_name)
    narrative_memory, _ = load_narrative_memory(user_id, project_name)

    def _append_character_name(names: List[str], raw_id: Any) -> None:
        try:
            cid = int(raw_id)
        except Exception:
            raw_name = str(raw_id or "").strip()
            if raw_name and raw_name not in {"旁白", "?"} and raw_name not in names:
                names.append(raw_name)
            return
        name = str(chr_map.get(cid) or "").strip()
        if name and name != "旁白" and name not in names:
            names.append(name)

    def _collect_character_ids(value: Any) -> List[Any]:
        ids: List[Any] = []
        if isinstance(value, dict):
            if "chr" in value:
                ids.append(value.get("chr"))
            for child in value.values():
                ids.extend(_collect_character_ids(child))
        elif isinstance(value, list):
            for child in value:
                ids.extend(_collect_character_ids(child))
        return ids

    # ── 构建 characters_payload（仅用于接口返回，供前端展示）────────────
    characters_payload: List[Dict[str, Any]] = [
        {"id": cid, "name": name}
        for cid, name in chr_map.items()
    ]

    # ── 解析 .arc 文件，提取前文和目标场景 ─────────────────────────────
    story_data = []
    target_scene = None
    canonical_context = clean_arc(context or "")
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
            story_data = parse_arc(arc_content, chr_map=chr_map)
            strip_private_fields(story_data)
            target_index = -1
            for i, s in enumerate(story_data):
                if s.get("scene") == scene_name:
                    target_scene = s
                    target_index = i
                    break
            if target_scene:
                context_scenes = story_data[: target_index + 1]
                canonical_context = clean_arc(serialize_to_arc(context_scenes, chr_map=chr_map))
                local_script = clean_arc(serialize_to_arc([target_scene], chr_map=chr_map))
                if (
                    context
                    and str(context).strip()
                    and str(context).strip() not in canonical_context
                ):
                    canonical_context = (
                        canonical_context
                        + "\n\n# 用户补充上下文\n"
                        + clean_arc(str(context))
                    )

    scene_characters: List[str] = []
    for raw_id in selected_character_ids or []:
        _append_character_name(scene_characters, raw_id)
    if target_scene:
        for raw_id in _collect_character_ids(target_scene):
            _append_character_name(scene_characters, raw_id)

    chapter_title = ""
    if normalized_file_path:
        chapter_title = os.path.basename(os.path.dirname(normalized_file_path.replace("/", os.sep)))
    scene_description = ""
    if isinstance(target_scene, dict):
        scene_description = str(
            target_scene.get("description")
            or target_scene.get("summary")
            or target_scene.get("guide")
            or target_scene.get("thought")
            or ""
        )

    outline_contract = resolve_outline_scene_contract(
        outline_data,
        scene_name=scene_name or "",
        file_path=normalized_file_path,
        chapter_title=chapter_title,
    )
    if outline_contract:
        chapter_title = outline_contract.get("chapter_title") or chapter_title
        outline_scene_description = str(outline_contract.get("scene_description") or "").strip()
        if outline_scene_description:
            scene_description = (
                f"{outline_scene_description}\n{scene_description}".strip()
                if scene_description and outline_scene_description not in scene_description
                else outline_scene_description
            )
        for name in outline_contract.get("characters") or []:
            if name and name not in scene_characters:
                scene_characters.append(name)

        contract_text = format_outline_scene_contract(outline_contract)
        if contract_text:
            canonical_context = (
                f"{contract_text}\n\n{canonical_context}"
                if canonical_context
                else contract_text
            )

    effective_guidance = guidance or ""
    if outline_contract and outline_contract.get("guidance"):
        contract_guidance = str(outline_contract.get("guidance") or "").strip()
        if contract_guidance and contract_guidance not in effective_guidance:
            effective_guidance = (
                f"{contract_guidance}\n\n用户/当前操作补充：{effective_guidance}"
                if effective_guidance
                else contract_guidance
            )

    try:
        from agents.story_memory import StoryMemoryFacade

        state_pack = StoryMemoryFacade(user_id, project_name).compose_scene_task_pack(
            chapter_title=chapter_title or "",
            chapter_description=str((outline_contract or {}).get("chapter_description") or ""),
            scene_title=scene_name or "",
            scene_description=scene_description,
            scene_characters=scene_characters,
            guidance=effective_guidance,
            chr_map=chr_map,
        )
        state_text = state_pack.get("text") or ""
        if state_text:
            canonical_context = (
                f"{state_text}\n\n{canonical_context}"
                if canonical_context
                else state_text
            )
    except Exception as e:
        print(f"[StoryMemory] 生产端场景任务包构建失败（已降级）：{e}")

    return {
        "project_meta": {
            "project_name": project_name,
            "file_path": normalized_file_path,
            "scene_name": scene_name,
            "node_id": node_id,
        },
        "worldview": worldview,
        "roles": roles,
        "chr_map": chr_map,
        "characters": characters_payload,
        "full_outline": full_outline,
        "narrative_memory": narrative_memory,
        "story_structure": {
            "operation": operation,
            "segment_count": segment_count,
            "guidance": effective_guidance,
            "outline_scene_contract": outline_contract,
        },
        "local_script": local_script,
        "task_intent": {
            "operation": operation,
            "guidance": effective_guidance,
            "last_node_text": last_node_text,
        },
        "guidance": effective_guidance,
        "outline_scene_contract": outline_contract,
        "context": canonical_context,
        "story_data": story_data,
        "target_scene": target_scene,
    }


def _persist_generated_text(
    user_id: str,
    project_name: str,
    current_file: str,
    generated_text: str,
    rewrite: bool = False,
) -> None:
    """ScriptWriter 小说正文落盘函数。"""
    from story.file_naming import resolve_story_file_path

    stories_path = get_project_stories_path(user_id, project_name)
    file_path, _, _ = resolve_story_file_path(stories_path, current_file or "")
    if not file_path:
        normalized_file = current_file or "新场景.md"
        if not os.path.splitext(normalized_file)[1]:
            normalized_file += ".md"
        file_path = os.path.join(stories_path, normalized_file)

    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    from story.novel_parser import parse_novel_document, serialize_novel_document

    generated_document = parse_novel_document(generated_text)
    new_text = generated_document["body"]
    if not new_text:
        return

    if rewrite or not os.path.exists(file_path):
        final_text = serialize_novel_document(new_text, generated_document["conception"])
    else:
        with open(file_path, "r", encoding="utf-8") as f:
            existing_document = parse_novel_document(f.read())
        body = f"{existing_document['body']}\n\n{new_text}" if existing_document["body"] else new_text
        conception = generated_document["conception"] or existing_document["conception"]
        final_text = serialize_novel_document(body, conception)

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(final_text)


def _record_story_memory_from_story_file(
    user_id: str,
    project_name: str,
    current_file: str,
    *,
    scene_name: str = "",
    guidance: str = "",
    chr_map: Dict[int, str] | None = None,
) -> None:
    """手动创作落盘后，后台从实际文件回读并吸收故事状态。"""
    from agents.story_memory import enqueue_story_file_memory_write

    enqueue_story_file_memory_write(
        user_id=user_id,
        project_name=project_name,
        current_file=current_file,
        scene_name=scene_name,
        guidance=guidance,
        chr_map=chr_map,
        label="手动生产流",
    )


def _clean_generated_nodes(
    final_nodes: List[Dict[str, Any]],
    *,
    allow_visual_illustration: bool = False,
    allowed_background_ids: set[str] | None = None,
) -> List[Dict[str, Any]]:
    """
    清洗 AI 生成的节点列表，只保留叙事字段与受门禁控制的插图描述，
    防止 AI 幻觉添加的额外字段污染落盘后的 .arc 文件。
    """
    from story.arc_safety import normalize_illustration_pending, normalize_illustration_prompt

    allowed_backgrounds = {
        str(value).strip() for value in (allowed_background_ids or set()) if str(value).strip()
    }

    allowed_fields = {"id", "chr", "speaker", "txt", "opt", "optn", "dia", "presentation"}

    def clean_node(node):
        if isinstance(node, dict):
            strip_private_fields(node)
            for key in list(node.keys()):
                if key not in allowed_fields:
                    del node[key]
            presentation = node.get("presentation")
            prompt = ""
            pending = ""
            background_id = ""
            if allow_visual_illustration and isinstance(presentation, dict):
                prompt = normalize_illustration_prompt(presentation.get("illustration_prompt"))
                if not prompt:
                    pending = normalize_illustration_pending(presentation.get("illustration_pending"))
                raw_background = presentation.get("bg")
                if isinstance(raw_background, list):
                    raw_background = raw_background[0] if raw_background else ""
                candidate_background = str(raw_background or "").strip()
                if candidate_background in allowed_backgrounds:
                    background_id = candidate_background
            safe_presentation = {}
            if prompt:
                safe_presentation["illustration_prompt"] = prompt
            elif pending:
                safe_presentation["illustration_pending"] = pending
            if background_id:
                safe_presentation["bg"] = background_id
            if safe_presentation:
                node["presentation"] = safe_presentation
            else:
                node.pop("presentation", None)
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


def _ensure_generated_output_is_persistable(
    *,
    export_format: str,
    generated_text: str,
    final_nodes: List[Dict[str, Any]] | None = None,
    label: str = "正文",
) -> None:
    """在落盘前确认模型确实产出了可被当前格式消费的内容。"""
    if export_format == "novel":
        if not str(generated_text or "").strip():
            raise RuntimeError(f"ScriptWriter 未生成可落盘的{label}，原文件未修改。")
        return

    if not str(generated_text or "").strip() or not isinstance(final_nodes, list) or not final_nodes:
        raise RuntimeError(f"ScriptWriter 未生成可解析的 ARC {label}，原文件未修改。")


def _persist_generated_nodes(
    user_id: str,
    project_name: str,
    current_file: str,
    scene_name: str,
    after_node_id: int,
    final_nodes: List[Dict[str, Any]],
    rewrite: bool = False,
    thought: str = "",
    chr_map: Dict[int, str] | None = None,
) -> None:
    """
    ScriptWriter 局部落盘函数：将生成的节点写回 .arc 文件。

    【写入模式语义】
    - rewrite=False（默认 - 插入模式）：
        在 after_node_id 节点之后逐个插入 final_nodes，将后续节点顶下后移。
        after_node_id=0 表示在场景内容最前面插入。
        适用于：单段续写、多段续写、場景过渡生成（bridge）。
    - rewrite=True（完全重写模式）：
        将目标场景的对话数组直接替换为 final_nodes（清空原内容）。
        适用于：重写整个场景 (rewrite_scene 模式)。
    """
    from story.arc_parser import parse_arc, serialize_to_arc

    stories_path = get_project_stories_path(user_id, project_name)
    normalized_file = (
        current_file if current_file.endswith(".arc") else f"{current_file}.arc"
    )
    file_path = os.path.join(stories_path, normalized_file)
    with open(file_path, "r", encoding="utf-8") as f:
        arc_content = f.read()
    story_data = parse_arc(arc_content, chr_map=chr_map)
    strip_private_fields(story_data)

    target_scene = None
    for s in story_data:
        if s.get("scene") == scene_name:
            target_scene = s
            break
    if not target_scene:
        raise FileNotFoundError(f"场景 '{scene_name}' 未找到")

    from core.project_settings import (
        get_visual_illustration_settings,
        is_visual_illustration_enabled,
    )
    from story.arc_safety import validate_arc_visual_prompt_candidate
    from story.presentation_manifest import get_project_background_catalog

    visual_settings = get_visual_illustration_settings(user_id, project_name)
    visual_enabled = is_visual_illustration_enabled(user_id, project_name)
    allowed_background_ids = {
        item["id"] for item in get_project_background_catalog(user_id, project_name)
    }
    final_nodes = _clean_generated_nodes(
        final_nodes,
        allow_visual_illustration=visual_enabled,
        allowed_background_ids=allowed_background_ids,
    )

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

    new_arc_content = serialize_to_arc(story_data, chr_map=chr_map)
    validate_arc_visual_prompt_candidate(
        arc_content,
        new_arc_content,
        max_per_scene=visual_settings["max_per_scene"],
        min_node_gap=visual_settings["min_node_gap"],
    )
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(new_arc_content)


@production_router.post("/api/ai/critic")
async def run_critic_review(
    data: CriticReviewRequest, user: dict = Depends(get_current_user)
):
    """手动触发 Critic 评审（不参与自动工作流）"""
    project_name = resolve_project_name(get_current_project_name(), data.projectName)
    if not project_name:
        return JSONResponse(status_code=400, content={"error": "缺少项目名称"})

    user_id = str(user["user_id"])
    bundle = load_project_context_bundle(user_id, project_name)
    style_profile = load_project_style_profile(user_id=user_id, project_name=project_name)
    effective_context = (data.activeContext or data.context or "").strip()

    # 读取项目级故事主题参数，注入审稿上下文
    story_tags = get_project_story_tags(user_id, project_name)
    effective_export_format = "novel" if story_tags.get("workspace_mode") == "novel" else "arc"
    review_target = data.sceneName or data.filePath or ("当前小说文本" if effective_export_format == "novel" else "当前场景剧本")
    story_tags_hint = build_story_tags_hint(story_tags)

    try:
        critic = CriticAgent(user_id)
    except ValueError as e:
        return JSONResponse(status_code=422, content={"error": str(e)})
    except Exception as e:
        return JSONResponse(
            status_code=500, content={"error": f"AI 服务初始化失败: {e}"}
        )
    review = await run_in_threadpool(
        critic.evaluate,
        script_nodes=data.script_nodes,
        script_text=data.script_text or "",
        context=effective_context,
        guidance=data.guidance or "",
        worldview=bundle.get("worldview", ""),
        roles=bundle.get("roles", ""),
        style_profile=style_profile,
        review_target=review_target,
        story_tags=story_tags_hint,
    )
    try:
        from agents.story_memory import StoryMemoryFacade

        StoryMemoryFacade(user_id, project_name).record_quality_review(
            review=review,
            review_target=review_target,
            scene_name=data.sceneName or "",
            source_path=data.filePath or "",
        )
    except Exception as memory_err:
        print(f"[StoryMemory] Critic 质量记忆回写失败（不影响评审返回）：{memory_err}")

    return {
        "success": True,
        **review,
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
    from agents.scriptwriter_prewrite import (
        PREWRITE_STATUS_MESSAGE,
        ScriptwriterPreWriteRequest,
        run_autonomous_scriptwriter_prewrite,
    )

    user_id = str(user["user_id"])
    project_name = resolve_project_name(get_current_project_name(), data.projectName)
    if not project_name:
        return JSONResponse(status_code=400, content={"error": "缺少项目名称"})

    operation = (data.operation or "continue").strip()
    mode = (data.mode or "multi-node").strip()
    set_agent_context(user_id, project_name)

    # 读取项目级故事主题参数，注入专有工作模式上下文
    story_tags = get_project_story_tags(user_id, project_name)
    effective_export_format = "novel" if story_tags.get("workspace_mode") == "novel" else "arc"
    story_tags_hint = build_story_tags_hint(story_tags)

    from core.request_context import set_current_export_format
    set_current_export_format(effective_export_format)

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

    style_profile = load_project_style_profile(user_id=user_id, project_name=project_name)

    try:
        agent = ScriptwriterAgent(user_id=user_id)
    except ValueError as e:
        return JSONResponse(status_code=422, content={"error": str(e)})
    except Exception as e:
        return JSONResponse(
            status_code=500, content={"error": f"AI 服务初始化失败: {e}"}
        )

    stop_event = threading.Event()
    # 桥接器会在每轮迭代收尾时设置 stop_event 以停止断连轮询，
    # 不能把它直接当作“客户端已断开”；只有 cancelled_event 才代表真实取消。
    cancelled_event = threading.Event()

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
                    story_tags=story_tags_hint,
                )
                async for chunk in iterate_sync_iterable_in_thread(
                    lambda: agent.execute(exec_context, stream=True),
                    request=request,
                    stop_event=stop_event,
                    cancelled_event=cancelled_event,
                ):
                    if cancelled_event.is_set():
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
                            chunk.get("transition_text", "") or "",
                            chr_map=context_pack.get("chr_map") or None,
                        )
                        _ensure_generated_output_is_persistable(
                            export_format="arc",
                            generated_text=chunk.get("transition_text", "") or "",
                            final_nodes=dialogues,
                            label="过渡正文",
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
                prompt = f'''我的世界观是：\n"{context_pack.get("worldview", "")}"\n\n你可能需要用到的角色设定：\n"{context_pack.get("roles", "")}"\n\n我当前的上下文是：\n"{data.context or ""}"\n\n请根据以上信息，续写一句纯文本内容，续写长度约为 {data.length} 字。'''
                chat = matchbox().get_user_llm(user_id, agent_name="agent_scriptwriter")
                messages = prepare_specialized_prompt_messages_with_budget(
                    agent_id="agent_scriptwriter",
                    system_prompt=prepend_prompt_language_policy("你是一个专业的剧本创作助手。你只输出纯文本的对话内容。"),
                    user_prompt=prompt,
                    llm_client=chat,
                ).messages
                parser = PrefixReasoningStreamParser()
                single_node_text = ""
                async for model_chunk in iterate_sync_iterable_in_thread(
                    lambda: chat.stream(messages),
                    request=request,
                    stop_event=stop_event,
                    cancelled_event=cancelled_event,
                ):
                    if cancelled_event.is_set():
                        yield semantic_event_data(
                            "cancelled",
                            status="cancelled",
                            operation=operation,
                            mode=mode,
                            **on_cancelled("单节点续写已取消"),
                        )
                        return
                    raw_text = extract_raw_text_content_from_message(model_chunk)
                    _, text = parser.push(raw_text)
                    if not text:
                        continue
                    single_node_text += text
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
                    single_node_text += trailing_text
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
                _ensure_generated_output_is_persistable(
                    export_format="novel",
                    generated_text=single_node_text,
                    label="单节点正文",
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

            project_meta = context_pack.get("project_meta") or {}
            outline_contract = context_pack.get("outline_scene_contract") or {}
            chapter_name = str(outline_contract.get("chapter_title") or "").strip()
            if not chapter_name:
                normalized_path = str(project_meta.get("file_path") or "").replace("\\", "/")
                chapter_name = normalized_path.rsplit("/", 1)[0].split("/")[-1] if "/" in normalized_path else ""
            scene_name = str(data.sceneName or project_meta.get("scene_name") or "").strip()
            yield semantic_event_data(
                "progress",
                message=PREWRITE_STATUS_MESSAGE,
                stage="prewrite",
                operation=operation,
                mode=mode,
                **on_progress(PREWRITE_STATUS_MESSAGE, stage="prewrite"),
            )
            prewrite_result = await asyncio.to_thread(
                run_autonomous_scriptwriter_prewrite,
                ScriptwriterPreWriteRequest(
                    user_id=user_id,
                    project_name=project_name,
                    task_description=str(context_pack.get("guidance") or data.guidance or operation),
                    chapter_name=chapter_name,
                    scene_name=scene_name,
                    scene_guidance=str(context_pack.get("guidance") or ""),
                    scene_characters=[
                        str(item.get("name") or "").strip()
                        for item in (context_pack.get("characters") or [])
                        if isinstance(item, dict) and str(item.get("name") or "").strip()
                    ],
                    full_outline=str(context_pack.get("full_outline") or ""),
                    available_context=str(context_pack.get("context") or data.context or ""),
                ),
                llm=agent.llm,
                clean_text=agent._clean_model_visible_arc_text,
            )
            combined_context = str(context_pack.get("context") or data.context or "")
            if prewrite_result.context_addition:
                combined_context = combined_context + "\n\n" + prewrite_result.context_addition
            yield semantic_event_data(
                "progress",
                message="PreWrite 已完成，开始撰写正文",
                stage="writing",
                operation=operation,
                mode=mode,
                **on_progress("PreWrite 已完成，开始撰写正文", stage="writing"),
            )
            started_at = time.monotonic()

            exec_context = agent.build_context(
                operation=operation,
                context=combined_context,
                worldview=context_pack.get("worldview") or "",
                roles=context_pack.get("roles") or "",
                full_outline=context_pack.get("full_outline") or "",
                narrative_memory=context_pack.get("narrative_memory") or "",
                segment_count=data.segmentCount,
                guidance=context_pack.get("guidance") or data.guidance or "",
                style_profile=style_profile,
                chr_map=context_pack.get("chr_map") or None,
                last_node_text=data.lastNodeText or "",
                export_format=effective_export_format,
                story_tags=story_tags_hint,
            )

            full_arc_script = ""
            thought = ""
            async for chunk in iterate_sync_iterable_in_thread(
                lambda: agent.execute(exec_context, stream=True),
                request=request,
                stop_event=stop_event,
                cancelled_event=cancelled_event,
            ):
                if cancelled_event.is_set():
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
                parse_arc_to_dialogues(full_arc_script, chr_map=context_pack.get("chr_map") or None)
                if full_arc_script and effective_export_format != "novel"
                else []
            )
            if cancelled_event.is_set():
                yield semantic_event_data(
                    "cancelled",
                    status="cancelled",
                    operation=operation,
                    mode=mode,
                    **on_cancelled("ScriptWriter 生成已取消"),
                )
                return
            _ensure_generated_output_is_persistable(
                export_format=effective_export_format,
                generated_text=full_arc_script,
                final_nodes=final_nodes,
            )
            if mode != "single-node" and data.filePath:
                if effective_export_format == "novel":
                    _persist_generated_text(
                        user_id=user_id,
                        project_name=project_name,
                        current_file=data.filePath,
                        generated_text=full_arc_script,
                        rewrite=(operation == "rewrite_scene" or data.rewrite),
                    )
                    _record_story_memory_from_story_file(
                        user_id,
                        project_name,
                        data.filePath,
                        scene_name=data.sceneName or "",
                        guidance=data.guidance or "",
                        chr_map=context_pack.get("chr_map") or None,
                    )
                elif data.sceneName:
                    _persist_generated_nodes(
                        user_id=user_id,
                        project_name=project_name,
                        current_file=data.filePath,
                        scene_name=data.sceneName,
                        after_node_id=data.nodeId,
                        final_nodes=final_nodes,
                        rewrite=(operation == "rewrite_scene" or data.rewrite),
                        thought=thought,
                        chr_map=context_pack.get("chr_map") or None,
                    )
                    _record_story_memory_from_story_file(
                        user_id,
                        project_name,
                        data.filePath,
                        scene_name=data.sceneName or "",
                        guidance=data.guidance or "",
                        chr_map=context_pack.get("chr_map") or None,
                    )
            elapsed = max(time.monotonic() - started_at, 0.001)
            final_speed = round(total_chars / elapsed, 2)
            yield semantic_event_data(
                "done",
                mode=mode,
                operation=operation,
                thought=thought,
                text=full_arc_script,
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
            if cancelled_event.is_set():
                yield semantic_event_data(
                    "cancelled",
                    status="cancelled",
                    operation=operation,
                    mode=mode,
                    **on_cancelled("ScriptWriter 生成已取消"),
                )
                return
            from .schemas import format_ai_error
            friendly = format_ai_error(e)
            yield semantic_event_data("error", error=friendly, **on_error(friendly))

    return EventSourceResponse(generate())


@production_router.post("/api/scriptwriter/feedback/stream")
async def scriptwriter_feedback_stream(
    request: Request,
    data: ScriptwriterFeedbackRequest,
    user: dict = Depends(get_current_user),
):
    """ScriptWriter 统一反馈流接口。"""
    user_id = str(user["user_id"])
    project_name = resolve_project_name(get_current_project_name(), data.projectName)
    if not project_name:
        return JSONResponse(status_code=400, content={"error": "缺少项目名称"})

    set_agent_context(user_id, project_name)

    bundle = load_project_context_bundle(user_id, project_name)
    worldview = bundle.get("worldview", "")
    roles = bundle.get("roles", "")

    try:
        agent = ScriptwriterAgent(user_id=user_id)
    except ValueError as e:
        return JSONResponse(status_code=422, content={"error": str(e)})
    except Exception as e:
        return JSONResponse(
            status_code=500, content={"error": f"AI 服务初始化失败: {e}"}
        )

    stop_event = threading.Event()
    cancelled_event = threading.Event()

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
                if cancelled_event.is_set():
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
                    cancelled_event=cancelled_event,
                ):
                    if cancelled_event.is_set():
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
            if cancelled_event.is_set():
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
            if cancelled_event.is_set():
                yield semantic_event_data(
                    "cancelled",
                    status="cancelled",
                    **on_cancelled("反馈任务已取消"),
                )
                return
            from .schemas import format_ai_error
            friendly = format_ai_error(e)
            yield semantic_event_data(
                "error", status="error", error=friendly, **on_error(friendly)
            )

    return EventSourceResponse(generate())

