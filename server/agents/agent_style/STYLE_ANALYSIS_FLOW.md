# SparkArc 风格分析系统：全流程技术白皮书

## 1. 系统定位
本系统是 SparkArc 的核心基础设施之一，旨在通过多维度、多智能体协作的方式，从原始文学作品中提取高保真的“风格指纹”。该指纹不仅包含词汇和句式，更深入到思维逻辑、情感递进和叙事节奏，为后续的 AI 创作提供灵魂导向。

---

## 2. 核心架构设计

### 2.1 编排层 (Orchestration)
采用 **LangGraph** 构建有状态的图结构工作流：
- **并行分发 (Fan-out)**：利用 `Send` API 将分析任务同时分发给 7 个专业 Agent。
- **状态聚合 (Fan-in)**：通过 `Annotated[List, operator.add]` 自动汇聚所有 Agent 的分析结果。
- **闭环验证 (Feedback Loop)**：引入 Validator 节点对生成结果进行回测，实现风格档案的自我进化。

### 2.2 知识层 (Knowledge/RAG)
- **向量引擎**：FAISS。
- **检索策略**：每个 Agent 拥有独立的 `queries` 集合，根据自身维度（如对话、修辞）在向量库中进行语义搜索，确保分析基于真实文本证据。

### 2.3 配置层 (Configuration)
- **解耦设计**：所有 Agent 的 Prompt、RAG 检索词、评分标准均存储在 `prompts/style_analysis.yaml` 中。
- **动态加载**：基类 `StyleAnalysisAgent` 负责在运行时解析 YAML，实现“热更新”提示词而无需重启服务。

---

## 3. 详细执行流 (Execution Flow)

### 阶段一：数据准备 (Data Ingestion)
1. **智能分块**：`SmartTextChunker` 识别段落边界，保持语义完整性（约 400 字符/块）。
2. **向量化**：构建本地 FAISS 索引，支持秒级语义检索。

### 阶段二：多维深度分析 (Multi-dimensional Analysis)
7 个 Agent 并行执行，每个 Agent 遵循 **“检索 -> 分析 -> 结构化输出”** 的模式：

| 维度 | Agent | 核心任务 |
| :--- | :--- | :--- |
| **对话** | `DialogueAgent` | 捕捉潜台词、说话模式、对话标签风格、沉默运用。 |
| **独白** | `MonologueAgent` | 分析思维结构（线性 vs 跳跃）、内心声音色调。 |
| **叙事** | `NarrativeAgent` | 拆解聚焦模式、场景转换技巧、感官层次（视觉 vs 听觉）。 |
| **角色** | `CharacterPlotAgent` | 提炼性格展现途径、伏笔布置手法、冲突升级逻辑。 |
| **语言** | `LanguageAgent` | 识别词汇指纹、句式建筑学、意象系统（核心意象群）。 |
| **结构** | `StructureAgent` | 分析信息流密度、留白艺术、因果紧密度。 |
| **情感** | `EmotionThemeAgent` | 挖掘情绪积累方式、价值取向、人生态度。 |

### 阶段三：元分析整合 (Meta-Synthesis)
- **CoordinatorAgent** 接收 7 份 JSON 报告。
- **任务**：识别各维度间的关联（如：短促的句式如何配合紧张的情绪），剔除冗余信息，生成统一的 `Signature Style`（风格签名）。

### 阶段四：图灵回测与去 AI 化 (Validation & De-AI)
这是本系统的独创环节，旨在解决 LLM 创作中的“同质化”问题：
1. **模仿测试**：`ValidatorAgent` 基于生成的风格档案，尝试重写一段原文摘要。
2. **严苛评分**：
   - **S级 (Perfect)**：捕捉到文字的“呼吸感”和“思维跳跃”。
   - **B级 (AI Residue)**：虽然形似，但骨子里是 AI 的“总分总”结构或说教感。
   - **D级 (Collapse)**：完全偏离，退化为标准助手语气。
3. **指令修正**：如果评分低于 A，Validator 会生成具体的“负向约束”（如：禁止使用‘然而’、‘总之’），强制修正风格档案。

---

## 4. 产出物：风格档案 (Style Profile)
最终产出的 JSON 档案包含：
- **核心特征库**：可直接作为 Scriptwriter 的 System Prompt。
- **负向约束**：明确标注作者“绝对不会用”的表达方式。
- **典型样本集**：提供给 Few-shot 学习的精选例句。

---

## 5. 维护与扩展
- **新增维度**：在 `agents/` 下添加新类并继承 `StyleAnalysisAgent`，同时在 YAML 中添加对应配置。
- **优化效果**：直接编辑 `prompts/style_analysis.yaml` 中的 `prompt` 或 `queries`。
