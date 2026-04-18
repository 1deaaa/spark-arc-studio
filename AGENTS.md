# SparkArc AGENTS 指南（给 AI 助手与贡献者）

## 1. 文档目标

本文件是 SparkArc 项目内“新增 Agent / 新增流程 / 修改流式链路”的强约束指南。

目标只有一个：

- 任何改动都要优先接入现有统一管线，避免同一能力在多处重复实现。
- 任何新增能力都要做到“改一处，全链路受益”。
- 任何短平快修补都不能以破坏长期可维护性为代价。

## 2. 架构北极星：统一收口，不复制实现

SparkArc 现有架构已经有清晰收口层。新增功能必须先判断是否能接入现有收口点，而不是新开平行管线。

 后端收口重点：

 - 通讯层底座：server/agents/communication.py
 - 执行协议层：server/agents/agent_utils.py
 - 工具门面层：server/agents/agent_tools.py（统一门面） + server/agents/tools/*（内部实现）
 - 公共工厂 / 服务层：server/agents/agent_factory.py + server/agents/project_content.py + server/agents/auto_write_service.py
 - 多 Agent 调度层：server/agents/director_graph.py
 - 流式桥接层：server/agents/routes/streaming_utils.py
 - 业务语义层：server/agents/routes/stream_semantics.py + server/agents/routes/execution_core.py
 - 路由聚合层：server/agents/routes/__init__.py

前端收口重点：

- 流式任务入口：client/src/utils/streamingRuntime.ts（createStreamingTask）
- 全局遮罩统计：client/src/utils/loadingStats.ts
- 事件总线：client/src/eventBus.ts
- 全局加载 UI：client/src/components/share/GlobalLoading.vue
- 聊天流消费收口：client/src/components/stores/chatStore.ts

## 3. 两条主链路（必须分清）

### 3.1 聊天主链路（Chat NDJSON）

用途：自由对话、Director 调度、工具调用可视化。

标准链路：

1. 前端通过 chatStore/chatService 发起聊天流。
2. 后端路由在 server/agents/routes/chat.py。
3. Agent 侧通过 SparkBaseAgent.chat_stream 推送事件。
4. chat.py 输出 NDJSON 事件（assistant_delta、reasoning_delta、tool_* 等）。
5. chatStore._consumeStream 统一消费并维护消息、segments、tool_traces。
6. chat.py 在落盘时写 metadata.segments 和 metadata.tool_traces，保证刷新后时序可恢复。

关键事实：

- 聊天链路是 NDJSON，不是业务语义 onStart/onDelta 协议。
- 工具事件与正文可以交错出现，不能假设固定顺序。

### 3.2 业务任务主链路（SSE/语义流）

用途：长耗时业务任务，例如 production、style、auto_write、structure、lorebook、muse。

标准链路：

1. 前端创建 createStreamingTask(scope, target)。
2. 前端使用 consumeSSEReader/consumeTextReader/consumeNdjsonReader 消费流。
3. 后端路由通过 iterate_sync_iterable_in_thread 桥接同步生成器到异步响应。
4. 业务事件统一附加 onStart/onProgress/onDelta/onStats/onDone/onError/onCancelled。
5. 全局遮罩统一走 global-loading/cancel-loading 事件。

关键事实：

- 业务流由 streamingRuntime 统一托管，不要在页面里重复写一套“读取器 + 取消 + 统计”状态机。
- SSE 心跳、取消、统计逻辑已在主链路中沉淀，优先复用。

## 4. 后端扩展规则

### 4.1 新增 Agent：先复用双基座

新 Agent 默认应复用：

- SparkBaseAgent（通讯与聊天能力）
- SparkAgentExecutor（build_context -> execute -> write_result 执行协议）

参考文件：

- server/agents/setup_agents.py
- server/agents/communication.py
- server/agents/agent_utils.py

强约束：

- 不要把核心业务逻辑散落在路由函数里。
- 不要跳过 build_context 直接在多个入口拼 prompt。

### 4.2 新增 Agent 后必须同步注册

 后端必须更新：

 1. server/agents/registry.py（Agent 元数据）
 2. server/agents/routes/runtime.py（若涉及信标/号角/锁定策略）
 3. server/agents/agent_tools.py（统一门面导出）+ server/agents/tools/registry.py（工具分组 / 绑定真相源）
 4. server/agents/director_graph.py（若需要被 Director 委派）

### 4.3 工具扩展必须走工具门面

 新增工具必须统一经 server/agents/agent_tools.py 门面接入；具体 schema 与实现按域落在 server/agents/tools/*，统一在 server/agents/tools/registry.py 注册，再由 agent_tools.py 对外导出。

 禁止：

 - 在单个 Agent 内部私自定义一套独立工具调用协议。
 - 在路由层直接执行“伪工具逻辑”绕过工具门面。
 - 在 `server/agents/tools/registry.py` 之外再造第二套工具注册表、Agent→工具映射或平行工具管线。
 - 工具层直接反向依赖 `server/agents/routes/*` 私有实现；若需要复用能力，应先下沉到 `agent_factory.py` / `project_content.py` / `auto_write_service.py` 这类公共层。

### 4.4 工具 UI 联动必须双端一致

工具事件中的 UI 提示由后端 communication.py 的 build_tool_stream_event 注入（ui_scope/ui_target/ui_refresh_events），前端 chatStore 读取。

### 4.5 Agent 三模态提示词协议（强制）

SparkArc 的每个专家 Agent 必须实现且仅实现三种调用模态，分别对应 `server/agents/prompts/<agent>.yaml` 的三个顶层字段。三种模态的运行态已由统一管线固定，贡献者只需保证 yaml 字段语义对齐。

| 模态 | 何时触发 | 使用字段 | 受众 | 行为约束 |
| :--- | :--- | :--- | :--- | :--- |
| **专有工作模式（Specialized Work）** | 业务路由 / 面板按钮 → `agent.execute()` / 具名方法（如 `expand_inspiration`、`generate_outline`）| `system` + `user` | 机器解析器 / 直接落盘 | 输出格式严格、可被解析器还原、禁止寒暄 |
| **用户交互模式（Chat Mode）** | 聊天路由 → `SparkBaseAgent.chat_stream(skip_tool_confirmation=False)` | `chat_system` | 真人用户 | 自然对话、可发散建议、不强制输出结构化格式 |
| **导演委派模式（Pipeline Mode）** | 导演 → `delegate_task` → `sub_agent_node` → `chat_stream(skip_tool_confirmation=True)` | `pipeline_system` | 导演（上游 Agent）| 按任务描述一次性产出 + 工具落盘 + 向导演简报，**产出规范与专有工作模式等价** |

运行态逻辑（禁止绕过）：

- 模式选择收口在 `server/agents/communication.py` 的 `chat_stream()` / `chat()` 里：`skip_tool_confirmation=True` 时优先取 `pipeline_system`；为 `False` 时优先取 `chat_system`；两者都缺才回落到 `system`。
- 导演委派时 `normalize_handoff_payload` 会强制把 `user_confirmation_state` 提升为 `not_required`，从而保证子 Agent 一定走 `pipeline_system`。
- 对应测试：`server/test/test_director_skip_confirmation.py`、`server/test/test_director_handoff_protocol.py`。

**`pipeline_system` 写法硬约束（重中之重）**：

1. **受众声明**：第一句必须明确"你的受众是导演，不是用户"，避免 LLM 代入头脑风暴/对话模式。
2. **三件套主干**：正文只写「调工具 + 一步到位 + 向导演简报」三件套，外加必要的反注入/反占位符提示。
3. **格式规范走 tool reference，不要复述**：详见下一节 §4.5.1。结构化产出规范（字段列表、Markup schema、禁止事项、结尾边界）应该通过 `_get_tool_prompt_references` 绑定到对应落盘工具，而**不是**把 `system` 里的规范复制粘贴到 `pipeline_system` 里——那样会双份维护、容易漂移。
4. **严禁无效引用**：禁止使用"与正常生成相同"、"格式同 system"、"参照默认模板"这类表述——两段 system 在代码里是**互斥选择**而非叠加，LLM 看不到另一个字段的内容。
5. **禁止头脑风暴式软约束**：`pipeline_system` 里不要出现"发散思维 / 打破常规 / 热情洋溢"这类与结构化产出冲突的语气修饰。

**`chat_system` 写法约束**：

1. 限定"对话模式下"的人设与语气，不要求任何严格输出格式。
2. 可以保留发散、建议、反问等对话风格。
3. 不要在这里重复结构化格式定义——防止用户只想聊天时反被套死。

**`system` 写法约束**：

1. 这是最严格的模式，所有结构化格式、字段定义、示例都应该放在这里。
2. 要配合 `user` 模板使用，由 `agent.execute()` 或具名方法直接传入。

违反以上任一项都会导致类似"导演委派灵感 Agent 时跑去构建世界观"这种模态串味问题（历史真实 Bug：Muse 未注册 tool reference，导致 pipeline 模式下 LLM 丢失 7 条格式规范）。

### 4.5.1 格式规范的唯一真相源：`_get_tool_prompt_references`

SparkArc 用「工具 reference 自动注入」机制避免在 `system` 与 `pipeline_system` 之间重复书写产出规范。

**运行态机制**：

- `server/agents/communication.py` 的 `_build_tool_prompt_reference_block()` 会在 LLM 被绑定工具时（无论 chat 还是 pipeline 模式），把 Agent 注册的「工具 → yaml 字段」映射展开为「当你决定调用工具 `rewrite_xxx` 时，必须复用以下既有生成规范：...」拼接到 system prompt 末尾。
- 注册点：每个 Agent 子类重写 `_get_tool_prompt_references()` 返回 `{tool_name: [{"prompt_key": ..., "field": "system"}]}`，并可用 `_get_tool_prompt_reference_values()` 为占位符提供默认填充（避免 LLM 看到字面 `{worldview}` 这类占位符）。

**最佳实践分类**：

| Agent 类型 | 示例 | 如何承载产出规范 |
| :--- | :--- | :--- |
| **有落盘工具** | muse / lorebook / showrunner / scriptwriter | ✅ 必须注册 `_get_tool_prompt_references`，把格式规范挂到对应工具的 yaml `system` 字段。`pipeline_system` 保持极简三件套。 |
| **无落盘工具**（产出直接给导演）| critic | ⚠️ 例外情况：tool reference 无处可挂。`pipeline_system` 必须内嵌 JSON schema / 产出字段清单的关键摘要。 |

**现状参考实现**（方便对照）：

- `MuseAgent._get_tool_prompt_references` → `rewrite_inspiration` 指向 yaml 顶层 `system`（7 条灵感规范）
- `WorldviewAgent._get_tool_prompt_references` → `rewrite_worldview` 指向 `rewrite_worldview.system`，`rewrite_all_characters` 指向 `generate_characters.system`
- `ShowrunnerAgent._get_tool_prompt_references` → 三个 rewrite_* 分别指向 `generate_synopsis.system` / `generate_beat_sheet.system` / `generate_outline.system`
- `ScriptwriterAgent._get_tool_prompt_references` → `create_or_rewrite_script` 指向顶层 `system`（含 `.arc` 规范 + `{arc_example}` 占位符）
- `CriticAgent`：**无落盘工具**，故不注册 tool reference；`critic.yaml/pipeline_system` 内嵌了五维审核 + 等级映射 + JSON 必填字段清单。

**贡献者常见错误**：

- ❌ 在 `pipeline_system` 里重复书写 `system` 里已有的格式规范，造成双份维护漂移。
- ❌ Agent 有落盘工具但忘记注册 `_get_tool_prompt_references`，LLM 调工具时看不到规范——这就是 Muse 历史 Bug 的本质。
- ❌ 把 Agent 专属工具的占位符（如 `{worldview}`）忘在 `_get_tool_prompt_reference_values` 里没提供默认填充，LLM 会看到字面 `{worldview}`。

### 4.6 新增 Agent 的三模态自检清单

新增 Agent 时，以下所有项必须同时满足：

 1. `server/agents/prompts/<agent>.yaml` 同时定义 `system`、`chat_system`、`pipeline_system` 三个顶层字段。
 2. 若该 Agent 有落盘工具：必须在 Agent 子类重写 `_get_tool_prompt_references()`，把 yaml `system`（或对应子 prompt `system`）绑定到落盘工具；对应 Agent 的 `pipeline_system` 保持极简三件套（受众 / 调工具 / 简报）。
 3. 若该 Agent 没有落盘工具（产出直接给导演，如 critic）：必须在 `pipeline_system` 里直接内嵌产出规范的关键摘要（字段清单、等级标准等），不得引用式指向 `system`。
 4. 对应 `SparkAgentExecutor` 的 `build_context` / `execute` / `write_result` 协议完整实现。
 5. `server/agents/tools/*` 中，该 Agent 落盘相关工具（如 `rewrite_xxx`）已按域实现，并在 `server/agents/tools/registry.py` 注册；`server/agents/agent_tools.py` 继续作为唯一公共导出与 `get_tools_for_agent` 门面。
 6. 若希望被导演委派，需在 `server/agents/prompts/director.yaml` 的"专家分工"速查表中列入。
 7. 新增测试覆盖三模态分别命中，对齐 `server/test/test_director_skip_confirmation.py` 的做法。

## 5. 前端扩展规则

### 5.1 不要绕过 createStreamingTask

所有需要遮罩、统计、可取消的流式任务必须通过：

- client/src/utils/streamingRuntime.ts

不要直接调用 loadingStats 或直接 emit global-loading 作为主方案。

### 5.2 聊天链路唯一收口是 chatStore

聊天流解析、tool event 桥接、segments/tool_traces 管理统一在：

- client/src/components/stores/chatStore.ts

禁止在组件里直接解析聊天 NDJSON 并自行维护状态。

### 5.3 新增 Agent 的前端映射检查清单

新增 Agent 时，除了后端注册，还需要检查以下前端映射点是否需要更新：

1. 视图默认 Agent 分配：client/src/components/share/GlobalChatFloat.vue（viewAgentMap）
2. 聊天气泡显示名/颜色/图标：client/src/components/share/ChatMessageList.vue
3. Agent 流程蓝图布局与默认连线：client/src/components/lorebook/AgentFlowBlueprint.vue
4. 运行态 mock 数据（如保留）：client/src/components/stores/agentRuntimeStore.ts
5. 页面级快捷模型选择入口（如需要）：client/src/components/lorebook/AiSettingsPanel.vue 与对应视图

说明：并非每次都必须改全部文件，但必须逐项确认。

### 5.4 前端文案与国际化（强制）

前端新增或修改界面时，必须遵守以下约束：

1. **禁止硬编码用户可见文本**（按钮、标题、提示、占位符、错误文案等）。
2. 所有用户可见文本必须通过 Vue I18n 管理（`t(...)` 或等价封装）。
3. 新功能上线前需同步补齐三语词条：`zh-CN` / `en-US` / `ja-JP`。
4. 若历史代码存在硬编码，改动触及该区域时应顺手迁移到 i18n，避免债务继续扩散。

## 6. 协议边界与兼容要求

### 6.1 Chat NDJSON 与业务语义流不可混用

- 聊天侧消费器：chatStore._consumeStream
- 业务侧消费器：streamingRuntime 的 SSE/Text/NDJSON 读取器

不要把 onStart/onDelta 直接塞到 chatStore，也不要把 assistant_delta 套到业务页面语义消费器。

### 6.2 reasoning/think 兼容必须走既有解析器

后端：

- server/llm/agen_matchbox/reasoning_compat.py

前端：

- client/src/utils/streamingRuntime.ts（createThinkStreamParser）

禁止各业务线重复实现一版 think 标签解析器。

## 7. 迁移与数据红线（强制）

数据库结构变更必须遵循：

1. 修改模型定义：server/core/models.py
2. 生成迁移：server/gen_migration.py
3. 启动时自动迁移：server/core/auto_migrate.py + server/app.py 生命周期

严禁：

- 手工创建 Alembic 迁移文件
- 手工修改 Alembic 迁移文件
- 直接在运行数据库上手写 DDL 绕过迁移体系

参考禁令文档：

- server/alembic/DO NOT MANUALLY EDIT MIGRATION FILES!.md

## 8. 新增流程的推荐模板

### 8.1 若是“聊天内能力”

优先做法：

1. 先判断能否作为已有 Agent 的新工具。
2. 在 agent_tools.py 增加工具 schema + 实现。
3. 让 Director 通过 delegate_task 或工具调用触发该能力。
4. 在 communication/chatStore 保持工具事件可视化一致。

### 8.2 若是“独立业务流”

优先做法：

1. 在 server/agents/routes 下新增或复用业务路由模块。
2. 使用 iterate_sync_iterable_in_thread 桥接同步生成器。
3. 统一发送 onXxx 语义帧与 cancelled/error 终态。
4. 前端通过 createStreamingTask + consumeSSEReader 接入。

## 9. 反模式清单（禁止堆屎山）

以下行为默认视为架构违规：

1. 在多个路由复制同一段流式桥接逻辑，不抽到 streaming_utils。
2. 在组件里手写全局遮罩协议，不走 createStreamingTask。
3. 在多个地方重复维护工具到 UI 的映射，且不同步后端 binding。
4. 在聊天与业务流之间混用事件协议，导致消费器耦合。
5. 在 Agent 内直接写文件路径与 IO 细节，绕过 write_result 统一出口。
6. 为赶进度创建“临时入口”而不接入 registry/director_graph/tools 门面。
7. 修改数据模型后不走迁移生成流程。

## 10. 最小回归测试清单

涉及聊天链路、工具事件、多 Agent 委派、流式语义时，至少回归以下测试：

后端：

- server/test/test_chat_stream_events.py
- server/test/test_chat_history_segments.py
- server/test/test_tool_event_ui_metadata.py
- server/test/test_director_graph.py
- server/test/test_director_handoff_protocol.py
- server/test/test_director_skip_confirmation.py
- server/test/test_stream_semantics_runtime.py

前端：

- client/src/components/stores/__tests__/chatStore.spec.ts
- client/src/utils/__tests__/streamingRuntime.spec.ts
- client/src/components/share/__tests__/GlobalLoading.spec.ts
- client/src/components/share/__tests__/ChatMessageList.spec.ts

建议命令（按需裁剪）：

- 后端：cd server && pytest test/test_chat_stream_events.py test/test_chat_history_segments.py test/test_tool_event_ui_metadata.py test/test_director_graph.py test/test_director_handoff_protocol.py test/test_director_skip_confirmation.py test/test_stream_semantics_runtime.py
- 前端：cd client && npm run test -- src/components/stores/__tests__/chatStore.spec.ts src/utils/__tests__/streamingRuntime.spec.ts src/components/share/__tests__/GlobalLoading.spec.ts src/components/share/__tests__/ChatMessageList.spec.ts

## 11. 提交前自检

提交前请逐项确认：

1. 新能力是否接入了既有统一收口层。
2. 是否避免了页面层/路由层重复状态机。
3. 后端与前端的工具 UI 映射是否双端一致。
4. 数据变更是否遵守迁移流程。
5. 是否补齐了对应链路测试。

如果以上任一项答案为“否”，先修正架构再提交。
