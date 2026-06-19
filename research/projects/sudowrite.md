# Sudowrite: Ghostwriter Card-based Beats Pipeline

*   **项目官网链接：** [https://www.sudowrite.com/](https://www.sudowrite.com/)
*   **流行/商业化时间：** 2023–2026年 (大模型商业写作先驱，以 Ghostwriter 引擎闻名)
*   **核心领域：** 商业化长篇写作、卡片式大纲、节拍（Beats）扩写、文风匹配

---

## 一、 核心目标与商业化解决痛点

在使用大模型进行长篇叙事（例如一次性生成 3000 字的一幕章节）时，创作者通常会面临以下两个痛点：
1.  **剧情极速崩塌/细节缺失**：直接让 AI 写 3000 字，AI 往往在 500 字内就把剧情草草收尾。例如大纲要求“John 与 Mary 在茶馆经历了一场艰难的谈判并最终破裂”，AI 会直接写 `“两人坐下，谈了谈，谈崩了，然后走了”`，缺乏动作描写、环境渲染与对话的拉扯。
2.  **文笔失配**：生成的文本缺乏作家的个人文笔风格，缺乏描写密度。

Sudowrite 的核心解决方案是：**“卡片式节拍细化流水线 (Card-based Beats Pipeline)”**。它将写作解构为极小粒度的“节拍”，每次只生成一个节拍对应的 300 字正文，最终拼装成 3000 字场景。

---

## 二、 系统架构设计 (Architecture)

Sudowrite 废弃了直接续写的长上下文模式，采用了一个由 **“场景卡片 -> 节拍拆解 -> 分步执笔 -> 样式克隆”** 组成的流水线架构：

```mermaid
graph TD
    Synopsis[用户初始故事梗概] -->|生成| OutlineCards[场景大纲卡片 Board]
    
    OutlineCards -->|1. 拆解阶段: Beat Generator| BeatsList[场景节拍卡片列表 Beats Card List]
    BeatsList -->|Beats 包含 10 个 100 字微动作描述| WriterEngine[2. 执笔引擎: Writer Engine]
    
    subgraph 执笔与文风克隆 (Ghostwriter Kernel)
        WriterEngine -->|只输入最近 1 个已写前文 + 当前 1 个 Beat| Generator[执笔 Generator]
        StyleProfile[用户自选文风克隆 Profile] --> Generator
    end
    
    Generator -->|循环 10 次生成| Sentence1[正文段落 1] & Sentence2[正文段落 2] & SentenceN[正文段落 N]
    
    Sentence1 & Sentence2 & SentenceN -->|合并拼接| FinalScene[最终 3000 字长场景正文]
```

---

## 三、 核心机制与算法细节

### 1. 场景节拍生成器 (Beat Generator)
当作家点击某个“场景卡片”开始写作时，系统第一步不是写文章，而是使用 LLM 将该场景大纲自动拆解为 **8 到 12 个“Beats（节拍）”**。
*   *场景大纲*：John 与 Mary 在茶馆交接玉佩并发生争吵。
*   *拆解后的 Beats 列表*：
    1.  描写茶馆昏暗、诡异的气氛和外面倾盆的大雨。
    2.  John 坐在角落的桌子旁，紧张地捏着茶杯，Mary 推门而入。
    3.  Mary 走到 John 对面坐下，小二上茶。
    4.  Mary 开门见山，要求 John 归还白玉簪，John 冷笑。
    5.  ...（以此类推，将细节推进到极致）。

### 2. 分步执笔与上下文裁剪 (Incremental Generation)
在生成第 4 个 Beat 的正文时，执笔 Generator 的输入中：
*   **不需要**包含第 5 个到第 12 个 Beat 的内容（物理未来隔离）。
*   **不需要**包含第 1 到第 2 个 Beat 的正文全文（只保留第 3 个 Beat 的正文作为最近前文）。
*   只关注当前 Beat 4 规定的动作：`“Mary 要求 John 归还白玉簪，John 冷笑”`。
由于模型在这一步只需要专注于这 80 个字的微观描述，它可以用极其细腻的动作和心理活动将其扩写为 300 字，完全避免了剧情的大跨步跳跃和敷衍。

---

## 四、 工程实现与数据流设计 (Engineering & Prompts)

在 Sudowrite 的 Ghostwriter 引擎中，执笔器的数据流拼装如下：

```
[System Prompt]
你是一位顶尖的协作写手。请将给定的【当前要写的节拍 (Current Beat)】扩写为 300-400 字的精美小说正文。

【风格克隆参考 (Style Profile)】
- 词汇密度：高
- 描写偏好：侧重环境的触觉和听觉描写，多用比喻。
- 对白比率：40%

【极近前文 (Previous Context)】
（此处拼入上一个 Beat 生成的正文，如：John 摩挲着温热的茶杯，Mary 撑着油纸伞推开茶馆的旧门，伞尖的水滴落在地板上，啪嗒作响...）

【当前要写的节拍 (Current Beat)】
Mary 走到 John 的对面拉开椅子坐下，两人相对无言，气氛冰冷。

【输出】
请开始撰写正文。
```

### 开源与工业价值：
Sudowrite 的成功证明了，**将长长的大纲分割成极细的物理“节拍卡片”**，是目前商业写作中解决 AI 废话和剧情跳跃最直接、最容易落地的工程方案。
