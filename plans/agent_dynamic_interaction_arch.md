# Agent 动态交互机制架构方案

基于“混合式被动插槽”的设计哲学，本方案旨在构建一套灵活、可控且支持用户特权的 Agent 协作网络。

## 1. 核心架构：信号-槽与路由中枢

我们将不再依赖单一的线性流程（A->B->C），而是引入一个**动态路由层**。

```mermaid
graph TD
    %% 核心中枢
    Router{Signal Router<br/>(信号路由中枢)}

    %% 信号源 (Signal Emitters)
    subgraph Signal_Sources [信号源]
        Scriptwriter[Scriptwriter Agent]
        User[User / Feedback Agent]
        System[System Monitor]
    end

    %% 插槽目标 (Slot Targets)
    subgraph Slot_Targets [插槽目标]
        Outline[Outline Agent]
        Char[Character Agent]
        World[Worldview Agent]
    end

    %% 信号流
    Scriptwriter -- "Signal: Request_Refine_Outline" --> Router
    User -- "Signal: User_Intervention (Priority: MAX)" --> Router
    
    %% 路由逻辑
    Router -- "Check: Is_Slot_Open(Outline)?" --> Logic{Logic Check}
    
    Logic -- "Yes / Forced" --> Outline
    Logic -- "No" --> Log[Action Log]

    %% 反馈闭环
    Outline -- "Update State" --> Scriptwriter
```

## 2. 数据结构设计

### 2.1 全局插槽状态表 (Global Slot Registry)
在 LangGraph 的 `State` 中维护一张动态表，记录当前哪些 Agent 开放了哪些插槽。

```python
class AgentSlotState(TypedDict):
    # Agent ID -> 插槽配置
    slots: Dict[str, Dict[str, bool]] 
    # 示例:
    # {
    #   "agent_outline": { "allow_structure_update": True, "allow_title_change": False },
    #   "agent_character": { "allow_new_trait": True }
    # }
```

### 2.2 信号对象 (Signal Object)
Agent 之间不再直接调用函数，而是抛出一个标准化的信号对象。

```python
class AgentSignal(BaseModel):
    source: str          # 发起者 (e.g., "agent_scriptwriter")
    target: str          # 目标 (e.g., "agent_outline")
    intent: str          # 意图 (e.g., "refine_structure")
    payload: Dict        # 数据 (e.g., { "chapter": 3, "suggestion": "增加冲突" })
    priority: int = 1    # 优先级 (1: 普通, 10: 用户强制)
```

## 3. 实现步骤

### 第一阶段：基础设施搭建 (Infrastructure)
1.  **定义 Signal 与 Slot 类型**：在 `server/agents/agent_workflow.py` 中扩展 `State` 定义。
2.  **实现 Router Node**：创建一个通用的路由节点，负责解析 Signal 并分发到对应的 Agent。

### 第二阶段：Agent 改造 (Agent Retrofit)
1.  **Scriptwriter 改造**：
    *   增加“自我反思”能力（或集成 Critic），使其能产生“我想改大纲”的 Signal。
    *   不再直接输出最终剧本，而是先输出“草稿+信号”。
2.  **Outline 改造**：
    *   增加 `update_outline` 插槽（入口函数），接受 Signal 并执行局部更新。

### 第三阶段：特权通道 (Privilege Channel)
1.  **Feedback Agent 升级**：
    *   使其发出的 Signal 默认携带 `priority=10`（最高优先级）。
    *   Router 识别到高优先级信号时，**忽略目标插槽的关闭状态**，强制执行。

## 4. 预期效果

*   **场景 1 (普通纠偏)**：Scriptwriter 觉得剧情平淡 -> 发出信号 -> Router 发现 Outline 插槽开启 -> Outline 增加转折 -> Scriptwriter 重写。
*   **场景 2 (用户干预)**：用户觉得剧情狗血 -> Feedback Agent 发出高优信号 -> Router 强制唤醒 Outline -> Outline 必须修改 -> 剧情重轨。

## 5. 待确认
*   是否需要我为您先创建一个简单的 **Proof of Concept (PoC)**，只实现最核心的“Router”和“Feedback Agent 强制修改”逻辑？
