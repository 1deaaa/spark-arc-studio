"""GraphRAG（项目知识图谱）配置 API。

提供项目级图谱开关、构建状态查询与手动刷新触发。

与语义搜索路由（semantic_search_routes）保持对称：
- 状态查询单项目 / 全部项目；
- 启用时若需要构建，会在后台 daemon 线程异步触发；
- 禁用不删除已构建图谱，仅暂停后续刷新；
- AI 端通过 ``graph_rag_tool`` 只读 ``status`` / ``query``，不再具备触发构建的能力。
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool
from typing import Annotated

from core.auth import get_current_user
from core.project_settings import (
    get_project_settings,
    set_project_setting,
    list_projects_graphrag_status,
    get_default_graphrag_enabled,
    set_default_graphrag_enabled,
)
from agents.project_background_builds import cancel_project_graphrag_build

graphrag_router = APIRouter(prefix="/api/graphrag", tags=["graphrag"])


# ==================== 状态序列化辅助 ====================

def _empty_build_state() -> dict:
    return {
        "status": "not_built",
        "stage": "idle",
        "error": "",
        "started_at": "",
        "finished_at": "",
        "progress": {
            "total_chunks": 0,
            "done_chunks": 0,
            "triplets_collected": 0,
            "source_docs": 0,
            "nodes": 0,
            "edges": 0,
        },
    }


def _resolve_project_graphrag_status_sync(
    user_id: str,
    project_name: str,
    enabled: bool,
    *,
    check_freshness: bool = False,
) -> dict:
    """同步实现：读图谱状态、读取 build_state（按需做 freshness 比对）。

    重要：``check_freshness`` 控制是否进行哈希扫盘（``_needs_rebuild``）。
    - **列表模式默认 False**：避免每次 GET /status 都对所有项目串行扫盘，
      防止"项目越多越卡"。
    - **单项目模式默认 True**：用户主动查看某个项目，愿意付出一次扫盘代价
      换得"待更新"状态判定。
    """
    graph_ready = False
    metadata_ready = False
    build_state = _empty_build_state()
    needs_rebuild = False
    metadata: dict = {}

    if not project_name:
        return {
            "graph_ready": graph_ready,
            "metadata_ready": metadata_ready,
            "needs_rebuild": needs_rebuild,
            "build_state": build_state,
            "metadata": metadata,
        }

    try:
        from agents.graphrag import GraphRAGService

        service = GraphRAGService(user_id=user_id, project_name=project_name)
        # enabled=False 永远不做 freshness；enabled=True 也按入参开关决定
        effective_freshness = bool(enabled and check_freshness)
        status = service.get_status(check_freshness=effective_freshness)
        graph_ready = bool(status.get("graph_ready", False))
        metadata_ready = bool(status.get("metadata_ready", False))
        needs_rebuild = bool(status.get("needs_rebuild", False))
        build_state = status.get("build_state", build_state)
        metadata = status.get("metadata", {}) or {}
    except Exception as e:
        build_state = {
            **_empty_build_state(),
            "status": "error",
            "stage": "error",
            "error": str(e),
        }

    return {
        "graph_ready": graph_ready,
        "metadata_ready": metadata_ready,
        "needs_rebuild": needs_rebuild,
        "build_state": build_state,
        "metadata": _summarize_metadata(metadata),
    }


def _summarize_metadata(metadata: dict | None) -> dict:
    """仅向前端返回必要的摘要字段，避免把完整 communities/file_hashes 推过去。"""
    md = metadata if isinstance(metadata, dict) else {}
    return {
        "built_at": md.get("built_at", ""),
        "source_docs": int(md.get("source_docs", 0) or 0),
        "chunks": int(md.get("chunks", 0) or 0),
        "triplets": int(md.get("triplets", 0) or 0),
        "nodes": int(md.get("nodes", 0) or 0),
        "edges": int(md.get("edges", 0) or 0),
    }


async def _resolve_project_graphrag_status(
    user_id: str,
    project_name: str,
    enabled: bool,
    *,
    check_freshness: bool = False,
) -> dict:
    return await run_in_threadpool(
        _resolve_project_graphrag_status_sync,
        user_id,
        project_name,
        enabled,
        check_freshness=check_freshness,
    )


def _trigger_project_graphrag_refresh_sync(user_id: str, project_name: str) -> dict:
    """同步实现：直接把"需不需要重建"的判断丢给 daemon 线程，路由层不再扫盘。

    设计要点：
    - 路由层只读 settings（很轻），决定是否启动 daemon 线程；
    - 是否真的需要重建 = daemon 线程内由 ``build_index`` 自己根据
      ``file_hashes`` 做命中跳过；命中时 daemon 几乎瞬间结束并把状态写成 ready。
    - 这样避免了"路由层先 hash + daemon 内再 hash"的重复劳动。
    """
    settings = get_project_settings(user_id, project_name)
    enabled = bool(settings.get("graphrag_enabled", False))

    if not enabled:
        # 关闭状态下也不做 freshness，直接返回内存/磁盘快照
        index_status = _resolve_project_graphrag_status_sync(
            user_id, project_name, False, check_freshness=False
        )
        return {
            "enabled": False,
            "triggered": False,
            **index_status,
        }

    try:
        from agents.graphrag import GraphRAGService

        service = GraphRAGService(user_id=user_id, project_name=project_name)
        # 直接交给 daemon 线程：内部会 hash 比对、命中跳过、否则跑全量构建
        status = service.start_background_build(force_rebuild=False)
        # daemon 启动后立刻读快照（status 多数情况是 queued/building/ready 之一）
        # 注意：这里不要再 get_status(check_freshness=True)，避免又扫一次盘
        full_status = service.get_status(check_freshness=False)
        return {
            "enabled": True,
            "triggered": True,
            "graph_ready": bool(full_status.get("graph_ready", False)),
            "metadata_ready": bool(full_status.get("metadata_ready", False)),
            "needs_rebuild": bool(full_status.get("needs_rebuild", False)),
            "build_state": full_status.get("build_state", status),
            "metadata": _summarize_metadata(full_status.get("metadata", {})),
        }
    except Exception as e:
        return {
            "enabled": True,
            "triggered": False,
            "graph_ready": False,
            "metadata_ready": False,
            "needs_rebuild": False,
            "build_state": {
                **_empty_build_state(),
                "status": "error",
                "stage": "error",
                "error": str(e),
            },
            "metadata": _summarize_metadata({}),
        }


async def _trigger_project_graphrag_refresh(user_id: str, project_name: str) -> dict:
    return await run_in_threadpool(
        _trigger_project_graphrag_refresh_sync, user_id, project_name
    )


# ==================== 请求模型 ====================

class ProjectNameRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    project_name: Annotated[str, Field(alias="projectName")]


class DefaultEnabledRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    default_enabled: Annotated[bool, Field(alias="defaultEnabled")]


# ==================== API 端点 ====================

@graphrag_router.get('/status')
async def get_graphrag_status(
    projectName: str = "",
    user: dict = Depends(get_current_user),
):
    """获取 GraphRAG 状态（单项目或全部项目）。"""
    user_id = str(user['user_id'])

    if projectName:
        settings = get_project_settings(user_id, projectName)
        enabled = bool(settings.get("graphrag_enabled", False))
        # 单项目模式：用户主动看一个项目，可以付出一次扫盘代价换 needs_rebuild 判定
        index_status = await _resolve_project_graphrag_status(
            user_id, projectName, enabled, check_freshness=True,
        )
        return {
            "projectName": projectName,
            "enabled": enabled,
            "graph_ready": index_status["graph_ready"],
            "metadata_ready": index_status["metadata_ready"],
            "needs_rebuild": index_status["needs_rebuild"],
            "build_state": index_status["build_state"],
            "metadata": index_status["metadata"],
        }

    # 列表模式：N 个项目串行调用，必须避免每个项目都扫盘哈希。
    # 仅返回 build_state（内存读）+ metadata（一次 JSON 文件读）。
    # "待更新"判定延迟到用户点单项目或主动 refresh 时进行。
    projects = list_projects_graphrag_status(user_id)
    project_items: list[dict] = []
    for item in projects:
        project_name = str(item.get("project_name", "") or item.get("projectName", "") or "")
        enabled = bool(item.get("enabled", False))
        index_status = await _resolve_project_graphrag_status(
            user_id, project_name, enabled, check_freshness=False,
        )
        project_items.append({
            **item,
            "graph_ready": index_status["graph_ready"],
            "metadata_ready": index_status["metadata_ready"],
            "needs_rebuild": index_status["needs_rebuild"],
            "build_state": index_status["build_state"],
            "metadata": index_status["metadata"],
        })

    return {
        "projects": project_items,
        "default_enabled": get_default_graphrag_enabled(user_id),
    }


@graphrag_router.post('/enable')
async def enable_graphrag(data: ProjectNameRequest, user: dict = Depends(get_current_user)):
    """启用项目知识图谱。会持久化开关，并在必要时后台启动构建。"""
    user_id = str(user['user_id'])
    project_name = data.project_name.strip()

    if not project_name:
        raise HTTPException(status_code=400, detail="缺少项目名称")

    set_project_setting(user_id, project_name, "graphrag_enabled", True)
    index_status = await _trigger_project_graphrag_refresh(user_id, project_name)
    return {
        "success": True,
        "projectName": project_name,
        "enabled": True,
        "triggered": bool(index_status.get("triggered", False)),
        "graph_ready": index_status["graph_ready"],
        "metadata_ready": index_status["metadata_ready"],
        "needs_rebuild": index_status["needs_rebuild"],
        "build_state": index_status["build_state"],
        "metadata": index_status["metadata"],
    }


@graphrag_router.post('/refresh')
async def refresh_graphrag(data: ProjectNameRequest, user: dict = Depends(get_current_user)):
    """显式触发单项目 GraphRAG 差异检查，必要时后台启动构建。"""
    user_id = str(user['user_id'])
    project_name = data.project_name.strip()

    if not project_name:
        raise HTTPException(status_code=400, detail="缺少项目名称")

    index_status = await _trigger_project_graphrag_refresh(user_id, project_name)
    return {
        "success": True,
        "projectName": project_name,
        "enabled": bool(index_status.get("enabled", False)),
        "triggered": bool(index_status.get("triggered", False)),
        "graph_ready": index_status["graph_ready"],
        "metadata_ready": index_status["metadata_ready"],
        "needs_rebuild": index_status["needs_rebuild"],
        "build_state": index_status["build_state"],
        "metadata": index_status["metadata"],
    }


@graphrag_router.post('/disable')
async def disable_graphrag(data: ProjectNameRequest, user: dict = Depends(get_current_user)):
    """禁用项目知识图谱。仅暂停刷新触发，不删除已构建文件。"""
    user_id = str(user['user_id'])
    project_name = data.project_name.strip()

    if not project_name:
        raise HTTPException(status_code=400, detail="缺少项目名称")

    set_project_setting(user_id, project_name, "graphrag_enabled", False)
    cancel_warnings = await run_in_threadpool(cancel_project_graphrag_build, user_id, project_name)
    # 禁用后查询时不再做 freshness 比对，避免无意义的哈希扫描
    index_status = await _resolve_project_graphrag_status(user_id, project_name, False)
    return {
        "success": True,
        "projectName": project_name,
        "enabled": False,
        "cancel_warnings": cancel_warnings,
        "graph_ready": index_status["graph_ready"],
        "metadata_ready": index_status["metadata_ready"],
        "needs_rebuild": index_status["needs_rebuild"],
        "build_state": index_status["build_state"],
        "metadata": index_status["metadata"],
    }


@graphrag_router.post('/reset')
async def reset_graphrag(data: ProjectNameRequest, user: dict = Depends(get_current_user)):
    """删除项目知识图谱产物。用于排查或彻底重置。"""
    user_id = str(user['user_id'])
    project_name = data.project_name.strip()

    if not project_name:
        raise HTTPException(status_code=400, detail="缺少项目名称")

    def _do_reset() -> dict:
        from agents.graphrag import GraphRAGService

        service = GraphRAGService(user_id=user_id, project_name=project_name)
        return service.reset()

    try:
        result = await run_in_threadpool(_do_reset)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    settings = get_project_settings(user_id, project_name)
    enabled = bool(settings.get("graphrag_enabled", False))
    index_status = await _resolve_project_graphrag_status(user_id, project_name, enabled)
    return {
        "success": True,
        "projectName": project_name,
        "enabled": enabled,
        "removed": bool(result.get("removed", False)),
        "graph_ready": index_status["graph_ready"],
        "metadata_ready": index_status["metadata_ready"],
        "needs_rebuild": index_status["needs_rebuild"],
        "build_state": index_status["build_state"],
        "metadata": index_status["metadata"],
    }


@graphrag_router.post('/defaults')
async def set_graphrag_defaults(data: DefaultEnabledRequest, user: dict = Depends(get_current_user)):
    """设置用户级默认：新项目是否默认启用 GraphRAG 知识图谱。"""
    user_id = str(user['user_id'])
    value = set_default_graphrag_enabled(user_id, data.default_enabled)
    return {"success": True, "default_enabled": value}
