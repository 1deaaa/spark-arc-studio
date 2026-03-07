# ScriptWriter 执行任务清单

更新时间：2026-03-06

本文档用于指导后续实际开发执行。
目标是：即便中途发生上下文压缩，也能严格按此清单逐步推进，不遗漏关键步骤。

---

## 0. 执行总原则

执行顺序必须遵循：

1. **先文档化**
2. **先 Context，再接口，再前端接入，再工具抽离，再清理旧接口**
3. **每一步都优先复用现有逻辑，不新增大系统**
4. **每一步完成后都要验证没有破坏现有主要链路**

本轮不允许一上来直接大面积改动多个模块。

补充一条最高优先级原则：

5. **先保证旧行为 100% 不变，再谈结构优化**

也就是说，本轮所有抽离都必须满足：

- 旧前端入口还能正常调用
- 旧返回格式不变
- 旧落盘副作用不变
- 旧 Loading 行为不变
- 旧流式事件协议不变
- 旧确认框 / 错误码 / 刷新时机不变

---

## 0.5 第一优先任务：固化兼容矩阵（必须先做）

状态：已完成

### 0.5.1 任务目标

在任何实际抽离之前，先把所有用户可见功能的现有表现固定下来，作为“不可回归”的兼容矩阵。

### 0.5.2 必须固化的链路

#### A. 灵感工坊手动生成

必须确认并记录：

- 先创建 inspirations 条目，再流式生成，再回填 `content`
- 返回为纯文本流
- `scope='muse'` 的 Loading 正常出现与关闭
- 历史灵感刷新时机不变

#### B. 灵感 MCP 捕获

必须确认并记录：

- `capture_spark` 不走 UI 专用 HTTP 端点
- 写入条目 `origin='mcp'`
- 未读计数逻辑只对 `origin='mcp'` 生效
- 工具返回结果必须包含完整生成内容

#### C. Lorebook 工具箱 / 聊天工具执行

必须确认并记录：

- 走 `/api/chat/send/stream`
- `tool_intent_started` / `tool_exec_started` / `tool_exec_finished` 事件完整存在
- `global-loading(scope='world', target='worldview|characters')` 正常
- `lorebook-refresh-*` 事件时机不变

#### D. 梗概 / 节拍 / 大纲页面生成

必须确认并记录：

- 梗概前端的流式 JSON 字段提取逻辑仍可工作
- 节拍表仍按全文积累后解析
- 大纲仍按全文积累后解析
- 大纲默认项目保存 / 历史保存语义不变

#### E. ScriptWriter 单段续写

必须确认并记录：

- 返回纯文本流
- 文本追加到编辑器，不直接落盘

#### F. ScriptWriter 多段续写 / 重写场景

必须确认并记录：

- `/api/ai/multi-node` 仍支持当前请求体
- 409 缺失信息确认仍保留
- 成功后仍由后端落盘 `.arc`
- 返回 `thought` 逻辑不变
- 前端 reload 后恢复场景 / 节点选中

#### G. Bridge / Auto-Write

必须确认并记录：

- Bridge 仍然是“生成结果后由用户决定是否插入”
- Auto-Write 的状态字段名完全不变

#### H. 通用聊天流

必须确认并记录：

- `assistant_delta`
- `reasoning_delta`
- `tool_intent_started`
- `tool_exec_started`
- `tool_exec_finished`

这些事件名和语义都不能变。

### 0.5.3 阶段完成标准

必须先形成一张“兼容矩阵”，后续每次抽离都按该矩阵回归验证。

---

## 1. 第一阶段：梳理并固定现有数据源

### 1.1 任务目标

把 ScriptWriter 可用的现有数据源梳理清楚，后续 Context Pack 只使用这些数据。

### 1.2 需要确认的现有数据源

#### A. 世界观
- 读取路径 / 读取接口
- 当前项目世界观内容

#### B. 角色设定
- `chr.bind`
- 角色文件内容
- 前端角色选择数据来源

#### C. 梗概
- `synopsis.json`

#### D. 节拍表
- `beats.json`

#### E. 大纲
- `outline.json`

#### F. 当前剧本文件
- 当前 `.arc` 文件内容
- 当前文件路径
- 当前场景对象
- 当前节点对象

### 1.3 执行要求

- 不新增数据源
- 不修改上游模块主逻辑
- 只确认如何读取和组合

### 1.4 阶段完成标准

得到一张稳定映射表：

- 每类数据从哪里来
- 由谁读取
- 在 ScriptWriter 哪一步需要使用

同时必须补充：

- 明确 Muse / Lorebook / Showrunner / ScriptWriter 四个执行域分别有哪些手动入口、聊天入口、工具入口、MCP 入口

---

## 1.5 同步建立“四域统一执行抽离表”

状态：已完成（首版）

### 1.5.1 任务目标

不只梳理 ScriptWriter，还要把以下四个执行域统一纳入抽离计划：

1. Muse（灵感）
2. Lorebook（设定）
3. Showrunner（梗概 / 节拍 / 大纲）
4. ScriptWriter（剧本）

### 1.5.2 每个域都要梳理的内容

#### A. 当前有哪些入口

- 页面手动调用
- 悬浮聊天调用
- Agent 工具调用
- MCP 调用
- 未来外部调用预留点

#### B. 当前共享到了哪一层

- 只是共享 Agent 方法
- 还是共享了业务保存逻辑
- 还是根本没共享

#### C. 后续要抽成哪三段

- `build_context`
- `execute`
- `persist`

### 1.5.3 阶段完成标准

形成四域统一抽离表，明确：

- 哪些逻辑是适配层
- 哪些逻辑必须汇聚到唯一执行内核

---

## 2. 第二阶段：实现 ScriptWriter 轻量 Context Pack

### 2.1 任务目标

新增一套仅供 ScriptWriter 使用的轻量 Context Pack 组装逻辑。

### 2.2 必做修改

#### A. 新增上下文构造函数

建议新增内部函数 / 模块，命名可类似：

- `buildScriptwriterContextPack(...)`

输入建议包含：

- `projectName`
- `filePath`
- `sceneName`
- `nodeId`
- `selectedCharacterIds`
- `operation`
- `guidance`
- `segmentCount`
- `lastNodeText`
- `mode`

输出必须包含：

- `project_meta`
- `worldview`
- `characters`
- `story_structure`
- `local_script`
- `task_intent`

#### B. 组装逻辑要求

- 优先复用现有读取逻辑
- 不引入复杂摘要生成器
- 可先直接携带原文 / 当前结构片段
- 上下文必须清晰、分层、显式命名

#### C. 首批接入点

至少统一接入两个地方：

1. ScriptWriter 页面内部 AI 执行入口
2. 悬浮聊天窗口给 Scriptwriter 的 `active_context`

注意：

- 这里的“接入”首先应采用“并联对照”方式
- 即先在内部同时生成“旧上下文”和“新 Context Pack”用于校验
- 在未确认表现一致前，不要直接替换旧入口

### 2.3 本阶段不要做的事情

- 不做复杂状态推导
- 不做向量检索
- 不做语义压缩引擎

### 2.4 阶段完成标准

- Context Pack 能稳定构造
- 现有 Scriptwriter 能吃到比“当前场景”更完整的上下文
- 不破坏现有聊天发送和 ScriptWriter 页面主流程

并且要为 Muse / Lorebook / Showrunner 三域后续抽离提供可复用模板。

---

## 2.5 同步为前三域预留抽离接口

### 2.5.1 任务目标

在 ScriptWriter Context Pack 实现的同时，给前三个域建立一致命名与分层规范。

### 2.5.2 需要同步规划的接口族

#### A. Muse

- `build_muse_context(...)`
- `execute_muse_expand(...)`
- `persist_inspiration_result(...)`

#### B. Lorebook

- `build_lorebook_context(...)`
- `execute_worldview_generate(...)`
- `execute_character_generate(...)`
- `persist_worldview(...)`
- `persist_characters(...)`

#### C. Showrunner

- `build_showrunner_context(...)`
- `execute_synopsis_generate(...)`
- `execute_beat_sheet_generate(...)`
- `execute_outline_generate(...)`
- `persist_synopsis(...)`
- `persist_beat_sheet(...)`
- `persist_outline(...)`

### 2.5.3 说明

这一阶段不一定要求前三域全部落地改完，但必须把抽离方向写死，后续执行不能再走回“每个入口维护一套”的老路。

---

## 3. 第三阶段：新增统一执行接口 `compose/stream`

状态：已完成（首版）

### 3.1 任务目标

用一个统一执行接口替代旧的 ScriptWriter 执行端点。

### 3.2 必做修改

#### A. 新建路由

建议新增：

- `POST /api/scriptwriter/compose/stream`

#### B. 支持的 operation

至少支持：

- `continue`
- `rewrite_scene`
- `bridge`

如实现成本可控，可加入：

- `rewrite_selection`

#### C. 请求参数统一

请求体至少应包含：

- `operation`
- `mode`
- `projectName`
- `filePath`
- `sceneName`
- `nodeId`
- `selectedCharacterIds`
- `guidance`
- `segmentCount`
- `lastNodeText`

#### D. 内部处理顺序

统一顺序必须为：

1. 校验请求参数
2. 调用 `buildScriptwriterContextPack(...)`
3. 根据 operation 构造执行参数
4. 调用 Scriptwriter 执行逻辑
5. 流式返回进度 / 内容 / 完成事件
6. 必要时落盘

补充要求：

7. 统一 executor 必须先由旧接口调用，再由新接口调用

也就是：

- 第一版不是“前端先改接新接口”
- 第一版必须是“旧接口内部换实现，但外部协议完全不变”

#### E. 返回协议建议

至少统一为事件流，支持：

- `progress`
- `chunk`
- `done`
- `error`

以后全局加载速度统计、LUI、GUI 都统一基于这一协议。

注意：

- 这个协议只用于新统一接口
- 旧接口在兼容期内仍必须维持旧返回格式
- 不能把旧接口直接改成新协议返回给旧前端

#### F. 必须同时纳入“简单测速”字段

新流接口从第一版开始就应支持测速统计事件或字段，至少支持：

- `chars`
- `speed`
- `elapsed`

实现要求：

- 可由前端自行计算并显示
- 后端如要提供统计字段，只能作为辅助信息，不能成为唯一数据来源

### 3.3 阶段完成标准

- 新接口可用
- 至少能完成“继续写 / 重写场景 / 生成过渡”中的主链路功能
- 流式输出正常

并且：

- 全局遮罩可实时显示简单速度
- 旧接口兼容适配仍正常

---

## 3.5 全局遮罩简单测速改造（必须写入本轮计划）

### 3.5.1 任务目标

给全局 Loading 遮罩增加简单实时测速显示，并确保在所有流式链路中都能工作。

### 3.5.2 改造范围

至少覆盖：

1. Muse 灵感扩展
2. 世界观生成
3. 梗概生成
4. 节拍表生成
5. 大纲生成
6. ScriptWriter 新 compose 流
7. Bridge 流
8. Auto-Write 流

### 3.5.3 必做修改

#### A. 扩展 `global-loading` payload

新增可选字段：

- `statsEnabled`
- `statsChars`
- `statsSpeed`
- `statsFtl`（可选）
- `statsLabel`（可选）

#### B. 扩展 `GlobalLoading` 组件展示

要求：

- 无测速字段时完全保持现有样式与行为
- 有测速字段时额外显示一行简单统计

建议文案：

- `已输出 382 字 · 12.4 字/秒`

#### C. 为所有流式调用点补充统计逻辑

所有流式调用点都应在前端统一做：

1. 开始时间记录
2. 首 chunk 时间记录（可选）
3. 已接收字符累加
4. 周期性更新 `global-loading`

#### D. 节拍表 / 大纲的特殊要求

虽然它们当前前端是“整段积累后再解析”，但因为传输本身就是流式，所以测速仍然必须实时显示。

#### E. ScriptWriter compose 的特殊要求

新 compose 接口必须把测速显示作为默认能力之一，而不是额外补丁。

### 3.5.4 阶段完成标准

- 所有流式链路在全局遮罩中都能实时显示速度
- 不影响现有生成结果
- 不影响现有 Loading scope / target 逻辑

---

## 4. 第四阶段：新增统一反馈接口 `feedback/stream`

状态：已完成（首版）

### 4.1 任务目标

把“讨论 / 建议 / 反馈”与“真正落盘执行”分开。

### 4.2 必做修改

#### A. 新建路由

建议新增：

- `POST /api/scriptwriter/feedback/stream`

#### B. 用途

用于：

- 讨论剧情
- 获取建议
- 请求多个方案
- 解释写法
- 诊断问题

#### C. 特点

- 不直接改稿
- 不直接写文件
- 只返回文本 / 结构化建议

### 4.3 接入要求

可先接入：

- ScriptWriter 页中的“讨论建议”模式
- 后续悬浮聊天窗口中针对 Scriptwriter 的讨论型能力

### 4.4 阶段完成标准

- 讨论与执行有明确边界
- 前端逻辑不再混杂“问建议”和“真改稿”

---

## 5. 第五阶段：前端 ScriptWriter AI 面板迁移

状态：已完成

### 5.1 任务目标

让 ScriptWriter 页面不再依赖旧接口。

### 5.2 必做修改

#### A. `AiPanel` 调用迁移

当前旧调用：

- `/api/ai/single-node`
- `/api/ai/multi-node`

需要迁移到：

- `compose/stream`
- 必要时 `feedback/stream`

迁移顺序必须是：

1. 先保持 `/api/ai/single-node` 与 `/api/ai/multi-node` 对外协议不变
2. 在后端内部把它们改为调用统一 executor
3. 回归确认完全无行为变化
4. 再新增前端对 `compose/stream` 的新接入
5. 最后移除旧前端调用点

补充：

- `single-node` 前端迁移后，必须仍保持“编辑器文本追加”效果
- `multi-node` 前端迁移后，必须仍保持“生成完成后 reload 文件并恢复选中”的效果
- “强制继续生成”的确认交互必须完整保留

#### B. 前端任务语义收敛

逐步替换旧模式名：

- `single-node` → 继续写
- `multi-node` → 继续写 / 局部执行（按具体实现调整）
- `rewrite-scene` → 重写场景
- `bridge` → 生成过渡

#### C. 统一全局加载与速度统计

只要 compose 进入流式协议，前端统一实现：

- 计时开始
- 累计字符
- 实时速度
- 进度文字

但必须注意：

- 单段续写当前是“编辑器文本追加”，不能变成“自动落盘”
- 多段续写当前是“后端改文件 + 前端 reload”，不能变成“前端拼装写回”
- 重写场景当前沿用 `/api/ai/multi-node` 语义，迁移时必须保留该体验

### 5.3 阶段完成标准

- `AiPanel` 不再直接调用旧 ScriptWriter 接口
- 页面主流程稳定
- 全局加载和流式反馈统一

---

## 6. 第六阶段：将新执行能力暴露为工具

### 6.1 任务目标

让悬浮总控台、Agent、未来 LUI 能复用 ScriptWriter 执行能力。

### 6.2 必做修改

#### A. 新增工具

建议新增：

- `scriptwriter_build_context`
- `scriptwriter_compose`
- `scriptwriter_feedback`

#### B. 工具底层必须复用统一逻辑

工具不能自己再写一套 Scriptwriter 执行逻辑。

必须复用：

- `buildScriptwriterContextPack(...)`
- `execute_scriptwriter_compose(...)`
- `execute_scriptwriter_feedback(...)`

同时必须保留：

- 聊天流事件协议不变
- Tool start / end 事件不变
- Lorebook 现有工具不受影响

#### C. 悬浮聊天窗口后续使用方式

悬浮窗口中的 Scriptwriter Agent：

- 讨论类请求 → 走 `feedback`
- 明确执行类请求 → 调用 `scriptwriter_compose`

### 6.3 本阶段不要做的事情

- 不要改全项目所有 Agent 的 tool use 架构
- 不要一次性把所有页面都切换到工具调用

### 6.4 阶段完成标准

- Scriptwriter 执行能力可被工具调用
- GUI 与 Agent 不再重复维护执行逻辑

同时必须产出一个总原则：

- Muse / Lorebook / Showrunner 后续工具化时，也必须直接复用各自统一执行层
- 不允许再新增“工具专用业务逻辑分支”

---

## 6.5 后续三域抽离落地任务（必须写入总计划）

### 6.5.1 Muse 抽离

状态：已完成（页面手动生成、MCP 捕获、Muse 工具调用已统一复用 `build_context -> execute -> persist`）

任务目标：

- 让手动页面、MCP、聊天触发都复用同一灵感执行内核

完成标准：

- 修改 Muse 生成基本逻辑时，只改一处

### 6.5.2 Lorebook 抽离

状态：已完成（世界观页面生成与工具改写已统一复用 `build_context -> execute/persist`）

任务目标：

- 让页面生成、工具执行、聊天执行、未来外部调用都复用同一设定执行内核

完成标准：

- 修改世界观 / 角色生成与保存逻辑时，只改一处

### 6.5.3 Showrunner 抽离

状态：已完成（梗概 / 节拍 / 大纲页面生成与工具改写已统一复用 `build_context -> execute/persist`）

任务目标：

- 让梗概 / 节拍 / 大纲的手动生成、工具执行、聊天执行、未来外部调用共享同一执行内核

完成标准：

- 修改梗概 / 节拍 / 大纲基础逻辑时，只改一处

### 6.5.4 这三域与 ScriptWriter 的关系

ScriptWriter 仍然是本轮第一优先级。

但总计划中必须明确：

> 本轮建立的是“统一执行层模式”，不是“只给 ScriptWriter 特判一次”。

---

## 7. 第七阶段：旧接口退役

状态：已完成

### 7.1 任务目标

让旧 ScriptWriter 接口退出主舞台。

### 7.2 必做修改

#### A. 后端旧接口标记为兼容层

需要降级的旧接口：

- `/api/ai/single-node`
- `/api/ai/multi-node`

如果你已确定本轮最终要删除，那么执行顺序必须进一步细化如下。

### 7.2.1 删除前必须完成的准备动作

1. 新 `compose/stream` 已稳定上线
2. `feedback/stream` 已上线
3. `AiPanel` 已完成迁移
4. Bridge 如要收敛到 compose，必须完成前端主入口切换
5. 所有兼容矩阵回归全部通过

### 7.2.2 删除方式

#### 第一步：内部挪空旧逻辑

- `/api/ai/single-node` 内部改为调用统一 compose executor
- `/api/ai/multi-node` 内部改为调用统一 compose executor
- 对外仍维持旧协议，作为过渡层

#### 第二步：前端清零旧调用点

- `AiPanel` 不再请求旧接口
- 任何残留调用都必须搜索清零

#### 第三步：真正删除旧路由

删除：

- `/api/ai/single-node`
- `/api/ai/multi-node`

并同步清理：

- 相关 schema
- 相关注释
- 相关兼容逻辑

### 7.2.3 删除完成标准

- 项目中不存在对两个旧接口的前端调用
- 后端路由已删除
- 用户侧表现无变化

当前结果：已完成。前端源码已切到 `compose/stream` / `feedback/stream`，后端旧路由与旧 schema 已删除，并完成删除后回归测试。

#### B. 前端调用点清零

确保前端不再直接依赖它们。

补充要求：

- 在调用点清零前，旧接口必须至少保留一个版本周期作为兼容层
- 如需删除，必须先完成兼容矩阵全量回归

#### C. 旧工具降级

以下工具保留兼容，但不再作为未来主路径：

- `patch_script`
- `rewrite_script`

#### D. 注释 / 文档更新

必须同步更新：

- 路由注释
- 前端说明
- 后端说明
- 计划文档

### 7.3 阶段完成标准

- 新主路径彻底明确
- 旧路径不再被继续扩展

---

## 8. 悬浮总控台专项要求

### 8.1 本轮必须确认的定位

悬浮聊天窗口是：

- 全局讨论中心
- 轻量执行中心
- Agent 调度中心
- 未来 LUI 的原型入口

### 8.2 本轮建议保留并强化的能力

可直接通过聊天工具继续完成：

- 重写世界观
- 重写梗概
- 重写节拍表
- 重写大纲
- 世界观 / 梗概 / 节拍表的小范围替换

### 8.3 本轮不建议继续依赖的能力

不应继续把复杂 ScriptWriter 落盘建立在：

- `patch_script`
- 纯字符串替换

之上。

复杂结构化剧本修改必须逐步迁移到 `compose`。

---

## 9. 每个阶段结束后的验证要求

状态：已完成（已执行一轮新旧接口 + agent 接口测试，结果通过）

每完成一个阶段，必须做以下检查：

### 通用检查

1. 现有主流程是否仍可运行
2. 是否引入明显前端报错
3. 是否引入明显后端异常
4. 流式输出是否还能正确结束
5. 是否破坏悬浮聊天窗口
6. 是否破坏 MCP 灵感捕获行为
7. 是否破坏通用聊天流事件协议

### ScriptWriter 专项检查

1. 当前文件能否正常加载
2. 当前场景能否正常保存
3. 当前节点编辑是否正常
4. AI 执行后文件是否可重新解析
5. 旧功能是否至少在兼容层保持可用

### 兼容矩阵专项检查

每次提交后都要至少人工回归以下链路：

1. World 页面手动点燃灵感
2. Lorebook 工具箱修改世界观
3. Lorebook 工具箱修改角色
4. Synopsis 页面生成梗概
5. Synopsis 页面生成节拍表
6. Structure 页面生成大纲
7. ScriptWriter 单段续写
8. ScriptWriter 多段续写
9. ScriptWriter 重写场景
10. Bridge 生成并插入
11. Auto-Write 流式生成
12. 悬浮聊天普通对话
13. 悬浮聊天工具调用
14. 全局遮罩测速在所有流式链路都能显示

只要其中一项表现变化，就不能视为“纯架构优化”。

---

## 10. 最终执行顺序（严禁跳步）

必须严格按以下顺序执行：

1. 固化兼容矩阵
2. 固定现有数据源
3. 形成四域统一抽离表（Muse / Lorebook / Showrunner / ScriptWriter）
4. 实现 Context Pack
5. 同步固化前三域的抽离接口规范
6. 先在后端内部抽离统一 executor，并让旧接口调用它
7. 回归验证旧行为不变
8. 新增 `compose/stream`
9. 新增 `feedback/stream`
10. 前端 `AiPanel` 迁移
11. 新增 Scriptwriter 工具族
12. 悬浮总控台接入新能力
13. 按同一模式继续推进 Muse / Lorebook / Showrunner 三域抽离
14. 旧接口退役

任何时候都不要先删旧接口再迁移前端。

---

## 11. 最终完成标志

当前进度：第 2、3、4、5、9、13、14 项已满足验收条件；Muse / Lorebook / Showrunner / ScriptWriter 四域均已进入统一执行层轨道。

当以下条件全部成立，才算本轮整改完成：

1. ScriptWriter 已使用新的轻量 Context Pack
2. ScriptWriter 页面执行类请求已走新主接口
3. 讨论类请求已与执行类逻辑分离
4. 悬浮聊天窗口可继续承担总控台职责
5. 新执行能力可供工具层复用
6. 前端已不再依赖旧 ScriptWriter 接口
7. 旧接口已降级为兼容层并停止扩展
8. 四个执行域都已进入“统一执行层”轨道
9. 后续无论手动调用、聊天调用、MCP 调用、外部调用，修改基础逻辑都只需改一处

---

## 12. 给执行者的最后提醒

这次整改的本质不是“多写功能”，而是：

> **把已有功能规范化、统一化、可复用化。**

只要始终坚持：

- 不新造大系统
- 只复用现有数据流
- 先上下文，后接口，后前端，后工具，最后退役旧逻辑

就能把 ScriptWriter 从遗留态拉回到可持续演进的状态。