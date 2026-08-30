# MCP 接入指南

SparkArc 提供一个统一的 Streamable HTTP MCP 服务。灵感与控制能力在同一个服务中按工具命名空间组织，并共用当前用户的 MCP API Key。

| 服务 | 地址 | 用途 |
| :--- | :--- | :--- |
| SparkArc 统一 MCP 服务 | `/api/mcp/` | 捕获灵感、查询项目、提交 Director 工单、读取进度与结果 |
| 控制兼容入口 | `/api/mcp/control/` | 为已有客户端保留的控制工具入口，新配置不必使用 |

## 获取配置

登录 SparkArc 后，在桌面端仪表盘或移动端 AI 管理页面打开「MCP 连接服务」。连接卡片会生成统一服务的可复制 JSON 配置，并在文本配置中保留旧控制入口地址。重置 API Key 后，旧 Key 会立即失效。

远程 MCP 客户端应使用实际可访问的 SparkArc 后端地址，而不是前端开发服务器地址。例如：

- 本机裸机部署：`http://localhost:6688`
- Docker 部署：`http://localhost:7788`
- 远程部署：`https://你的域名`

## 客户端配置

将示例中的域名和 Key 替换为实际值：

```json
{
  "mcpServers": {
    "spark-arc": {
      "type": "http",
      "url": "https://你的域名/api/mcp/",
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

统一服务提供 23 个工具。灵感工具保留原名：

- `capture_spark`：捕获并扩展灵感。
- `list_sparks`：查询灵感列表。

控制工具统一使用 `control_` 前缀，避免不同业务域的工具重名：

- 工单与控制：`control_submit_director_task`、`control_get_task_status`、`control_list_tasks`、`control_read_task_events`、`control_read_task_result`、`control_cancel_task`、`control_get_all_work_status`。
- 项目概览：`control_list_projects`、`control_get_project_overview`。
- 只读查询：`control_list_chapters`、`control_read_chapter_scene`、`control_read_chapter_outline_raw`、`control_read_worldview`、`control_read_character`、`control_read_synopsis`、`control_read_beat_sheet`、`control_search_project`、`control_semantic_search`、`control_list_inspirations`、`control_read_inspiration`、`control_check_scriptwriter_status`。

已有客户端如果仍连接 `/api/mcp/control/`，可以继续使用未加前缀的原控制工具名；新客户端应连接统一入口并使用 `control_` 前缀工具名。

写盘操作不直接暴露为控制 MCP 查询工具。需要生成或修改内容时，新客户端应通过 `control_submit_director_task` 交给 Director 按现有 Agent 与工具管线执行；兼容入口仍使用 `submit_director_task`。

## Director 工单流程

1. 调用 `control_list_projects` 确认项目名。
2. 调用 `control_get_project_overview` 获取当前项目状态。
3. 调用 `control_submit_director_task`，保存返回的 `task_id`。
4. 用 `control_get_task_status` 或 `control_read_task_events` 轮询。
5. 完成后调用 `control_read_task_result`，再用只读查询工具验证项目内容。

以上是统一入口的工具名；通过 `/api/mcp/control/` 兼容入口时，去掉工具名中的 `control_` 前缀即可。

工单按用户持久化。服务重启后，已完成任务仍可读取；重启时尚未完成的任务会恢复为 `error/interrupted`，不会被错误标记为仍在运行。

## 安全边界

- 统一服务和控制兼容入口都必须通过用户 MCP API Key 鉴权。
- 工单状态、事件、结果与取消操作只能由创建工单的用户访问。
- `project_name` 只能是项目目录名，不能包含 `/`、`\`、`.`、`..` 或绝对路径。
- `semantic_search` 依赖用户已启用语义检索并配置 Embedding 模型；未启用时会返回明确状态。
- MCP API Key 等同于远程操作凭证。公网部署必须使用 HTTPS，并限制后端端口和反向代理访问策略。
