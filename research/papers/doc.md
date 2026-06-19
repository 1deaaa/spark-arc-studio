# DOC: Improving Long Story Coherence with Detailed Outline Control

*   **论文链接：** [https://arxiv.org/abs/2305.14800](https://arxiv.org/abs/2305.14800)
*   **发布时间：** 2023年5月
*   **核心领域：** 层级控制生成、大纲细化器 (Outline Controller)、长文本小说评估

---

## 一、 核心贡献与思想

大模型在直接撰写长故事时，往往会出现“虎头蛇尾”或“跑题”现象。即使事先有大纲约束，普通的 Prompt 也极易随着生成字符的增多而逐渐失去对大纲的“注意力（Attention Decay）”，导致剧情走向发生漂移。

DOC (Detailed Outline Control) 提出了 **“层级化大纲详尽控制”** 的思想。它设计了一个两阶段的故事生成流水线：
1.  **大纲细化器 (Detailed Outliner)**：将一个简略的故事大纲，递归扩展成一个树状、包含微观设定和因果依赖的“超详尽大纲（Detailed Outline）”。
2.  **大纲检测与控制器 (Outline Controller)**：在正文生成期间，通过“控制器”在每一个段落级别强力比对“当前段落生成文本”与“超详尽大纲分片”的契合度，防止生成偏离。

---

## 二、 系统架构 (System Architecture)

DOC 采用双阶段层级式生成与细化架构：

```mermaid
graph TD
    BriefOutline[初始简略大纲] -->|1. 递归扩展| DetailedOutliner[大纲细化器 Detailed Outliner]
    DetailedOutliner -->|输出| DetailedOutlineTree[超详尽大纲树]
    
    DetailedOutlineTree -->|提供段落级控制卡| Controller[大纲控制器 Outline Controller]
    
    subgraph 控制写作循环 (Paragraph-level Control Loop)
        Controller -->|约束条件与任务| Generator[正文生成器 Text Generator]
        Generator -->|生成当前段落| ParaText[段落正文]
        ParaText -->|反馈比对| Controller
    end
    
    ParaText -->|拼接输出| LongStory[最终高连贯长故事]
```

---

## 三、 核心机制与算法细节

### 1. 树状大纲细化算法 (Hierarchical Outline Expansion)
DOC 将大纲详尽化（Detailed Outlining）视为一棵树的生长过程。
*   **根节点**：100 字的故事主旨。
*   **子节点（一级分支）**：章节纲要。每个章节约 150 字描述。
*   **叶节点（二级分支 - 详尽卡）**：将每个章节进一步拆分为 4~6 个“段落卡（Paragraph Cards）”。每个段落卡规定了当前 200 字正文必须包含的具体动作细节、提及的实体状态变化。

### 2. 段落控制器工作流 (Paragraph Controller)
大纲控制器在每一轮段落写作中起主导控制作用：
1.  **约束提取**：提取当前段落卡 $C_i$ 规定的微观约束。
2.  **注意力锚定 (Attention Anchoring)**：在 prompt 中，通过特定的强隔离边界（如 XML 标签），将 $C_i$ 框起来，命令 Generator：`“本段落只允许且必须完成 <card> 中的事件，严禁涉及卡片之外的任何情节推进。”`
3.  **合规性比对**：段落写完后，由控制器比对正文是否已将 $C_i$ 的约束要素写出。若漏写（如漏掉了 Mary 生气这一事实），则强制 Generator 在下一段落中补写，或者回滚重写当前段。

---

## 四、 Engineering & Prompts

在 DOC 的工程实现中，大纲细化器使用如下 prompt 格式来生长“详尽大纲树”：

```
[System Prompt]
你是一个大纲细化器（Detailed Outliner）。你的职责是将以下给定的“粗略章节大纲”展开为 4 个极其具体的“段落写作卡片（Paragraph Cards）”。
每个卡片必须限制在 80 个字内，且只描述一个核心事件或角色的动作，为下一阶段的执笔模型提供硬约束。

【粗略大纲】
John 在茶馆与 Mary 谈判玉佩的下落。谈判最终因 John 的态度傲慢而破裂。

【请输出详尽段落卡片】
- 卡片 1 (环境与入场)：描写暴雨中茶馆的死寂，John 独自喝茶，Mary 撑伞推门坐到其对面。
- 卡片 2 (对话切入)：Mary 开门见山，要求 John 归还古玉。John 并不正面回答，而是讥讽 Mary。
- 卡片 3 (冲突升级)：Mary 怒斥 John 的无耻。John 冷笑，右手按压刀柄，展现威胁姿态。
- 卡片 4 (谈判破裂)：Mary 拍案而起，怒视 John 后拂袖而去，John 留在茶馆内脸色阴沉。
```

### 实验结论：
在长篇故事生成的实验中，DOC 与 baseline 线性生成模型对比：
*   **全局情节契合率 (Global Plot Adherence)** 提升了 **28.4%**（故事完全遵循预定路线，没有发散）。
*   **人设与背景连贯性 (Consistency)** 获得显著改善。
*   有效解决了长文本生成中“模型写着写着就把主线大纲抛到脑后，自顾自水字数”的问题。
