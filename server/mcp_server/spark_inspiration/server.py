"""
Spark Inspiration MCP Server

使用 fastmcp 框架实现的 MCP 服务器，用于捕获和保存灵感。
"""

from fastmcp import FastMCP
from typing import List
from .logic import save_inspiration, current_user_id
from core.auth import user_db


# 自定义鉴权验证函数
async def verify_api_key(token: str) -> dict | None:
    """
    验证 API Key 并返回用户信息。
    
    Args:
        token: 客户端传来的 API Key
        
    Returns:
        包含 user_id 的字典（验证成功）或 None（验证失败）
    """
    user_id = user_db.verify_mcp_key(token)
    if user_id:
        return {"user_id": str(user_id)}
    return None


# 创建 MCP Server 实例
# fastmcp 框架提供更好的 FastAPI 集成和内置鉴权支持
mcp = FastMCP(
    "Spark Inspiration",
    instructions="用于捕获聊天中的灵感火花，将有价值的想法保存到 SparkArc。"
)


@mcp.tool()
def capture_spark(
    summary: str,
    content: str,
    original_slice: str,
    thought_process: str,
    tags: List[str],
    source: str = "Unknown"
) -> str:
    """
    捕获对话中的灵感火花。
    
    Args:
        summary: 灵感的简洁标题或摘要
        content: 精炼后的内容/想法
        original_slice: 触发灵感的原始对话片段
        thought_process: 思考过程（为什么这个有趣？）
        tags: 分类标签（如 ["角色", "剧情", "科幻"]）
        source: 来源平台（如 "Cursor", "Claude"）
        
    Returns:
        成功或失败的消息
    """
    result = save_inspiration(
        summary=summary,
        content=content,
        original_slice=original_slice,
        thought_process=thought_process,
        tags=tags,
        source=source
    )
    
    if result["success"]:
        return f"✅ 灵感已捕获: {summary} (ID: {result['id']})"
    else:
        return f"❌ 捕获失败: {result.get('error')}"


# 导出验证函数供 app.py 使用
__all__ = ["mcp", "verify_api_key", "current_user_id"]
