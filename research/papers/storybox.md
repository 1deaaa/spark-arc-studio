# StoryBox: Collaborative Multi-Agent Simulation for Hybrid Bottom-Up Long-Form Story Generation

*   **论文链接：** [https://arxiv.org/abs/2510.11618](https://arxiv.org/abs/2510.11618)
*   **发布时间：** 2025年10月 (2026年深入迭代)
*   **核心领域：** 多智能体沙盒模拟、自底向上故事生成、涌现式叙事、人物性格张力控制

---

## 一、 核心贡献与思想

传统的大模型小说写作框架（如 Sudowrite 等工业写手）主要依赖“自顶向下（Top-Down）”的规划。即人类或 Planner 事先定死每一个大纲卡片，AI 只是大纲的机械扩写器。这种方式在生成大长篇时极易发生**“剧情套路化、角色像木偶、冲突解决草率、缺乏戏剧张力”**的毛病。

StoryBox 提出了 **“自底向上（Bottom-Up）”** 故事生成的概念。它将小说创作视为一个**“动态物理/社会沙盒（Dynamic Sandbox）”**。在沙盒中，角色被具象化为拥有独立意图（Goals）、秘密（Secrets）、性格基调（Personas）的 Agent。通过运行多 Agent 之间的交互动作决策环，让它们自发演进和博弈，碰撞出意想不到的戏剧冲突。最终，这些“冲突涌现记录”被转换为高度文学化的小说正文。

---

## 二、 系统架构 (System Architecture)

StoryBox 的架构由“沙盒管理器”、“行动决策环”、“世界解释内核（World Kernel）”和“叙事翻译器（Narrative Realizer）”组成：

```mermaid
graph TD
    OutlineConstraints[全局大纲约束/故事框架] -->|初始化环境| SandboxManager[沙盒管理器 Sandbox Manager]
    SandboxManager -->|分配人设/秘密/目标| CharacterAgents[多角色智能体 Character Agents]
    
    subgraph 决策博弈环 (Sandbox Decision Loop)
        CharacterAgents -->|每个 Agent 决定行动| ActionProposals[动作提案 Action Proposals]
        ActionProposals -->|收集汇总| WorldKernel[世界解释内核 World Kernel]
        WorldKernel -->|1. 动作成功率与物理判定| WorldStateUpdate[环境状态与因果树更新]
        WorldStateUpdate -->|2. 反馈结果与新线索| CharacterAgents
    end
    
    WorldStateUpdate -->|3. 拓扑冲突日志| PlotLog[情节日志 Plot Log]
    PlotLog -->|4. 文风转换| NarrativeRealizer[叙事翻译器 Narrative Realizer]
    NarrativeRealizer -->|输出| NovelText[最终的小说/剧本正文]
```

---

## 三、 核心机制与算法细节

### 1. 智能体意图与秘密系统 (Intent & Secret Allocation)
每一个进入沙盒的角色 Agent 并不是只有一张干瘪的人设卡，它必须被赋予两层强约束属性：
1.  **显式意图 (Explicit Goal)**：角色当前急需达成的任务（如：John 想要说服 Mary 透露簪子的下落）。
2.  **隐式秘密 (Implicit Secret)**：角色绝不能被他人知晓的背景（如：John 其实是暗害 Mary 父亲的主谋的密友）。

### 2. 世界解释内核 (World Kernel) 的物理/逻辑判定
动作不能由角色 Agent 自己说了算。比如 Agent A 说 `“我使用迷烟熏晕了 B 抢走了簪子”`。如果允许 Agent 直接决定结果，故事会立刻崩坏。
*   所有的 Action Proposals 会提交给 **World Kernel**。
*   World Kernel 是一个加载了“世界观物理规则”和“环境背景”的第三方中立 LLM。
*   它会评估动作的冲突。例如：`“由于 B 警惕性极高，且身手敏捷，A 的迷烟下毒动作失败了，B 听到了异响，警觉地握紧了武器，冲突升级。”`
*   这种判定方式保证了情节的高逻辑合理性。

### 3. 情节冲突日志 (Plot Log) 与文学化转换 (Narrative Realizing)
博弈环运行 5-8 轮后，沙盒管理器会收集这几轮的动作和环境解释轨迹，称之为 `Plot Log`（里面全都是 A 说了什么、B 怎么防备、现场发生了什么物理变化）。
最终，`Narrative Realizer` 将这份干瘪的逻辑博弈日志翻译成精美的小说语言，添加环境烘托、人物心理以及生动的对话细节，使小说读起来既自然流畅，又具备极强的情节拉扯感。

---

## 四、 工程实现与数据流设计 (Engineering & Prompts)

在 StoryBox 的工程实现中，World Kernel 使用了如下 prompt 模板进行动作博弈判定：

```
[System Prompt]
你是沙盒故事引擎的世界解释内核（World Kernel）。你负责维护故事里的物理规律、逻辑合理性和角色的信息差。
你目前收集了以下角色在当前场景中的“动作提案”：

【当前环境】
- 地点：客栈二楼天字号房
- 物理状态：暴雨击打着窗户，房间内没有点灯，十分昏暗。

【动作提案】
1. 刺客 A：偷偷潜入窗台，从背后用匕首刺向客人的后脑。
2. 侠客 B：正在房间内打坐，时刻注意着窗外的风吹草动。

请判定这组动作的交互结果，你的判定必须符合以下原则：
- 动作不能无障碍成功，必须根据双方的属性和环境给出合理的对抗结果。
- 请输出冲突结果，更新环境物理状态，并以 JSON 格式输出给双方 Agent 接收的新现场信息。
```

### 实验结果：
在生成 10,000+ 字以上的长篇段落时，StoryBox 与传统大纲驱动的 baseline 相比：
*   **读者满意度 (Human Evaluation on Plot Tension)** 提升了 **38.7%**（情节张力和悬念极其出色）。
*   **角色行为真实度 (Character Consistency)** 提升了 **26.4%**（角色不再是工具人，而是表现出强烈的性格自主度）。
*   有效解决了长篇小说中“反派智商突然下线”或“冲突解决平淡、草率”的致命通病。
