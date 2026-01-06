
import asyncio
from mcp.server.fastmcp import FastMCP
from starlette.testclient import TestClient

mcp = FastMCP("test")
app = mcp.sse_app()

client = TestClient(app)
with client.stream("GET", "/sse") as response:
    for line in response.iter_lines():
        if line:
            print(line)
        if "event: endpoint" in line:
            data = next(response.iter_lines())
            print(data)
            break
