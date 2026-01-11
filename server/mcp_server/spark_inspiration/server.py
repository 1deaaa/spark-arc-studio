"""
Spark Inspiration MCP Server

使用 fastmcp 框架实现的 MCP 服务器，用于捕获和保存灵感。
保存的灵感会自动触发 SparkArc 的灵感工坊 Agent 进行扩展生成。
"""

from fastmcp import FastMCP
from typing import List, Optional, Dict
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
mcp = FastMCP(
    "Spark Inspiration",
    instructions="""用于捕获聊天中的灵感火花，将有价值的想法保存到 SparkArc 灵感工坊。

【重要工作流程】
在调用 capture_spark 工具之前，你必须：
1. 先向用户总结你捕捉到的灵感内容
2. 询问用户是否满意这个灵感种子
3. 只有在用户确认后，才调用此工具

原因：此工具会直接将灵感保存并触发 SparkArc 的灵感 Agent 进行扩展生成，
因此需要确保用户对灵感内容满意后再执行。

【标签维度说明】
tags 参数包含四个维度（均可为空）：
- styles: 风格标签，如 ["治愈", "悬疑", "恐怖"]
- genres: 题材标签，如 ["校园", "都市", "冒险"]
- tones: 基调标签，如 ["现实主义", "梦核", "黑色幽默"]
- worldviews: 世界观标签，如 ["架空", "规则怪谈", "赛博朋克"]
"""
)


@mcp.tool()
def capture_spark(
    source: str,
    tags: Optional[Dict[str, List[str]]] = None
) -> str:
    """
    捕获对话中的灵感火花。
    
    【调用前必读】
    在调用此工具之前，请先向用户总结你要保存的灵感内容，
    并获得用户确认后再调用。此工具会触发灵感 Agent 自动扩展。
    
    Args:
        source: 灵感原始文本/种子内容。这是用户希望记录的核心想法。
        tags: 四维分类标签（可选），格式为:
            {
                "styles": ["治愈", "悬疑"],      # 风格
                "genres": ["校园"],              # 题材
                "tones": ["现实主义"],           # 基调
                "worldviews": ["架空"]           # 世界观
            }
        
    Returns:
        成功或失败的消息
    """
    result = save_inspiration(
        source=source,
        content="",  # content 由灵感 Agent 后续生成
        tags=tags
    )
    
    if result["success"]:
        return f"✅ 灵感已捕获并提交到灵感工坊 (ID: {result['id']})"
    else:
        return f"❌ 捕获失败: {result.get('error')}"


# 导出验证函数供 app.py 使用
__all__ = ["mcp", "verify_api_key", "current_user_id"]
