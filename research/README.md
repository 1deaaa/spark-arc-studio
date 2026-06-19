# SparkArc 大模型长篇创作流与一致性前沿研究

本目录是 SparkArc 项目关于大模型小说/剧本生成、长文本全局一致性控制与多智能体工作流的前沿技术研究成果库。本研究遵循学术中立性与第三方参考中立性原则，将**学术文献/开源项目调研**与**本项目的具体审计及重构设计方案**进行了物理文件隔离。

---

## 📂 目录结构与快速链接

### 1. 🔍 学术论文深度个案研究 (Papers)
存放于 `papers/` 子目录下，针对 2025–2026 年最具技术启发性和权威性的 11 篇学术论文进行单篇极致详尽的剖析（包含核心贡献、系统架构图、核心算法、工程 prompts 与实验数据）：
*   **[PLOTTER (2026) 图推理故事规划器](file:///d:/Desktop/sparkarc/research/papers/plotter.md)**: 解决长距离情节连贯性，引入“事件图”与“角色图”的拓扑编辑（EPR）循环。
*   **[SCORE (2025) 符号状态机与分层记忆](file:///d:/Desktop/sparkarc/research/papers/score.md)**: 解决物品生死状态的“实体警报”，采用符号状态机（Active/Lost/Destroyed）与混合 RAG 检索。
*   **[StoryBox (2026) 涌现式沙盒模拟](file:///d:/Desktop/sparkarc/research/papers/storybox.md)**: 解决自顶向下大纲的套路化，构建基于意图与秘密的角色 Agent 行动博弈沙盒。
*   **[CreAgentive (2025) 故事原型解耦](file:///d:/Desktop/sparkarc/research/papers/creagentive.md)**: 解决 LLM 构思与写作的注意力过载，通过语义三元组解耦“逻辑骨架”与“文辞 Realization”。
*   **[Lost in Stories (2026) 一致性漏洞分类学](file:///d:/Desktop/sparkarc/research/papers/lost_in_stories.md)**: 剖析 ConStory-Bench 对一致性 Bug 的 19 类细粒度定义，以及 ConStory-Checker 的双向证据比对算法。
*   **[SNAP (2025) 时空 Cell 交互智能体](file:///d:/Desktop/sparkarc/research/papers/snap.md)**: 解决交互叙事中的时空瞬移，将场景限制在图连通的离散叙事 Cell 空间中。
*   **[StoryAlign (2026) 推理期自对齐博弈](file:///d:/Desktop/sparkarc/research/papers/storyalign.md)**: 探索推理期算力扩展（Inference-Time Scaling），采用多维度 Reviewer 打分筛选最优成稿（Best-of-N）。
*   **[STORYWRITER (2025) 三阶段大纲细化](file:///d:/Desktop/sparkarc/research/papers/storywriter.md)**: 解耦大纲 Outlining、节拍 Planning 与微观 Writing 智能体，配合分层压缩前文管理。
*   **[RecurrentGPT (2023) 递归小说生成算子](file:///d:/Desktop/sparkarc/research/papers/recurrentgpt.md)**: 学术基石，使用外置结构化内存模拟 CPU 门控以实现理论上无限长的故事续写。
*   **[DOC (2023) 树状大纲详尽控制](file:///d:/Desktop/sparkarc/research/papers/doc.md)**: 通过递归树状大纲扩展生成“段落写作卡”，利用控制器在正文段落级进行硬约束对齐。
*   **[Temporal Graph RAG 升级 (2025/2026) 时序双图](file:///d:/Desktop/sparkarc/research/papers/temporal_graph_rag.md)**: 剖析传统 Graph RAG 局限，详解 E2RAG 实体-事件时序分离双图架构与 LazyGraphRAG 延迟构建机制。

### 2. 🛠️ 工业级与开源项目深度剖析 (Projects)
存放于 `projects/` 子目录下，解构工业界与开源社区最主流的创作系统：
*   **[Sudowrite (Ghostwriter) 节拍流水线](file:///d:/Desktop/sparkarc/research/projects/sudowrite.md)**: 剖析商业化“卡片式节拍细化与分步执笔扩写”的工程实现与 prompts。
*   **[Novelcrafter (Codex) 动态法典注入](file:///d:/Desktop/sparkarc/research/projects/novelcrafter.md)**: 剖析故事宝典卡片的“NLP 别名扫描与 On-demand 按需热注入”机制。
*   **[SillyTavern (Lorebook) 递归检索记忆](file:///d:/Desktop/sparkarc/research/projects/sillytavern.md)**: 剖析开源社区 Lorebook 的关键词正则匹配、递归条目触发与插入深度/Token权重管理。
*   **[EPOS-AI 拓扑图大纲系统](file:///d:/Desktop/sparkarc/research/projects/epos_ai.md)**: 剖析基于 DAG 拓扑图卡片的剧情因果连线与大纲断链智能自动修复。
*   **[Inkfluence AI 实时节奏编辑器](file:///d:/Desktop/sparkarc/research/projects/inkfluence_ai.md)**: 剖析编辑器后台“节奏与信息量实时审计”和“伏笔双击反向追溯历史引文”的交互设计。
*   **[2026 中美大模型上下文上限与 Prompt Caching (2026)](file:///d:/Desktop/sparkarc/research/projects/model_context_windows_2026.md)**: 汇总 2026 年中美主流模型的物理/有效窗口与 Model ID，深度分析提示词缓存对长篇小说拼装架构的重塑作用。

### 3. 📊 50+ 论文与项目索引清单
*   **[papers_and_projects_index.md](file:///d:/Desktop/sparkarc/research/papers_and_projects_index.md)**: 汇总整理了本次研究所涉及的全部 52 个核心学术研究、前沿论文与开源项目的分类索引总表。

### 4. 🎯 SparkArc 项目客观审计与重构建议 (独立提)
*   **[sparkarc_current_analysis.md](file:///d:/Desktop/sparkarc/research/sparkarc_current_analysis.md)**: 对 SparkArc 现有“三圈记忆”前文拼接机制、角色卡全量载入现状的纯客观代码审计，指出其跨章盲区、Token 膨胀与 GraphRAG 闲置等硬伤。
*   **[sparkarc_redesign_recommendations.md](file:///d:/Desktop/sparkarc/research/sparkarc_redesign_recommendations.md)**: 基于本次前沿调研，针对本项目大长篇创作痛点提出的核心重构设计（时序双图 E2RAG 与 Lazy 构建、基于 Prompt Caching 的 System 前缀缓存与动态 User 尾部分流、推理期 Critic 智能体博弈审计）。
