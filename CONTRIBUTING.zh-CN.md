# SparkArc 贡献指南（简体中文）

## 1. 目标
本指南用于主项目贡献。请与 AGENTS.md 一并阅读，优先遵守统一收口与可维护性原则。

## 2. 架构红线
- 聊天链路：前端统一走 chatStore，后端统一走 server/agents/routes/chat.py + SparkBaseAgent.chat_stream。
- 业务流链路：前端统一走 createStreamingTask，后端统一走 stream_semantics + iterate_sync_iterable_in_thread。
- 工具扩展：统一经 server/agents/agent_tools.py 门面接入；内部实现按域放在 server/agents/tools/*，并统一在 server/agents/tools/registry.py 注册。不要在路由、单 Agent 或其他模块再造平行工具协议 / 第二套注册表。
- 数据库变更：只能改模型并通过 server/gen_migration.py 生成迁移，禁止手写迁移。

## 3. 前端贡献规范（强制）
- 禁止硬编码任何用户可见文本。
- 所有用户可见文案必须使用 Vue I18n。
- 新功能必须同步补齐三语：zh-CN / en-US / ja-JP。
- 修改聊天或流式逻辑时，必须复用既有收口：
  - client/src/components/stores/chatStore.ts
  - client/src/utils/streamingRuntime.ts

## 4. Agent 与提示词规范
- Agent 提示词优先通过统一入口维护：server/agents/agent_utils.py（load_prompt）与 SparkBaseAgent 系统提示拼装。
- 语言规则：Agent 默认优先使用当前设置语言；当用户主动使用其他语言或明确要求切换时，才切换到用户指定语言。
- 不要在多个 Agent 内复制同一段提示词约束，优先做统一注入。

### 4.1 Agent 三模态提示词协议（强制，详见 AGENTS.md §4.5）
每个专家 Agent 的 `server/agents/prompts/<agent>.yaml` 必须同时定义三个顶层字段，分别对应三种调用模态：

| 模态 | 触发路径 | 使用字段 | 受众 |
| :--- | :--- | :--- | :--- |
| 专有工作（Specialized Work） | 业务路由 / 面板按钮 → `agent.execute()` / 具名方法 | `system` + `user` | 机器解析器 |
| 用户交互（Chat Mode） | `chat_stream(skip_tool_confirmation=False)` | `chat_system` | 真人用户 |
| 导演委派（Pipeline Mode） | 导演 `delegate_task` → `sub_agent_node` → `chat_stream(skip_tool_confirmation=True)` | `pipeline_system` | 导演（上游 Agent） |

`pipeline_system` 写法硬约束：
- **受众声明**：第一句必须明确"你的受众是导演，不是用户"。
- **三件套主干**：正文只写「调工具 + 一步到位 + 向导演简报」三件套。
- **格式规范走 tool reference，不要复述**：结构化产出规范应通过 `_get_tool_prompt_references()` 绑定到对应落盘工具的 yaml `system` 字段，而不是在 `pipeline_system` 里复制粘贴——那样会双份维护、容易漂移。详见 AGENTS.md §4.5.1。
- **严禁无效引用**：禁止使用"与正常生成相同 / 格式同 system"这类表述——两段 system 在代码里是互斥选择而非叠加，LLM 看不到另一个字段的内容。
- **禁止头脑风暴式软约束**：不要在 `pipeline_system` 里出现"发散思维 / 打破常规 / 热情洋溢"等与结构化产出冲突的语气修饰。
- **例外：无落盘工具的 Agent**（如 critic，产出直接给导演）：`pipeline_system` 必须内嵌产出规范的关键摘要（字段清单、等级标准等），不得引用式指向 `system`。

`chat_system` 只写"对话模式下"的人设与语气，不要求严格输出格式；`system` 承载最严格的结构化规范。违反以上任一项都会导致导演委派时 Agent 模态串味（例如灵感 Agent 跑去构建世界观——历史真实 Bug：Muse 未注册 tool reference，导致 pipeline 模式下 LLM 丢失 7 条格式规范）。

## 5. 测试与验证
涉及聊天链路、多 Agent、工具可视化、语义流时，至少回归：
- server/test/test_chat_stream_events.py
- server/test/test_chat_history_segments.py
- server/test/test_tool_event_ui_metadata.py
- server/test/test_director_graph.py
- server/test/test_stream_semantics_runtime.py
- client/src/components/stores/__tests__/chatStore.spec.ts
- client/src/utils/__tests__/streamingRuntime.spec.ts

## 6. 提交清单
- 是否接入既有统一管线，而非平行实现。
- 是否引入了硬编码文案（若有，必须改为 i18n）。
- 是否补齐三语词条。
- 是否完成必要测试与手动回归。

## 7. 贡献版权与许可
- 除非另有书面约定，贡献者保留其原创贡献在法律上的相应权利。
- 向本仓库提交 Pull Request、补丁、文档、设计稿、脚本或其他贡献，即表示贡献者确认其有权提交该内容，并同意该贡献按本仓库当前适用的开源许可进行发布、合并与再分发。
- 贡献者不应提交未经授权的第三方代码、素材、文档或其他受限制内容。
- 如贡献涉及受雇开发、委托开发、合作开发或第三方授权材料，请在提交前自行确认权利链条完整。
