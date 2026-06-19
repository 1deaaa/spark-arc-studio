# StoryAlign: Self-Improving Writer-Reviewer Agent Pairs

*   **论文链接：** [https://arxiv.org/abs/2602.04560](https://arxiv.org/abs/2602.04560)
*   **发布时间：** 2026年2月
*   **核心领域：** 推理期算力扩展 (Inference-Time Scaling)、最佳候选片段选择 (Best-of-N Sampling)、Writer-Reviewer 对齐博弈

---

## 一、 核心贡献与思想

大模型在生成小说正文时具有一定的**随机性**。直接生成的单条文本（Single-pass generation）往往无法兼顾“文字的流畅文学性”与“与大纲/事实的一致性”。

StoryAlign 提出了 **“智能体写-审结对（Writer-Reviewer Agent Pairs）”** 的博弈自对齐机制。它认为，与其花费巨大精力去训练一个懂全局故事逻辑的单一庞大模型，不如在生成阶段（推理期）扩展算力：由 Writer Agent 一次性生成 $N$ 个不同的故事后续草稿（Candidates），由 Reviewer Agent 依据大纲、世界观和人设进行多维评分，并训练一个 self-improving 的奖励模型来选择分数最高（Best-of-N）的草稿作为最终成稿。

---

## 二、 系统架构 (System Architecture)

StoryAlign 由生成生成支路（Writer）、审查评估支路（Reviewer）以及最佳样本对齐回路（Best-of-N Selector）构成：

```mermaid
graph TD
    Prompt[故事当前上下文 + 大纲约束] -->|1. 并行采样 (Temp=0.8)| WriterAgent[写作智能体 Writer Agent]
    
    WriterAgent -->|生成 Candidate 1| C1[草稿 1]
    WriterAgent -->|生成 Candidate 2| C2[草稿 2]
    WriterAgent -->|生成 Candidate N| CN[草稿 N]
    
    C1 & C2 & CN -->|2. 多维度评分| ReviewerAgent[评审智能体 Reviewer Agent]
    
    subgraph 评审维度 (Reviewer dimensions)
        ReviewerAgent -->|人设一致性评分| CharacterScore[人设分]
        ReviewerAgent -->|冲突张力评分| TensionScore[张力分]
        ReviewerAgent -->|逻辑因果判定| CausalScore[因果分]
    end
    
    CharacterScore & TensionScore & CausalScore -->|3. 加权汇总| RewardModel[自改进奖励模型 Reward Model]
    RewardModel -->|4. 挑选最优成稿| BestOfN[Best-of-N 选择器]
    
    BestOfN -->|落盘保存| FinalOutput[最终小说正文]
    BestOfN -->|Feedback 提供负反馈样本| AlignmentLoop[自对齐训练回路]
```

---

## 三、 核心机制与算法细节

### 1. 推理期最佳选择 (Best-of-N Sampling)
在大模型温度（Temperature）设为 0.8 时，Writer Agent 的随机性会产生很多文学性极强但逻辑偶尔偏离的文笔片段，或者逻辑严密但文字生硬的片段。
StoryAlign 让 Writer 同时生成 $N$ 个（例如 $N=8$）短文片段。

### 2. 评审维度与自对齐奖励模型 (Reward Model)
Reviewer Agent 对每一个草稿进行高强度的三维评分：
*   **Persona Score (人设分)**：比对草稿中的对话和动作是否与预设的角色卡吻合。
*   **Plot Entailment Score (情节因果分)**：比对草稿是否符合当前章节的情感节拍和因果约束。
*   **Literary Quality Score (文学性分)**：评估文字的描写密度和对话张力。

这三项分数通过加权获得最终评定分：
$$Score_{total} = w_1 \cdot Score_{Persona} + w_2 \cdot Score_{Plot} + w_3 \cdot Score_{Lit}$$
选择得分最高的草稿，将其写入最终成稿。

### 3. 自我提升对齐 (Self-Improving Pairwise Alignment)
系统会收集得分最高的优秀样本（作为 $y_w$）与得分最低的劣等样本（作为 $y_l$），形成成对的偏好数据集 $(x, y_w, y_l)$。在后台异步通过 DPO（Direct Preference Optimization）微调 Writer 模型，使 Writer 在后续生成中自发产生高分的草稿，从而让博弈环自我进化。

---

## 四、 工程实现与数据流设计 (Engineering & Prompts)

在 StoryAlign 的工程实现中，Reviewer 智能体的打分 prompt 设计如下：

```
[System Prompt]
你是故事评审专家（Reviewer Agent）。请针对以下给出的“故事草稿”，对比“大纲与人物约束”，进行 1 到 10 分的打分。

【故事大纲约束】John 目前正隐藏身份伪装成书生，且左臂受了重伤。
【人物卡片】John：高傲，行事冷静，不苟言笑。

【评估草稿】
“John 哈哈大笑起来，左臂猛地一挥，拍了拍 Mary 的肩膀说道：‘兄弟，你这主意不错！’...”

【打分逻辑与输出】
请输出以下 JSON 格式的打分及理由：
{
  "persona_score": 2, // 理由: John 性格高傲冷静，不符合“哈哈大笑、大呼兄弟”的豪爽设定。
  "factual_consistency_score": 1, // 理由: 前文规定 John 左臂重伤，不可能“左臂猛地一挥拍人肩膀”。
  "tension_score": 4, 
  "justification": "草稿严重违反了 John 的外貌特征与行事人设，属于逻辑冲突样本。"
}
```

### 实验结论：
*   在 Best-of-8 的采样评估中，StoryAlign 使得生成的长篇故事：
    *   **人设一致性 (Persona Coherence)** 相比单次直接生成提升了 **29.3%**。
    *   **文学性与遣词造句质量** 大幅超过了常规的 RAG 续写。
    *   有效消除了模型由于随机采样而发生的“高频逻辑神游”和“语气突然崩塌”。
