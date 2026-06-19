# CreAgentive: An Agent Workflow Driven Multi-Category Creative Generation Engine

*   **论文链接：** [https://arxiv.org/abs/2509.26461](https://arxiv.org/abs/2509.26461) (ICLR 2026 提交)
*   **发布时间：** 2025年9月
*   **核心领域：** 故事原型解耦、知识图谱与语义三元组表征、多流派写作引擎

---

## 一、 核心贡献与思想

CreAgentive (An Agent Workflow Driven Multi-Category Creative Generation Engine) 针对大模型在进行创意写作（Creative Writing）时，经常因为**同时需要思考“故事的逻辑骨架（Plot Logic）”与“文辞修饰风格（Style/Prose）”而导致上下文过载**，最终两头不讨好（故事漏洞百出，且文字缺乏文采）。

CreAgentive 提出了 **“故事原型（Story Prototype）”** 的核心概念。它将故事的创作解耦成两个互不相干的层级：
1.  **剧情逻辑层 (Logic Layer)**：使用基于知识图谱的语义三元组（Semantic Triplets）和因果网络表示故事。
2.  **文笔修饰层 (Realization Layer)**：将剧情骨架翻译成具体小说流派风格的语言。
这种做法既保障了超长文本中情节逻辑的绝对严密，又支持通过更换文风包将同一个故事骨架“翻译”为完全不同的文学风格。

---

## 二、 System Architecture

CreAgentive 由三个阶段（初始化大纲、图谱实例化、文字具象化）的智能体工作流构成：

```mermaid
graph TD
    UserQuery[用户创作需求] -->|阶段 1: 骨架初始化| InitAgent[大纲智能体 Initialization Agent]
    InitAgent -->|生成大纲| DraftSkeleton[故事概念骨架]
    
    DraftSkeleton -->|阶段 2: 图谱实例化| GraphPopulator[图谱填充智能体 Group]
    GraphPopulator -->|提取实体/动作/因果边| StoryPrototype[故事原型知识图谱 Story Prototype]
    
    StoryPrototype -->|阶段 3: 文字翻译 (Realization)| WriteAgent[执笔智能体 Realization Agent]
    StyleProfile[风格包/文体克隆 Profile] --> WriteAgent
    
    WriteAgent -->|翻译输出| FinalNovel[最终的文学作品正文]
```

---

## 三、 核心机制与算法细节

### 1. 故事原型表示 (Story Prototype Representation)
故事原型是一套无流派倾向的知识图谱，通过 **语义三元组** 对小说核心要素进行静态与动态描述：
*   **静态要素 (Static State)**：包含实体（角色、物品、地点的属性）。例如：`("John", "attribute", "blind_in_left_eye")`。
*   **动态事件 (Dynamic Events)**：包含动作因果。例如：`("John", "steals", "white_jade_pin")` 以及 `("steals_action", "causes", "mary_anger_state")`。
这种图表征使得创作者（和 Critic 智能体）可以像调试代码一样，通过查询图中的有向无环图（DAG）结构，在动笔前验证逻辑的一致性。

### 2. 逻辑与文风解耦生成 (Decoupled Realization)
在文字具象化阶段，执笔智能体（Writing Agent）只做一件事：**将给定的三元组动作序列和角色静态特征翻译成文章**。因为剧情逻辑已经由上游的“故事原型”强力框死，Writing Agent 可以将 100% 的上下文和注意力花在“遣词造句、修饰手法、文风匹配”上。

*   **多文体克隆能力**：
    由于输入是逻辑中立的图谱，通过在阶段 3 载入不同的 `Style Profile`，Writing Agent 可以将同一个故事原型翻译为：
    *   **Wuxia Genre (武侠网文风)**：`“John 冷哼一声，右手化作一道残影直取 Mary 怀中...”`
    *   **Sci-Fi Genre (科幻风)**：`“John 的生化义体瞬间超载，执行抢夺 Mary 纳米核心的程序...”`

---

## 四、 工程实现与数据流设计 (Engineering & Prompts)

在 CreAgentive 实验中，从 Prototype 到文学正文的数据流逻辑如下：

### 1. 实例化图谱生成的 Prompt
```
[System Prompt]
你是一个故事原型构建器。请将大纲拆解为由 (主语, 谓语, 宾语) 构成的语义三元组图谱，并用 JSON 形式表达。
必须包含三类关系：
- attribute (属性：角色特征、外貌、物品归属)
- action (动作：角色执行的特定因果事件)
- causality (因果：一个动作导致了某种结果状态)
```

### 2. 执笔 Realizer 的输入数据结构
```
[Realizer Input]
【故事逻辑原型】
- 属性：John (外貌: 独眼且左脸有疤)
- 属性：Mary (情感状态: 极度戒备 John)
- 动作三元组：
  1. (John, 递出, 一杯热茶)
  2. (Mary, 挥手拍落, 热茶)
  3. (John, 左手按压, 长刀刀柄, 强忍杀意)
- 风格包 (Style Profile)：古典仙侠风格，用词需优雅、含蓄，避免现代词汇。

请将上述逻辑动作序列翻译成 800 字的小说正文。
```

### 实验结论：
*   CreAgentive 架构在大长篇故事生成的多流派适配性实验中：
    *   **情节因果错误率 (Causality Error Rate)** 降低了 **42.3%**。
    *   **风格拟真度 (Prose Style Fidelity)** 提升了 **35.1%**。
    *   有效消除了 LLM 混合“构思”与“写作”时容易出现的文字干瘪、啰嗦、情节混乱的痼疾。
