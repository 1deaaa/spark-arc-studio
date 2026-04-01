# Director Agent 创作链路能力汇报

## 概述

本报告详细分析 SparkArc 系统中导演 Agent (Director) 是否具备从生成灵感到完成每一篇章剧本生成的完整创作链路能力，以及能否实现自动化不间断执行。

---

## 一、导演 Agent 架构分析

### 1.1 核心配置 (`@/server/agents/prompts/director.yaml:1-37`)

**职责定义：**
- 理解用户意图并转化为可执行任务
- 自主决策与任务分解
- 多轮协调与进度跟踪
- 汇总反馈并推进下一步

**创作原则链（核心方法论）：**
```
灵感 → 设定 → 梗概 → 节奏 → 大纲 → 写作
```

**工具使用原则：**
- 通过 `delegate_task` 委派任务给专家
- 提供完整上下文（世界观、角色、当前进度）
- 选择合适的 `completion_mode`：
  - `silent_continue`：静默执行后继续下一步（**实现不间断自动化的关键**）
  - `return_to_director`：执行后返回导演继续调度
  - `report_to_user`：执行后向用户汇报

### 1.2 实现层 (`@/server/agents/agent_director.py:1-70`)

**类继承：**
```python
class DirectorAgent(SparkBaseAgent):
    # 继承通讯基类，具备信标/号角/旗帜三件套
```

**动态能力构建：**
```python
def _build_team_capability_block(self) -> str:
    # 构建团队成员能力块，列出所有专家及其工具
    # 让 LLM 了解可以委派给谁、对方能做什么
```

**关键发现：** 导演 Agent 的系统提示词会动态注入所有专家的能力列表，使其具备全局视野进行智能调度。

### 1.3 可用工具 (`@/server/agents/agent_tools.py:1187`)

```python
DIRECTOR_TOOLS = [list_chapters, read_chapter_scene, delegate_task]
```

- `list_chapters`：了解项目章节结构
- `read_chapter_scene`：读取具体章节/场景内容
- `delegate_task`：**核心调度工具**

---

## 二、DirectorGraph 调度引擎

### 2.1 架构设计 (`@/server/agents/director_graph.py:1-566`)

系统采用 **LangGraph StateGraph** 实现导演调度，这是实现不间断自动化的技术基础。

**状态定义：**
```python
class DirectorState(TypedDict):
    user_id: str
    project_name: str
    messages: list              # 对话历史
    active_context: str         # 当前上下文
    pending_delegate: dict      # 待委派任务
    sub_agent_result: str       # 子 Agent 执行结果
    baton_holder: str           # 旗帜持有者（任务链控制权）
    stream_events: list         # 流事件记录
```

**图结构：**
```
START → director_node → [条件路由]
                           ↓
                     sub_agent_node → [条件路由]
                           ↓                ↓
                       director_node        END
```

### 2.2 核心机制

**Sentinel 拦截机制：**
```python
# delegate_task 工具不直接执行，而是返回特殊标记
return f"__DELEGATE__:{json.dumps(handoff_payload)}"
```

**流程控制：**
1. `director_node` 驱动 LLM，检测工具调用
2. 若检测到 `__DELEGATE__:` Sentinel，暂停当前节点
3. 将任务载荷传递给 `sub_agent_node`
4. `sub_agent_node` 执行目标专家的完整 `chat_stream`
5. 根据 `completion_mode` 决定返回 `director_node` 还是终止

**旗帜传递机制：**
- `baton_holder` 追踪当前任务链控制权
- 委派时：导演 → 专家
- 完成时：专家 → 导演（`return_to_director` / `silent_continue` 模式）

### 2.3 路由逻辑

**委派后路由：**
```python
def route_after_director(state):
    if state.get("pending_delegate"):
        return "sub_agent"  # 有待委派任务，进入子 Agent 节点
    return END              # 无任务，终止

def route_after_sub_agent(state):
    completion_mode = delegate.get("completion_mode")
    if completion_mode in {"return_to_director", "silent_continue"}:
        return "director"   # 返回导演继续调度
    return END              # 向用户汇报后终止
```

---

## 三、专家 Agent 工具矩阵

### 3.1 工具分配表

| Agent | 工具列表 | 创作阶段 |
|-------|---------|---------|
| **Muse** | `rewrite_inspiration` | 灵感生成 |
| **Lorebook** | `rewrite_worldview`, `rewrite_all_characters`, `update_character`, `patch_worldview` | 设定管理 |
| **Showrunner** | `rewrite_synopsis`, `rewrite_beat_sheet`, `rewrite_outline`, `patch_synopsis`, `patch_beat_sheet` | 梗概/节拍/大纲 |
| **Scriptwriter** | `rewrite_script`, `patch_script`, `read_worldview`, `read_character`, `read_synopsis`, `read_beat_sheet`, `list_chapters`, `read_chapter_scene` | 剧本写作 |

### 3.2 工具实现细节

**capture_inspiration (Muse)：**
```python
@tool(args_schema=CaptureInspirationInput)
def capture_inspiration(raw_input: str, style: str = None, ...):
    agent = MuseAgent(user_id)
    result = collect_text_output(agent.execute(context))
    save_result = agent.write_result(result, ...)
    return f"已成功捕获并扩写灵感。\n\n{result}"
```

**rewrite_synopsis / rewrite_beat_sheet / rewrite_outline (Showrunner)：**
- 调用 `ShowrunnerAgent` 的对应生成方法
- 结果持久化到项目文件（`synopsis.json`, `beats.json`, `outline.json`）

**rewrite_script (Scriptwriter)：**
- 调用 `ScriptwriterAgent` 的 `write_script` 方法
- 输出 `.arc` 格式剧本文件

---

## 四、聊天面板 Agent 切换机制

### 4.1 前端实现 (`@/client/src/components/stores/chatStore.ts`)

**会话隔离：**
```typescript
// 按 user + project + agent + contextKey 四维隔离
session = {
    agentId: string,
    contextKey: string,
    history: Message[],
    streamEpoch: number,      // 流版本号，用于检测过期
    abortController: AbortController,
    ...
}
```

**Agent 切换流程：**
```typescript
function setAgent(agentId: string) {
    this._getPrimarySession(agentId, this.primaryContextKey);
    this.primaryAgentId = agentId;
}

function setSessionAgent(sessionId, agentId) {
    this._invalidateSessionStream(sessionId);  // 关键！
    session.agentId = agentId;
    session.history = [];  // 清空历史
    // ...
}
```

**流失效机制：**
```typescript
_invalidateSessionStream(sessionId) {
    session.streamEpoch += 1;
    if (session.abortController) {
        session.abortController.abort('session_invalidated');
    }
    session.sending = false;
    session.toolCalling = false;
    // ...
}
```

### 4.2 后端实现 (`@/server/agents/routes/chat.py`)

**流式处理：**
```python
async def send_chat_message_stream(...):
    agent_inst = _create_agent_instance(agent_id, user_id, project_name)
    async for delta in iterate_sync_iterable_in_thread(
        lambda: agent_inst.chat_stream(message, history, active_context),
        request=request,
        stop_event=stop_event,
    ):
        yield _serialize_stream_event(delta)
```

**导演 Agent 特殊处理：**
```python
if agent_id == "agent_director":
    # 使用 DirectorGraphWrapper 包装 LangGraph 调度
    return DirectorGraphWrapper(user_id, project_name)
```

---

## 五、完整创作链路流程

### 5.1 理论链路

```
┌─────────┐    ┌──────────┐    ┌────────────┐    ┌─────────┐    ┌────────┐    ┌──────────┐
│  灵感   │ →  │   设定   │ →  │    梗概    │ →  │  节拍   │ →  │  大纲  │ →  │   写作   │
│ (Muse)  │    │(Lorebook)│    │(Showrunner)│    │(Showrun)│    │(Showrun)│    │(Scriptwr)│
└─────────┘    └──────────┘    └────────────┘    └─────────┘    └────────┘    └──────────┘
```

### 5.2 导演委派链路

**单步委派示例：**
```
用户: "帮我生成一个科幻悬疑故事的灵感"
    ↓
Director: 调用 delegate_task(
    target_agent = "agent_muse",
    task_description = "生成科幻悬疑灵感",
    completion_mode = "report_to_user"
)
    ↓
Muse: 执行 capture_inspiration → 返回创意种子
    ↓
Director: 汇报给用户
```

**多步链式委派（理论）：**
```
Director: delegate_task(
    target_agent = "agent_muse",
    completion_mode = "silent_continue"  # 关键！
)
    ↓
Muse: 完成灵感生成
    ↓
[自动返回 Director]
    ↓
Director: delegate_task(
    target_agent = "agent_lorebook",
    completion_mode = "silent_continue"
)
    ↓
Lorebook: 完成设定生成
    ↓
[自动返回 Director]
    ↓
... 继续下一步
```

---

## 六、自动化能力评估

### 6.1 ✅ 已具备的能力

1. **完整的工具链**：每个创作阶段都有对应的专家 Agent 和工具
2. **DirectorGraph 调度引擎**：支持多轮状态流转
3. **silent_continue 模式**：支持静默执行后自动返回导演
4. **旗帜传递机制**：追踪任务链控制权
5. **上下文注入**：专家执行时自动获取项目上下文

### 6.2 ⚠️ 当前限制

1. **LLM 决策依赖**：
   - 导演需要自主决定何时使用 `silent_continue`
   - 需要正确构建多步委派的逻辑
   - **风险点**：LLM 可能选择 `report_to_user` 导致链路中断

2. **前端交互中断**：
   ```typescript
   // 用户切换 Agent 时会调用：
   _invalidateSessionStream(sessionId);
   session.abortController.abort('session_invalidated');
   ```
   - 正在执行的多步链会被强制终止
   - **影响**：用户在链式执行期间切换面板会打断流程

3. **状态持久化**：
   - `DirectorState` 存在于内存中
   - 页面刷新后状态丢失
   - **影响**：长链路执行中刷新页面会丢失进度

4. **历史记录隔离**：
   - 每次委派会在目标 Agent 的会话中写入历史
   - 导演的会话历史与专家历史分离
   - **影响**：难以从单一视角追踪完整链路

### 6.3 🔧 技术可行性分析

**实现完整自动化链路需要：**

1. **导演提示词优化**：
   - 明确指示使用 `silent_continue` 进行链式执行
   - 提供标准化的多步委派模板

2. **前端交互保护**：
   - 在链式执行期间锁定 Agent 切换
   - 或提供"后台执行"模式

3. **状态持久化增强**：
   - 将 `DirectorState` 持久化到数据库
   - 支持断点续传

4. **链路进度可视化**：
   - 前端展示当前执行阶段
   - 提供链路进度追踪

---

## 七、结论与建议

### 7.1 核心结论

**导演 Agent 理论上具备完整创作链路的调度能力**，技术架构已支持：

| 能力项 | 支持程度 | 实现位置 |
|--------|---------|---------|
| 任务委派 | ✅ 完整 | `delegate_task` 工具 |
| 多步流转 | ✅ 完整 | DirectorGraph + `silent_continue` |
| 专家工具链 | ✅ 完整 | 各 Agent 工具矩阵 |
| 自动化执行 | ⚠️ 部分 | 依赖 LLM 决策 + 前端配合 |
| 不中断运行 | ⚠️ 限制 | 用户交互可能打断 |

### 7.2 实现不间断自动化的关键路径

**短期优化（提示词层面）：**
```yaml
# director.yaml 增强指令
chain_execution:
  - "当用户请求完整的创作流程时，使用 silent_continue 模式依次委派"
  - "每步完成后自动触发下一步，直到写作完成"
  - "仅在全部完成后使用 report_to_user 汇报"
```

**中期优化（前端层面）：**
- 增加"自动化创作模式"开关
- 链式执行期间禁用 Agent 切换
- 提供链路进度可视化

**长期优化（架构层面）：**
- DirectorState 持久化
- 支持断点续传
- 后台任务队列

### 7.3 当前最佳实践

**推荐使用方式：**
1. 用户明确表达完整创作意图
2. 导演使用 `silent_continue` 模式逐步委派
3. 用户在链路执行期间避免切换面板
4. 完成后导演统一汇报结果

---

## 附录：关键代码引用

### A. delegate_task 工具签名

```python
@tool(args_schema=DelegateTaskInput)
def delegate_task(
    target_agent: str,                    # 目标专家 ID
    task_description: str,                # 任务描述
    delivery_mode: str = "direct_to_user",
    completion_mode: str = "report_to_user",  # 关键参数
    return_to: str = "agent_director",
    grant_baton_to: str = "",
    requires_review: bool = False,
) -> str:
```

### B. completion_mode 选项

| 值 | 行为 | 适用场景 |
|----|------|---------|
| `report_to_user` | 执行后向用户汇报，终止链路 | 单步任务 |
| `return_to_director` | 执行后返回导演，导演继续对话 | 需要导演决策 |
| `silent_continue` | 静默执行后自动返回导演继续调度 | **链式自动化** |

### C. DirectorGraph 流程图

```
┌──────────────────────────────────────────────────────────────────┐
│                         DirectorGraph                            │
│                                                                  │
│  ┌─────────────┐    pending_delegate?    ┌─────────────────┐    │
│  │   START     │ ─────────────────────→ │  director_node  │    │
│  └─────────────┘                         └─────────────────┘    │
│                                                 │                │
│                                    ┌────────────┼────────────┐  │
│                                    ↓            ↓            ↓  │
│                              [sub_agent]  [director]      [END] │
│                                    │            │                │
│                                    ↓            │                │
│                           ┌─────────────────┐  │                │
│                           │  sub_agent_node │  │                │
│                           └─────────────────┘  │                │
│                                    │            │                │
│                    ┌───────────────┼────────────┘                │
│                    ↓               ↓                              │
│              [director]         [END]                            │
│                    │                                              │
│                    └──────────────────────────────────────────────│
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```
