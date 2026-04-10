# SparkArc 贡献指南（简体中文）

## 1. 目标
本指南用于主项目贡献。请与 AGENTS.md 一并阅读，优先遵守统一收口与可维护性原则。

## 2. 架构红线
- 聊天链路：前端统一走 chatStore，后端统一走 server/agents/routes/chat.py + SparkBaseAgent.chat_stream。
- 业务流链路：前端统一走 createStreamingTask，后端统一走 stream_semantics + iterate_sync_iterable_in_thread。
- 工具扩展：统一接入 server/agents/agent_tools.py，不要在路由或单 Agent 私自实现工具协议。
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
