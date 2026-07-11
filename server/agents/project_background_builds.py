from __future__ import annotations

import gc


def cancel_project_vector_index_build(
    user_id: str,
    project_name: str,
    *,
    wait_timeout: float = 4.0,
) -> list[str]:
    """请求取消项目语义索引后台构建。"""
    warnings: list[str] = []
    try:
        from agents.vector_index import VectorIndexService

        VectorIndexService(user_id, project_name).cancel_background_build(wait_timeout=wait_timeout)
        VectorIndexService.release_process_resources()
    except Exception as exc:
        warnings.append(f"取消向量索引构建失败: {exc}")
    return warnings


def cancel_project_graphrag_build(
    user_id: str,
    project_name: str,
    *,
    wait_timeout: float = 2.0,
) -> list[str]:
    """请求取消项目知识图谱后台构建。"""
    warnings: list[str] = []
    try:
        from agents.graphrag import GraphRAGService

        GraphRAGService(user_id=user_id, project_name=project_name).cancel_background_build(wait_timeout=wait_timeout)
    except Exception as exc:
        warnings.append(f"取消知识图谱构建失败: {exc}")
    return warnings


def cancel_project_auto_write(
    user_id: str,
    project_name: str,
    *,
    wait_timeout: float = 4.0,
) -> list[str]:
    """请求取消项目自动写作后台任务。"""
    warnings: list[str] = []
    try:
        from agents.auto_write_service import cancel_auto_write_background

        if not cancel_auto_write_background(user_id, project_name, wait_timeout=wait_timeout):
            warnings.append("自动写作任务未在等待时间内停止")
    except Exception as exc:
        warnings.append(f"取消自动写作任务失败: {exc}")
    return warnings


def cancel_project_background_builds(
    user_id: str,
    project_name: str,
    *,
    vector_wait_timeout: float = 4.0,
    graph_wait_timeout: float = 2.0,
    auto_write_wait_timeout: float = 4.0,
) -> list[str]:
    """统一取消项目级后台任务，供关闭开关和项目生命周期复用。"""
    warnings: list[str] = []
    warnings.extend(
        cancel_project_vector_index_build(
            user_id,
            project_name,
            wait_timeout=vector_wait_timeout,
        )
    )
    warnings.extend(
        cancel_project_graphrag_build(
            user_id,
            project_name,
            wait_timeout=graph_wait_timeout,
        )
    )
    warnings.extend(
        cancel_project_auto_write(
            user_id,
            project_name,
            wait_timeout=auto_write_wait_timeout,
        )
    )
    gc.collect()
    return warnings
