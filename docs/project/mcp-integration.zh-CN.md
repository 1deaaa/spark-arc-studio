# MCP 接入指南

SparkArc 提供两套相互隔离的 Streamable HTTP MCP 服务，二者共用当前用户的 MCP API Key。

| 服务 | 地址 | 用途 |
| :--- | :--- | :--- |
| 灵感服务 | `/api/mcp/` | 捕获灵感、查询灵感列表 |
| 控制服务 | `/api/mcp/control/` | 查询项目、提交 Director 工单、读取进度与结果 |

## 获取配置

登录 SparkArc 后，在桌面端仪表盘或移动端 AI 管理页面打开「MCP 连接服务」。连接卡片会显示两个端点，并生成可复制的 JSON 配置。重置 API Key 后，旧 Key 会立即失效。

远程 MCP 客户端应使用实际可访问的 SparkArc 后端地址，而不是前端开发服务器地址。例如：

- 本机裸机部署：`http://localhost:6688`
- Docker 部署：`http://localhost:7788`
- 远程部署：`https://你的域名`

## 客户端配置

将示例中的域名和 Key 替换为实际值：

```json
{
  "mcpServers": {
    "spark-inspiration": {
      "type": "http",
      "url": "https://你的域名/api/mcp/",
      "headers": {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "Authorization": "YOUR_MCP_API_KEY"
      }
    },
    "spark-control": {
      "type": "http",
      "url": "https://你的域名/api/mcp/control/",
      "headers": {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "Authorization": "YOUR_MCP_API_KEY"
      }
    }
  }
}
```

`Authorization` 直接填写 MCP API Key，不添加 `Bearer` 前缀。建议保留地址末尾的 `/`，避免依赖客户端的重定向兼容性。

## 工具范围

灵感服务提供 2 个工具：

- `capture_spark`：捕获并扩展灵感。
- `list_sparks`：查询灵感列表。

控制服务提供 21 个工具：

- 工单与控制：`submit_director_task`、`get_task_status`、`list_tasks`、`read_task_events`、`read_task_result`、`cancel_task`、`get_all_work_status`。
- 项目概览：`list_projects`、`get_project_overview`。
- 只读查询：`list_chapters`、`read_chapter_scene`、`read_chapter_outline_raw`、`read_worldview`、`read_character`、`read_synopsis`、`read_beat_sheet`、`search_project`、`semantic_search`、`list_inspirations`、`read_inspiration`、`check_scriptwriter_status`。

写盘操作不直接暴露为控制 MCP 查询工具。需要生成或修改内容时，应通过 `submit_director_task` 交给 Director 按现有 Agent 与工具管线执行。

## Director 工单流程

1. 调用 `list_projects` 确认项目名。
2. 调用 `get_project_overview` 获取当前项目状态。
3. 调用 `submit_director_task`，保存返回的 `task_id`。
4. 用 `get_task_status` 或 `read_task_events` 轮询。
5. 完成后调用 `read_task_result`，再用只读查询工具验证项目内容。

工单按用户持久化。服务重启后，已完成任务仍可读取；重启时尚未完成的任务会恢复为 `error/interrupted`，不会被错误标记为仍在运行。

## 安全边界

- 两套服务都必须通过用户 MCP API Key 鉴权。
- 工单状态、事件、结果与取消操作只能由创建工单的用户访问。
- `project_name` 只能是项目目录名，不能包含 `/`、`\`、`.`、`..` 或绝对路径。
- `semantic_search` 依赖用户已启用语义检索并配置 Embedding 模型；未启用时会返回明确状态。
- MCP API Key 等同于远程操作凭证。公网部署必须使用 HTTPS，并限制后端端口和反向代理访问策略。

