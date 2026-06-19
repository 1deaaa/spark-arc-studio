# STORYWRITER: Outlining, Planning, and Writing Agents

*   **论文链接：** [https://arxiv.org/abs/2502.10800](https://arxiv.org/abs/2502.10800)
*   **发布时间：** 2025年2月
*   **核心领域：** 分层故事生成、多级大纲细化、大长篇上下文预算管理

---

## 一、 核心贡献与思想

大模型在直接撰写 10,000 字以上的长篇小说章节时，若没有严密的层级化拆解，大模型极易在写完第一千字后**“忘记大纲结局，直接偏离主线剧情，发生严重的叙事漂移”**。

STORYWRITER 提出了 **“分阶段智能体流水线（Multi-Stage Agentic Pipeline）”** 的核心思想。它主张将大长篇小说的写作完全剥离为三个高内聚的阶段：**Outline Agent (大纲设计)** -> **Planning Agent (详细节拍规划)** -> **Writing Agent (微观场景写作)**。每一个智能体只接收上一层传递的细化卡片，并专注本层任务。该系统同时提出了一套“滑动窗口与压缩摘要同步”的机制，解决了数十万字小说生成时的上下文预算（Context Budget）崩溃问题。

---

## 二、 系统架构 (System Architecture)

STORYWRITER 采用分层的智能体协作架构：

```mermaid
graph TD
    Synopsis[梗概 synopsis] -->|1. 大纲规划| OutlineAgent[大纲智能体 Outline Agent]
    OutlineAgent -->|输出| ChaptersList[章节列表大纲 (Chapter Outline)]
    
    ChaptersList -->|2. 节拍拆解| PlanningAgent[规划智能体 Planning Agent]
    PlanningAgent -->|输出| SceneBeats[场景微观节拍列表 (Scene Beats)]
    
    SceneBeats -->|3. 正文具象化| WritingAgent[执笔智能体 Writing Agent]
    HistorySummary[层次化压缩前文摘要] --> WritingAgent
    
    WritingAgent -->|翻译生成| EpisodeText[小说正文段落]
```

---

## 三、 核心机制与算法细节

### 1. 三阶段层级化拆解
*   **阶段 1: 大纲设计 (Outlining)**：
    *   *输入*：1000 字的故事梗概。
    *   *任务*：由 Outline Agent 生成包含章节结构、每章主要矛盾和最终结局的列表。例如拆解为 10 个章节。
*   **阶段 2: 节拍规划 (Planning)**：
    *   *输入*：第 3 章章节大纲。
    *   *任务*：由 Planning Agent 将其细化为该章节内 5~8 个具体的动作节拍（Beats），明确规定第几个节拍哪些角色必须完成什么交谈、物理环境发生什么改变。
*   **阶段 3: 执笔生成 (Writing)**：
    *   *输入*：第 3 章第 2 个节拍。
    *   *任务*：Writing Agent 仅仅加载这个节拍的描述（约 150 字），辅以压缩后的前序摘要，扩写为 800 字的精美小说正文。

### 2. 层次化前文压缩记忆 (Hierarchical Context Management)
为了不让 Writing Agent 被几万字的历史前文撑爆窗口：
1.  **极近戏剧前文 (Active Memory Window)**：仅保留上一场景的原文。
2.  **本章前序章节摘要 (Chapter-level Summaries)**：前序章节的正文被异步压缩成 300 字的高信息密度大事件摘要，拼在上下文头部。
3.  **全局大纲锚定 (Global Anchor)**：始终保留结局描述，防止剧情发散。

---

## 四、 工程实现与数据流设计 (Engineering & Prompts)

在 STORYWRITER 实验中，Planning Agent 的节拍拆解 prompt 如下：

```
[System Prompt]
你是一个章节规划智能体（Planning Agent）。你的职责是将给定的“章节大纲”细化为 5 个微观的情节节拍（Beats）。
每个节拍必须描述具体角色的动作、对话的子主题或现场的环境改变。

【章节大纲】
第 3 章：John 与 Mary 在雨中茶馆密谈。Mary 拒绝交出玉佩，两人反目。

【输出要求】
请输出 5 个 Beat 的 JSON 列表，格式如下：
[
  {"beat_index": 1, "description": "描写茶馆外的大雨，John 独自等待，Mary 撑伞推门而入。"},
  {"beat_index": 2, "description": "Mary 坐下，John 开门见山索要玉佩，Mary 闪烁其词。"},
  ...
]
```

### 实验结论：
在生成超长篇（8万字以上）的小说连贯性测试中：
*   **剧情大纲对齐度 (Outline Alignment Rate)** 提升了 **34.2%**（小说结局和主线路线完全收敛，无偏离）。
*   **生成效率**：由于采用了层级压缩前文，每次写入时的 Token 数量比全量灌入**减少了 62%**。
*   彻底解决了模型因“大纲太粗”而自己胡编乱造、写着写着就把重要配角丢在脑后的弊端。
