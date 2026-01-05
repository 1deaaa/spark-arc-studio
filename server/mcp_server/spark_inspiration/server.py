
from mcp.server.fastmcp import FastMCP
from typing import List
from .logic import save_inspiration

# Create the MCP Server instance
mcp = FastMCP("Spark Inspiration")

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
    Capture a spark of inspiration from a conversation.
    
    Args:
        summary: A concise title or summary of the inspiration.
        content: The refined content/idea.
        original_slice: The raw conversation snippet that triggered this.
        thought_process: The reasoning context (Why is this interesting?).
        tags: Classification tags (e.g., ["character", "plot", "scifi"]).
        source: The source platform (e.g., "Cursor", "Claude").
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
        return f"Successfully captured inspiration: {summary} (ID: {result['id']})"
    else:
        return f"Failed to capture inspiration: {result.get('error')}"

# Note: We don't run mcp.run() here because we will mount it in the main FastAPI app.
