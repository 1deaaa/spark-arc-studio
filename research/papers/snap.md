# SNAP: Story and Narrative-based Agent with Planning

*   **论文链接：** [https://arxiv.org/abs/2501.11600](https://arxiv.org/abs/2501.11600)
*   **发布时间：** 2025年1月
*   **核心领域：** 规划驱动的智能体、时空一致性、叙事单元 (Cell) 表征、交互式故事生成

---

## 一、 核心贡献与思想

在交互式故事生成或拥有大量探索元素的小说中，智能体容易发生 **“时空穿梭”** 或 **“历史因果混乱”**。例如，前一秒在森林，后一秒在没有任何移动暗示的情况下瞬间出现在城堡；或者发生了与主线计划相左的分支情节。

SNAP 提出了 **“基于 Cell 规划的叙事智能体”**。它将叙事空间和时间节点定义为离散的“Cell”（单元）。每一个 Cell 包含严格的实体列表、物理位置连通边、以及前置剧情解锁开关。角色智能体的行动和情节生成，必须在 Cell 图谱所规定的路径和前置条件约束下进行，以此确保了即便在大规模、多分支的超长叙事中，也绝不发生时空或因果逻辑混乱。

---

## 二、 系统架构 (Architecture)

SNAP 由空间-事件 Cell 拓扑图、剧情规划器（Narrative Planner）和场景生成智能体（Scene Generator）构成：

```mermaid
graph TD
    NarrativeGoal[全局故事目标/结局] -->|编译| NarrativePlanner[剧情规划器 Narrative Planner]
    
    subgraph 叙事单元空间 (Cell-based Map)
        CellA[Cell 1: 森林 <br> 实体: 猎人A, 宝玉] -->|移动路径/解锁条件: 获得玉佩| CellB[Cell 2: 城堡门外 <br> 实体: 守卫]
    end
    
    NarrativePlanner -->|管理当前进度| ActiveCell[当前活跃的 Cell 状态]
    ActiveCell -->|限制活动边界与实体| SceneGenerator[场景生成智能体 Scene Generator]
    SceneGenerator -->|用户/环境输入| ActionDecider[行动决策]
    ActionDecider -->|改变实体与解锁开关| ActiveCell
```

---

## 三、 核心机制与算法细节

### 1. 叙事单元 (Cell) 的数据模型
每一个 Cell 是一个包含物理空间属性与叙事逻辑状态的独立结构：
```json
{
  "cell_id": "cell_02_castle_gate",
  "location_name": "城堡东侧偏门",
  "connected_cells": ["cell_01_forest", "cell_03_throne_room"],
  "allowed_entities": ["John", "Castle_Guard_NPC"],
  "pre_requisites": {
    "items_required": ["magic_token"],
    "completed_events": ["met_forest_hunter_event"]
  },
  "narrative_goals": {
    "pacing": "slow_tension",
    "required_dialogues": [("John", "Castle_Guard_NPC", "request_entry")]
  }
}
```

### 2. 状态驱动的剧情规划器 (State-driven Narrative Planner)
剧情规划器监控所有 Cell 的状态。只有当 John 的当前位置在 `cell_01_forest`，且获取了 `magic_token`，触发了与猎人的对话，规划器才会“点亮” `cell_02_castle_gate`，允许 Scene Generator 载入该 Cell 下的环境设定和 Guard 角色。
如果 John 试图提前触发城堡情节，Scene Generator 会因为 Cell 图谱中的 `pre_requisites` 未满足，而拒绝生成进入城堡的文本，从而物理断绝了剧情因果颠倒的可能性。

---

## 四、 工程实现与数据流设计 (Engineering & Prompts)

在 SNAP 的工程实现中，剧情生成的输入受到了当前活跃 Cell 的严格控制：

```
[System Prompt]
你是一个场景发生智能体（Scene Generator）。你的任务是根据当前“活跃叙事 Cell”和玩家动作生成故事内容。

【当前活跃 Cell】
- 地点：城堡东侧偏门 (Cell_02)
- 现场实体：主角 John (携带物: magic_token), 城堡守卫 (状态: 警惕)
- 连通路径：可以返回森林 (Cell_01)，若通过守卫则通往王座厅 (Cell_03)
- 当前任务：John 必须向守卫出示 magic_token 以求进入。

【行动输入】
John 试图越过守卫强行推开偏门。

【生成要求】
因为守卫状态为“警惕”，且 John 并没有出示 token 而是强行推门，请生成一段冲突动作描述，守卫必须拦下 John 并询问。严禁直接生成 John 越过偏门进入王座厅的内容（因为 Cell_03 尚未解锁）。
```

### 实验结论：
在复杂的分支互动和长篇叙事中，SNAP 相比无规划约束的 baseline 模型：
*   **时空与因果连贯性正确率 (Temporal/Spatial Consistency)** 达到了 **94.8%**（完全杜绝了地点瞬移和因果逆序错误）。
*   **支线情节收敛率 (Plot Convergence)** 提升了 **31.2%**，使得多分支故事不会漫无目的地发散到无法收尾的死胡同中。
