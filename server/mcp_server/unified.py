"""SparkArc 统一 MCP 服务。

统一入口保留灵感工具原名，并为控制工具增加 ``control_`` 前缀，
避免不同业务域未来出现同名工具时互相覆盖。
"""

from fastmcp import FastMCP

from mcp_server.spark_control.server import mcp as control_mcp
from mcp_server.spark_inspiration.server import mcp as inspiration_mcp


mcp = FastMCP(
    "SparkArc",
    instructions="""SparkArc 统一 MCP 服务。

灵感工具：capture_spark、list_sparks。
控制工具：统一入口下使用 control_ 前缀，例如 control_list_projects、
control_submit_director_task、control_read_task_result。

控制工具中的写入操作仍必须通过 Director 工单进入既有 Agent 工具管线。
""",
)

# 灵感工具保留原名，兼容原先连接 /api/mcp/ 的客户端。
mcp.mount(inspiration_mcp)
# 控制域显式命名空间，统一端点中不会与其他业务域发生名称冲突。
mcp.mount(control_mcp, namespace="control")


__all__ = ["mcp"]
