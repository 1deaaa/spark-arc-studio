# PLOTTER: Planning Beyond Text: Graph-based Reasoning for Complex Narrative Generation

*   **论文链接：** [https://arxiv.org/abs/2604.21253](https://arxiv.org/abs/2604.21253)
*   **发布时间：** 2026年4月
*   **核心领域：** 长篇叙事生成、图神经网络与大模型协同规划、情节因果关系维护

---

## 一、 核心贡献与思想

传统的 LLM 故事生成方法（如自顶向下的分层大纲生成）在生成超长故事时，常因线性前文的遗忘和滑动窗口的限制而发生**“情节断裂”、“伏笔烂尾”以及“人物行为因果冲突”**。

PLOTTER 提出了 **“Planning Beyond Text”** 的核心思想。它认为，小说创作的骨架应当被定义并维护在**结构化图表征（Structural Graphs）**层面，而不是用自然语言大纲。PLOTTER 设计了“事件图”和“角色图”，并在写作前使用多智能体对图进行评估和重构（Evaluate-Plan-Revise 循环），确保逻辑在实体拓扑层面完全无缝，最后再由執笔模型翻译为线性文本。

---

## 二、 系统架构 (System Architecture)

PLOTTER 采用了一个包含图构建、图诊断（Critic）、拓扑编辑器（Graph Editor）以及文本具象化器（Realizer）的分层协作系统：

```mermaid
graph TD
    UserPrompt[用户故事意图] -->|生成初始原型| GraphBuilder[图构建器 Graph Builder]
    GraphBuilder -->|构建初始双图| DoubleGraph[Event Graph & Character Graph]
    
    subgraph Evaluate-Plan-Revise 拓扑循环 (Graph Reasoning Kernel)
        DoubleGraph -->|1. Evaluate| GraphCritic[图评审智能体 Graph Critic]
        GraphCritic -->|输出拓扑诊断报告| GraphEditor[图拓扑编辑器 Graph Editor]
        GraphEditor -->|2. Plan & Revise| EditOps[图原子编辑操作]
        EditOps -->|修改拓扑| DoubleGraph
    end
    
    DoubleGraph -->|3. Realize (校验通过后)| TextRealizer[文本执笔 Realizer]
    TextRealizer -->|生成| NovelText[最终连贯的小说文本]
```

---

## 三、 核心机制与算法细节

### 1. 结构化图表征模型 (Dual-Graph Representation)
PLOTTER 维护两个强关联的图结构：
*   **事件图 (Event Graph, $G_E = (V_E, E_E)$)**：
    *   *节点 $V_E$*：每一个核心故事事件。节点属性包括：事件发生的章节、地点、出场实体列表以及“核心因果状态描述”。
    *   *边 $E_E$*：有向边。代表“因果蕴含关系（Causal Entailment）”和“时间必然先后顺序（Temporal Sequence）”。只有前置事件节点全部达成，后续事件才可被触发。
*   **角色图 (Character Graph, $G_C = (V_C, E_C)$)**：
    *   *节点 $V_C$*：故事中的角色实体。
    *   *边 $E_C$*：无向边或有向边。代表角色间的情感、阵营或社会关系（如“父子”、“死敌”），且边上绑定了“触发此关系变更的事件节点 ID $v_E$”。

### 2. Evaluate-Plan-Revise (EPR) 拓扑演化循环
在正式动笔写章节之前，系统启动 EPR 循环对图谱进行多轮诊断与修复：
1.  **Evaluate (图评估)**：Graph Critic 遍历 $G_E$ 与 $G_C$，通过分析图的拓扑特征诊断逻辑冲突。例如：
    *   发现孤立事件节点（没有前因，也没有后果）。
    *   发现关系倒置（在第 3 章写着“A 杀死了 B”，但在第 5 章的事件中 B 依然是出场角色，即 Causal Violation 冲突）。
2.  **Plan (图编辑规划)**：针对发现的冲突，智能体生成一系列原子编辑命令（Atomic Graph Operations）：
    *   `ADD_NODE(v)`: 添加新的修正事件。
    *   `ADD_EDGE(u, v, rel)`: 建立因果/时间连接。
    *   `DELETE_EDGE(u, v)`: 断开不合逻辑的关联。
    *   `MODIFY_NODE_ATTR(v, attr, val)`: 修正节点属性。
3.  **Revise (拓扑重构与验证)**：Graph Editor 执行这些命令，并运行环路检测与可达性搜索算法，直至图拓扑完全收敛、逻辑无冲突。

---

## 四、 工程实验与数据流设计 (Engineering & Prompts)

在论文的工程实验中，PLOTTER 展示了双图与执笔的 prompt 拼接方式：

```
[System Prompt]
你是一个故事文本具象化器（Realizer）。
你的唯一天职是将给定的“事件图”和“角色图”信息翻译成高文学性的故事正文，严禁擅自篡改或偏离图中的因果走向。

[Graph Context]
【出场角色与最新关系网】
- 节点：人物 A (性格: 隐忍), 人物 B (性格: 骄狂)
- 连边：A 与 B 的关系为“杀父之仇”(事件来源: Ch1_Event2)

【当前场景事件约束 (Event Chain)】
- 当前事件：Event 15 (发生地: 茶馆)
- 事件描述：A 在茶馆偶然遇到了 B，A 强行压制住杀意，向 B 敬茶，B 傲慢拒绝。
- 前置依赖事件：Event 2 (A 亲眼目睹父亲被 B 害死)

请根据上述图谱关系和当前事件约束，撰写 1500 字的小说正文。
```

### 实验结果：
在超长篇（5万字以上）的叙事连贯性对比实验中，PLOTTER 相比传统线性 RAG 和 Sliding Window 架构：
*   **情节逻辑合理率（Plot Consistency Rate）** 提升了 **32.8%**。
*   **伏笔回收成功率（Foreshadowing Recycle Rate）** 提升了 **45%**。
*   极大地避免了模型“写着写着角色突然复活”或“忘记杀父之仇并与仇人握手言和”等低级逻辑灾难。
