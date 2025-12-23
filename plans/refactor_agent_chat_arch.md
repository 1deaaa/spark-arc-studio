# Agent 交互架构重构计划：基于 Session 的精准上下文管理

## 1. 核心目标
构建一套统一的 Agent 交互系统，实现以下目标：
- **精准交流**：用户可针对特定对象（如特定剧本节点、特定灵感条目）与 Agent 进行对话。
- **上下文隔离**：不同对象的修改建议互不干扰（例如：修改“场景A”的建议不应出现在“场景B”的聊天记录中）。
- **统一入口**：前端使用单一悬浮窗组件，根据用户焦点自动切换聊天上下文。

## 2. 架构设计

### 2.1 Session ID 生成规则
所有聊天会话通过唯一的 Session ID 进行索引：
$$ \text{Session ID} = \text{Project\_ID} : \text{Agent\_ID} : \text{Context\_Key} $$

- **Project_ID**: 当前项目标识。
- **Agent_ID**: 目标 Agent 标识 (e.g., `agent_scriptwriter`).
- **Context_Key**: 上下文标识符。
    - 全局模式: `global`
    - 节点模式: `node_{uuid}`
    - 历史条目模式: `entry_{id}`

### 2.2 数据存储结构
在项目目录下新增 `chat_history` 文件夹，按 Agent 分文件存储。

**路径**: `server/_userdata/{uid}/{project}/chat_history/{agent_id}.json`

**JSON 结构**:
```json
{
  "sessions": {
    "global": [
      {
        "role": "user",
        "content": "...",
        "timestamp": 1700000000,
        "context_snapshot": { ... } 
      }
    ],
    "node_abc123": [ ... ],
    "entry_456": [ ... ]
  }
}
```

## 3. 实施步骤

### Phase 1: 后端基础设施 (Server Infrastructure)

#### 1.1 创建 `ChatManager` 类
- **位置**: `server/agents/chat_manager.py`
- **职责**: 负责聊天记录的 CRUD 操作（读取、追加、清空）。
- **接口**:
    - `get_history(agent_id, session_key, limit)`
    - `append_message(agent_id, session_key, role, content, snapshot)`
    - `clear_session(agent_id, session_key)`

#### 1.2 改造 `SparkBaseAgent`
- **位置**: `server/agents/communication.py`
- **改动**:
    - 移除原有的 `self.dialogue_history`（单体历史）。
    - 集成 `ChatManager`。
    - 修改 `receive_message`：解析 `metadata` 中的 `session_key`，将消息路由到正确的 Session 存储中。

#### 1.3 新增 API 路由
- **位置**: `server/agents/routes_agents.py`
- **新增接口**:
    - `GET /api/chat/history/{project_name}`: 获取指定 Session 的历史。
    - `POST /api/chat/history/{project_name}`: 手动追加消息（用户发送）。
    - `DELETE /api/chat/history/{project_name}`: 清空会话。

### Phase 2: 前端交互逻辑 (Client Interaction)

#### 2.1 全局状态管理 (Store)
- 新增 `useChatStore` (Pinia/VueUse):
    - `currentAgent`: 当前激活的 Agent。
    - `contextKey`: 当前上下文 Key (默认 'global')。
    - `contextSnapshot`: 当前选中对象的数据快照。
    - `history`: 当前显示的聊天记录列表。

#### 2.2 悬浮窗组件改造
- 监听 `contextKey` 的变化。
- 当 Key 变化时，自动调用 `GET /api/chat/history` 刷新列表。
- 发送消息时，自动附带 `session_key` 和 `context_snapshot`。

#### 2.3 焦点联动
- 在 **剧本编辑器** 组件中：点击节点 -> 更新 Store 的 `contextKey` 为节点 ID。
- 在 **灵感历史** 组件中：点击条目 -> 更新 Store 的 `contextKey` 为条目 ID。
- 点击空白处 -> 重置 `contextKey` 为 `global`。

## 4. 预期效果
完成重构后，用户在编辑器中点击不同节点，悬浮窗内的聊天记录会自动切换，就像在微信中切换联系人一样流畅。Agent 将能够根据具体的节点历史提供针对性的修改建议。
