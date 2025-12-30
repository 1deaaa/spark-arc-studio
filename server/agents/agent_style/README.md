# SparkArc 风格分析系统 (Style Analysis System)

## 1. 系统概述
SparkArc 风格分析系统是一个基于 **LangGraph** 编排、**RAG (Retrieval-Augmented Generation)** 驱动的多智能体协作系统。其核心目标是从海量文本样本中精准提取作者的创作“灵魂”，生成一份可供 AI 创作使用的结构化风格档案，并最大限度地消除生成过程中的“AI 味”。

## 2. 核心架构
系统采用分层架构，确保了分析的深度、广度与最终产出的可操作性。

### 2.1 技术栈
- **编排引擎**: LangGraph (支持并行分发与状态管理)
- **向量数据库**: FAISS (用于高效的 RAG 检索)
- **配置中心**: YAML (所有提示词与检索逻辑与代码解耦)
- **基类驱动**: 统一继承自 `StyleAnalysisAgent`，实现标准化的 RAG 流程。

## 3. 详细工作流

### 第一阶段：数据预处理 (Preprocessing)
1.  **智能分块 (Smart Chunking)**: 
    - 使用 `SmartTextChunker` 将原始文本切分为约 400 字符的语义块。
    - 自动保留章节、作者等元数据。
2.  **向量化 (Vectorization)**: 
    - 构建 FAISS 向量库，为后续 Agent 提供“按需检索”能力。

### 第二阶段：并行多维分析 (Parallel Analysis)
LangGraph 将任务并行分发给 7 个专业 Agent，每个 Agent 仅关注其擅长的维度：

| Agent 名称 | 分析维度 | 核心关注点 |
| :--- | :--- | :--- |
| **DialogueAgent** | 对话系统 | 潜台词、说话模式、对话节奏、沉默的运用 |
| **MonologueAgent** | 内心独白 | 思维结构、心理时间感、自我对话模式 |
| **NarrativeAgent** | 叙事场景 | 聚焦模式、场景构建技巧、细节颗粒度、感官层次 |
| **CharacterPlotAgent** | 角色情节 | 角色塑造手法、伏笔设置、冲突升级逻辑 |
| **LanguageAgent** | 语言修辞 | 词汇指纹、句式建筑学、意象系统、修辞手法 |
| **StructureAgent** | 结构节奏 | 信息流密度、因果紧密度、张力释放机制 |
| **EmotionThemeAgent** | 情感主题 | 情感递进方式、核心主题、价值取向 |

**RAG 机制**: 每个 Agent 根据配置文件中的 `queries` 从向量库检索最相关的片段，确保分析结果“言之有据”，而非凭空臆测。

### 第三阶段：整合提炼 (Synthesis)
- **CoordinatorAgent (协调者)**:
    - 收集并解析所有并行 Agent 的 JSON 报告。
    - 执行**元分析 (Meta-Analysis)**，识别跨维度的风格一致性（例如：语言的冷峻如何配合情节的残酷）。
    - 提炼出**标志性风格签名 (Signature Style)**。

### 第四阶段：验证与闭环修正 (Validation & Refinement)
这是系统的“去 AI 味”核心环节：
1.  **抽样与模仿**: `ValidatorAgent` 从向量库抽取原文，并基于生成的风格档案进行模仿创作。
2.  **图灵测试评分**: 使用 YAML 中定义的 **S/A/B/C/D 级量表**进行严苛评分。
    - **S级**: 完美拟合，捕捉到“呼吸感”与“思维跳跃”。
    - **B级**: AI 味残留，逻辑过于严密，强行升华主题。
    - **D级**: 风格坍塌。
3.  **反向修正**: 识别模仿文中的“AI 特征”，生成具体的 Prompt 修正指令（如“禁止使用‘然而’、‘总而言之’等连接词”），并更新最终的风格档案。

## 4. 配置管理
系统实现了**提示词与代码的完全解耦**。
- **配置文件**: `server/agents/agent_style/prompts/style_analysis.yaml`
- **内容包含**: 
    - 各 Agent 的 RAG 检索词 (`queries`)
    - 深度分析提示词 (`prompt`)
    - 验证评分标准 (`grading_rubric`)
    - 模仿与验证提示词 (`mimic_prompt`, `eval_prompt`)

## 5. 核心优势
1.  **深度解构**: 相比单一 Prompt 分析，多 Agent 并行能捕捉到更多微观层面的文学特征。
2.  **去 AI 化**: 通过 Validator 的回测机制，强制识别并剔除 LLM 常见的说教感和过度逻辑化倾向。
3.  **快速迭代**: 优化风格提取效果只需修改 YAML 配置文件，无需触动核心逻辑。
4.  **可解释性**: 每一项风格特征都关联着具体的原文样本和 Agent 分析逻辑。
