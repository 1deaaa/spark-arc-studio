# 悬浮 AI 助手上下文感知与会话管理优化计划

## 1. 问题分析

### 问题一：会话场景（Session）划分不清
**现状**：
- 用户感觉“灵感（Scenes/Nodes）”有独立入口，但“其他（Global/Project）”混在一起，缺乏清晰的历史记录隔离。
- 目前后端存储是基于 `contextKey` (`node_...` 或 `global`)，这其实已经支持了隔离，但用户体验上可能感觉割裂或混乱。

**核心痛点**：
- "我的对话到底基于什么？" -> 用户需要明确知道当前是在和“谁”聊，聊“什么”。
- 全局聊天（Global）缺乏具体的上下文，导致 Agent 表现得像个局外人。

### 问题二：Agent 无法读取和互动内容
**现状**：
- Agent 仅依赖聊天历史 (`history`) 进行回复。
- Agent **看不见** 用户当前编辑器里写的内容（剧本、设定等）。
- 导致 Agent 无法进行“帮我润色这段”、“分析这个角色”等基于内容的互动。

---

## 2. 解决方案：混合上下文注入 (Hybrid Context Injection)

我们不改变底层的存储逻辑（依然按 `contextKey` 隔离历史），而是改变 **Agent 的认知范围**。

### 核心策略
每次对话时，向 Agent 注入 **三层信息**：
1.  **身份层 (Persona)**: Agent 的人设（编剧、导演等）。
2.  **全局层 (Global Context)**: 项目的大纲、世界观摘要（所有会话共享）。
3.  **焦点层 (Active Context)**: 用户当前**正在看/正在写**的内容（由前端实时抓取）。

### 详细实施计划

#### 第一步：前端上下文捕获 (Client Side)
修改 `chatStore` 和 `GlobalChatFloat`，在发送消息时附带当前编辑器状态。

**数据结构**:
```javascript
// 发送给后端的 payload 新增 activeContext 字段
{
  "message": "帮我看看这段对话",
  "contextKey": "node_file::scene::type::id", // 依然用于历史记录隔离
  "activeContext": {
    "type": "scene_node", // 或 'character', 'lore', 'global'
    "id": "node_1",
    "name": "初遇",
    "content": "（剧本正文内容...）", // <--- 关键：把内容传过去
    "cursor": 120 // 可选：光标位置
  }
}
```

#### 第二步：后端 API 升级 (Server Side)
1.  **修改 `ChatSendRequest` 模型**:
    - 在 `server/agents/routes_agents.py` 中增加 `activeContext` 字段。

2.  **修改 `SparkBaseAgent.chat` 方法**:
    - 在 `server/agents/communication.py` 中。
    - 接收 `active_context` 参数。
    - **动态构建 System Prompt**:
      ```text
      [System Prompt]
      你是一个专业的编剧助手。
      
      [Global Project Info]
      Project: <ProjectName>
      Synopsis: <Summary>
      
      [Current Focus]
      User is currently editing: <Name> (<Type>)
      Content:
      """
      <Content>
      """
      
      请基于上述内容回答用户的问题。
      ```

#### 第三步：会话策略明确化 (Session Strategy)
回答用户的第一个问题：“对话session到底应该基于什么分场景？”

**新的定义**：
- **Session (历史记录)**: 基于 **“关注点 (Focus)”**。
    - 当你选中一个节点时，历史记录属于该节点。
    - 当你未选中任何东西时，历史记录属于“项目全局”。
- **Context (认知范围)**: 基于 **“项目 + 关注点”**。
    - 无论在哪个 Session，Agent 都能通过“全局层”知道项目的整体情况。
    - Agent 总是优先关注你“当前打开的内容”。

---

## 3. 执行步骤

1.  **后端**: 更新 `ChatSendRequest` Pydantic 模型。
2.  **后端**: 更新 `SparkBaseAgent` 基类，支持在 Prompt 中插入 `active_context`。
3.  **前端**: 在 `chatStore.js` 的 `send` 方法中，从 `sceneStore` 或 `projectStore` 获取当前文本内容。
4.  **前端**: 传递该内容给后端。

这样，当你问“这段写得怎么样”时，Agent 就能真正“读”到你写的内容并给出反馈了。
