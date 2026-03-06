# ScriptWriter 整改总方案

更新时间：2026-03-06

## 1. 本次整改的目标

本次工作不是全项目底层重构，也不是新功能大爆炸，而是一次 **围绕 ScriptWriter 的规范化整改**。

核心目标只有四个：

1. **把 ScriptWriter 做好**：尽量利用现有数据流，提高上下文准确度，降低风格漂移和“吃书”。
2. **把执行接口抽离出来**：让 GUI、悬浮总控台、Agent tool use、未来 LUI 都能复用同一套执行能力。
3. **废弃旧的 ScriptWriter 相关接口**：不再继续维护旧命名、旧语义、旧流程的遗留接口。
4. **保留现有模块主逻辑**：不在本轮引入角色关系图、防 OOC 规则引擎、语义审计系统、全项目 service 化等大型新增工程。

---

## 2. 本次整改明确不做的事情

以下事项本次 **不做**，避免目标失控：

- 不做全项目彻底重构
- 不做新的数据库层 / 领域模型重建
- 不做角色关系图
- 不做复杂角色状态推导
- 不做防 OOC 规则系统
- 不做语义审计系统
- 不做全项目 tool-first 彻底改造
- 不做新的剧情图谱 / 检索系统
- 不做 beat 到 scene 的复杂自动映射系统

这些内容都属于未来阶段的工作，不在本轮范围内。

---

## 3. 对项目当前状态的判断

### 3.1 ScriptWriter 的真实定位

ScriptWriter 不是单纯的 AI 续写工具，而是：

- 互动叙事最终落地层
- `.arc` 文件的结构化编辑器
- AI 写作能力的执行末端
- 整个创作链路里最容易暴露上下文问题的模块

### 3.2 当前创作链路

项目当前主链路可概括为：

1. 灵感工坊（Muse）
2. 世界观 / 角色设定（Lorebook）
3. 梗概（Synopsis）
4. 节拍表（Beat Sheet）
5. 大纲（Outline）
6. 导出为 `.arc` 文件
7. ScriptWriter 中按文件 / 场景 / 节点精修
8. 自动批量写稿 / 分享 / 播放

### 3.3 当前最主要的问题

1. ScriptWriter 传给 Agent 的上下文偏局部，主要是当前场景，缺少当前文件、结构信息、上游创作结果的稳定注入。
2. ScriptWriter 的执行接口存在旧遗留：
	- `/api/ai/single-node`
	- `/api/ai/multi-node`
3. 新旧接口并存，语义混乱，不利于统一 GUI / Agent / LUI。
4. 悬浮聊天窗口已经是“总控台”雏形，但还没有正式纳入产品和工程规划。
5. 项目已有大量“写入文本 / 搜索替换 / 覆写内容”的能力，但没有统一抽离为可复用执行层。

---

## 4. 本次整改的总体策略

### 4.1 战略原则

本次整改采取以下策略：

#### 原则 A：优先复用现有数据流

不新造大系统，优先复用现有的：

- 世界观文件
- 角色设定文件
- `synopsis.json`
- `beats.json`
- `outline.json`
- 当前 `.arc` 文件
- 当前场景 / 当前节点 / 当前文件路径

#### 原则 B：优先抽离执行能力，而不是堆新路由

不再让“每个页面 / 每个按钮 / 每个 agent”各自写一套执行逻辑。

#### 原则 C：讨论与执行分离

- 讨论：建议、分析、诊断、方案比较，不落盘
- 执行：修改、重写、续写、生成过渡，会落盘

#### 原则 D：悬浮聊天窗口作为总控台纳入正式规划

悬浮聊天窗口不再被视为附属功能，而是：

- 全局交互入口
- Agent 调度中心
- GUI 与未来 LUI 的共享指挥所

#### 原则 E：本轮只做“架构抽离”，不改变任何用户可见行为

这是本轮最重要的落地约束。

所谓“不改变用户可见行为”，包括但不限于：

- 不改变现有按钮位置与交互语义
- 不改变现有全局 Loading 的触发时机、scope、target、文案语义
- 不改变现有流式 / 非流式传输表现
- 不改变现有前端对返回格式的解析方式
- 不改变现有文件落盘位置与文件格式
- 不改变现有 MCP 返回结果的业务语义
- 不改变现有聊天流事件协议
- 不改变现有 ScriptWriter 的 409 缺失信息确认流程

换言之：

> 本轮允许改变“代码组织方式”，不允许改变“功能表现结果”。

---

## 4.2 已追踪确认的现有调用链

以下链路已按“前端入口 / 后端入口 / Agent 或工具 / 文件副作用 / 用户可见表现”进行核对。

### A. 灵感工坊（手动页面）

当前链路：

1. 前端 `handleIgnite()`
2. 先创建空灵感条目
3. 再流式调用 Muse 扩展
4. 后端生成完成后回填该条目的 `content`
5. 前端实时拼接文本并刷新历史

关键事实：

- UI 路径不是“一次生成并保存”，而是“先建条目，再生成，再回填”
- 前端当前依赖纯文本流，而不是 SSE 事件协议
- 当前全局遮罩使用 `scope='muse'`

因此本轮禁止的破坏性改动：

- 不能把 UI 手动路径直接改成 MCP 的一次性保存模式
- 不能把 `/api/ai/muse` 的返回从纯文本流改成 NDJSON / SSE 而不做适配层
- 不能改变 inspirations 条目 `origin='ui'` 的语义

### B. 灵感工坊（MCP）

当前链路：

1. MCP `capture_spark`
2. 直接调用 `MuseAgent.expand_inspiration()`
3. 一次性得到完整文本
4. 直接 `save_inspiration(origin='mcp')`
5. 返回“保存成功 + 原样生成内容”

关键事实：

- MCP 路径不走 `/api/ai/muse`
- MCP 条目 `origin='mcp'`，默认 `unread`
- MCP 工具返回值要求把生成内容完整展示给上游客户端

因此本轮禁止的破坏性改动：

- 不能改变 `origin='mcp'` 对未读计数的影响
- 不能让 MCP 只返回 ID、不返回完整生成内容
- 不能让 MCP 路径偷偷落到 UI 专用的“先建空条目再回填”流程而改变通知语义

### C. Lorebook 工具箱 / 悬浮聊天工具执行

当前链路：

1. 前端走 `/api/chat/send/stream`
2. `agent_lorebook` 根据提示决定是否调用工具
3. 流中发出 `tool_intent_started` / `tool_exec_started` / `tool_exec_finished`
4. 前端 `chatStore` 和工具面板根据事件显示全局 Loading
5. 工具直接写项目文件
6. 前端发出 `lorebook-refresh-*` 事件刷新界面

关键事实：

- 这里用户可见行为高度依赖聊天流事件协议
- 世界观与角色工具的 Loading target 不同：`worldview` / `characters`
- 当前工具执行后的刷新不是自动轮询，而是事件驱动

因此本轮禁止的破坏性改动：

- 不能破坏 `tool_*` 事件名
- 不能改变 `global-loading` 的 scope / target 组合
- 不能把工具执行结果改成“前端自己保存”而移除后端文件落盘

### D. 梗概 / 节拍表 / 大纲页面手动生成

当前链路：

- 梗概：前端读取纯文本流，边收边解析 JSON 字段 `synopsis_text`
- 节拍表：前端先整段积累，再解析 markup
- 大纲：前端先整段积累，再解析 markup；后端可同步保存项目文件与历史

关键事实：

- 三者当前都不是通用聊天流协议
- 三者前端各有自己的解析逻辑
- Outline 还带有 `saveToProject` / `saveToHistory` 语义

因此本轮禁止的破坏性改动：

- 不能直接把这些接口改成聊天 NDJSON 流而不做兼容
- 不能改变 outline 生成后自动存项目 / 存历史的默认语义
- 不能改变节拍表 / 大纲的解析输入格式

### E. ScriptWriter 单段续写

当前链路：

1. 前端 `AiPanel.handleSingleNode()` 调旧接口
2. 后端返回纯文本流
3. 前端把 chunk 逐段追加到当前编辑器文本框
4. 不直接写文件

关键事实：

- 这是“编辑器追加文本”行为，不是“自动落盘”行为
- 当前用户可见结果是边生成边在编辑框出现文本

因此本轮禁止的破坏性改动：

- 不能把它改成直接修改 `.arc` 文件
- 不能把返回格式改成必须前端二次解析复杂事件才能显示文本，除非保留旧适配层

### F. ScriptWriter 多段续写 / 重写场景

当前链路：

1. 前端 `AiPanel.handleMultiNode()` / `handleRewriteScene()` 调 `/api/ai/multi-node`
2. 后端读取项目世界观、角色、目标 `.arc` 文件
3. 生成后直接修改目标 `.arc`
4. 返回 JSON，附带可选 `thought`
5. 前端 reload 当前文件并恢复场景/节点选中
6. 若信息缺失，先返回 409，再由用户确认继续

关键事实：

- 当前是“后端落盘 + 前端重载文件”模式
- 409 确认流程是用户可见行为的一部分
- `thought` 的保留与展示是现有体验的一部分

因此本轮禁止的破坏性改动：

- 不能移除 409 缺失信息确认流程
- 不能把后端落盘改成前端自己拼装写回
- 不能丢失 `thought`
- 不能破坏刷新后恢复场景 / 节点的体验

### G. Bridge 与 Auto-Write

Bridge 当前链路：

- 前端调用 bridge 流式接口
- 服务层收最终结果
- 前端手动选择是否把结果插入场景

Auto-Write 当前链路：

- 前端使用 SSE
- 后端持续推送 `chapter_start` / `writing_scene` / `streaming` / `scene_completed` / `chapter_saved` / `paused` / `complete`
- 前端依赖这些状态更新日志、速度、预览、暂停恢复

关键事实：

- Auto-Write 已经有独立的用户可见状态协议
- Bridge 当前是“生成结果 -> 用户确认插入”，不是直接落盘

因此本轮禁止的破坏性改动：

- 不能改掉 Auto-Write 的状态机字段名
- 不能把 Bridge 变成默认自动写入场景

### H. 通用聊天流

当前链路：

1. 前端统一走 `/api/chat/send/stream`
2. 后端根据 `agentId` 分发到对应 Agent
3. 流式返回 NDJSON 事件
4. 前端统一消费并更新历史、工具状态、推理文本

关键事实：

- 这套是当前悬浮聊天和工具调用的“总线”
- 事件格式已经被多个前端位置依赖

因此本轮禁止的破坏性改动：

- 不能改变 `assistant_delta` / `reasoning_delta` / `tool_intent_started` / `tool_exec_started` / `tool_exec_finished` 的语义
- 不能改变 Lorebook 工具调用在聊天流中的表现

---

## 5. ScriptWriter 本轮整改后的最终定位

### 5.1 ScriptWriter 页面

ScriptWriter 页面在本轮整改后，定位为：

> 面向当前文件 / 当前场景 / 当前节点的专业精修工作台。

它负责：

- 精确场景编辑
- 结构化 `.arc` 操作
- AI 精修执行
- 可视化确认和实时反馈

### 5.2 悬浮聊天窗口

悬浮聊天窗口在本轮整改后，定位为：

> 创作总控台 / 指挥所。

它负责：

- 讨论与反馈
- 轻量修改命令
- 调用已有覆写 / patch 工具
- 将复杂任务转交统一执行接口
- 承接未来 LUI 的主要入口能力

---

## 6. ScriptWriter 本轮只保留的核心能力

本轮后，ScriptWriter 侧的 AI 执行能力收敛为以下几类：

### 6.1 继续写

适用场景：

- 当前节点后续写
- 当前场景末尾续写

### 6.2 局部重写

适用场景：

- 重写当前选中片段
- 重写某一小段对白 / 旁白

### 6.3 重写场景

适用场景：

- 当前场景整体重写

### 6.4 生成过渡

适用场景：

- 前后场景之间补桥段

### 6.5 讨论 / 反馈

适用场景：

- 仅讨论，不直接写入
- 要求 Agent 提建议、分析、方案比较

---

## 7. 轻量 Context Pack 方案（本轮必须实现）

### 7.1 为什么要做

当前 ScriptWriter 的关键问题不是模型能力不足，而是：

> 传给 Scriptwriter 的上下文不够完整、不够稳定、不够规范。

所以本轮必须新增一个 **轻量 ScriptWriter Context Pack**。

注意：

- 它不是全项目新系统
- 不引入复杂推理逻辑
- 只是一个稳定的上下文组装层

### 7.2 Context Pack v1 的结构

建议只包含以下六组：

#### A. `project_meta`

- 当前项目名
- 当前创作模式：`interactive_arc` / `prose_scene`
- 当前视图来源（可选）

#### B. `worldview`

来源：世界观文件

内容：

- 世界观全文或合理截断版

#### C. `characters`

来源：角色设定 + `chr.bind`

内容：

- 角色 ID
- 角色名
- 角色设定正文
- 当前任务选中角色优先

#### D. `story_structure`

来源：

- `synopsis.json`
- `beats.json`
- `outline.json`

内容：

- 梗概正文
- 相关节拍表内容
- 当前文件对应章节的大纲内容

#### E. `local_script`

来源：当前 `.arc` 文件、当前场景、当前节点

内容：

- 当前文件完整 `.arc`
- 当前场景完整 `.arc`
- 当前节点文本
- 当前文件路径
- 当前场景名

#### F. `task_intent`

来源：前端当前操作

内容：

- 操作类型：continue / rewrite_selection / rewrite_scene / bridge / discuss
- 用户 guidance
- 目标段数 / 长度
- 锚点 `last_node_text`

### 7.3 本轮不做的上下文增强项

本轮不做：

- 全书自动摘要系统
- 复杂角色状态推导
- 冲突检测
- 复杂结构校验引擎
- beat → scene 的自动精确定位系统

只要把现有数据源稳定、清晰地送给 Scriptwriter，收益已经足够大。

---

## 8. 执行接口抽离方案

### 8.1 本轮目标

把 ScriptWriter 的“执行能力”从旧遗留接口里抽出来，形成一套统一可复用能力。

但这里的“抽离”不能只理解成 ScriptWriter 单点抽离。

本轮还必须把一个更高层的原则写死：

> 灵感、设定、梗概、节拍、大纲这些前序创作执行域，也必须逐步进入同一种统一执行层模式。

否则即使 ScriptWriter 做好了，前面的 Muse / Lorebook / Showrunner 仍然会继续维持：

- 手动调用一套
- 悬浮聊天一套
- MCP 一套
- 未来外部调用再来一套

那维护成本还是会持续失控。

### 8.2 本轮不要求的事情

本轮不要求：

- 全项目 service 层重构
- 所有模块同时迁移

### 8.3 本轮建议的抽离方式

先在 ScriptWriter 相关模块内部，整理出三个稳定入口函数：

1. `build_scriptwriter_context(...)`
2. `execute_scriptwriter_compose(...)`
3. `execute_scriptwriter_feedback(...)`

由：

- GUI 接口调用
- 聊天 Agent tool 调用
- 后续 LUI 调用

共同复用这三类能力。

### 8.4 前序创作链也要进入统一执行层

除 ScriptWriter 外，本轮总计划还必须明确覆盖以下三个执行域：

#### A. Muse（灵感域）

要覆盖的入口：

- 页面手动点燃灵感
- MCP 捕获灵感
- 悬浮聊天 / Agent 触发灵感扩展
- 未来 A 站 / SAP / 第三方调用

目标：这些入口最终共享同一套基础执行内核。

建议抽离为：

1. `build_muse_context(...)`
2. `execute_muse_expand(...)`
3. `persist_inspiration_result(...)`

#### B. Lorebook（设定域）

要覆盖的入口：

- 页面生成世界观
- 页面生成角色
- 工具箱改写世界观 / 角色
- 悬浮聊天工具调用
- 未来外部调用

目标：这些入口最终共享同一套基础执行内核。

建议抽离为：

1. `build_lorebook_context(...)`
2. `execute_worldview_generate(...)`
3. `execute_character_generate(...)`
4. `persist_worldview(...)`
5. `persist_characters(...)`

#### C. Showrunner（结构域）

要覆盖的入口：

- 页面手动生成梗概 / 节拍 / 大纲
- Showrunner 对话 / 工具改写
- 悬浮聊天调用
- 未来外部调用

目标：这些入口最终共享统一生成 / 保存逻辑。

建议抽离为：

1. `build_showrunner_context(...)`
2. `execute_synopsis_generate(...)`
3. `execute_beat_sheet_generate(...)`
4. `execute_outline_generate(...)`
5. `persist_synopsis(...)`
6. `persist_beat_sheet(...)`
7. `persist_outline(...)`

#### D. ScriptWriter（剧本域）

ScriptWriter 仍然是本轮主战场，但不再被视为唯一需要抽离的地方。

### 8.5 统一执行层的总原则

无论是 Muse、Lorebook、Showrunner 还是 ScriptWriter，抽离后的统一执行层都必须遵守同一套原则：

#### 原则 1：入口可以不同，执行内核必须唯一

允许存在多种入口：

- 项目手动点击
- 悬浮聊天 / Agent tool use
- MCP
- 未来 A 站调用
- 未来 SAP / 第三方服务调用

但这些入口不能各自维护一套业务主逻辑。

#### 原则 2：上下文构造、执行、落盘三段分离

每个创作域最终都应拆为：

1. `build_context`
2. `execute`
3. `persist`

这样未来改模型策略、改提示词策略、改保存语义时，只需要改一处。

#### 原则 3：协议适配层可以多，核心逻辑只能有一处

例如：

- UI 可能需要纯文本流
- 聊天可能需要 NDJSON 事件流
- MCP 可能需要一次性字符串结果

这些都可以存在，但只能是适配层差异，不能是业务执行层分裂。

#### 原则 4：抽离必须保证全链路功能不变

抽离之后：

- 手动调用还能用
- 悬浮窗还能用
- MCP 还能用
- 将来接外部调用也不需要再复制业务逻辑

---

## 9. 新接口收敛方案

### 9.1 旧接口状态

当前旧接口：

- `/api/ai/single-node`
- `/api/ai/multi-node`

问题：

- 语义旧
- 一个纯文本流，一个 JSON 落盘
- 不适合未来统一复用

### 9.2 本轮建议的新主接口

#### A. `POST /api/scriptwriter/compose/stream`

统一处理：

- continue
- rewrite_selection
- rewrite_scene
- bridge

请求参数建议包含：

- `operation`
- `mode`
- `filePath`
- `sceneName`
- `nodeId`
- `selectedCharacterIds`
- `guidance`
- `segmentCount`
- `lastNodeText`

#### B. `POST /api/scriptwriter/feedback/stream`

统一处理：

- 讨论
- 反馈
- 建议
- 诊断

#### C. `POST /api/scriptwriter/autowrite/stream`

统一处理：

- 按章节 / 文件批量写稿

### 9.3 `bridge` 的收敛策略

现有 `/api/bridge/generate/stream` 的底层逻辑可以保留，但前端主入口不再单独强调 bridge 路由，而是通过：

- `compose(operation=bridge)`

统一进入 ScriptWriter 执行链。

---

## 10. 悬浮聊天窗口的正式职责

### 10.1 本轮必须承认的事实

悬浮聊天窗口已经是全局总控台雏形，不应再视为附属功能。

它当前已经具备：

- 主会话
- 多窗口 Agent 会话
- Agent 互斥占用
- Director 分发
- 工具调用显示
- `active_context` 注入

### 10.2 本轮定义的新职责

悬浮聊天窗口负责三类事：

#### A. 讨论

- 问建议
- 做分析
- 让 Agent 提多个方案

#### B. 轻量执行

直接复用现有：

- `rewrite_worldview`
- `rewrite_synopsis`
- `rewrite_beat_sheet`
- `rewrite_outline`
- `patch_worldview`
- `patch_synopsis`
- `patch_beat_sheet`

#### C. 发起重型执行

对于 ScriptWriter 的复杂修改：

- 继续写
- 场景重写
- 局部结构性改写
- 生成过渡

由悬浮聊天窗口发起命令，但底层必须调用统一的 ScriptWriter compose 执行能力。

### 10.3 不建议继续依赖的方式

不应再把复杂 ScriptWriter 改稿建立在：

- `patch_script`
- 纯字符串替换

之上。

它们只适合小范围、明确、低风险的修改，不适合承担 ScriptWriter 主执行链。

---

## 11. 工具层策略

### 11.1 本轮结论

本轮不做“全项目全工具化”，但 ScriptWriter 必须先走出样板。

### 11.2 保留并继续复用的工具

保留用于悬浮聊天窗口和总控台的现有工具：

- `rewrite_worldview`
- `rewrite_synopsis`
- `rewrite_beat_sheet`
- `rewrite_outline`
- `patch_worldview`
- `patch_synopsis`
- `patch_beat_sheet`

### 11.3 保留但降级为兼容层的工具

- `patch_script`
- `rewrite_script`

策略：

- 保留兼容
- 不再继续扩展
- 不作为 ScriptWriter 未来主路径

### 11.4 本轮新增的 ScriptWriter 工具族（建议）

后续新增：

- `scriptwriter_build_context`
- `scriptwriter_compose`
- `scriptwriter_feedback`

这些工具背后调用统一执行层，而不是重复写业务逻辑。

---

## 12. 前端交互整改方向

### 12.1 AI 面板不再强调旧模式名

建议前端逐步从：

- `single-node`
- `multi-node`
- `rewrite-scene`
- `bridge`

迁移到用户任务语义：

- 继续写
- 局部重写
- 重写场景
- 生成过渡
- 讨论建议

### 12.2 讨论与执行分离

建议在产品语义上拆为：

- 讨论：不落盘
- 执行：会真正改稿

### 12.3 实时速度显示统一纳入 compose

当执行类能力统一进入流式 compose 后，可以统一给全局加载和执行界面显示：

- 实时字数
- 输出速度
- 进度文本
- 首字延迟（如后续需要）

---

## 12.4 全局遮罩简单测速方案（本轮建议直接纳入）

### 12.4.1 目标

在不改变任何原有业务功能的前提下，为全局 Loading 遮罩补充一行简单实时统计，例如：

- `已输出 382 字`
- `12.4 字/秒`

本轮目标是“简单测速”，不是复杂性能面板。

### 12.4.2 适用范围

原则上应覆盖所有**真实流式输出**的执行链路，包括：

- 灵感扩展
- 世界观生成
- 梗概生成
- 节拍 / 大纲生成（哪怕前端当前是整段积累后解析，也仍可统计传输速度）
- ScriptWriter 新 compose 流
- Bridge 流
- Auto-Write 流
- 聊天工具执行中，如存在持续文本流，也可视情况纳入

### 12.4.3 前端实现原则

测速逻辑必须是**前端统计**，而不是依赖后端返回速度值。

原因：

- 前端最清楚“用户此刻实际收到多少字符”
- 不需要侵入每个后端端点
- 不会破坏现有返回协议

建议统计项：

1. `startedAt`
2. `firstChunkAt`（可选）
3. `receivedChars`
4. `speed = receivedChars / elapsedSeconds`

### 12.4.4 建议的全局遮罩扩展字段

在现有 `global-loading` bus payload 上新增可选字段：

- `statsEnabled: boolean`
- `statsChars: number`
- `statsSpeed: number`
- `statsFtl: number`（可选，后续再显示）
- `statsLabel: string`（可选，自定义显示文案）

要求：

- 全部为可选字段
- 不传时完全保持当前表现
- 旧调用点无需立刻修改

### 12.4.5 `GlobalLoading` 组件改造要求

`GlobalLoading` 只能做“显示层扩展”，不能承担统计逻辑本体。

也就是说：

- 统计值由调用方算好再传入
- 组件只负责渲染
- 如果没有测速字段，界面保持原样

### 12.4.6 为什么这件事现在就值得做

因为这项改造：

- 不改变生成结果
- 不改变路由语义
- 不改变落盘逻辑
- 不改变旧接口行为

它属于典型的“增强体验但不破坏兼容”的改动。

---

## 12.5 ScriptWriter 两个旧接口删除策略

本轮已明确：

- `/api/ai/single-node`
- `/api/ai/multi-node`

最终都要删除，而不是长期兼容。

### 12.5.1 删除前提

删除前必须满足：

1. 新统一接口已完整覆盖旧能力
2. 前端已不再调用旧接口
3. 用户可见行为已 100% 对齐
4. 回归矩阵全部通过

### 12.5.2 删除原则

必须坚持：

> 先迁移行为，再删除入口。

绝不能：

- 先删旧接口
- 再要求前端适配

---

## 12.6 流接口改造细节

### 12.6.1 `single-node` 的迁移目标

旧行为：

- 返回纯文本流
- 前端逐段追加到当前编辑器输入区域
- 不直接落盘

新目标：

- 底层由统一 compose executor 驱动
- 但对外仍保留一个“文本增量输出模式”供 GUI 使用

换言之：

- 统一 executor 内部可以是结构化流
- 但前端 ScriptWriter 单段续写最终仍应拿到“可直接追加到编辑器的文本流”

### 12.6.2 `multi-node` 的迁移目标

旧行为：

- 请求发送完整上下文
- 后端生成多个节点
- 后端直接修改 `.arc`
- 返回 JSON
- 前端 reload 文件

新目标：

- 底层统一改成流式 compose
- 流中可持续输出 `chunk / progress / stats`
- 生成完成后仍由后端执行最终落盘
- 最终仍返回一个可让前端稳定完成 reload 的完成态结果

### 12.6.3 推荐的统一 compose 事件协议

建议新接口支持如下事件：

- `start`
- `progress`
- `chunk`
- `stats`
- `thought`
- `require_confirmation`
- `done`
- `error`

其中：

#### `progress`

用于显示阶段性文案，例如：

- 正在分析上下文
- 正在生成场景节点
- 正在写入剧本文件

#### `chunk`

用于实时累计输出文本。

#### `stats`

用于输出：

- `chars`
- `speed`
- `elapsed`
- `ftl`（可选）

#### `thought`

用于单独传递当前生成出的思考文本，而不是混在最终正文里。

#### `require_confirmation`

用于承接旧 `409 MISSING_INFO` 语义。

即使迁到新流接口，也必须保留“信息不足，用户确认后继续”的产品行为。

#### `done`

必须包含足够信息让前端完成：

- 是否成功
- 是否已落盘
- 最终 `thought`
- 必要时目标文件 / 场景信息

### 12.6.4 旧接口删除前的兼容桥接

在真正删除旧接口前，建议保留一层适配：

- `single-node`：内部调用 compose，再把 `chunk` 转回纯文本流
- `multi-node`：内部调用 compose，收集结果后转回旧 JSON

这样可以保证：

- 先完成内部收口
- 再完成前端迁移
- 最后删除旧接口

---

## 13. 分阶段实施顺序

在所有阶段之上，再加一个总约束：

> 每一个新抽离出来的能力，第一阶段都必须先作为“内部函数 + 兼容适配层”上线，
> 只有当旧入口仍然返回和过去完全一致的结果后，才允许前端逐步迁移。

### Phase 1：Context Pack 上线

目标：不改产品形态，先提升上下文准确度。

任务：

1. 实现轻量 `build_scriptwriter_context(...)`
2. GUI 与聊天入口统一使用它
3. 把当前文件 / 当前场景 / 梗概 / 节拍 / 大纲稳定注入

### Phase 2：统一执行接口

目标：让 ScriptWriter 只有一个主执行入口。

任务：

1. 新建 `compose/stream`
2. 先让旧接口内部改为调用统一 executor
3. 验证旧接口对前端表现零变化
4. 再让前端逐步改接 compose
5. 旧接口进入兼容层

### Phase 3：统一反馈接口

目标：把讨论从执行里拆出去。

任务：

1. 新建 `feedback/stream`
2. 悬浮窗口与 ScriptWriter 讨论模式都可接入

### Phase 4：工具抽离

目标：让 GUI / 悬浮总控台 / Agent tool use 共用执行逻辑。

任务：

1. 新增 ScriptWriter 工具族
2. 将 compose / feedback / context 统一给工具层使用

### Phase 5：旧接口正式退役

目标：清理遗留。

任务：

1. 前端不再调用旧接口
2. 后端旧接口仅留兼容和警告
3. 文档与注释全面更新

注意：

- “退役”不等于立刻删除
- 必须先确认所有用户可见路径都已迁移并经过回归验证
- MCP / 聊天流 / 页面专用流各自的协议适配器都必须先稳定

---

## 14. 本轮整改的最终成果标准

如果本轮整改成功，应该达到以下结果：

### 用户侧

- ScriptWriter 更懂前情
- 风格漂移明显减少
- “吃书”减少
- 讨论与执行更清晰
- 悬浮聊天窗口真正成为总控台

### 工程侧

- ScriptWriter 关键能力有统一上下文构造逻辑
- 新执行接口可被 GUI / 悬浮聊天 / Agent 复用
- 旧 ScriptWriter 接口不再是主路径
- 为未来 LUI 铺平路径

---

## 15. 一句话总结

本轮整改不是革命，而是一次非常明确的工程规范化：

> 利用现有数据流，把 ScriptWriter 做成高质量的创作末端；
> 把执行接口抽离出来，实现 GUI、悬浮总控台、Agent tool use 的统一复用；
> 并在不改变任何现有用户可见行为的前提下，让旧 ScriptWriter 接口退出主舞台。
