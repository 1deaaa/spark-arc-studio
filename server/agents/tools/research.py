from __future__ import annotations

from typing import Literal

from langchain.tools import tool
from pydantic import BaseModel, Field

from .common import ToolExecutionContext


class GraphRagToolInput(BaseModel):
    action: Literal["build", "query", "status", "reset"] = Field(description="操作类型：build=构建索引，query=问答检索，status=查看状态，reset=清空索引")
    question: str | None = Field(default=None, description="当 action=query 时必填。要询问的自然语言问题。")
    query_mode: Literal["local", "global", "drift"] = Field(default="drift", description="检索模式：local=实体邻域，global=全局摘要，drift=local+global 混合")
    force_rebuild: bool = Field(default=False, description="仅 build 时生效。true 表示强制重建。")
    max_hops: int = Field(default=2, ge=1, le=4, description="仅 query 时生效。local/drift 模式下的图遍历跳数。")
    max_edges: int = Field(default=56, ge=12, le=120, description="仅 query 时生效。返回的最大关系条数。")
    response_mode: Literal["answer", "writing_guardrails"] = Field(default="answer", description="query 输出模式。answer=普通问答；writing_guardrails=返回写作约束清单")


@tool(args_schema=GraphRagToolInput)
def graph_rag_tool(
    action: Literal["build", "query", "status", "reset"],
    question: str | None = None,
    query_mode: Literal["local", "global", "drift"] = "drift",
    force_rebuild: bool = False,
    max_hops: int = 2,
    max_edges: int = 56,
    response_mode: Literal["answer", "writing_guardrails"] = "answer",
) -> str:
    """执行 GraphRAG 构建、查询、状态检查或重置。"""
    from agents.graphrag import GraphRAGService

    user_id, project_name = ToolExecutionContext.get_context()
    caller_agent_id = ToolExecutionContext.get_agent_id()
    service = GraphRAGService(user_id=user_id, project_name=project_name)

    try:
        if action == "status":
            status = service.get_status()
            meta = status.get("metadata") or {}
            return (
                "GraphRAG 状态\n"
                f"- graph_ready: {status.get('graph_ready')}\n"
                f"- metadata_ready: {status.get('metadata_ready')}\n"
                f"- artifacts_dir: {status.get('artifacts_dir')}\n"
                f"- build_usage_key: {status.get('build_usage_key')}\n"
                f"- query_agent_policy: {status.get('query_agent_policy')}\n"
                f"- nodes: {meta.get('nodes', 0)}\n"
                f"- edges: {meta.get('edges', 0)}\n"
                f"- chunks: {meta.get('chunks', 0)}\n"
                f"- triplets: {meta.get('triplets', 0)}\n"
                f"- built_at: {meta.get('built_at', '-')}"
            )

        if action == "build":
            info = service.build_index(force_rebuild=force_rebuild)
            return (
                "GraphRAG 构建完成\n"
                f"- reused: {info.get('reused')}\n"
                f"- nodes: {info.get('nodes', 0)}\n"
                f"- edges: {info.get('edges', 0)}\n"
                f"- chunks: {info.get('chunks', 0)}\n"
                f"- triplets: {info.get('triplets', 0)}\n"
                f"- build_usage_key: {info.get('build_usage_key', '-')}\n"
                f"- query_agent_policy: {info.get('query_agent_policy', '-')}\n"
                f"- built_at: {info.get('built_at', '-')}"
            )

        if action == "reset":
            result = service.reset()
            return (
                "GraphRAG 已清理\n"
                f"- removed: {result.get('removed')}\n"
                f"- artifacts_dir: {result.get('artifacts_dir')}"
            )

        if not question or not question.strip():
            return "GraphRAG 查询失败：action=query 时 question 不能为空。"

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
