"""
Spark Inspiration MCP Server

使用 fastmcp 框架实现的 MCP 服务器，用于捕获和保存灵感。
保存的灵感会自动触发 SparkArc 的灵感工坊 Agent 进行扩展生成。
"""

from fastmcp import FastMCP
from typing import List, Optional, Dict
from .logic import save_inspiration, get_all_inspirations, current_user_id
from core.auth import user_db
from agents.agent_utils import collect_text_output
from agents.setup_agents import MuseAgent


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
1. 调用 capture_spark 前：先总结灵感内容并获得用户确认。
2. capture_spark 会触发生成，生成完成后会返回“原样内容”，你必须完整展示，不得改写或删减。
3. 若用户要查看历史灵感，使用 list_sparks。

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
    请先向用户总结你要保存的灵感内容，并获得用户确认后再调用。
    此工具会触发灵感 Agent 自动扩展，并返回“原样生成内容”，必须完整展示。
    
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
    user_id = current_user_id.get()
    if not user_id:
        return "❌ 捕获失败: Authentication required. User context missing."

    def _as_list(value):
        if isinstance(value, list):
            return [v.strip() for v in value if isinstance(v, str) and v.strip()]
        if isinstance(value, str) and value.strip():
            return [value.strip()]
        return []

    def _first(value):
        values = _as_list(value)
        return values[0] if values else None

    styles = _as_list((tags or {}).get("styles"))
    genres = _as_list((tags or {}).get("genres"))
    tones = _as_list((tags or {}).get("tones"))
    worldviews = _as_list((tags or {}).get("worldviews"))
    length_hint = _first((tags or {}).get("lengthHint") or (tags or {}).get("length_hint"))

    # 生成灵感内容
    try:
        muse = MuseAgent(user_id)
        context = muse.build_context(
            operation="expand_inspiration",
            raw_input=source,
            style=styles[0] if styles else None,
            genres=genres,
            tones=tones,
            worldviews=worldviews,
            length_hint=length_hint,
        )
        generated_content = collect_text_output(muse.execute(context)).strip()
        if not generated_content:
            return "❌ 捕获失败: 灵感生成为空。"
    except Exception as e:
        return f"❌ 捕获失败: 灵感生成失败 - {e}"

    result = muse.write_result(
        generated_content,
        user_id=user_id,
        source=source,
        tags=tags,
        origin="mcp",
    )
    
    if isinstance(result, dict) and result.get("success"):
        return (
            f"✅ 灵感已捕获并提交到灵感工坊 (ID: {result['id']})\n"
            f"【灵感工坊生成内容】\n{generated_content}"
        )
    else:
        return f"❌ 捕获失败: {getattr(result, 'get', lambda *_: None)('error') or result}"


@mcp.tool()
def list_sparks(limit: int = 20, unread_only: bool = False) -> Dict[str, object]:
    """
    获取当前用户的灵感列表（按时间倒序）。

    Args:
        limit: 返回条目数量上限（默认 20）
        unread_only: 是否仅返回未读（仅对 MCP 来源生效）

    Returns:
        含 inspirations 列表的字典
    """
    user_id = current_user_id.get()
    if not user_id:
        return {"success": False, "error": "Authentication required. User context missing."}

    inspirations = get_all_inspirations(str(user_id))
    if unread_only:
        inspirations = [
            i for i in inspirations
            if i.get("origin") == "mcp" and i.get("status") == "unread"
        ]

    return {
        "success": True,
        "inspirations": inspirations[: max(0, int(limit))]
    }


# 导出验证函数供 app.py 使用
__all__ = ["mcp", "verify_api_key", "current_user_id"]
