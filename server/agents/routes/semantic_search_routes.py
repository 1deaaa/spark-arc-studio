"""语义检索配置 API。

提供项目级语义搜索开关、嵌入模型测试、索引状态查询。
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from typing import Annotated

from core.auth import get_current_user
from core.project_settings import (
    get_project_settings,
    set_project_setting,
    list_projects_semantic_status,
    get_default_semantic_enabled,
    set_default_semantic_enabled,
)

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


def _resolve_project_semantic_status(user_id: str, project_name: str, enabled: bool) -> dict:
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
        status = service.get_status(check_freshness=enabled)
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


def _trigger_project_semantic_refresh(user_id: str, project_name: str) -> dict:
    index_status = _resolve_project_semantic_status(user_id, project_name, True)
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


# ==================== 请求模型 ====================

class ProjectNameRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    project_name: Annotated[str, Field(alias="projectName")]


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

        # 检查嵌入模型是否就绪
        embedding_ready = False
        embedding_model_name = ""
        try:
            from llm.agen_matchbox import matchbox
            emb = matchbox().get_user_embedding(user_id)
            embedding_ready = True
            embedding_model_name = emb.model
        except Exception:
            pass

        index_status = _resolve_project_semantic_status(user_id, projectName, enabled)

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

        # 检查嵌入模型就绪状态（用户级，所有项目共享）
        embedding_ready = False
        embedding_model_name = ""
        try:
            from llm.agen_matchbox import matchbox
            emb = matchbox().get_user_embedding(user_id)
            embedding_ready = True
            embedding_model_name = emb.model
        except Exception:
            pass

        project_items: list[dict] = []
        for item in projects:
            project_name = str(item.get("project_name", "") or item.get("projectName", "") or "")
            enabled = bool(item.get("enabled", False))
            index_status = _resolve_project_semantic_status(user_id, project_name, enabled)
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
        emb = mb.get_user_embedding(user_id)
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
                        result = test_platform_embedding(plat.base_url, api_key, model_name)
                        dims = result.get("dims", 0)
                        if dims == 0:
                            raise ValueError("嵌入模型返回了零维度向量，请检查模型配置")
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
    index_status = _trigger_project_semantic_refresh(user_id, project_name)

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

    index_status = _trigger_project_semantic_refresh(user_id, project_name)
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
    index_status = _resolve_project_semantic_status(user_id, project_name, False)

    return {
        "success": True,
        "projectName": project_name,
        "enabled": False,
        "settings": settings,
        "index_exists": index_status["index_exists"],
        "needs_rebuild": index_status["needs_rebuild"],
        "build_state": index_status["build_state"],
    }


@semantic_search_router.post('/test-embedding')
async def test_semantic_embedding(user: dict = Depends(get_current_user)):
    """测试当前用户配置的嵌入模型是否可用。"""
    user_id = str(user['user_id'])

    try:
        from llm.agen_matchbox import matchbox
        mb = matchbox()

        # 获取用户嵌入模型
        emb = mb.get_user_embedding(user_id)
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
                        result = test_platform_embedding(plat.base_url, api_key, model_name)
                        dims = result.get("dims", 0)
                        return {
                            "success": True,
                            "dims": dims,
                            "model_name": model_name,
                            "platform_name": platform_name,
                        }

        # 回退：直接 embed_query
        test_vector = emb.embed_query("测试")
        dims = len(test_vector) if test_vector else 0
        return {
            "success": True,
            "dims": dims,
            "model_name": model_name,
            "platform_name": platform_name,
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


class DefaultEnabledRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    default_enabled: Annotated[bool, Field(alias="defaultEnabled")]


@semantic_search_router.post('/defaults')
async def set_semantic_search_defaults(data: DefaultEnabledRequest, user: dict = Depends(get_current_user)):
    """设置用户级默认：新项目是否默认启用语义搜索。"""
    user_id = str(user['user_id'])
    value = set_default_semantic_enabled(user_id, data.default_enabled)
    return {"success": True, "default_enabled": value}
