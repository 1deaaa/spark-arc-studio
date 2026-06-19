# 大模型文学创作与长文本连贯性研究：50+ 核心文献与项目索引

本索引汇总了大模型在文学创作、智能体小说/剧本生成、长文本一致性控制、记忆管理与前沿评测等领域的 52 个具有代表性的学术论文与开源/商业项目。

---

## 📂 核心调研个案（各文档单篇详细剖析）

以下 17 个核心个案在对应的 `papers/` 和 `projects/` 目录下拥有独立的、极致详尽的 Markdown 研究报告。可点击链接直接跳转查阅其核心架构图、算法细节与工程 Prompts：

### 学术论文 (Papers)
1.  **[PLOTTER (2026)](file:///d:/Desktop/sparkarc/research/papers/plotter.md)**: *Planning Beyond Text: Graph-based Reasoning for Complex Narrative Generation*. 基于图编辑与结构推理的故事规划器。
2.  **[SCORE (2025)](file:///d:/Desktop/sparkarc/research/papers/score.md)**: *Story Coherence and Retrieval Enhancement*. 动态符号状态机与分层记忆增强。
3.  **[StoryBox (2026)](file:///d:/Desktop/sparkarc/research/papers/storybox.md)**: *Collaborative Multi-Agent Simulation for Hybrid Bottom-Up Long-Form Story Generation*. 自底向上的多智能体沙盒模拟。
4.  **[CreAgentive (2025)](file:///d:/Desktop/sparkarc/research/papers/creagentive.md)**: *An Agent Workflow Driven Multi-Category Creative Generation Engine*. 逻辑与文风解耦的故事原型表示法。
5.  **[Lost in Stories (2026)](file:///d:/Desktop/sparkarc/research/papers/lost_in_stories.md)**: *Consistency Bugs in Long Story Generation by LLMs*. ConStory-Bench 一致性漏洞分类学与自动审计引擎。
6.  **[SNAP (2025)](file:///d:/Desktop/sparkarc/research/papers/snap.md)**: *Story and Narrative-based Agent with Planning*. 基于时空 Cell 规划的交互式叙事智能体。
7.  **[StoryAlign (2026)](file:///d:/Desktop/sparkarc/research/papers/storyalign.md)**: *Self-Improving Writer-Reviewer Agent Pairs*. 推理期 Best-of-N 采样博弈自对齐机制。
8.  **[STORYWRITER (2025)](file:///d:/Desktop/sparkarc/research/papers/storywriter.md)**: *Outlining, Planning, and Writing Agents*. 三阶段层级大纲细化与分层记忆管理。
9.  **[RecurrentGPT (2023)](file:///d:/Desktop/sparkarc/research/papers/recurrentgpt.md)**: *Interactive Generation of Arbitrary-Long Novels*. 模仿 CPU 门控外置内存的循环小说生成算子。
10. **[DOC (2023)](file:///d:/Desktop/sparkarc/research/papers/doc.md)**: *Improving Long Story Coherence with Detailed Outline Control*. 递归树状大纲详尽控制与段落控制器。
11. **[Temporal Graph RAG 升级 (2025/2026)](file:///d:/Desktop/sparkarc/research/papers/temporal_graph_rag.md)**: 传统 Graph RAG 的局限与 2025–2026 年小说时序双图 (E2RAG) 与 LazyGraphRAG 升级方案。

### 开源与商业项目 (Projects)
12. **[Sudowrite (Ghostwriter)](file:///d:/Desktop/sparkarc/research/projects/sudowrite.md)**: 商业写作先驱，卡片式大纲与节拍（Beats）扩写流水线。
13. **[Novelcrafter (Codex)](file:///d:/Desktop/sparkarc/research/projects/novelcrafter.md)**: Codex 故事法典，显式实体匹配与按需卡片动态注入。
14. **[SillyTavern (Lorebook)](file:///d:/Desktop/sparkarc/research/projects/sillytavern.md)**: 开源角色扮演前端，关键词正则触发与递归扫描动态记忆。
15. **[EPOS-AI](file:///d:/Desktop/sparkarc/research/projects/epos_ai.md)**: 拓扑有向无环图（DAG）情节卡片与人机协同重规划白板。
16. **[Inkfluence AI](file:///d:/Desktop/sparkarc/research/projects/inkfluence_ai.md)**: 工业级编辑器，实时逻辑纠错、节奏审计与伏笔双击反向追踪。
17. **[2026 中美大模型上下文上限与 Prompt Caching (2026)](file:///d:/Desktop/sparkarc/research/projects/model_context_windows_2026.md)**: 2026 年中美主流模型超长上下文上限与 Model ID 数据字典，及对长篇小说上下文拼装演进的影响。

---

## 📚 50+ 文献与项目汇总分类清单

以下列出本次研究所涵盖的全部 **52 个** 标志性研究与项目，分类如下：

### 一、 规划与大纲控制 (Planning & Outline Control)
18. **Plot-guided Long-form Narrative Generation via RL (2024)**: 探索以强化学习价值网络评估故事偏离大纲的风险。
19. **Hierarchical Novel Generation with LLMs (2024)**: 分层大纲对齐算法，从 500 字梗概生长至 5 万字小说。
20. **Interactive Story Planning via LLMs (2025)**: 用户与智能体共同规划小说情节树（Plot Tree）并支持局部撤销。
21. **Showrunner-Agent: Multi-stage Structural Drama Planner (2025)**: 专为多幕剧本设计的“三幕式”与“英雄之旅”规划系统。
22. **Re-planning in Interactive Storytelling (2024)**: 智能体根据读者行为，实时对后续大纲进行图剪枝与重规划。
23. **Causal Outlining for Fiction Coherence (2025)**: 引入因果关联边约束的大纲细化生成框架。
24. **Outlines: Structured Text Generation (开源项目)**: 使用 FSM 约束 LLM 格式输出，常用于剧本格式控制。

### 二、 多智能体协同与写作沙盒 (Multi-Agent & Sandbox Simulation)
25. **ChatEval: Multi-agent debate for narrative evaluation (2023)**: 引入多个不同审美偏好的智能体辩论小说质量。
26. **RolePlay-Fiction: Character Interaction Simulation (2025)**: 多智能体角色扮演，生成高度符合人设的自然对白。
27. **The Novelists' Collective (2025)**: 包含策划、执笔、润色与模拟读者的异步协作智能体社会生态系统。
28. **Auto-Drama: Multi-Agent System for Screenplay Generation (2025)**: 特化于电影剧本创作与自动排版的多 Agent 系统。
29. **Plug-and-Play Dramaturge (2026)**: 基于“节奏、POV、戏剧张力”等模块化评审专家意见的循环重写机制。
30. **Agents' Room: Decomposing Narrative Writing (2025)**: 将写作拆分为动作描写、环境渲染、心理活动等智能体会议。
31. **Narrative Sandbox with LLM Physics Kernel (2025)**: 基于物理与常识解释器约束的多角色冲突决策沙盒。
32. **Co-Writing Sandbox (2024)**: 创意写作人机协同协作演进沙盒。

### 三、 记忆追踪、知识图谱与状态管理 (Memory, Graphs & State Tracking)
33. **MemoFiction: Long-term Memory for Persona Consistency (2024)**: 基于记忆树（Memory Tree）的外置角色“回忆录”。
34. **Microsoft GraphRAG (2024/2025)**: 基于图上社区划分与事实抽象的全局小说设定检索方法。
35. **Memory Sandboxes: Dynamic Database Management (2025)**: 为创意写作设计的智能体动态滑动权重内存数据库。
36. **Hierarchical Vector Memory in Agentic Novel Writing (2025)**: 支持词-句-段-章多粒度前文召回的分级向量库技术。
37. **State-Tracking Agent for Visual Novel Coherence (2025)**: 在提示词中提供轻量级的地理位置、血量与情感状态栏。
38. **Narrative Memory Consolidation using Symbolic Graphs (2026)**: 增量写入后，自动对图谱中过时关系进行剪枝与合并的算法。
39. **Dynamic Plot Context Retrieval via Entailment Trees (2025)**: 利用蕴含树维护小说因果，拉取当前情节的直接前因。
40. **Sudowrite's Story Bible (商业项目)**: 商业写作中的静态与动态故事变量管理面板。
41. **SillyTavern Lorebook (开源项目)**: 基于正则关键词触发与 Token 预算插入深度的开源动态记忆系统。
42. **Novelcrafter Codex (商业项目)**: 具备别名表匹配与动态卡片热注入的故事故事法典。

### 四、 评测标准、偏好对齐与审计 (Evaluation, Alignment & Critique)
43. **WebNovelBench: Multi-Faceted Evaluation Framework (2026)**: 针对爽文、网文特征的自动与人工评测指标。
44. **StoryLens: Preference-Aligned Narrative Enrichment (2026)**: 基于人类写作偏好对齐（DPO/RLHF）的故事重写框架。
45. **Critique-Loop: Continuous Quality Assessment (2025)**: 在创作中以段落为单位进行“负反馈阻尼”的连续评估循环。
46. **Detecting Persona Drift in Long LLM Generations (2025)**: 基于 MBTI 性格特征分析的实时角色人设漂移检测模型。
47. **Foreshadowing Detection in Long Stories (2026)**: 利用自动语义对比，计算小说中伏笔的“断弦率（未回收率）”。
48. **Pacing Auditor for Multi-Chapter Novels (2025)**: 基于词汇信息量与句子长度方差的情节节奏审计器。
49. **POV Consistency Verifier for Long Narratives (2025)**: 自动审计和查出长篇大作在不同视角之间切换混乱的分类器。
50. **Conflict Quality Metrics for Storytelling Agents (2025)**: 评估故事冲突合理性与张力的计算指标。
51. **LazyGraphRAG (2025)**: 针对动态小说修改的低成本运行时延迟图检索算法。
52. **Entity-Event RAG / E2RAG (2025)**: 时序事件 DAG 与实体图物理分离的双图叙事连贯性控制方法。
