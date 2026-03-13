"""
Lorebook API - Lorebook / Worldview 设定管理
"""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse, JSONResponse
from sse_starlette.sse import EventSourceResponse
from typing import Optional
import os
import json
import threading

from core.auth import get_current_user, get_optional_user
from core.request_context import current_project_name
from core.utils import (
    get_project_path,
    get_project_worldview_path,
    get_project_lorebook_path,
    ensure_project_worldview_and_character_settings,
    ensure_project_directory,
    ensure_project_characters_directory,
)

from agents.agent_lorebook import WorldviewAgent
from agents.agent_utils import iter_text_output
from agents.agent_style.utils import load_project_style_profile

from .schemas import (
    WorldviewRequest,
    LorebookRequest,
    WorldviewGenerateRequest,
    LorebookResetRequest,
    _write_worldview,
    format_ai_error,
)
from .streaming_utils import iterate_sync_iterable_in_thread
from .stream_semantics import on_cancelled

lorebook_router = APIRouter()


def _extract_xml_tag_value(text: str, tag: str) -> str | None:
    start_tag = f"<{tag}>"
    end_tag = f"</{tag}>"
    start = text.find(start_tag)
    if start == -1:
        return None
    start += len(start_tag)
    end = text.find(end_tag, start)
    if end == -1:
        return None
    return text[start:end].strip()


def _extract_xml_tag_fragment(text: str, tag: str) -> str | None:
    start_tag = f"<{tag}>"
    end_tag = f"</{tag}>"
    start = text.find(start_tag)
    if start == -1:
        return None
    start += len(start_tag)
    end = text.find(end_tag, start)
    if end == -1:
        return text[start:].lstrip("\r\n")
    return text[start:end].lstrip("\r\n")


def _parse_character_payload(text: str) -> tuple[str | None, str | None]:
    raw = (text or "").strip()
    if not raw:
        return None, None

    name = _extract_xml_tag_value(raw, "name")
    content = _extract_xml_tag_fragment(raw, "content")
    if name or content is not None:
        return name, (content or "").strip()

    separator_pos = raw.find("\n\n")
    if separator_pos != -1:
        legacy_name = raw[:separator_pos].strip() or None
        legacy_content = raw[separator_pos + 2 :].strip()
        return legacy_name, legacy_content

    return None, raw


@lorebook_router.get("/api/worldview/{project_name}")
async def get_worldview(
    project_name: str, user: Optional[dict] = Depends(get_optional_user)
):
    """读取指定项目的世界观文本"""
    try:
        if not user:
            return {"content": ""}
        user_id = str(user["user_id"])
        ensure_project_worldview_and_character_settings(user_id, project_name)
        worldview_path = get_project_worldview_path(user_id, project_name)
        if not os.path.exists(worldview_path):
            return {"content": ""}
        with open(worldview_path, "r", encoding="utf-8") as f:
            content = f.read()
        return {"content": content}
    except Exception as exc:
        return JSONResponse(
            status_code=500, content={"error": f"读取世界观失败: {exc}"}
        )


@lorebook_router.post("/api/worldview")
async def save_worldview_content(
    data: WorldviewRequest, user: dict = Depends(get_current_user)
):
    """保存世界观内容"""
    try:
        user_id = str(user["user_id"])
        project_name = data.projectName
        content = data.content
        if not project_name:
            return JSONResponse(
                status_code=400, content={"success": False, "message": "缺少项目名称"}
            )

        agent = WorldviewAgent(int(user_id))
        agent.write_result(
            content, operation="worldview", user_id=user_id, project_name=project_name
        )
        return {"success": True, "message": "世界观保存成功"}
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"保存世界观失败: {exc}"},
        )


@lorebook_router.post("/api/worldview/{project_name}")
async def save_worldview_by_path(
    project_name: str, data: WorldviewRequest, user: dict = Depends(get_current_user)
):
    user_id = str(user["user_id"])
    try:
        agent = WorldviewAgent(int(user_id))
        agent.write_result(
            data.content,
            operation="worldview",
            user_id=user_id,
            project_name=project_name,
        )
        return {"success": True, "message": "世界观保存成功"}
    except Exception as exc:
        return JSONResponse(
            status_code=500, content={"success": False, "message": str(exc)}
        )


@lorebook_router.post("/api/lorebook/reset")
async def reset_lorebook(
    data: LorebookResetRequest, user: dict = Depends(get_current_user)
):
    """重置世界观并删除所有角色（保留旁白）"""
    try:
        user_id = str(user["user_id"])
        project_name = data.projectName

        # 1. 重置世界观
        _write_worldview(user_id, project_name, "")

        # 2. 删除所有角色（保留 ID 为 -1 的旁白）
        characters_path = ensure_project_characters_directory(user_id, project_name)
        bind_file = os.path.join(characters_path, "chr.bind")

        mapping = {}
        if os.path.exists(bind_file):
            try:
                with open(bind_file, "r", encoding="utf-8") as f:
                    old_mapping = json.load(f) or {}
                    if "-1" in old_mapping:
                        mapping["-1"] = old_mapping["-1"]
            except Exception:
                mapping = {}

        # 删除所有角色文件（除了旁白 -1.txt）
        for filename in os.listdir(characters_path):
            if filename.endswith(".txt") and filename != "-1.txt":
                try:
                    os.remove(os.path.join(characters_path, filename))
                except Exception:
                    pass

        with open(bind_file, "w", encoding="utf-8") as f:
            json.dump(mapping, f, ensure_ascii=False, indent=2)

        return {"success": True, "message": "世界观与角色已重置"}
    except Exception as exc:
        return JSONResponse(
            status_code=500, content={"success": False, "message": f"重置失败: {exc}"}
        )


@lorebook_router.post("/api/ai/worldview/generate")
async def generate_worldview(
    request: Request,
    data: WorldviewGenerateRequest,
    user: dict = Depends(get_current_user),
):
    """流式生成世界观（通过后台线程桥接同步 LLM stream，避免阻塞事件循环）。"""

    user_id = str(user["user_id"])
    project_name = current_project_name.get() or data.projectName
    if not project_name:
        return JSONResponse(status_code=400, content={"error": "缺少项目名称"})

    if data.reset:
        _write_worldview(user_id, project_name, "")

    base_worldview = ""
    if not data.reset:
        worldview_path = get_project_worldview_path(user_id, project_name)
        if os.path.exists(worldview_path):
            with open(worldview_path, "r", encoding="utf-8") as f:
                base_worldview = f.read() or ""

    if not data.seed and not base_worldview:
        return JSONResponse(
            status_code=400, content={"error": "缺少 seed 且当前世界观为空"}
        )

    seed_text = data.seed or ""
    if base_worldview:
        if seed_text:
            seed_text = (
                "【当前世界观】\n"
                + base_worldview.strip()
                + "\n\n【用户补充方向】\n"
                + seed_text.strip()
            )
        else:
            seed_text = "【当前世界观】\n" + base_worldview.strip()

    try:
        agent = WorldviewAgent(user_id)
    except ValueError as e:
        return JSONResponse(status_code=422, content={"error": str(e)})
    except Exception as e:
        return JSONResponse(
            status_code=500, content={"error": f"AI 服务初始化失败: {e}"}
        )
    style_profile = load_project_style_profile(user_id=user_id, project_name=project_name)

    context = agent.build_context(
        operation="worldview",
        seed=seed_text,
        style_profile=style_profile,
        length_hint=data.lengthHint,
    )
    stop_event = threading.Event()

    async def streamer():
        full_text = []
        # cancelled_event 仅在客户端主动断开时被 iterate_sync_iterable_in_thread 设置，
        # 正常生成完成时不会被触发，可以安全地用于判断是否需要持久化结果。
        cancelled_event = threading.Event()
        try:
            async for chunk in iterate_sync_iterable_in_thread(
                lambda: iter_text_output(agent.execute(context)),
                request=request,
                stop_event=stop_event,
                cancelled_event=cancelled_event,
            ):
                if stop_event.is_set():
                    yield format_ai_error(RuntimeError("任务已取消"))
                    return
                if isinstance(chunk, str) and chunk:
                    full_text.append(chunk)
                    yield chunk
        except Exception as e:
            if stop_event.is_set():
                yield format_ai_error(RuntimeError("任务已取消"))
                return
            yield format_ai_error(e)
        finally:
            # 保存已生成内容：正常完成时保存完整内容，意外中断时也保存已生成的部分
            # cancelled_event 未被设置 = 非客户端主动断开，此时保存（含异常中断的部分结果）
            if full_text and not cancelled_event.is_set():
                try:
                    agent.write_result(
                        "".join(full_text),
                        operation="worldview",
                        user_id=user_id,
                        project_name=project_name,
                    )
                except Exception:
                    pass

    return StreamingResponse(streamer(), media_type="text/plain; charset=utf-8")


@lorebook_router.get("/api/lorebooks/{project_name}/{file_name}")
async def get_lorebook_file(
    project_name: str, file_name: str, user: dict = Depends(get_current_user)
):
    user_id = str(user["user_id"])
    lorebook_path = get_project_lorebook_path(user_id, project_name, file_name)
    if not os.path.exists(lorebook_path):
        return {"content": ""}
    with open(lorebook_path, "r", encoding="utf-8") as f:
        content = f.read()
    return {"content": content}


@lorebook_router.post("/api/lorebooks")
async def save_lorebook_file(
    data: LorebookRequest, user: dict = Depends(get_current_user)
):
    project_name = data.projectName
    file_name = data.fileName
    if not project_name or not file_name:
        return JSONResponse(status_code=400, content={"error": "缺少项目或文件名"})
    user_id = str(user["user_id"])
    lorebook_path = get_project_lorebook_path(user_id, project_name, file_name)
    try:
        with open(lorebook_path, "w", encoding="utf-8") as f:
            f.write(data.content)
        return {"success": True}
    except Exception as exc:
        return JSONResponse(status_code=500, content={"error": str(exc)})


@lorebook_router.get("/api/ai/gen-characters/stream")
async def gen_characters_stream(
    request: Request,
    projectName: str,
    count: int = 1,
    prompt: str = "",
    overwrite: bool = False,
    user: dict = Depends(get_current_user),
):
    """SSE 流式生成角色"""
    user_id = str(user["user_id"])
    stop_event = threading.Event()

    if count < 1 or count > 8:
        return JSONResponse(status_code=400, content={"error": "生成数量需在 1-8 之间"})

    async def event_generator():
        try:
            worldview_path = get_project_worldview_path(user_id, projectName)
            worldview = ""
            if os.path.exists(worldview_path):
                with open(worldview_path, "r", encoding="utf-8") as f:
                    worldview = f.read()

            characters_path = ensure_project_characters_directory(user_id, projectName)
            bind_path = os.path.join(characters_path, "chr.bind")

            mapping = {}
            if os.path.exists(bind_path):
                try:
                    with open(bind_path, "r", encoding="utf-8") as f:
                        mapping = json.load(f) or {}
                except Exception:
                    mapping = {}

            lines = []
            for cid, name in mapping.items():
                try:
                    char_file = os.path.join(characters_path, f"{cid}.txt")
                    content = ""
                    if os.path.exists(char_file):
                        with open(char_file, "r", encoding="utf-8") as f:
                            text = f.read()
                            parts = text.split("\n", 2)
                            content = parts[2] if len(parts) >= 3 else text
                    content = (content or "").strip()
                    if len(content) > 400:
                        content = content[:400] + "…"
                    lines.append(f"- {name}: {content}")
                except Exception:
                    continue
            existing_block = "\n".join(lines) if lines else ""

            if overwrite:
                # 清空角色文件（保留旁白 -1）但保留旧设定作为生成参考
                narrator_name = None
                if "-1" in mapping:
                    narrator_name = mapping.get("-1")

                for filename in os.listdir(characters_path):
                    if filename.endswith(".txt") and filename != "-1.txt":
                        try:
                            os.remove(os.path.join(characters_path, filename))
                        except Exception:
                            pass

                mapping = {}
                if narrator_name:
                    mapping["-1"] = narrator_name

                with open(bind_path, "w", encoding="utf-8") as f:
                    json.dump(mapping, f, ensure_ascii=False, indent=2)

            existing_ids = {int(k) for k in mapping.keys()} if mapping else set()

            created_count = 0

            for _ in range(count):
                char_id = 0
                while char_id in existing_ids:
                    char_id += 1
                existing_ids.add(char_id)

                mapping[str(char_id)] = "生成中..."
                with open(bind_path, "w", encoding="utf-8") as f:
                    json.dump(mapping, f, ensure_ascii=False, indent=2)

                agent = WorldviewAgent(user_id)

                buffer = ""
                name_sent = False
                sent_content_length = 0
                final_name = "新角色"
                final_content = ""

                yield {
                    "event": "character-start",
                    "data": json.dumps({"id": char_id, "name": ""}, ensure_ascii=False),
                }

                context = agent.build_context(
                    operation="character",
                    worldview=worldview,
                    existing_characters=existing_block,
                    extra_guidance=prompt,
                )

                # 为每个角色创建独立的 stop_event 和 cancelled_event：
                # - char_stop_event：由 iterate_sync_iterable_in_thread 的 finally 无条件 set，用于停止工作线程
                # - char_cancelled_event：仅在客户端主动断开时 set，用于准确判断是否真的被取消
                char_stop_event = threading.Event()
                char_cancelled_event = threading.Event()

                async for chunk in iterate_sync_iterable_in_thread(
                    lambda: agent.execute(context),
                    request=request,
                    stop_event=char_stop_event,
                    cancelled_event=char_cancelled_event,
                ):
                    if char_stop_event.is_set():
                        yield {
                            "event": "cancelled",
                            "data": json.dumps(
                                {
                                    "status": "cancelled",
                                    **on_cancelled("角色生成已取消"),
                                },
                                ensure_ascii=False,
                            ),
                        }
                        return
                    content = chunk if isinstance(chunk, str) else ""
                    if not content:
                        continue

                    buffer += content

                    parsed_name = _extract_xml_tag_value(buffer, "name")
                    if not name_sent and parsed_name:
                        final_name = parsed_name
                        yield {
                            "event": "character-streamed",
                            "data": json.dumps(
                                {"id": char_id, "name": final_name},
                                ensure_ascii=False,
                            ),
                        }
                        name_sent = True

                    parsed_content = _extract_xml_tag_fragment(buffer, "content")
                    current_content = parsed_content or ""
                    if len(current_content) > sent_content_length:
                        delta = current_content[sent_content_length:]
                        sent_content_length = len(current_content)
                        if delta:
                            yield {
                                "event": "character-delta",
                                "data": json.dumps(
                                    {"id": char_id, "delta": delta}, ensure_ascii=False
                                ),
                            }

                # char_cancelled_event 仅在客户端真正断开时被设置，
                # 因此可以准确区分"角色正常完成"和"被取消"两种情况。
                if char_cancelled_event.is_set():
                    yield {
                        "event": "cancelled",
                        "data": json.dumps(
                            {"status": "cancelled", **on_cancelled("角色生成已取消")},
                            ensure_ascii=False,
                        ),
                    }
                    return

                parsed_name, parsed_content = _parse_character_payload(buffer)
                if parsed_name:
                    final_name = parsed_name or "新角色"
                final_content = (parsed_content or "").strip()

                mapping[str(char_id)] = final_name
                with open(bind_path, "w", encoding="utf-8") as f:
                    json.dump(mapping, f, ensure_ascii=False, indent=2)

                char_file = os.path.join(characters_path, f"{char_id}.txt")
                with open(char_file, "w", encoding="utf-8") as f:
                    f.write(f"{final_name}\n\n{final_content}")

                yield {
                    "event": "character-end",
                    "data": json.dumps(
                        {"id": char_id, "name": final_name, "content": final_content},
                        ensure_ascii=False,
                    ),
                }
                created_count += 1

                snippet = (
                    final_content
                    if len(final_content) <= 400
                    else final_content[:400] + "…"
                )
                existing_block += f"\n- {final_name}: {snippet}"

            yield {
                "event": "done",
                "data": json.dumps({"count": created_count}, ensure_ascii=False),
            }

        except Exception as e:
            if stop_event.is_set():
                yield {
                    "event": "cancelled",
                    "data": json.dumps(
                        {"status": "cancelled", **on_cancelled("角色生成已取消")},
                        ensure_ascii=False,
                    ),
                }
                return
            print(f"AI 生成角色(SSE)失败: {e}")
            yield {
                "event": "error",
                "data": json.dumps({"message": f"生成失败: {e}"}, ensure_ascii=False),
            }

    return EventSourceResponse(event_generator())
