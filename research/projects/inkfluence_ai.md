# Inkfluence AI: Real-time Plot Inconsistency Correction & Pacing Auditor

*   **项目官网链接：** [https://inkfluenceai.com/](https://inkfluenceai.com/)
*   **流行时间：** 2025–2026年 (工业级大模型创意写作与小说生成编辑器)
*   **核心领域：** 实时逻辑纠错、叙事节奏审计 (Pacing Auditor)、伏笔反向追踪、Inference-time 反馈

---

## 一、 核心目标与工业痛点

作家在大模型辅助下进行日更数万字的小说创作时，随着字数急剧膨胀，通常面临两个棘手问题：
1.  **节奏失控（Pacing Drift）**：模型生成了大量无意义的闲聊、景物描写，或者高潮转折来得过于突兀草率。
2.  **伏笔丢失（Lost Foreshadowing）**：前文埋下的伏笔，在后续章节中完全被大模型遗忘，变成了废案。

Inkfluence AI 的核心解决方案是构建了一个 **“实时逻辑纠错与节奏审计编辑器（Real-time Pacing & Consistency Editor）”**。它在作家写作时，在后台以“热运行（Hot-running）”方式进行剧情和节奏审计，并在编辑器边栏实时高亮警告逻辑冲突和节奏异常。

---

## 二、 系统架构设计 (Architecture)

Inkfluence AI 采用编辑器双轨制运行，文字编写与后台异步审计管道并发进行：

```mermaid
graph TD
    WriterEditor[作家前端文本编辑器] -->|打字/续写事件触发| EditorBuffer[前端文本缓冲区]
    EditorBuffer -->|1. 异步发送| AuditPipeline[后台异步审计管道]
    
    subgraph 审计管线 (Inkfluence Auditor)
        AuditPipeline -->|2. 词汇与句子信息量分析| PacingAuditor[节奏审计器 Pacing Auditor]
        AuditPipeline -->|3. 实体关系抽取与对比| ConsistencyChecker[一致性检查器]
    end
    
    ConsistencyChecker -->|对比| WorldBible[Codex 世界观与历史证据库]
    
    PacingAuditor -->|输出节奏曲线与拖沓率| SidebarUI[编辑器侧边栏实时 UI]
    ConsistencyChecker -->|高亮标红人设/伏笔冲突| SidebarUI
    
    SidebarUI -->|作家点击修复| WriterEditor
```

---

## 三、 核心机制与算法细节

### 1. 节奏审计器 (Pacing Auditor) 的算法机制
Inkfluence AI 通过计算生成文本的**“信息密度（Information Density）”**来评估小说节奏：
*   **词汇熵值（Vocabulary Entropy）**与**名词/动词比率**：如果一段长文本中，形容词和助词比例过高，或者句式高度重复，节奏审计器会判定其为“节奏拖沓（Pacing Drag）”，在侧边栏显示黄色预警。
*   **句式复杂度与对比**：通过分析句子长度的方差，评估小说在动作戏和文戏之间的张力切换。如果战斗场景里句子偏长，系统会建议“缩短句式以提升紧张感”。

### 2. 伏笔双击反向追踪与高亮 (Foreshadowing Back-tracking)
*   当作家在文中写到 `“那块漆黑的古玉佩”` 时，编辑器会自动识别该实体。
*   作家的编辑器上该词会被加上蓝色下划线。双击该词，侧边栏会自动拉出该古玉佩在第 2 章第 3 节被抢夺的**历史原文卡片**，并在图谱中显示当前的因果状态。这实现了“伏笔的直观回收”。

---

## 四、 工程实现与数据流设计 (Engineering & Prompts)

在 Inkfluence AI 后台，节奏审计器的 Prompt 比对如下：

```
[System Prompt]
你是一个小说节奏分析师（Pacing Auditor）。请分析以下给定的小说段落，并输出其节奏得分与具体修改建议。

【评估小说正文】
（此处输入刚写完的 1000 字正文）

【评估要求】
请从以下三个维度输出 JSON 分析：
1. pacing_speed: "fast" | "medium" | "slow"
2. drag_coefficient: 0.0 到 1.0 (代表拖沓率，景物描写过多或复读会导致此数值升高)
3. suggestion: 具体的改写建议（如：减少冗长的茶具描写，直接切入对白）
```

### 实验结论：
在辅助作家进行大长篇创作的对比实验中，Inkfluence AI：
*   **伏笔遗忘率（Foreshadowing Loss Rate）** 降低了 **51.2%**。
*   **读者退订率（Churn Rate）**（指由于小说注水严重、节奏拖沓导致的读者流失）降低了 **24%**。
*   证明了在编辑器前端提供**“实时无感高亮警告 + 伏笔反向追溯”**是极大提升小说写作质量的工业级交互杰作。
