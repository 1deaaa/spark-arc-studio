from __future__ import annotations

from typing import Literal

from langchain.tools import tool
from pydantic import BaseModel, Field

from .common import ToolExecutionContext


class GraphRagToolInput(BaseModel):
    """GraphRAG 工具入参。

    注意：构建（build）/重建（reset）已经收归到用户侧 UI，AI 端只保留
    只读能力（status / query），避免 AI 在聊天链路中私自触发昂贵的图谱构建。
    """

    action: Literal["query", "status"] = Field(
        description="操作类型：status=查看当前索引是否就绪/过期；query=按问题检索图谱。构建与重建已交给用户在设置中手动触发。"
    )
    question: str | None = Field(default=None, description="当 action=query 时必填。要询问的自然语言问题。")
    query_mode: Literal["local", "global", "drift"] = Field(default="drift", description="检索模式：local=实体邻域，global=全局摘要，drift=local+global 混合")
    max_hops: int = Field(default=2, ge=1, le=4, description="仅 query 时生效。local/drift 模式下的图遍历跳数。")
    max_edges: int = Field(default=56, ge=12, le=120, description="仅 query 时生效。返回的最大关系条数。")
    response_mode: Literal["answer", "writing_guardrails"] = Field(default="answer", description="query 输出模式。answer=普通问答；writing_guardrails=返回写作约束清单")


def _format_status_lines(status: dict) -> str:
    """把后端状态结构化打印成给 LLM 看的纯文本。"""
    build_state = status.get("build_state") or {}
    progress = build_state.get("progress") or {}
    meta = status.get("metadata") or {}

    return (
        "GraphRAG 状态\n"
        f"- 项目知识图谱状态: {build_state.get('status', 'unknown')}（阶段: {build_state.get('stage', '-')}）\n"
        f"- 索引文件已就绪: {status.get('graph_ready')}\n"
        f"- 需要刷新: {status.get('needs_rebuild')}\n"
        f"- 节点数: {meta.get('nodes', 0)}\n"
        f"- 关系数: {meta.get('edges', 0)}\n"
        f"- 切块数: {meta.get('chunks', 0)}\n"
        f"- 三元组数: {meta.get('triplets', 0)}\n"
        f"- 上次构建时间: {meta.get('built_at', '-')}\n"
        f"- 当前进度: {progress.get('done_chunks', 0)}/{progress.get('total_chunks', 0)} 块"
    )


def _guard_not_ready_message(status: dict) -> str:
    """生成 AI 友好的“未就绪”提示，引导用户去设置中刷新，而不是自己触发构建。"""
    build_state = status.get("build_state") or {}
    state_status = str(build_state.get("status") or "").lower()
    if state_status in {"building", "queued"}:
        progress = build_state.get("progress") or {}
        return (
            "GraphRAG 当前正在后台构建（"
            f"{progress.get('done_chunks', 0)}/{progress.get('total_chunks', 0)} 块）。"
            "请稍等再发起查询。"
        )
    if status.get("needs_rebuild"):
        return (
            "GraphRAG 知识图谱已过期（项目源文件相对于上次构建有变化）。"
            "请提示用户到「设置 → 项目检索索引」中点击对应项目的「刷新」按钮重建图谱，"
            "本次查询暂不会执行。"
        )
    return (
        "GraphRAG 知识图谱尚未为当前项目构建。"
        "请提示用户到「设置 → 项目检索索引」中开启对应项目的「知识图谱」开关，"
        "构建完成后再发起查询。"
    )


@tool(args_schema=GraphRagToolInput)
def graph_rag_tool(
    action: Literal["query", "status"],
    question: str | None = None,
    query_mode: Literal["local", "global", "drift"] = "drift",
    max_hops: int = 2,
    max_edges: int = 56,
    response_mode: Literal["answer", "writing_guardrails"] = "answer",
) -> str:
    """对项目知识图谱执行只读查询或状态检查。

    重要：本工具不再支持构建（build）或重置（reset）。构建由用户在
    「设置 → 项目检索索引」中手动触发；AI 只能读取「是否就绪 / 是否过期」
    的状态，并基于已有图谱执行查询。
    """
    from agents.graphrag import GraphRAGService

    user_id, project_name = ToolExecutionContext.get_context()
    caller_agent_id = ToolExecutionContext.get_agent_id()
    service = GraphRAGService(user_id=user_id, project_name=project_name)

    try:
        if action == "status":
            status = service.get_status(check_freshness=True)
            return _format_status_lines(status)

        # action == "query"
        if not question or not question.strip():
            return "GraphRAG 查询失败：action=query 时 question 不能为空。"

        # 查询前做就绪检查，不就绪/过期直接返回友好提示，绝不私自构建
        status = service.get_status(check_freshness=True)
        if not status.get("graph_ready") or status.get("needs_rebuild"):
            return _guard_not_ready_message(status)
        build_state = status.get("build_state") or {}
        if str(build_state.get("status") or "").lower() in {"queued", "building"}:
            return _guard_not_ready_message(status)

        payload = service.query(
            question=question,
            query_agent_name=caller_agent_id,
            query_mode=query_mode,
            max_hops=max_hops,
            max_edges=max_edges,
        )
        matched = payload.get("matched_entities") or []
        entities_line = ", ".join(matched) if matched else "(无)"

        if response_mode == "writing_guardrails":
            constraints = payload.get("fact_constraints") or {}
            must_keep = constraints.get("must_keep") or []
            avoid_conflicts = constraints.get("avoid_conflicts") or []
            unresolved = constraints.get("unresolved") or []

            lines = [
                "GraphRAG 写作约束",
                f"- mode: {payload.get('mode')}",
                f"- matched_entities: {entities_line}",
                "",
                "[必须保持事实]",
            ]
            if must_keep:
                lines.extend([f"- {item}" for item in must_keep])
            else:
                lines.append("- (暂无)")

            lines.append("\n[避免冲突]")
            if avoid_conflicts:
                lines.extend([f"- {item}" for item in avoid_conflicts])
            else:
                lines.append("- (暂无)")

            lines.append("\n[待补充信息]")
            if unresolved:
                lines.extend([f"- {item}" for item in unresolved])
            else:
                lines.append("- (暂无)")

            return "\n".join(lines)

        return (
            "GraphRAG 查询结果\n"
            f"- mode: {payload.get('mode')}\n"
            f"- matched_entities: {entities_line}\n\n"
            f"{payload.get('answer') or '未生成回答。'}"
        )
    except Exception as e:
        return f"GraphRAG 工具执行失败：{e}"
