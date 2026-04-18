# 火柴Agent网关——完整接入指南

本文档包含火柴Agent网关（Matchbox Agent Gateway）的深度技术细节。README 中仅保留概述。

---

## 1. 标准设计（SparkArc 默认推荐）

采用"**强管理通道 + 轻量直连通道**"的双通道设计：

### 1.1 强管理通道（默认业务通道）

- 应用启动时显式初始化一次：`initialize_matchbox(ensure_defaults=True)`
- 请求期统一从 `matchbox()` 取管理器，再调用 `get_user_llm(...)` / `get_user_embedding(...)`
- 自动覆盖：用户选型、密钥优先级、`sys_paid`/`self_paid` 配额拦截、用量落库与统计

### 1.2 轻量直连通道（旁路能力）

- 用 `create_quick_llm(...)` / `create_quick_embedding(...)` 快速创建客户端
- 不依赖数据库与用户态，适合一次性任务、离线脚本、健康检查和外部工具桥接

### 1.3 生命周期强约束

- 启动初始化，关闭调用 `reset_matchbo()` 清理全局实例，避免导入副作用
- 通过 `AGENT_MATCHBOX_HOME` 统一控制运行目录（DB/.env/YAML/state），默认回退到包目录

---

## 2. 推荐链路（开发者落地）

1. **应用启动**：在 FastAPI lifespan / startup 中调用 `initialize_matchbox(ensure_defaults=True)`
2. **业务调用**：Agent/路由内统一使用 `matchbox().get_user_llm(user_id, usage_key=...)`
3. **流式输出**：直接 `invoke/stream`，推理字段自动兼容，且请求完成后自动统计用量
4. **配额与计费**：按实际命中的 Key 自动归档到 `sys_paid` 或 `self_paid` 并执行拦截
5. **旁路任务**：仅在无需用户态治理时，才使用 `create_quick_llm` / `create_quick_embedding`

---

## 3. 灵活的系统托管与用户自定义 (BYOK)

- **系统托管模式**：管理员一键配置共享模型池，用户注册即享"开箱即用"
- **BYOK 模式**：原生支持多租户配置，用户可自由添加个人专属平台配置与私有 API Key。所有敏感信息强制通过高强度对称加密存储并严格隔离
- **混合模式**：用户可以在用尽系统额度后自行接入大模型，实现额度完全自由。站长可切换三种模式，自由决定商业模式

---

## 4. 原生多口径配额与账单体系 (Quota & Ledger)

针对真实 C 端场景设计。每一次请求发往前都会被精准分为 `sys_paid`（消耗站长余额）和 `self_paid`（消耗用户自费 Key）进行独立流控。

- 支持周期性限流（例如每 N 小时限额）以及总量封顶策略
- 避免耗尽站长配额时误伤用户自带的免费服务

---

## 5. 精准 Token 估算

摒弃不稳定的 API 返回值（中断获取不到计费信息），采用**本地混合估算**算法：

- 基于 `tiktoken` 基准，结合**动态 CJK 修正系数**
- 准确还原 Qwen/DeepSeek 等国产模型在中文环境下的高压缩率特性
- 确保计费统计精准可靠

---

## 6. 多用途槽位 (Smart Slots)

系统预设三种槽位，并允许用户自定义预设多种情境下不同的模型，根据任务复杂度路由模型，平衡成本与效果：

| 槽位 | 用途 | 典型模型 |
| :--- | :--- | :--- |
| **Fast (快速槽)** | 轻量级快速模型 | 文本自动格式化、分类标签抓取 |
| **Reason (推理槽)** | 具备极强思维推演能力的模型 | 设定审核、情节大纲评估与逻辑链验证 |
| **Main (默认槽)** | 标准的优质文本输出模型 | 日常创作与生成 |

---

## 7. 推理流兼容

网关**兼容 Open AI 协议**，并支持自动将常见的推理字段（如 `reasoning_content` 和 `<think>`）**统一为推理流**，确保最佳的流式体验，拒绝空等待。

核心实现位于 `server/llm/agen_matchbox/reasoning_compat.py`，通过 `PrefixReasoningStreamParser` 对不同厂商的推理输出格式做统一适配。
