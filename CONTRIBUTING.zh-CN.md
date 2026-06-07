# SparkArc 贡献指南 (简体中文)

## 1. 目标与定位
本指南是 SparkArc 主项目的强约束贡献指南。由于项目规模庞大且涉及多 Agent 协同体系，所有贡献者（包括人类开发者与 AI 编程助手）在开发或修改代码前，**必须将本指南与 [AGENTS.md](file:///d:/Desktop/sparkarc/AGENTS.md) 结合阅读**。
我们遵循 **“统一收口，不复制实现”** 的根本原则：在开发任何新功能前，应优先寻找系统是否已有可承载该逻辑的 Facade、Pipeline 或大统一基建，严禁自行实现平行管线或重复造轮子。

## 2. 核心架构与双轨链路协议
SparkArc 的流式响应体系分为两条职责边界清晰的链路，禁止在双轨链路间混用事件协议或消费器。

### 2.1 聊天主链路 (Chat NDJSON)
- **用途**：自由对话、Agent 委派调度交互、工具调用可视化。
- **前端收口**：[chatStore.ts](file:///d:/Desktop/sparkarc/client/src/components/stores/chatStore.ts)（`_consumeStream` 统一消费与维护时序 Segments）。
- **后端收口**：[chat.py](file:///d:/Desktop/sparkarc/server/agents/routes/chat.py) 路由 + [communication.py](file:///d:/Desktop/sparkarc/server/agents/communication.py)（`SparkBaseAgent.chat_stream`）。
- **关键事实**：
  - 链路传输格式为 NDJSON（事件包含 `task_snapshot`、`assistant_delta`、`reasoning_delta`、`tool_*`、`task_done` 等）。
  - 聊天状态与历史采用 Event Log 增量 Checkpoint 模式恢复，重连/刷新恢复必须走 `task_snapshot` 与游标回放，**严禁**使用 Progress Queue 回放或破坏性 `get_nowait` 接口。

### 2.2 业务任务主链路 (Business SSE / 语义流)
- **用途**：长耗时业务任务（例如：文风克隆、Muse、设定集生成、大纲编排、剧本创作等独立业务线）。
- **前端收口**：[streamingRuntime.ts](file:///d:/Desktop/sparkarc/client/src/utils/streamingRuntime.ts)（使用 `createStreamingTask` 统一托管生命周期与遮罩）。
- **后端收口**：[streaming_utils.py](file:///d:/Desktop/sparkarc/server/agents/routes/streaming_utils.py)（使用 `iterate_sync_iterable_in_thread` 桥接同步生成器）。
- **关键事实**：
  - 遵循标准语义帧协议，统一附带 `onStart` / `onProgress` / `onDelta` / `onStats` / `onDone` / `onError` / `onCancelled` 等事件帧。
  - 前端不要在组件内自建“取消+统计”状态机，必须统一走 `createStreamingTask`。

## 3. 大统一工具与基础设施基建
为了项目的长期可维护性，避免多处雷同的重复逻辑，SparkArc 提供了以下工具性底层基建。任何涉及类似功能的需求必须**强制复用**以下组件，严禁在业务层或 Agent 内部自行实现：

1. **局部替换与增量修改 (Patch)**：
   - 统一收口于 [common.py](file:///d:/Desktop/sparkarc/server/agents/tools/common.py) 的 `_apply_patch` 函数。无论是剧本复写、大纲修改还是设定更新，定位并替换文本的逻辑必须调用此函数，严禁自写正则或 `replace()`。
2. **智能文本切分 (Token Chunking)**：
   - 统一收口于 [chunking.py](file:///d:/Desktop/sparkarc/server/core/file_ingest/chunking.py) 的 `TokenTextSplitter`。凡是涉及基于 Token 数量切分文本的逻辑必须复用此组件。
3. **语义分块器 (Semantic Chunker)**：
   - 统一收口于 [SemanticChunker](file:///d:/Desktop/sparkarc/server/story/semantic_chunker/) 目录。所有项目文件、知识图谱与向量索引的语义分块需复用此底层。
4. **基建扩展原则**：
   - 后续任何新增的、可能被多处复用的底层基础设施（如向量检索、缓存控制、文件解析等），必须先下沉至公共工具层或核心服务层，严禁各业务线或 Agent 内部重复造轮子。

## 4. 后端扩展与 Agent 三模态契约
新加 Agent 或扩展工具必须遵循严谨的注册与契约流程：

### 4.1 新增 Agent 注册流程
1. **基座复用**：默认应继承 `SparkBaseAgent`（通讯与聊天）与 `SparkAgentExecutor`（执行协议）。
2. **四大注册收口点**：
   - [registry.py](file:///d:/Desktop/sparkarc/server/agents/registry.py)：注册 Agent 元数据。
   - [runtime.py](file:///d:/Desktop/sparkarc/server/agents/routes/runtime.py)：若涉及锁定策略与路由信标，在此配置。
   - [agent_tools.py](file:///d:/Desktop/sparkarc/server/agents/agent_tools.py) & [tools/registry.py](file:///d:/Desktop/sparkarc/server/agents/tools/registry.py)：将新增工具注册并与 Agent 绑定。
   - [director_graph.py](file:///d:/Desktop/sparkarc/server/agents/director_graph.py)：配置是否允许被 Director 委派。

### 4.2 Agent 三模态提示词协议
所有专家 Agent 必须且仅实现三种调用模态，严防模态串味：
- **专有工作模式 (Specialized Work)**：触发自 `agent.execute()`。使用 YAML 的 `system` + `user` 字段。输出格式极度严格，面向机器解析器/直接落盘，禁止任何寒暄。
- **用户交互模式 (Chat Mode)**：触发自普通聊天路由。使用 YAML 的 `chat_system` 字段。面向真人用户，支持自然对话与启发式建议。
- **导演委派模式 (Pipeline Mode)**：触发自导演委派。使用 YAML 的 `pipeline_system` 字段。面向导演 Agent。

#### 提示词架构与唯一真相源约束
1. **Tool Reference 自动注入**：
   - 使用 `_get_tool_prompt_references()` 将格式规范挂到对应落盘工具的 YAML `system` 字段中。`pipeline_system` 应当保持极简（仅声明受众、调用工具和简报），严禁在 `pipeline_system` 中复制代码格式规范。
2. **共享基底 (`base` 字段)**：
   - 共享的人设声明或核心原则应当提取到 YAML 的顶层 `base` 字段中，通过 `{base.xxx}` 在各模态中引用，避免多份维护。
3. **补充规则 (`tool_rules` 字段)**：
   - Agent 专属的工具调用顺序、输出纯度与反注入要求，应当写入 YAML 的 `tool_rules` 字段，由基类自动拼接，严禁在 Python 代码中硬编码。

## 5. 前端扩展与国际化 (I18n)
1. **工具 UI 联动双端一致性**：
   - 工具执行时的 UI 元数据（`ui_scope` / `ui_target` / `ui_refresh_events`）必须由后端 [communication.py](file:///d:/Desktop/sparkarc/server/agents/communication.py) 的 `build_tool_stream_event` 注入，前端由 `chatStore` 统一读取，禁止前端组件内部硬编码工具 UI 刷新事件。
2. **前端映射自检 checklist**：
   - 修改/新增 Agent 时，确认以下前端映射点是否需要更新：
     1. 默认分配：[GlobalChatFloat.vue](file:///d:/Desktop/sparkarc/client/src/components/share/GlobalChatFloat.vue) (`viewAgentMap`)。
     2. 气泡样式：[useAgentRegistry.ts](file:///d:/Desktop/sparkarc/client/src/composables/useAgentRegistry.ts) (`agentIconMap`/`agentColorMap`/`agentNameMap`)。
     3. 蓝图布局：[AgentFlowBlueprint.vue](file:///d:/Desktop/sparkarc/client/src/components/lorebook/AgentFlowBlueprint.vue)。
     4. 模拟数据：`agentRuntimeStore.ts`。
     5. 配置面板：`AiSettingsPanel.vue`。
3. **Vue I18n 强约束**：
   - **禁止硬编码**任何用户可见文本。所有可见文案必须在 `zh-CN` / `en-US` / `ja-JP` 词条文件中同步补齐。

## 6. 数据与迁移红线
1. **禁止手写/修改 Alembic 迁移脚本**：
   - 所有数据库结构变更必须首先修改 [models.py](file:///d:/Desktop/sparkarc/server/core/models.py) 模型定义，再运行自动化生成脚本：
     `python server/gen_migration.py`
     系统会在启动时通过 [auto_migrate.py](file:///d:/Desktop/sparkarc/server/core/auto_migrate.py) 自动执行数据迁移。

## 7. 典型架构反模式清单 (禁令)
在 SparkArc 编码中，以下行为被视为**严重架构违规**：
1. **桥接复制**：在多个路由中复制流式桥接逻辑，不使用 `streaming_utils.py`。
2. **绕过遮罩托管**：在组件内手工控制全局遮罩或直接 emit 全局加载事件，而不走 `createStreamingTask`。
3. **双端逻辑不一致**：在前端组件自建工具状态机或手写刷新映射，绕过后端 `build_tool_stream_event`。
4. **混用流协议**：将 `NDJSON` 桥接到普通 SSE 语义帧，或将 SSE 事件直接塞入 `chatStore`。
5. **绕过落盘出口**：在 Agent 内直接拼接写文件物理路径，绕过 `write_result` 的大统一出口。
6. **幽灵注册**：创建 Agent 或工具后不更新 `registry.py` 及门面。
7. **数据越权**：不走 `gen_migration.py` 而是手动在 DB 执行 DDL。
8. **Git 库污染**：将测试、调试或验证生成的临时文件（如缓存、FAISS 向量库、pickle 序列化产物、中间 JSON）直接写入受 Git 跟踪的测试目录（如 `server/test/`），导致版本库被垃圾产物污染。
9. **循环依赖**：在底层公共服务或工具类中，反向引用路由层（`server/agents/routes/*`）的私有实现。
10. **危险并发**：长耗时物理任务未配备并发写锁保护，或前端消费重连流时未携带 `clientId`。

## 8. 回归测试与临时文件红线
在涉及聊天流、Agent 协同或工具联动修改时，必须保证以下测试的通过，并严格遵守临时文件落盘红线：

### 8.1 临时文件落盘红线 (非常重要)
- 所有测试运行、本地调试脚本、一次性验证代码生成的中间缓存、索引、图谱及序列化文件，**必须强制写入项目根目录下的 `/.tmp/` 中**。
- 严禁将任何临时输出直接写入 `server/test/` 及其子目录，必须保证 Git 版本库的清洁度。

### 8.2 推荐回归测试命令
- **后端测试**：
  ```bash
  cd server
  pytest test/test_chat_stream_events.py test/test_chat_history_segments.py test/test_tool_event_ui_metadata.py test/test_director_graph.py test/test_director_handoff_protocol.py test/test_director_skip_confirmation.py test/test_stream_semantics_runtime.py
  ```
- **前端测试**：
  ```bash
  cd client
  npm run test -- src/components/stores/__tests__/chatStore.spec.ts src/utils/__tests__/streamingRuntime.spec.ts
  ```

## 9. AI 权限与安全红线
1. 未经用户明确的**简体中文**语言命令要求，AI 编程助手仅允许使用【只读型】Git 命令，严禁执行 `git commit`、`git push` 等写入行为。
2. 即使项目开启了自动批准流，AI 助手也必须将安全防范放在首位，绝不将自动批准视为用户授权，严禁通过 GitHub CLI 等工具操作远程代码仓。
