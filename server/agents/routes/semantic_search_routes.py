"""语义检索配置 API。

提供项目级语义搜索开关、嵌入模型测试、索引状态查询。
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool
from typing import Annotated
import threading

from core.auth import get_current_user
from core.auth import require_admin
from core.project_settings import (
    get_project_settings,
    set_project_setting,
    list_projects_semantic_status,
    get_default_semantic_enabled,
    set_default_semantic_enabled,
)
from core.system_settings import (
    get_local_embedding_enabled,
    set_local_embedding_enabled,
)
from agents.vector_index.embedding_contract import (
    QWEN3_EMBEDDING_DIMENSIONS,
    embedding_contract_metadata,
    embedding_extra_body,
)
from agents.project_background_builds import cancel_project_vector_index_build

semantic_search_router = APIRouter(prefix="/api/semantic-search", tags=["semantic_search"])


def _empty_build_state() -> dict:
    return {
        "status": "not_built",
        "stage": "idle",
        "error": "",
        "started_at": "",
        "finished_at": "",
        "progress": {
            "total_files": 0,
            "done_files": 0,
            "total_chunks": 0,
            "embedded_chunks": 0,
            "changed_files": 0,
            "removed_files": 0,
            "reused_files": 0,
        },
    }


def _resolve_project_semantic_status_sync(
    user_id: str,
    project_name: str,
    enabled: bool,
    *,
    check_freshness: bool = True,
) -> dict:
    """同步实现：读 build_state（按需做 freshness 比对）。

    重要：``check_freshness`` 控制是否进行哈希扫盘（``_needs_rebuild``）。

    - **列表模式默认 False**：避免每次 GET /status 都对所有项目串行扫盘
      （项目正文 + 附件全文 md5），防止"项目越多越卡"。
    - **单项目 / 显式刷新模式默认 True**：愿意付出一次扫盘代价换得
      "待更新"判定。
    """
    index_exists = False
    build_state = _empty_build_state()
    needs_rebuild = False
    if not project_name:
        return {
            "index_exists": index_exists,
            "needs_rebuild": needs_rebuild,
            "build_state": build_state,
        }

    try:
        from agents.vector_index import VectorIndexService

        service = VectorIndexService(user_id, project_name)
        # enabled=False 永远不做 freshness；enabled=True 也按入参开关决定
        effective_freshness = bool(enabled and check_freshness)
        status = service.get_status(check_freshness=effective_freshness)
        index_exists = bool(status.get("exists", False))
        needs_rebuild = bool(status.get("needs_rebuild", False))
        build_state = status.get("build_state", build_state)
    except Exception as e:
        build_state = {
            **_empty_build_state(),
            "status": "error",
            "stage": "error",
            "error": str(e),
        }

    return {
        "index_exists": index_exists,
        "needs_rebuild": needs_rebuild,
        "build_state": build_state,
    }


async def _resolve_project_semantic_status(
    user_id: str,
    project_name: str,
    enabled: bool,
    *,
    check_freshness: bool = True,
) -> dict:
    """统一只读状态查询入口：异步外壳，阻塞 IO 走线程池，避免阻塞 event loop。"""
    return await run_in_threadpool(
        _resolve_project_semantic_status_sync,
        user_id,
        project_name,
        enabled,
        check_freshness=check_freshness,
    )


async def _resolve_embedding_runtime_status(user_id: str) -> tuple[bool, str]:
    """读取当前语义检索使用的嵌入运行时，优先展示已启用的本地服务。"""
    try:
        if get_local_embedding_enabled():
            from agents.vector_index.local_embedding import (
                is_local_embedding_alive,
                local_embedding_model_name,
            )
            if await run_in_threadpool(lambda: is_local_embedding_alive(timeout=1.0, ttl=0)):
                return True, local_embedding_model_name()
    except Exception:
        pass

    try:
        from llm.agen_matchbox import matchbox
        emb = matchbox().get_user_embedding(user_id)
        return True, emb.model
    except Exception:
        return False, ""


def _trigger_project_semantic_refresh_sync(user_id: str, project_name: str) -> dict:
    """同步实现：freshness 检查 + 必要时启动后台增量更新（启动本身仍走 daemon 线程）。"""
    index_status = _resolve_project_semantic_status_sync(user_id, project_name, True)
    triggered = False
    settings = get_project_settings(user_id, project_name)
    enabled = bool(settings.get("semantic_search_enabled", False))
    if not enabled:
        return {
            "enabled": False,
            "triggered": False,
            **index_status,
        }

    try:
        from agents.vector_index import VectorIndexService

        service = VectorIndexService(user_id, project_name)
        has_indexable_content = bool(service._compute_file_hashes())
        if index_status["needs_rebuild"] or (not index_status["index_exists"] and has_indexable_content):
            triggered = True
            status = service.ensure_background_build_started(check_freshness=True)
            return {
                "enabled": True,
                "triggered": triggered,
                "index_exists": bool(status.get("exists", False)),
                "needs_rebuild": bool(status.get("needs_rebuild", False)),
                "build_state": status.get("build_state", _empty_build_state()),
            }
    except Exception as e:
        return {
            "enabled": True,
            "triggered": False,
            "index_exists": False,
            "needs_rebuild": False,
            "build_state": {
                **_empty_build_state(),
                "status": "error",
                "stage": "error",
                "error": str(e),
            },
        }

    return {
        "enabled": True,
        "triggered": triggered,
        **index_status,
    }


async def _trigger_project_semantic_refresh(user_id: str, project_name: str) -> dict:
    """统一显式刷新入口（async 主函数）。

    - freshness 检查、文件哈希计算、ensure_background_build_started 全部在线程池里执行；
    - 不阻塞 event loop；
    - 后台真正的索引构建仍然由 ensure_background_build_started 创建 daemon 线程，
      构建中再次触发会自动排队补一轮（参见 VectorIndexService.start_background_build）。
    """
    return await run_in_threadpool(
        _trigger_project_semantic_refresh_sync, user_id, project_name
    )


# ==================== 请求模型 ====================

class ProjectNameRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    project_name: Annotated[str, Field(alias="projectName")]


class LocalEmbeddingToggleRequest(BaseModel):
    enabled: bool


# ==================== API 端点 ====================

@semantic_search_router.get('/status')
async def get_semantic_search_status(
    projectName: str = "",
    user: dict = Depends(get_current_user),
):
    """获取语义检索状态（单项目或全部项目）"""
    user_id = str(user['user_id'])

    if projectName:
        # 单项目查询
        settings = get_project_settings(user_id, projectName)
        enabled = settings.get("semantic_search_enabled", False)

        embedding_ready, embedding_model_name = await _resolve_embedding_runtime_status(user_id)

        # 单项目模式：用户主动看一个项目，可以付出一次扫盘代价换 needs_rebuild 判定
        index_status = await _resolve_project_semantic_status(
            user_id, projectName, enabled, check_freshness=True,
        )

        return {
            "projectName": projectName,
            "enabled": enabled,
            "embedding_ready": embedding_ready,
            "embedding_model_name": embedding_model_name,
            "index_exists": index_status["index_exists"],
            "needs_rebuild": index_status["needs_rebuild"],
            "build_state": index_status["build_state"],
        }
    else:
        # 全部项目批量查询
        projects = list_projects_semantic_status(user_id)

        embedding_ready, embedding_model_name = await _resolve_embedding_runtime_status(user_id)

        # 列表模式：N 个项目串行调用，必须避免每个项目都扫盘哈希。
        # 仅返回 build_state（内存读）+ index_exists（一次目录探测）。
        # "待更新"判定延迟到用户点单项目或主动 refresh 时进行。
        project_items: list[dict] = []
        for item in projects:
            project_name = str(item.get("project_name", "") or item.get("projectName", "") or "")
            enabled = bool(item.get("enabled", False))
            index_status = await _resolve_project_semantic_status(
                user_id, project_name, enabled, check_freshness=False,
            )
            project_items.append({
                **item,
                "index_exists": index_status["index_exists"],
                "needs_rebuild": index_status["needs_rebuild"],
                "build_state": index_status["build_state"],
            })

        return {
            "projects": project_items,
            "embedding_ready": embedding_ready,
            "embedding_model_name": embedding_model_name,
            "embedding_contract": embedding_contract_metadata(),
            "default_enabled": get_default_semantic_enabled(user_id),
        }


@semantic_search_router.post('/enable')
async def enable_semantic_search(data: ProjectNameRequest, user: dict = Depends(get_current_user)):
    """启用语义搜索。先测试嵌入模型，成功后才持久化开关。"""
    user_id = str(user['user_id'])
    project_name = data.project_name.strip()

    if not project_name:
        raise HTTPException(status_code=400, detail="缺少项目名称")

    # 测试嵌入模型
    try:
        from llm.agen_matchbox import matchbox
        from llm.agen_matchbox.utils import test_platform_embedding
        mb = matchbox()

        # 获取用户选择的嵌入模型
        emb = mb.get_user_embedding(user_id, extra_body=embedding_extra_body())
        model_name = emb.model

        # 获取平台信息
        with mb.Session() as session:
            from llm.agen_matchbox.models import UserEmbeddingSelection, LLMPlatform
            selection = session.query(UserEmbeddingSelection).filter_by(user_id=user_id).first()
            if selection and selection.platform_id:
                plat = session.query(LLMPlatform).filter_by(id=selection.platform_id).first()
                if plat:
                    api_key = mb._get_effective_api_key(session, user_id, plat)
                    if api_key:
                        result = test_platform_embedding(
                            plat.base_url,
                            api_key,
                            model_name,
                            extra_body=embedding_extra_body(),
                        )
                        dims = result.get("dims", 0)
                        if dims != QWEN3_EMBEDDING_DIMENSIONS:
                            raise ValueError(
                                f"嵌入模型维度为 {dims}，但当前索引契约要求 {QWEN3_EMBEDDING_DIMENSIONS} 维。"
                            )
                    else:
                        raise ValueError("嵌入模型所在平台未配置 API Key")
                else:
                    raise ValueError("嵌入模型所在平台不存在")
            else:
                # 无用户选择，使用 get_user_embedding 的回退逻辑已经能拿到实例
                # 直接用 embed_query 做一次真实调用
                test_vector = emb.embed_query("测试")
                if not test_vector or len(test_vector) == 0:
                    raise ValueError("嵌入模型返回了空向量，请检查模型配置")

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        error_msg = str(e)
        if "未找到可用的 Embedding 模型" in error_msg:
            raise HTTPException(
                status_code=400,
                detail="未找到可用的嵌入模型。请在设置 → AI管理 中配置并选择一个 Embedding 模型。"
            )
        raise HTTPException(status_code=400, detail=f"嵌入模型测试失败：{error_msg}")

    # 测试通过，持久化开关
    settings = set_project_setting(user_id, project_name, "semantic_search_enabled", True)
    index_status = await _trigger_project_semantic_refresh(user_id, project_name)

    return {
        "success": True,
        "projectName": project_name,
        "enabled": True,
        "settings": settings,
        "index_exists": index_status["index_exists"],
        "needs_rebuild": index_status["needs_rebuild"],
        "build_state": index_status["build_state"],
    }


@semantic_search_router.post('/refresh')
async def refresh_semantic_search(data: ProjectNameRequest, user: dict = Depends(get_current_user)):
    """显式触发单项目语义索引差异检查，并在必要时后台启动增量更新。"""
    user_id = str(user['user_id'])
    project_name = data.project_name.strip()

    if not project_name:
        raise HTTPException(status_code=400, detail="缺少项目名称")

    index_status = await _trigger_project_semantic_refresh(user_id, project_name)
    return {
        "success": True,
        "projectName": project_name,
        "enabled": bool(index_status["enabled"]),
        "triggered": bool(index_status["triggered"]),
        "index_exists": index_status["index_exists"],
        "needs_rebuild": index_status["needs_rebuild"],
        "build_state": index_status["build_state"],
    }


@semantic_search_router.post('/disable')
async def disable_semantic_search(data: ProjectNameRequest, user: dict = Depends(get_current_user)):
    """禁用语义搜索。"""
    user_id = str(user['user_id'])
    project_name = data.project_name.strip()

    if not project_name:
        raise HTTPException(status_code=400, detail="缺少项目名称")

    settings = set_project_setting(user_id, project_name, "semantic_search_enabled", False)
    cancel_warnings = await run_in_threadpool(cancel_project_vector_index_build, user_id, project_name)
    index_status = await _resolve_project_semantic_status(user_id, project_name, False)

    return {
        "success": True,
        "projectName": project_name,
        "enabled": False,
        "settings": settings,
        "cancel_warnings": cancel_warnings,
        "index_exists": index_status["index_exists"],
        "needs_rebuild": index_status["needs_rebuild"],
        "build_state": index_status["build_state"],
    }


@semantic_search_router.post('/test-embedding')
async def test_semantic_embedding(user: dict = Depends(get_current_user)):
    """测试当前用户配置的嵌入模型是否可用。"""
    user_id = str(user['user_id'])

    try:
        if get_local_embedding_enabled():
            from agents.vector_index.local_embedding import (
                is_local_embedding_alive,
                local_embedding_model_name,
                LOCAL_EMBEDDING_API_KEY,
                LOCAL_EMBEDDING_BASE_URL,
            )
            if await run_in_threadpool(lambda: is_local_embedding_alive(timeout=2.0, ttl=0)):
                from langchain_openai import OpenAIEmbeddings

                emb = OpenAIEmbeddings(
                    model=embedding_contract_metadata()["model"],
                    api_key=LOCAL_EMBEDDING_API_KEY,
                    base_url=LOCAL_EMBEDDING_BASE_URL,
                    check_embedding_ctx_length=False,
                    extra_body=embedding_extra_body(),
                )
                test_vector = await run_in_threadpool(emb.embed_query, "测试")
                dims = len(test_vector) if test_vector else 0
                if dims != QWEN3_EMBEDDING_DIMENSIONS:
                    raise ValueError(
                        f"本地嵌入模型维度为 {dims}，但当前索引契约要求 {QWEN3_EMBEDDING_DIMENSIONS} 维。"
                    )
                return {
                    "success": True,
                    "dims": dims,
                    "model_name": local_embedding_model_name(),
                    "platform_name": "local",
                    "embedding_contract": embedding_contract_metadata(),
                }

        from llm.agen_matchbox import matchbox
        mb = matchbox()

        # 获取用户嵌入模型
        emb = mb.get_user_embedding(user_id, extra_body=embedding_extra_body())
        model_name = emb.model

        # 获取平台信息做精确测试
        with mb.Session() as session:
            from llm.agen_matchbox.models import UserEmbeddingSelection, LLMPlatform
            selection = session.query(UserEmbeddingSelection).filter_by(user_id=user_id).first()
            platform_name = ""
            if selection and selection.platform_id:
                plat = session.query(LLMPlatform).filter_by(id=selection.platform_id).first()
                if plat:
                    platform_name = plat.name
                    api_key = mb._get_effective_api_key(session, user_id, plat)
                    if api_key:
                        from llm.agen_matchbox.utils import test_platform_embedding
                        result = test_platform_embedding(
                            plat.base_url,
                            api_key,
                            model_name,
                            extra_body=embedding_extra_body(),
                        )
                        dims = result.get("dims", 0)
                        if dims != QWEN3_EMBEDDING_DIMENSIONS:
                            raise ValueError(
                                f"嵌入模型维度为 {dims}，但当前索引契约要求 {QWEN3_EMBEDDING_DIMENSIONS} 维。"
                            )
                        return {
                            "success": True,
                            "dims": dims,
                            "model_name": model_name,
                            "platform_name": platform_name,
                            "embedding_contract": embedding_contract_metadata(),
                        }

        # 回退：直接 embed_query
        test_vector = emb.embed_query("测试")
        dims = len(test_vector) if test_vector else 0
        if dims != QWEN3_EMBEDDING_DIMENSIONS:
            raise ValueError(
                f"嵌入模型维度为 {dims}，但当前索引契约要求 {QWEN3_EMBEDDING_DIMENSIONS} 维。"
            )
        return {
            "success": True,
            "dims": dims,
            "model_name": model_name,
            "platform_name": platform_name,
            "embedding_contract": embedding_contract_metadata(),
        }

    except ValueError as e:
        error_msg = str(e)
        if "未找到可用的 Embedding 模型" in error_msg:
            return {
                "success": False,
                "error": "未找到可用的嵌入模型。请在设置 → AI管理 中配置并选择一个 Embedding 模型。",
            }
        return {"success": False, "error": error_msg}
    except Exception as e:
        error_msg = str(e)
        return {"success": False, "error": f"嵌入模型测试失败：{error_msg}"}


@semantic_search_router.get('/local-embedding')
async def get_local_embedding(user: dict = Depends(get_current_user)):
    """查看本地嵌入服务状态。"""
    try:
        from agents.vector_index.local_embedding import get_local_embedding_status

        status = await run_in_threadpool(get_local_embedding_status)
        return {
            "success": True,
            "status": status,
            "enabled": get_local_embedding_enabled(),
            "embedding_contract": embedding_contract_metadata(),
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "status": {
                "configured": False,
                "running": False,
                "alive": False,
            },
            "enabled": get_local_embedding_enabled(),
            "embedding_contract": embedding_contract_metadata(),
        }


@semantic_search_router.post('/local-embedding')
async def set_local_embedding(
    data: LocalEmbeddingToggleRequest,
    admin_user: dict = Depends(require_admin),
):
    """管理员手动启动或停止本地嵌入服务。"""
    try:
        from agents.vector_index.local_embedding import (
            get_local_embedding_status,
            mark_local_embedding_starting,
            start_local_embedding_service,
            stop_local_embedding_service,
        )

        if data.enabled:
            set_local_embedding_enabled(True)
            mark_local_embedding_starting()
            thread = threading.Thread(
                target=start_local_embedding_service,
                name="local-embedding-startup",
                daemon=True,
            )
            thread.start()
            status = await run_in_threadpool(get_local_embedding_status)
            enabled = True
        else:
            status = await run_in_threadpool(stop_local_embedding_service)
            enabled = False
            set_local_embedding_enabled(False)
        return {
            "success": True,
            "status": status,
            "enabled": enabled,
            "embedding_contract": embedding_contract_metadata(),
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


class DefaultEnabledRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    default_enabled: Annotated[bool, Field(alias="defaultEnabled")]


@semantic_search_router.post('/defaults')
async def set_semantic_search_defaults(data: DefaultEnabledRequest, user: dict = Depends(get_current_user)):
    """设置用户级默认：新项目是否默认启用语义搜索。"""
    user_id = str(user['user_id'])
    value = set_default_semantic_enabled(user_id, data.default_enabled)
    return {"success": True, "default_enabled": value}
