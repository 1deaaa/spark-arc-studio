# 🛠️ SparkArc 技术开发路线图 (Tech Roadmap)

本文件旨在规划项目的技术落地路径，涵盖后端架构、前端交互、Agent 策略及生态集成。

## Phase 1: 核心基建与工作流 (Infrastructure & Workflow)
**目标**: 搭建稳固的前后端框架，实现最基础的"节点编辑"与"LLM调用"闭环。

### 1. 后端基础 (Server - Python/Flask)
- [x] **通用 LLM 管理器 (LLM Manager)**
    - 统一接口封装，支持多模型切换、API Key 管理。
    - 实现了 `LLM_Manager` 单例与配置 GUI。
- [ ] **Agent 消息总线 (Agent Bus)**
    - 设计一套简易的 Agent 通信协议，允许 "大纲 Agent" 向 "扩写 Agent" 传递上下文。
    - 统一的 Prompt 模板管理系统 (Prompt Registry)，支持版本控制。
- [ ] **数据持久化**
    - 确定 Project / Scene / Character 的 JSON 数据结构标准。
    - 实现基于文件系统的项目存储 (非数据库)，方便 Git 管理与分享。

### 2. 前端编辑器 (Client - Vue3/NaiveUI)
- [x] **基础框架**
    - Vite + Pinia + Vue Router 搭建完成。
- [x] **可视化节点编辑器 (DialogueTree)**
    - 能够创建、连接、拖拽节点。
- [ ] **智能交互设计**
    - **"两点一连"**: 选中两个剧情节点，前端发送上下文给后端，后端调用 LLM 生成中间过渡剧情。
    - **流式对话面板 (AiPanel)**: 右侧侧边栏支持与 AI 实时对话，并能将对话结果一键 "Apply" 到左侧节点树中。
    - **操作回溯**: 实现基础的 Undo/Redo 栈，防止 AI 生成内容覆盖误操作。

### 3. 开发者工具 (DevTools) - *新增*
- [ ] **Agent 调试台 (The Blackbox)**
    - 显示 Agent 实际接收到的完整 Prompt (包含系统指令 + RAG 注入的内容)。
    - 显示 Agent 的原始思考链 (Chain of Thought) 和 Token 消耗。
    - **作用**: 帮助用户理解为什么 AI 会写出这段话，从而优化 Prompt。

---

## Phase 2: 智能编剧团队 (AI Agents Crew)
**目标**: 构建分工明确的 AI Agent 体系，提升生成内容的逻辑性与文学性。

### 1. 策划与大纲 (The Planner)
- [ ] **灵感扩充器 (Spark Expander)**
    - 输入: 单句灵感 / 关键词。
    - 输出: 3-5 个差异化的故事大纲分支。
- [ ] **剧情结构化**
    - 自动识别并打标剧情节奏点 (起承转合)，在生成时控制张力。

### 2. 世界观与记忆 (The Historian - RAG)
- [ ] **GraphRAG 集成 (知识图谱)**
    - [ ] 实体抽取: 从用户上传的设定集/旧剧本中自动提取 "人名"、"地名"、"关系"。
    - [ ] 关系存储: 使用 NetworkX 或类似库构建内存中的关系图。
    - [ ] 检索增强: 写新剧情时，自动检索相关实体的前置设定，防止 "吃书"。
- [ ] **Lorebook 动态注入**
    - 实现基于语义相似度 + 关键词匹配的 Prompt 动态注入机制。

### 3. 角色与演出 (The Actor)
- [ ] **文风模仿 (Style Mimicry)**
    - 基于 `agent_style` 模块，分析目标作者/角色的文本特征 (词频、句长、语气词)。
    - 构建 Few-shot 示例库，让 LLM 模仿特定口癖。
- [ ] **台词润色**
    - 将书面语转化为口语，自动添加潜台词 (Subtext) 标注。

---

## Phase 3: 生产力与生态 (Ecosystem & Production)
**目标**: 打通游戏引擎与 Web 分享，实现"所见即所得"的最终演出。

### 1. Unity 集成 (Presenter - C#)
- [ ] **Runtime SDK**
    - 在 Unity 中实现一个轻量级解析器，读取后端生成的 JSON 剧本。
- [ ] **实时预览 (Live Preview)**
    - 通过 WebSocket 连接编辑器与 Unity，编辑器修改节点文本，Unity 画面实时刷新台词。
- [ ] **演出指令绑定**
    - 在节点编辑器中提供简单的 GUI (下拉框/开关)，插入 Unity 能够识别的指令 (如 `PlayAnim("Cry")`, `CameraShake(2.0)`)。

### 2. Web 分享与社区
- [ ] **Web Player**
    - 一个纯前端的播放器组件，用于在网页上直接跑通剧本。
- [ ] **一键分享**
    - 将项目打包为静态链接，方便用户分享给朋友试玩。

---

## ✨ 待探索特性 (Future Research)
- [ ] **多模态辅助**: 根据当前场景描述，调用 SD/Midjourney 生成背景图。
- [ ] **TTS 配音**: 集成 VITS/GPT-SoVITS，为角色生成语音。