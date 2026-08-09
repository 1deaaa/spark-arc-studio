from __future__ import annotations

import copy
import contextvars
import os
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any, Optional


_EXECUTOR: ThreadPoolExecutor | None = None
_EXECUTOR_LOCK = threading.Lock()


def _worker_count() -> int:
    raw = os.environ.get("SPARKARC_STORY_MEMORY_WORKERS", "2")
    try:
        value = int(raw)
    except Exception:
        value = 2
    return max(1, min(value, 8))


def _executor() -> ThreadPoolExecutor:
    global _EXECUTOR
    if _EXECUTOR is None:
        with _EXECUTOR_LOCK:
            if _EXECUTOR is None:
                _EXECUTOR = ThreadPoolExecutor(
                    max_workers=_worker_count(),
                    thread_name_prefix="story-memory",
                )
    return _EXECUTOR


def _submit(label: str, fn, *args, **kwargs) -> Future:
    try:
        worker_context = contextvars.copy_context()
        return _executor().submit(worker_context.run, fn, *args, **kwargs)
    except Exception as exc:
        failed: Future = Future()
        failed.set_exception(exc)
        print(f"[StoryMemory] {label} 提交失败（不影响主流程）：{exc}")
        return failed


def _copy_payload(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        return copy.deepcopy(payload)
    except Exception:
        return dict(payload)


def _load_project_chr_map(user_id: str, project_name: str) -> dict[int, str]:
    """后台任务内兜底加载角色表，供 ARC 说话人名和隐藏 ID 互相解析。"""
    try:
        from story.project_files import load_character_id_name_map

        raw_map = load_character_id_name_map(user_id, project_name)
    except Exception:
        return {}
    result: dict[int, str] = {}
    for raw_id, raw_name in (raw_map or {}).items():
        try:
            cid = int(raw_id)
        except (TypeError, ValueError):
            continue
        name = str(raw_name or "").strip()
        if name:
            result[cid] = name
    return result


def _record_scene_write_job(user_id: str, project_name: str, payload: dict[str, Any], label: str) -> None:
    try:
        from agents.story_memory import StoryMemoryFacade

        facade = StoryMemoryFacade(user_id, project_name)
        delta = facade.prepare_scene_enrichment(**payload)
        commit_payload = _copy_payload(payload)
        commit_payload["use_llm_extractor"] = False
        commit_payload["precomputed_delta"] = delta
        facade.record_scene_write(**commit_payload)
    except Exception as exc:
        print(f"[StoryMemory] {label} 异步状态吸收失败（不影响主流程）：{exc}")


def enqueue_scene_memory_write(
    *,
    user_id: str,
    project_name: str,
    label: str = "场景",
    **payload: Any,
) -> Optional[Future]:
    """先写入确定性快照，再异步补充 LLM 结构化状态。"""
    scene_text = str(payload.get("scene_text") or "")
    if not user_id or not project_name or not scene_text.strip():
        return None

    requested_llm = payload.get("use_llm_extractor")
    snapshot_payload = _copy_payload(payload)
    snapshot_payload["use_llm_extractor"] = False
    snapshot_payload.pop("require_current_source_hash", None)
    try:
        from agents.story_memory import StoryMemoryFacade

        StoryMemoryFacade(str(user_id), str(project_name)).record_scene_write(**snapshot_payload)
    except Exception as exc:
        print(f"[StoryMemory] {label} 确定性快照写入失败（继续尝试后台吸收）：{exc}")

    if requested_llm is False:
        return None

    enrichment_payload = _copy_payload(payload)
    enrichment_payload["use_llm_extractor"] = True
    enrichment_payload["require_current_source_hash"] = True
    return _submit(
        label,
        _record_scene_write_job,
        str(user_id),
        str(project_name),
        enrichment_payload,
        label,
    )


def _record_story_file_job(
    user_id: str,
    project_name: str,
    current_file: str,
    scene_name: str,
    guidance: str,
    chr_map: dict[int, str] | None,
    label: str,
) -> None:
    try:
        from core.utils import get_project_stories_path
        from story.arc_parser import parse_arc, serialize_to_arc
        from story.file_naming import resolve_story_file_path

        chr_map = chr_map or _load_project_chr_map(user_id, project_name)
        stories_path = get_project_stories_path(user_id, project_name)
        file_path, file_format, parsed = resolve_story_file_path(stories_path, current_file or "")
        if not file_path or not os.path.exists(file_path):
            return

        with open(file_path, "r", encoding="utf-8") as f:
            file_text = f.read()

        scene_text = file_text
        if file_format != "novel" and scene_name:
            try:
                scenes = parse_arc(file_text, chr_map=chr_map)
                matched = [scene for scene in scenes if scene.get("scene") == scene_name]
                if matched:
                    scene_text = serialize_to_arc(matched, chr_map=chr_map)
            except Exception:
                scene_text = file_text

        source_rel_path = os.path.relpath(file_path, stories_path).replace("\\", "/")
        chapter_title = os.path.basename(os.path.dirname(file_path))
        if chapter_title == os.path.basename(stories_path):
            chapter_title = ""

        from agents.story_memory import StoryMemoryFacade

        StoryMemoryFacade(user_id, project_name).record_scene_write(
            scene_text=scene_text,
            chapter_index=(parsed.get("chapter_num") - 1) if parsed and parsed.get("chapter_num") else None,
            scene_index=(parsed.get("scene_num") - 1) if parsed and parsed.get("scene_num") else None,
            chapter_title=chapter_title,
            scene_title=scene_name or ((parsed or {}).get("display_name") or ""),
            guidance=guidance,
            source_path=source_rel_path,
            export_format=file_format or "arc",
            chr_map=chr_map,
        )
    except Exception as exc:
        print(f"[StoryMemory] {label} 异步文件状态吸收失败（不影响主流程）：{exc}")


def enqueue_story_file_memory_write(
    *,
    user_id: str,
    project_name: str,
    current_file: str,
    scene_name: str = "",
    guidance: str = "",
    chr_map: dict[int, str] | None = None,
    label: str = "故事文件",
) -> Optional[Future]:
    """按文件路径提交后台状态吸收任务，文件读取与解析也在后台执行。"""
    if not user_id or not project_name or not current_file:
        return None
    copied_chr_map = _copy_payload(chr_map or {})
    return _submit(
        label,
        _record_story_file_job,
        str(user_id),
        str(project_name),
        str(current_file),
        str(scene_name or ""),
        str(guidance or ""),
        copied_chr_map,
        label,
    )


def _record_story_content_job(
    user_id: str,
    project_name: str,
    stories_path: str,
    file_path: str,
    content: str,
    file_format: str,
    label: str,
) -> None:
    try:
        from story.arc_parser import parse_arc, serialize_to_arc
        from story.file_naming import parse_story_filename

        from agents.story_memory import StoryMemoryFacade

        chr_map = _load_project_chr_map(user_id, project_name)
        facade = StoryMemoryFacade(user_id, project_name)
        source_path = os.path.relpath(file_path, stories_path).replace("\\", "/")
        filename_meta = parse_story_filename(os.path.basename(file_path)) or {}
        chapter_title = os.path.basename(os.path.dirname(file_path))
        if chapter_title == os.path.basename(stories_path):
            chapter_title = ""

        chapter_index = None
        if filename_meta.get("chapter_num"):
            chapter_index = int(filename_meta["chapter_num"]) - 1

        scene_index_base = None
        if filename_meta.get("scene_num"):
            scene_index_base = int(filename_meta["scene_num"]) - 1

        display_name = filename_meta.get("display_name") or os.path.splitext(os.path.basename(file_path))[0]
        if file_format == "novel":
            facade.record_scene_write(
                scene_text=content,
                chapter_index=chapter_index,
                scene_index=scene_index_base,
                chapter_title=chapter_title,
                scene_title=display_name,
                source_path=source_path,
                export_format="novel",
            )
            return

        scenes = parse_arc(content, chr_map=chr_map)
        if not scenes:
            facade.record_scene_write(
                scene_text=content,
                chapter_index=chapter_index,
                scene_index=scene_index_base,
                chapter_title=chapter_title,
                scene_title=display_name,
                source_path=source_path,
                export_format="arc",
                chr_map=chr_map,
            )
            return

        for offset, scene in enumerate(scenes):
            scene_index = (scene_index_base + offset) if scene_index_base is not None else offset
            scene_title = str(scene.get("scene") or display_name or f"场景{offset + 1}").strip()
            guidance = str(scene.get("guide") or "").strip()
            intro = str(scene.get("intro") or "").strip()
            facade.record_scene_write(
                scene_text=serialize_to_arc([scene], chr_map=chr_map),
                chapter_index=chapter_index,
                scene_index=scene_index,
                chapter_title=chapter_title,
                scene_title=scene_title,
                scene_description=intro,
                guidance=guidance,
                source_path=source_path,
                export_format="arc",
                chr_map=chr_map,
            )
    except Exception as exc:
        print(f"[StoryMemory] {label} 异步内容状态吸收失败（不影响主流程）：{exc}")


def enqueue_story_content_memory_write(
    *,
    user_id: str,
    project_name: str,
    stories_path: str,
    file_path: str,
    content: str,
    file_format: str,
    label: str = "故事内容",
) -> Optional[Future]:
    """提交手动吸收用的后台任务；普通保存接口默认不调用它。"""
    if not user_id or not project_name or not file_path:
        return None
    return _submit(
        label,
        _record_story_content_job,
        str(user_id),
        str(project_name),
        str(stories_path),
        str(file_path),
        str(content or ""),
        str(file_format or "arc"),
        label,
    )
