# Codex、OpenCode 与 SparkArc 上下文压缩策略对照

本文只记录源码中能够确认的上下文压缩行为，重点覆盖：压缩触发、压缩输入、保留与丢弃的原始信息、工具调用、压缩提示词以及压缩后的消息排列。

## 1. 调查范围

本次调查使用的外部源码快照位于：

~~~text
.tmp/context-research-20260828/pinned/
~~~

源码行号均指向该快照中的文件；上游项目后续版本可能改变实现。Codex 需要区分四条行为路径：三条会调用模型或服务生成压缩结果，另一条 <code>TokenBudget</code> 路径直接重置上下文窗口。

为核对 <code>Session::start_new_context_window</code> 的实际安装内容，调查缓存另外拉取了 OpenAI Codex 仓库提交 <code>5f49aba876922d6f2f55caa153bbb0ed1b46feba</code> 的 <code>codex-rs/core/src/session/mod.rs</code>；其余列出的外部文件来自上述 pinned 快照。

- 本地模型生成摘要的 <code>compact.rs</code>。
- 旧版远程 <code>/responses/compact</code>。
- 远程压缩 V2，即 <code>ResponsesCompactionV2</code>。
- <code>Feature::TokenBudget</code> 开启时的无摘要窗口重置。

OpenCode 快照同时包含 <code>packages/core</code> 的通用压缩模块和 <code>packages/opencode</code> 的应用层会话压缩模块。本文以应用层 <code>SessionCompaction</code> 的流程为主，并单独列出 core 提供的提示词构造和通用实现。

本文中的“保留”指压缩完成后仍进入后续模型请求的内容；“丢弃”指不再进入该活动上下文的内容。两者都不等同于从磁盘或远端服务永久删除。各项目对原始会话的持久化方式另行处理。

## 2. Codex

### 2.1 触发与共同流程

Codex 在 <code>context_window.rs</code> 中分别统计：

- 活动上下文总 token。
- 配置的自动压缩范围 token。
- 完整模型上下文窗口上限。
- 是否达到自动压缩范围或完整窗口。

<code>AutoCompactTokenLimitScope::Total</code> 按整个活动上下文计数；<code>BodyAfterPrefix</code> 按初始前缀之后的内容计数。达到配置的自动压缩阈值，或达到完整上下文窗口时，<code>turn.rs</code> 会触发自动压缩。自动压缩可以发生在新一轮采样前，也可以发生在工具循环中间；手动压缩则是独立的压缩 turn。

三条摘要型路径共同使用 <code>InitialContextInjection</code>：

- <code>BeforeLastUserMessage</code>：中途压缩时，把当前会话的初始上下文和世界状态重新插入最后一个真实 user/agent 消息之前。
- <code>DoNotInject</code>：预 turn 或手动压缩时，替换历史中不重新放入初始上下文；下一次正常 turn 再完整注入。

源码：<code>codex-rs/core/src/session/context_window.rs:23</code>、<code>codex-rs/core/src/session/turn.rs:1033</code>、<code>codex-rs/core/src/session/turn.rs:1210</code>、<code>codex-rs/core/src/compact.rs:64</code>。

### 2.2 Codex <code>TokenBudget</code> 窗口重置

当 <code>Feature::TokenBudget</code> 开启时，<code>run_auto_compact</code> 在选择远程 V2、旧远程或本地摘要路径之前，直接调用 <code>compact_token_budget::run_inline_auto_compact_task</code>。该路径不调用摘要模型，也不调用远程压缩端点；它仍执行压缩前/后的 hook 和 <code>ContextCompaction</code> 生命周期，然后调用 <code>Session::start_new_context_window</code>。

当前实现安装的新窗口内容是：

1. 先推进新的自动压缩窗口状态。
2. 用当前 <code>WorldState</code> 重新构造完整初始上下文。
3. 如果启用 <code>RetainClientDeveloperMessages</code>，从旧历史中筛选 <code>client_authored=true</code> 的 developer 消息，并复用 V2 的 <code>64,000</code> token 保留截断器；未启用时不保留这类旧消息。
4. 用「完整初始上下文 + 可选的 client-authored developer 消息」替换活动历史，同时安装当前 turn context 和 world-state baseline。

因此该路径不会把旧 user、assistant、reasoning、工具调用链或工具结果直接保留在新窗口中；旧历史事实只能通过重新构造的初始上下文或可选的 client-authored developer 消息间接存在。它是窗口重置，不是生成高密度摘要。<code>compact_token_budget.rs</code> 同时提供手动和 inline auto 两个入口，二者都调用同一个窗口重置过程。

源码：<code>codex-rs/core/src/session/turn.rs:1210</code>、<code>codex-rs/core/src/compact_token_budget.rs:21</code>、<code>codex-rs/core/src/session/mod.rs:3942</code>。

### 2.3 Codex 本地压缩

#### 压缩输入和模型调用

自动压缩使用配置中的 <code>compact_prompt</code>，没有配置时使用 <code>SUMMARIZATION_PROMPT</code>。该提示被构造成一个合成的 user input，并追加到当前历史之后。模型请求大致是：

~~~text
Prompt.base_instructions = 当前会话的 base instructions
Prompt.input = [已有完整历史, 合成的 user 压缩提示]
~~~

本地 <code>Prompt</code> 构造只在该函数中填入 <code>input</code> 和 <code>base_instructions</code>，没有显式绑定工具规格、并行工具调用或 output schema；这些字段由 <code>Prompt</code> 的默认值处理。压缩 turn 会读取完整历史，模型输出后由 <code>get_last_assistant_message_from_turn</code> 取本轮最后一个 assistant 消息作为摘要文本。若压缩请求本身仍超出上下文窗口，代码会从历史头部移除最早 item 后重试，以保留较新的输入和前缀缓存。

本地压缩请求的默认提示词原文是：

~~~text
You are performing a CONTEXT CHECKPOINT COMPACTION. Create a handoff summary for another LLM that will resume the task.

Include:
- Current progress and key decisions made
- Important context, constraints, or user preferences
- What remains to be done (clear next steps)
- Any critical data, examples, or references needed to continue

Be concise, structured, and focused on helping the next LLM seamlessly continue the work.
~~~

提示词要求输出面向下一个 LLM 的简洁、结构化交接摘要；提示词可以由配置覆盖。

#### 替换历史的保留规则

压缩结果不是把原始历史逐条改写，而是用新的 replacement history 替换活动历史：

1. 从规范化历史中筛选能解析为 <code>TurnItem::UserMessage</code> 的消息。
2. 丢弃已经以 <code>SUMMARY_PREFIX</code> 开头的旧摘要 user message。
3. 从最新 user message 向旧消息反向累计，最多保留所有选中 user 消息合计 <code>20,000</code> token。
4. 如果边界处的 user message 放不下，只按 token 截断该条消息。
5. 恢复为时间正序后写入新历史。
6. 最后追加一个 <code>ContextualUserFragment::CompactionSummary</code>。

保留的 user message 会携带 <code>InternalChatMessageMetadataPassthrough</code> 和 <code>CodexHarnessMetadata</code>。因此保留的是用户消息文本及其部分协议元数据，不是原始 assistant 消息的完整副本。

#### 丢弃的内容

本地 replacement history 不再直接保留：

- 旧 assistant 正文。
- 旧 reasoning 项。
- 旧 function/tool call 项。
- 旧 function/tool call output 项。
- 旧 shell、搜索或其它工具事件。
- 已被 <code>SUMMARY_PREFIX</code> 标识的旧摘要。

这些内容在生成摘要时仍作为输入提供给模型，但在替换后的活动历史中由新的摘要文本取代。对于中途压缩，初始上下文会按上面的注入规则重新插入；对于预 turn 或手动压缩，初始上下文不在本次 replacement history 中。

#### 压缩后的结构

本地压缩后的基本结构是：

~~~text
[选中的较旧 user 消息]
→ [中途压缩时插入到最后一个真实 user/agent 之前的初始上下文]
→ [选中的最新 user 消息；全部 user 消息合计最多 20,000 token]
→ CompactionSummary（SUMMARY_PREFIX + 本轮最后一个 assistant 文本）
~~~

<code>CompactionSummary</code> 是 Codex 内部上下文项，不是普通的用户可见 assistant 回复。

#### 工具调用处理

本地压缩的 <code>Prompt</code> 没有绑定工具规格，因此不存在压缩专用的工具执行循环。工具调用和结果如果出现在发送给摘要模型的规范化历史中，只作为输入的一部分参与摘要；replacement history 不单独重建旧工具调用闭合关系。下一次正常推理使用的是保留的 user 消息和摘要，而不是旧的工具调用链。

### 2.4 Codex 旧版远程 <code>/responses/compact</code>

#### 压缩请求

旧版远程路径先克隆当前历史，并在发送远程压缩请求前执行一次客户端侧工具输出缩减。随后构造 <code>Prompt</code>，其中包括：

- <code>history.for_prompt(...)</code> 产生的历史输入。
- 当前模型的 <code>base_instructions</code>。
- <code>tool_router.model_visible_specs()</code> 返回的模型可见工具规格。
- <code>parallel_tool_calls: true</code>。
- 无客户端 output schema。

客户端源码中没有与 OpenCode 类似的自然语言摘要模板；摘要内容由 <code>/responses/compact</code> 服务端实现决定。客户端收到远端返回的压缩历史后，再按 <code>should_keep_compacted_history_item</code> 过滤。

#### 发送前的工具输出缩减

如果发送到远程压缩端点前，估算的历史加基础指令超过完整模型窗口，<code>trim_function_call_history_to_fit_context_window</code> 从最新历史向旧历史扫描：

- <code>FunctionCallOutput</code> 的 output 替换为固定文本 <code>Output exceeded the available model context and was truncated</code>，并保留 success 状态。
- <code>CustomToolCallOutput</code> 使用同样的固定文本替换 output。
- <code>ToolSearchOutput</code> 保留调用状态和执行信息，但把工具列表清空。
- 其它不能由该函数重写的 item 会使该扫描停止。

这是为了让远程压缩请求本身尽量能发出，不是最终的远程 replacement history 保留规则。

#### 远端结果的保留规则

旧版远程返回结果经过过滤后，规则如下：

| 返回项 | 是否保留 | 条件或处理 |
|---|---:|---|
| <code>Message(role="developer")</code> | 否 | 丢弃可能过期或重复的 developer 包装指令 |
| <code>Message(role="user")</code> | 有条件 | 只有能解析为真实 <code>UserMessage</code> 或 <code>HookPrompt</code> 时保留 |
| <code>Message(role="assistant")</code> | 是 | 若远端返回 assistant 消息，客户端保留 |
| <code>AgentMessage</code> | 是 | 保留；另有 V2 对协作消息的更细过滤 |
| <code>Compaction</code> / <code>ContextCompaction</code> | 是 | 保留压缩项 |
| <code>CompactionTrigger</code> | 否 | 仅是触发标记 |
| reasoning | 否 | 不保留 |
| function/tool call | 否 | 不保留 |
| function/tool output | 否 | 不保留 |
| shell、web search、image generation | 否 | 不保留 |
| 其它 item | 否 | 不保留 |

过滤完成后，若是中途压缩，当前会话初始上下文会插入最后一个真实 user/agent 消息之前；没有真实 user/agent 时则按摘要或压缩项的保序规则插入。旧远程路径在安装阶段用普通 <code>ResponseItemEnvelope</code> 重新包装返回项，不保留原输入中的 <code>CodexHarnessMetadata</code> sidecar。

#### 远程路径的结构

远程服务实际返回的历史形状由服务端压缩实现决定。客户端只保证对返回项执行保留过滤，并按相对顺序安装；可表示为：

~~~text
[远程返回且通过 should_keep_compacted_history_item 的消息/压缩项，保持相对顺序]
→ [中途压缩时：初始上下文插入最后真实 user/agent 之前]
→ [若没有真实 user/agent：按插入函数规则置于摘要或 compaction item 之前；无注入则省略]
~~~

这里没有“客户端始终在末尾追加一个摘要/压缩项”的保证；返回结果是否含有这类项、其具体位置以及其文本内容，取决于旧版远程压缩服务。只有 V2 路径由客户端在保留项之后明确追加新的 <code>Compaction</code>。

客户端没有像本地路径那样在 Rust 侧固定一个 <code>20,000</code> token 的 user-message 尾部预算。

源码：<code>codex-rs/core/src/compact_remote.rs:311</code>、<code>codex-rs/core/src/compact_remote.rs:354</code>、<code>codex-rs/core/src/compact_remote.rs:399</code>、<code>codex-rs/core/src/compact_remote_request.rs:23</code>。

### 2.5 Codex 远程 V2

#### 压缩请求和返回值

V2 的客户端侧请求流程是：

1. 克隆历史。
2. 使用与旧版远程路径相同的 <code>trim_function_call_history_to_fit_context_window</code> 预缩减大工具输出。
3. 调用 <code>history.for_prompt_annotated(...)</code>。
4. 在输入末尾追加 <code>ResponseItem::CompactionTrigger {}</code>。
5. 发送 <code>base_instructions</code>、模型可见工具规格、<code>parallel_tool_calls: true</code> 的 <code>Prompt</code>。
6. 等待远端流中的 <code>response.completed</code>。
7. 要求输出中恰好有一个 <code>ResponseItem::Compaction</code>；没有压缩项或出现多个压缩项都视为失败。

V2 的压缩结果是一个协议级 <code>Compaction</code> item，内容由远端服务保存，不是客户端可读的普通摘要字符串。

#### 客户端保留预算

客户端常量为：

~~~text
RETAINED_MESSAGE_TOKEN_BUDGET = 64,000
MAX_RETAINED_AGENT_MESSAGE_TOKENS = 10,000
~~~

V2 会从输入历史中筛选可保留的消息组，再从最新向旧消息累计，最多留下 64,000 token。最后把远端返回的新的 <code>Compaction</code> item 追加到保留内容之后。单个可保留的 <code>AgentMessage</code> 超过 10,000 token 时不会进入保留集合；如果最后一个消息组只部分适合预算，文本会按 token 截断。

#### V2 的保留规则

<code>build_v2_compacted_history</code> 先执行 <code>is_retained_for_remote_compaction_v2</code>，再执行旧版的 <code>should_keep_compacted_history_item</code>。因此当前源码快照中的普通源消息规则是：

| 输入项 | 是否进入 V2 保留集合 |
|---|---:|
| 真实 user message / hook prompt | 是 |
| 普通 developer message | 否 |
| 普通 system message | 否 |
| 普通 assistant <code>Message</code> | 否 |
| 满足条件的 <code>AgentMessage</code> | 是，但必须不是子 Agent 进度消息、不是 <code>FINAL_ANSWER</code>，且不超过 10,000 token |
| 客户端 authored developer message | 只有启用 <code>RetainClientDeveloperMessages</code> 且元数据 <code>client_authored=true</code> 时才保留 |
| 与保留源消息绑定的 notice | 随消息组保留 |
| 旧 <code>Compaction</code> item | 不作为旧源消息保留；最后追加新的 V2 <code>Compaction</code> |
| reasoning、function/tool call、function/tool output | 否 |
| shell、web search、image generation | 否 |

这里的“普通 system/developer”指历史中的源消息。中途压缩所需的当前初始上下文是客户端在过滤后另行重新注入的，不属于这个保留集合。

#### 文本、图片和附件的截断

<code>truncate_retained_messages</code> 以消息组为单位从新到旧选择：

- 整个消息组适合剩余预算时，保留消息及其 notice。
- 消息组放不下但仍有预算时，按内容 item 顺序截断文本。
- 图片和音频不按文本 token 计算；启用图片预算后，图片会参与单独的图片预算处理。
- 如果一个超大的图片消息已经消耗了剩余预算，不再用更旧消息回填。
- 附加的 <code>CodexHarnessMetadata</code> 随保留项和截断项保留。

#### V2 的结构

V2 安装到活动历史后的基本结构是：

~~~text
[保留的真实 user/hook、符合条件的 AgentMessage、可选的 client-authored developer 及关联 notice]
→ [中途压缩时插入到最后真实 user/agent 前的初始上下文]
→ [新的远端 Compaction item]
~~~

V2 的工具调用链不在客户端尾部被完整复制；工具相关事实由远端压缩项承载，客户端只对发送前的大 output 做固定占位替换。V2 从 prompt 输入旁路携带并保留符合条件的 <code>CodexHarnessMetadata</code>，这一点与旧远程安装路径不同。

源码：<code>codex-rs/core/src/compact_remote_v2_attempt.rs:32</code>、<code>codex-rs/core/src/compact_remote_v2.rs:75</code>、<code>codex-rs/core/src/compact_remote_v2.rs:481</code>、<code>codex-rs/core/src/compact_remote_v2.rs:535</code>、<code>codex-rs/core/src/compact_remote_v2.rs:586</code>。

## 3. OpenCode

### 3.1 两层实现和预算入口

源码快照中有两层相关代码：

- <code>packages/core/src/session/compaction.ts</code>：提供 <code>buildPrompt</code>、摘要模板，以及一套使用 <code>keep.tokens</code> 的通用 <code>make</code> 实现。
- <code>packages/opencode/src/session/compaction.ts</code>：应用层会话实现，负责按 turn 选择历史、重复压缩、工具结果 prune、创建压缩消息和自动继续。

core 层定义以下基础常量：

~~~text
DEFAULT_BUFFER = 20,000
DEFAULT_KEEP_TOKENS = 8,000
TOOL_OUTPUT_MAX_CHARS = 2,000
SUMMARY_OUTPUT_TOKENS = 4,096
~~~

应用层另外定义了 <code>TOOL_OUTPUT_MAX_CHARS = 2,000</code>、<code>PRUNE_MINIMUM = 20,000</code> 和 <code>PRUNE_PROTECT = 40,000</code>。core 通用 <code>make</code> 的默认 <code>keep.tokens</code> 为 8,000；应用层 <code>SessionCompaction.select</code> 使用的是另一套 <code>preserveRecentBudget</code>：未配置时按 <code>usable(input) * 25%</code> 计算，并限制在 2,000 到 15,000 token 之间。两个数值来自不同层，不能合并成一个预算。

<code>overflow.ts</code> 的 <code>usable</code> 从模型可用输入窗口中扣除 compaction reserve；未配置时 reserve 为 <code>min(20,000, provider max output tokens)</code>。core 通用 <code>make</code> 的自动检查还会比较：

~~~text
估算的 system + messages + tools
≤ context - max(requested output, compaction buffer)
~~~

如果 token 使用量达到 <code>usable</code>，且没有关闭自动压缩，则判定为 overflow。模型上下文为 0 时不触发。

core 通用 <code>make</code> 的历史选择与应用层不同：它排除已有 compaction entry，把每条消息序列化为文本，从末尾按 <code>keep.tokens</code>（默认 <code>8,000</code>）累计，在消息字符串边界切成 <code>head</code> 和 <code>recent</code>，不按 user turn 计算。它把旧 compaction entry 的 <code>recent</code> 与新的 <code>head</code> 一起作为摘要输入；摘要成功后只发布 <code>Compaction.Ended</code> 事件，历史如何持久化和安装由上层负责。

源码：<code>packages/opencode/src/session/overflow.ts:8</code>、<code>packages/opencode/src/session/compaction.ts:28</code>、<code>packages/opencode/src/session/compaction.ts:115</code>、<code>packages/core/src/session/compaction.ts:12</code>。

### 3.2 OpenCode 主压缩流程

#### 历史按 turn 选择

应用层先把历史按 user message 分成 turn。带有 compaction part 的 user message 不作为普通 turn 起点。然后：

1. 从最新 turn 向旧 turn 反向遍历。
2. 能完整放进 <code>preserveRecentBudget</code> 的 turn 整体保留。
3. 第一个放不下的 turn，尝试从该 turn 的第二条消息开始切出尾部。
4. 尾部切分只按消息边界，不把单条普通消息截成两半。
5. <code>tail_turns</code> 如果配置，则只在最后指定数量的 turn 中选择。
6. 选择结果分为 <code>head</code> 和 <code>tail_start_id</code>；<code>head</code> 送入摘要，尾部后续原样保留。

这意味着 OpenCode 应用层的原始近期尾部通常是完整 turn；只有边界 turn 的尾部可能按消息边界切出，单条消息不会被应用层 <code>select</code> 截成两半。摘要只处理尾部之前的 head。

#### 旧压缩结果如何参与下一次压缩

<code>completedCompactions</code> 识别一对满足以下条件的消息：

- user 消息带 compaction part。
- 对应的 assistant 消息具有 <code>summary=true</code>、已完成且没有错误。

重复压缩时：

1. 把已经完成的旧 compaction user 和 summary assistant 从待摘要历史中隐藏。
2. 取最近的旧 summary 作为 <code>previousSummary</code>。
3. 把旧 summary 放入 <code>&lt;prior-summary&gt;</code>，再把新的 head 放入 <code>&lt;conversation&gt;</code>。
4. 新摘要生成后，旧摘要不再单独进入模型历史。

<code>&lt;conversation&gt;</code> 与 <code>&lt;prior-summary&gt;</code> 冲突时，提示词要求以更新的 conversation 为准。

#### 压缩后的持久化消息

压缩成功后，OpenCode 创建：

- 一个带 compaction part 的 user 消息，记录 <code>auto</code>、<code>overflow</code> 和 <code>tail_start_id</code>。
- 一个 <code>summary=true</code>、<code>mode="compaction"</code> 的 assistant 消息，保存摘要文本。

在存在已完成 summary 且 compaction part 带有 <code>tail_start_id</code> 时，<code>filterCompacted</code> 为模型重新排列消息，使其呈现为：

~~~text
compaction user marker
→ summary assistant
→ 被保留的近期 tail
→ 后续继续执行的 user message
~~~

这个数组排列是模型消费顺序，不再等于数据库中的严格时间顺序；没有可用的 tail 起点时，过滤器会返回未按该结构重排的结果。<code>message-v2.ts</code> 在转换 compaction part 时，把 marker 转成文本：

~~~text
What did we do so far?
~~~

overflow 场景还可以暂存一个原始 user message，在压缩成功后以新的 user message 重新放回并重新执行；重放时媒体文件会转换为附件占位文本。没有 replay 时，插件可以开启合成的继续消息，其默认文本是：

~~~text
Continue if you have next steps, or stop and ask for clarification if you are unsure how to proceed.
~~~

当 <code>overflow</code> 与大媒体有关时，合成消息前还会追加“此前请求因大型媒体附件超过 provider 大小限制，压缩后媒体已从上下文移除；如果用户询问附件内容，应说明附件过大并建议使用更小或更少的附件”的提示。

源码：<code>packages/opencode/src/session/compaction.ts:97</code>、<code>packages/opencode/src/session/compaction.ts:223</code>、<code>packages/opencode/src/session/compaction.ts:319</code>、<code>packages/opencode/src/session/message-v2.ts:521</code>。

### 3.3 OpenCode 压缩摘要的输入序列化

应用层将待压缩的 <code>head</code> 序列化成带标签的文本，再放进 <code>&lt;conversation&gt;</code>。核心标签如下：

~~~text
[User]: 用户文本
[Attached mime: filename]
[Assistant]: assistant 正文
[Assistant reasoning]: reasoning 文本
[Assistant tool call]: 工具名(JSON 参数)
[Tool result]: 工具结果
[Tool error]: 工具错误
~~~

core 通用序列化器另外定义了：

~~~text
[System update]: 系统更新
[Synthetic context]: 合成上下文
[Shell]: 命令
命令输出
~~~

已完成工具的结果在摘要输入中默认最多 2,000 个字符，超出时保留开头并追加 <code>[truncated]</code>；工具错误文本没有使用同一个 2,000 字符截断器。已被独立 prune 的已完成工具结果则改为：

~~~text
[Old tool result content cleared]
~~~

用户附件不复制文件正文，而是写成 MIME 类型和文件名占位信息。工具结果中的附件会先序列化成文本/附件标记，再按 provider 能力决定是否转换为模型媒体输入。

### 3.4 OpenCode 的摘要提示词

core 通用 <code>make</code> 路径的摘要调用是一条 user message：

~~~text
messages: [Message.user(summaryPrompt)]
tools: []
generation.maxTokens: min(requested output or 4,096, 4,096)
~~~

应用层 <code>SessionCompaction.process</code> 则通过 compaction agent 的 processor 调用模型，并显式传入：

~~~text
system: []
tools: {}
messages: [一条 role=user 的 summary prompt]
~~~

应用层这个函数没有显式设置 <code>generation.maxTokens</code>；因此不能仅根据该函数把 4,096 认定为应用层的实际输出上限。4,096 是 core 通用调用中的 <code>SUMMARY_OUTPUT_TOKENS</code> 上限。

应用层 compaction Agent 还加载 <code>packages/opencode/src/agent/prompt/compaction.txt</code> 作为系统级提示词，要求自己是上下文摘要 Agent：严格遵守 user prompt 要求的结构、保留精确路径和标识符、使用对话语言、不要继续回答原对话问题，只输出指定的结构化摘要。应用层的实际摘要调用因此由“该 Agent 系统提示词 + 一条包含 <code>buildPrompt</code> 结果的 user message”组成；调用处传入的 <code>system: []</code> 是 processor 参数，不等于整个请求没有 Agent 系统提示词。

该 Agent 系统提示词的核心原文是：

~~~text
You are a context summarization agent. You are given a conversation between a user and an agent. Your goal is to produce a structured summary matching the format specified by the user prompt so another coding agent can continue the work.

Always follow the exact output structure requested by the user prompt. Keep every section, preserve exact file paths and identifiers when known, and prefer terse bullets over paragraphs.

Do not continue the conversation. Do not respond to any questions in the conversation. Only output the structured summary in the exact format requested by the user prompt. Respond in the same language as the conversation.
~~~

没有旧摘要时，<code>buildPrompt</code> 的结构是：

~~~text
Here is the conversation so far:

<conversation>
...
</conversation>

Create a new anchored summary from the conversation history in the <conversation> tags above so another coding agent can continue the work.
~~~

然后追加固定 Markdown 模板：

~~~markdown
## Objective
- [one or two brief sentences describing what the user is trying to accomplish]

## Important Details
- [constraints/preferences, decisions and why, important facts/assumptions, exact context needed to continue, or "(none)"]

## Work State
### Completed
- [finished work, verified facts, or changes made; otherwise "(none)"]

### Active
- [current work, partial changes, or investigation state; otherwise "(none)"]

### Blocked
- [blockers, failing commands, or unknowns; otherwise "(none)"]

## Next Move
1. [immediate concrete action, or "(none)"]
2. [next action if known, or "(none)"]

## Relevant Files
- [file or directory path: why it matters, or "(none)"]
~~~

固定规则要求：

- 每个 section 都必须保留，即使为空。
- 使用简短 bullet，不写大段叙述。
- 保留已知的文件路径、符号、命令、错误字符串、URL 和标识符。
- 不要提到摘要过程或“上下文已压缩”。

有旧摘要时追加：

~~~text
<prior-summary>
旧摘要
</prior-summary>
~~~

并要求继承旧摘要中的目标、约束、用户指令、决策和并行工作流；丢弃已经完成且不再需要的内容；以新 conversation 覆盖冲突事实；把 Active 中已完成的内容移动到 Completed；更新 Objective 和 Next Move。

插件 <code>experimental.session.compacting</code> 可以追加 context 或替换 prompt；<code>experimental.chat.messages.transform</code> 可以在序列化前修改待摘要的 head。若替换了 prompt，应用层还会把序列化后的 conversation 作为“以下是对话历史”附加到 user message 中。

源码：<code>packages/core/src/session/compaction.ts:16</code>、<code>packages/core/src/session/compaction.ts:160</code>、<code>packages/core/src/session/compaction.ts:176</code>、<code>packages/opencode/src/session/compaction.ts:372</code>。

### 3.5 OpenCode 工具调用、工具结果和附件

#### 摘要输入中的工具调用

压缩摘要会把 completed 工具表示为一对文本：

~~~text
[Assistant tool call]: name(JSON input)
[Tool result]: output
~~~

错误工具表示为调用加错误；pending/running 工具在摘要序列化中只留下调用行。

实际模型消息转换由 <code>message-v2.ts</code> 负责：

- completed 工具保留输入和输出；输出可按 <code>toolOutputMaxChars</code> 截断。
- error 工具保留输入和错误；被标记为 interrupted 且有可用输出时，转换为可用输出。
- pending/running 工具转换为 output-error，并使用 <code>[Tool execution was interrupted]</code>，避免留下没有对应结果的 tool_use。
- tool result 中的媒体如果不被当前 provider 支持，会被抽出为一个 synthetic user message，文本为 <code>Attached media from tool result:</code>，后面放文件附件。
- <code>stripMedia</code> 时，用户媒体改成 <code>[Attached mime: filename]</code> 文本标记；已被 compaction 清理的工具附件不会继续发送。

#### 独立 prune

工具结果 prune 与生成摘要是两个独立动作，只有启用 <code>cfg.compaction.prune</code> 时执行：

1. 从最新消息向旧消息扫描。
2. 最近一轮 user turn 不处理；从第二新 turn 开始检查工具结果。
3. <code>skill</code> 工具结果受保护。
4. 从后向前累计 completed 工具结果 token；最近 40,000 token 作为保护范围。
5. 保护范围之外的旧工具结果加入待清理集合。
6. 只有实际可清理量严格大于 20,000 token 时才写入 <code>time.compacted</code>。
7. 后续模型转换将这些结果显示为 <code>[Old tool result content cleared]</code>。

源码：<code>packages/opencode/src/session/compaction.ts:271</code>、<code>packages/opencode/src/session/message-v2.ts:131</code>、<code>packages/opencode/src/session/message-v2.ts:244</code>。

## 4. SparkArc 当前策略

### 4.1 主聊天历史来源

SparkArc 的 <code>ChatManager.get_context_history</code> 不把完整数据库聊天记录全部发送给模型。它先读取当前 Agent 和 <code>context_key</code> 的最新 checkpoint，然后只返回：

~~~text
最新 context checkpoint
→ checkpoint 边界之后的原始 user/assistant 消息
~~~

<code>_history_to_messages</code> 对普通历史只生成 <code>HumanMessage</code> 和 <code>AIMessage</code>。工具消息不会作为独立历史行从 ChatManager 自动进入普通聊天；运行时工具信息主要在 assistant 的 <code>metadata.tool_traces</code> 中持久化。原始 user/assistant 仍留在数据库，可由 <code>search_chat_history</code> 回查。

源码：<code>server/agents/chat_manager.py:129</code>、<code>server/agents/chat_manager.py:175</code>、<code>server/agents/context_budget.py:174</code>。

### 4.2 专有工作模式的 user prompt 裁剪

SparkArc 还有一条不生成历史摘要的预算路径：<code>prepare_specialized_prompt_messages_with_budget</code>。它服务于专有工作模式的「固定 system + 一条动态 user prompt」，目标是保持 system 前缀不变，只在 user prompt 超预算时裁剪可恢复材料。

处理规则是：

1. 先按模型上下文窗口和输出预留计算同一套 <code>hard_budget</code>。
2. system 本身保持原文；user 的目标预算是 <code>max(1,024, hard_budget - system_tokens)</code>。
3. 仅按以 <code>### </code> 开头的三级标题行切分 user prompt；独立的 <code># </code> 或 <code>## </code> 标题不会创建新的切分边界。随后优先选择超过自身下限最多的非保护区块进行裁剪。
4. “当前场景事实包”“当前大纲场景契约”“当前场景的创作指导”“修正意见”“审阅目标”“待审阅剧本”“写作指导”等区块默认 <code>protected=true</code>；世界观、全局大纲、叙事记忆、角色档案、前文/前情和风格档案等区块有各自的最小字符数与保留比例。
5. 大区块使用保留首尾的中段截断，并写入明确的截断标记；如果所有可裁剪区块都达到下限，仍超预算则停止继续裁剪，不调用 UtilityAgent，也不创建 checkpoint。

该路径因此是结构化 user prompt 裁剪，不是对话历史压缩；其输出仍是 <code>[SystemMessage, HumanMessage]</code> 两条消息。

源码：<code>server/agents/context_budget.py:704</code>、<code>server/agents/context_budget.py:745</code>、<code>server/agents/context_budget.py:768</code>。

### 4.3 输入预算、压缩工作集和预留空间

SparkArc 在 <code>context_budget.py</code> 中把正常输出预留和上下文安全缓冲分开计算：

~~~text
reserved_output = min(max_output, 20,000, max_context - 256)
small_context_floor = min(16,000, max_context * 10%)
safety_margin = max(small_context_floor, max_context * 6.25%)
reserved_context = reserved_output + safety_margin
hard_budget = max(256, max_context - reserved_context)
trigger_budget = hard_budget
~~~

<code>safety_margin</code> 最后还会受剩余可用空间限制。这里的 <code>reserved_output</code> 是给当前正常回答预留的空间，不是压缩摘要的输出空间。

当历史超出 <code>hard_budget</code> 时，压缩后的目标工作集和摘要/近期预算另行计算。触发预算仍为：

~~~text
reserved_output = min(max_output, 20,000, max_context - 256)
small_context_floor = min(16,000, max_context * 10%)
safety_margin = max(small_context_floor, max_context * 6.25%)
hard_budget = max(256, max_context - reserved_output - safety_margin)
trigger_budget = hard_budget
~~~

然后由 <code>ContextCompactionBudget</code> 计算压缩后的总工作集：

~~~text
128K -> 28%, 256K -> 24%, 512K -> 18%, 1M -> 14%, 2M -> 12%
段间按 max_context 线性插值；Agent 偏移后限制在 10%–30%
target_context = min(hard_budget, max(required_context, max_context * target_ratio))
~~~

从目标工作集中扣除稳定 system、当前 user 及当前工具闭合尾部，剩余部分按 Agent 画像在“摘要”和“近期完整轮次”之间分配。摘要目标约占剩余历史预算的 35%–70%，同时受当前模型真实 <code>max_output_tokens</code> 的约 95% 限制；近期历史按完整 user turn 保留。

在 <code>max_output_tokens=64K</code> 时，导演预算近似如下：

| 模型上下文窗口 | 正常输出预留 | 安全缓冲 | <code>hard_budget</code> | 导演目标工作集 | 导演摘要预算 |
|---:|---:|---:|---:|---:|---:|
| 256,000 | 20,000 | 16,000 | 220,000 | 56,320 | 34,918 |
| 512,000 | 20,000 | 32,000 | 460,000 | 81,920 | 50,790 |
| 1,000,000 | 20,000 | 62,500 | 917,500 | 120,000 | 60,800 |

如果模型的最大输出小于 20,000，正常输出预留会随之降低；摘要预算仍按模型真实输出能力重新计算。system prompt、当前 user 和工具尾部还要从目标工作集中扣除。

### 4.4 普通聊天压缩

<code>prepare_chat_messages_with_budget</code> 的流程是：

1. 构造当前稳定 <code>system_instruction</code>。
2. 读取 checkpoint 和其后的 user/assistant 历史。
3. 追加当前 user message。
4. 估算完整 messages；未超预算时不压缩。
5. 超预算时固定保留 <code>system_instruction</code> 和当前 user message。
6. 按目标工作集和 Agent 画像分离摘要预算与近期预算；从历史末尾按完整 user turn 累计近期预算。
7. 将未被选中的旧历史交给 <code>UtilityAgent</code> 生成结构化摘要；如果必需的 system + 当前 user 已经超过 <code>hard_budget</code>，直接报告窗口不兼容，不进入摘要。
8. 生成 <code>[system, summary, retained history, current user]</code>。

普通聊天的 replacement history 形状是：

~~~text
system_instruction
→ 已压缩的 checkpoint/summary SystemMessage
→ 最近保留的原始 user/assistant 消息
→ 当前 user message
~~~

压缩 summary 的 SystemMessage 外层带有：

~~~text
【已压缩的早期上下文】
以下内容是系统生成的内部创作交接摘要，请把它视为此前对话事实、用户意图与工作进度，不要向用户解释压缩过程。
~~~

<code>summary_reserved</code> 是传给 UtilityAgent 的目标/校验预算，不是一次 LLM API 调用中显式设置的 output max token。它由窗口、Agent 画像和模型真实输出能力共同计算。UtilityAgent 首次结果超出该目标时会再次结构化收敛，仍超限则失败。压缩失败会抛出 <code>ContextCompactionFailedError</code>，当前请求停止，不以未摘要的旧历史静默替代。

压缩成功后，budget 函数返回 checkpoint 候选，payload 会记录压缩来源、边界消息 ID、原始消息数量和 token 信息。聊天路由在本轮模型请求成功完成后才调用 <code>persist_context_checkpoint</code>；该保存是幂等且尽力而为的优化，保存失败不会回滚已经完成的模型或工具调用。下一次读取时使用最新 checkpoint 及其边界后的原始消息，而不是重复发送已被覆盖的原文。

源码：<code>server/agents/context_budget.py:894</code>、<code>server/agents/context_budget.py:957</code>、<code>server/agents/context_budget.py:1010</code>、<code>server/agents/context_budget.py:1020</code>、<code>server/agents/chat_manager.py:197</code>、<code>server/agents/routes/chat.py:396</code>。

### 4.5 SparkArc 手动压缩

<code>POST /api/chat/context/compact</code> 使用与自动压缩不同的分区规则：

1. 读取当前 Agent/context 的运行时历史，即最新 checkpoint 加其边界后的原始 user/assistant。
2. 过滤为空的内容以及非 system/user/assistant 角色。
3. 按 user 消息划分轮次，使用当前 Agent 的动态近期预算保留尽可能多的最近完整轮次；更早部分作为 <code>compactible_source</code> 交给 UtilityAgent。
4. 目标摘要 token 默认使用动态摘要预算；若请求显式提供 <code>targetTokens</code>，只会进一步收紧目标，不会突破动态上限。传给摘要器的“当前用户消息”固定是“用户手动触发上下文压缩。”。
5. 生成摘要后，以更早部分的边界创建新的 checkpoint；随后额外写入一个空 assistant notice，metadata 中保存摘要段、原始消息数、摘要 token 和保留轮数。

手动路径不删除数据库中的原始 user/assistant；新的运行时读取只从最新 checkpoint 边界继续。若无法确定有效边界，或边界对应的原始 user/assistant 行已不存在，接口返回冲突错误，不写入新的 checkpoint；已有更新 checkpoint 时持久化层会直接复用更新版本。

源码：<code>server/agents/routes/chat.py:1064</code>、<code>server/agents/routes/chat.py:1081</code>、<code>server/agents/routes/chat.py:1114</code>、<code>server/agents/routes/chat.py:1155</code>、<code>server/agents/routes/chat.py:1183</code>、<code>server/agents/context_budget.py:407</code>。

### 4.6 SparkArc 摘要模型和提示词

摘要由独立的 <code>UtilityAgent</code> 调用。它发送两条消息：

~~~text
SystemMessage: utility.yaml 中 compress_context.system
HumanMessage: utility.yaml 中 compress_context.user
~~~

user 模板会提供：

~~~text
当前 Agent、估算模型、目标压缩 token 上限、当前用户最新消息、待压缩历史 JSON
~~~

#### SparkArc 实际使用的原始提示词

下面是 <code>server/agents/prompts/utility.yaml</code> 中
<code>compress_context.system</code> 的原文（保留源码中的字段说明）：

~~~text
你是 SparkArc 的系统级上下文压缩器。你的任务不是回复用户，而是把一段过长的历史对话压缩成可供后续 AI 继续工作的交接上下文。

你必须遵守：
1. 只保留对继续任务有用的信息，不写寒暄，不评价用户；摘要不是新创作，也不能擅自补全留白。
2. 不得编造历史中不存在的信息。不确定、推测、待用户确认的内容必须显式标为“未确认”，不能升级为事实。
3. 用户原始意图优先级最高。保留请求、硬约束及会影响语义的原话短句；不要只保留 AI 对用户意图的转述。
4. 这是创作工作上下文。必须保留世界观规则、时代与地点、角色身份/动机/关系、时间线、当前章节或场景状态、伏笔与连续性事实。
5. 必须保留作者的审美偏好、文风要求、禁区、受众和平台约束；把“已采用方案”和“明确否决方案”分开，连同理由保存，防止后续重复提出被否决内容。
6. 必须保留叙事或工程决策及理由、版本更新、后来覆盖旧结论的变更。若信息冲突，保留冲突双方与时间顺序，放入 conflicts_and_uncertainties。
7. 不要丢掉当前工作进度。计划、TODO、已完成项、承诺、正在执行的链路、文件/附件结论、工具调用结果、错误与重试都应保留。
8. 原始历史仍由系统完整持久化（直到用户主动编辑、删除或清空），并可通过 search_chat_history 检索。对摘要中缺乏证据的旧细节，应提醒后续 AI 搜索原文，不要自信猜测。
9. “当前用户最新消息”只用于判断摘要优先级，它仍会以原文保留在压缩窗口中，不属于待压缩历史。不得把它伪装成已经发生在旧历史中的事实，也不要在摘要里重复扩写。
10. 对体积很大的工具结果，保留已验证结论、错误、来源和后续用途，不复制冗长正文。为可能需要回看的细节生成 retrieval_anchors，优先采用历史原文中真实出现、适合 literal/regex 搜索的专有名词、文件名、角色名或连续短语。
11. 以高信息密度写作：相同事实只保留一次；使用短句、精确名词、路径、标识符、状态和因果关系；不复述摘要过程，不保留已经失效且无追溯价值的过程性内容。
12. 目标 token 是当前模型窗口为本次摘要动态分配的可用预算，不是固定上限。应在不超过预算的前提下尽量保留所有有效信息，不能因为追求简短而丢失约束、决策、证据、工具结论或开放任务。
13. 输出必须是严格 JSON，不能包含 Markdown 代码块、解释文字或额外前后缀；总长度不得超过目标压缩 token 上限。
14. 即使请求中绑定了原 Agent 的工具，也禁止调用任何工具；这些工具只为保持原请求前缀与缓存条件一致。你只输出压缩 JSON。

JSON 字段固定如下：
{
  "summary": "整体压缩摘要，200-800字，面向接手任务的 AI。",
  "user_intent_anchors": [
    {"intent": "用户当前目标或长期目标", "verbatim_anchor": "必要时保留的用户原话短句", "status": "进行中/已完成/待确认"}
  ],
  "creative_state": {
    "world_facts": ["世界规则、时代、地点与不可违背事实"],
    "characters": ["角色身份、动机、状态与形象事实"],
    "relationships": ["角色关系及其变化"],
    "timeline": ["事件时间顺序与连续性锚点"],
    "current_story_position": ["当前章节、场景、情绪节拍、伏笔与未兑现承诺"]
  },
  "author_preferences": {
    "required": ["作者明确要求的风格、体验、受众与平台约束"],
    "avoid": ["作者明确禁用或不喜欢的内容"],
    "soft_preferences": ["尚非硬约束的倾向"]
  },
  "current_progress": ["已经完成的工作、已产生的结论、当前推进到哪一步"],
  "important_facts": ["项目文件、接口、字段、路径、测试等非叙事事实"],
  "decisions": [{"decision": "已经采用的明确决策", "reason": "采用理由", "supersedes": "覆盖的旧决定或空字符串"}],
  "rejected_options": [{"option": "用户明确否决或放弃的方案", "reason": "否决理由"}],
  "conflicts_and_uncertainties": ["冲突信息、版本差异、未确认假设及需要查原文之处"],
  "open_tasks": ["仍需完成、仍需验证、仍需询问用户的事项"],
  "recent_turns": ["最近几轮对话中不能丢的上下文"],
  "tool_results": ["工具调用、附件读取、搜索、写入、错误或重试的关键结果"],
  "retrieval_anchors": [
    {"query": "适合 search_chat_history 的原文关键词或短语", "source_message_ids": [123, 124], "purpose": "需要回看何种细节以及何时检索"}
  ],
  "handoff_notes": ["给后续 AI 的执行提醒，包含风险、边界和不要重复做的事"]
}
~~~

对应的 <code>compress_context.user</code> 原文是：

~~~text
请压缩以下历史上下文，用于后续 AI 在同一个任务中无缝继续。

元信息：
- 当前 Agent：{agent_id}
- 当前 Agent 的压缩重点：{agent_profile}
- 估算模型：{model_name}
- 目标压缩 token 上限：{target_tokens}
- 当前用户最新消息：{current_user_message}

待压缩历史：
{history_text}
~~~

调用 <code>UtilityAgent._compress_once</code> 时，<code>{agent_id}</code>、
<code>{agent_profile}</code>、<code>{model_name}</code>、<code>{target_tokens}</code>、
<code>{current_user_message}</code> 和 <code>{history_text}</code> 会被实际值替换；
随后以一条 <code>SystemMessage</code> 和一条 <code>HumanMessage</code> 调用
<code>llm.invoke</code>。当源 Agent 的模型客户端和历史前缀可复用时，则发送“原稳定 system + 待压缩历史前缀 + 一条追加的压缩指令 HumanMessage”，并沿用工具 schema、将工具选择设为 <code>none</code>；收到工具调用响应会直接拒绝。这样上面的提示词是 SparkArc 压缩模型实际看到的模板，而不是仅供文档说明的抽象规则。

系统提示词明确要求：

- 只保留后续任务有用的信息，不写寒暄和评价。
- 不编造历史中不存在的信息；未确认内容必须标记为未确认。
- 保留用户原始意图、硬约束和必要原话锚点。
- 保留世界观、时代、地点、角色、关系、时间线、当前章节/场景状态和伏笔。
- 分开记录作者偏好、禁区、已采用方案和明确否决方案。
- 保留决策理由、版本覆盖关系、冲突、不确定性、进度、开放任务、工具结果和错误。
- 大工具结果只保留已验证结论、错误、来源和检索锚点。
- 当前最新 user message 仍会以原文保留，不能在摘要中将其伪装成旧历史事实。
- 相同事实只保留一次，使用短句、路径、标识符、状态和因果关系提高信息密度。
- 目标 token 是动态分配的预算，不是固定摘要长度；在预算内尽量保留约束、决策、证据、工具结论和开放任务。
- 即使绑定原 Agent 工具，也禁止调用工具，只输出压缩 JSON。
- 只输出严格 JSON，不能有 Markdown 围栏或额外说明。

固定 JSON 字段为：

~~~text
summary
user_intent_anchors
creative_state
author_preferences
current_progress
important_facts
decisions
rejected_options
conflicts_and_uncertainties
open_tasks
recent_turns
tool_results
retrieval_anchors
handoff_notes
~~~

其中 <code>creative_state</code> 继续拆分为 <code>world_facts</code>、<code>characters</code>、<code>relationships</code>、<code>timeline</code> 和 <code>current_story_position</code>；<code>author_preferences</code> 拆分为 <code>required</code>、<code>avoid</code> 和 <code>soft_preferences</code>；决策和否决方案各自保留理由。

### 4.7 UtilityAgent 的二次压缩和分块

<code>compress_chat_history</code> 先把待压缩历史转成 JSON，并从 Utility 模型上下文中扣除摘要目标和 5% 安全余量，计算单次输入上限；如果 Utility LLM 没有暴露上下文长度，则使用 <code>100,000</code> 作为估算上限：

~~~text
max_input_tokens = max(4,000, utility_max_context - target_tokens - max(2,000, utility_max_context * 5%))
~~~

如果历史 JSON 能放入该上限，则执行一次结构化压缩；否则：

1. 使用公共 <code>TokenTextSplitter</code> 按 token 分块。
2. 每个分块生成一个部分摘要，目标通常为最终目标的一半且至少 1,200 token。
3. 把部分摘要再次交给 UtilityAgent 合并。
4. 对最终 JSON 重新估算 token。
5. 若仍超过 <code>target_tokens</code>，再执行一次结构化收敛；第二次仍超限则报错。

解析器会先尝试去掉 Markdown 围栏并截取首尾 JSON 对象；只有仍无法解析为对象时，才保留最多 4,000 字符的原始摘要文本，并填充空数组和“未返回严格 JSON”的 handoff note。提示词要求的固定字段由模型遵守，Python 侧没有对每个字段做 schema 校验。

源码：<code>server/agents/utility_agent.py:100</code>、<code>server/agents/utility_agent.py:168</code>、<code>server/agents/prompts/utility.yaml:7</code>。

### 4.8 工具循环中的二次预算

工具循环不继续使用只含 user/assistant 的数据库历史，而是把运行中的 LangChain messages 交给 <code>rebudget_existing_messages</code>：

1. 找到最后一个 Human/User message。
2. 该消息及其后面的所有工具消息组成 <code>required_tail</code>，不可压缩。
3. 只有它之前的 <code>compressible_body</code> 参与近期保留和摘要。
4. 从 <code>compressible_body</code> 末尾向前保留 <code>recent_budget</code>。
5. 通过 <code>_repair_tool_boundary</code> 向前扩展边界，保证 assistant <code>tool_calls</code> 和后面的 ToolMessage 不被拆开。
6. 旧部分交给同一个 UtilityAgent 摘要。
7. 生成 <code>[system, summary, retained tool/history messages, required_tail]</code>。

工具调用的协议构造在 <code>tool_protocol.py</code>：

- 从 <code>tool_calls</code>、<code>invalid_tool_calls</code> 和兼容字段抽取调用。
- 规范化工具名和参数（参数可按工具的 JSON Schema 递归解包），并规范化调用 ID；缺少或重复 ID 时生成新的 ID。
- <code>build_tool_history_message</code> 只把实际进入执行链的调用写入 assistant <code>tool_calls</code>。
- 每个结果由 <code>build_tool_result_messages</code> 生成带相同 <code>tool_call_id</code> 的 ToolMessage。
- <code>validate_tool_message_history</code> 要求 assistant 调用和 ToolMessage 一一闭合，禁止缺少、重复或孤立的调用。

用于摘要的 <code>_messages_to_history_items</code> 只把运行时消息投影为 <code>role</code> 和 <code>content</code>。工具结果会作为 <code>role="tool"</code> 的内容进入摘要输入；该转换本身不会额外写入 <code>tool_call_id</code>、工具名或参数字段，assistant 消息上的结构化 <code>tool_calls</code> 也不会由这个函数展开到摘要 JSON。活动 messages 中的完整调用字段仍在保留的工具消息里维护；工具循环的摘要是临时消息，不生成普通聊天 checkpoint，但子 Agent 委派结束时其压缩后快照会写入专用交接记忆。

源码：<code>server/agents/context_budget.py:1114</code>、<code>server/agents/context_budget.py:1179</code>、<code>server/agents/context_budget.py:1216</code>、<code>server/agents/context_budget.py:255</code>、<code>server/llm/agen_matchbox/tool_protocol.py:275</code>、<code>server/llm/agen_matchbox/tool_protocol.py:374</code>。

### 4.9 长读取工具结果折叠

在二次预算前，<code>communication.py</code> 调用统一的 <code>collapse_attachment_chunk_history</code>。当前可折叠的长读取工具及占位文本是：

| 工具 | 旧结果替换文本 |
|---|---|
| <code>read_attachment_chunk</code> | <code>[附件分片原文已折叠 - AI 已在后续回复中提炼相关要点；如需重新阅读请再次调用 read_attachment_chunk]</code> |
| <code>read_chapter_scene</code> | <code>[章节/场景原文已折叠 - AI 已在随后一轮读取并处理过该内容；如需逐字核对请再次调用 read_chapter_scene]</code> |
| <code>read_chapter_outline_raw</code> | <code>[章节大纲原文已折叠 - AI 已在随后一轮读取并处理过该内容；如需逐字核对请再次调用 read_chapter_outline_raw]</code> |

处理规则是：

- 只处理这些工具的 ToolMessage。
- 当前最后一个 user message 之后的结果全部保留。
- 本轮新产生的 <code>fresh_call_ids</code> 全部保留。
- 更早 user 轮次的相同工具结果替换为占位文本。
- 已经是占位文本的结果不重复处理。

因此，SparkArc 对长读取结果有“先折叠旧正文、再按工具调用边界重新预算、必要时再结构化摘要”的连续处理链。

源码：<code>server/agents/attachment/chunk_history.py:3</code>、<code>server/agents/attachment/chunk_history.py:21</code>、<code>server/agents/communication.py:1720</code>、<code>server/agents/communication.py:2115</code>。

## 5. 各实现对照

| 维度 | Codex 本地 | Codex 旧远程 | Codex 远程 V2 | OpenCode | SparkArc |
|---|---|---|---|---|---|
| 摘要生成位置 | 当前 Codex 模型 | <code>/responses/compact</code> 服务端 | 远程 V2 服务端 | 独立 compaction agent/模型 | 独立 UtilityAgent |
| 摘要产物 | 文本 <code>CompactionSummary</code> | 远端返回的过滤后历史/压缩项 | 一个远端 <code>Compaction</code> item | Markdown summary assistant | 普通聊天为固定字段 JSON checkpoint；工具循环为临时 JSON 摘要消息 |
| 明确保留的近期原文 | user 消息合计最多 20,000 token | 由远端返回控制 | 输入源消息最多 64,000 token | 默认 2,000–15,000 token，按 turn 保留 | 普通聊天为 hard budget 扣除摘要空间后的近期消息；工具循环另保留必需尾部 |
| 单条大消息 | user 边界可按 token 截断 | 远端控制；发送前只缩减可重写工具 output | 保留尾部时按 token 截断 | turn 内尾部只按消息边界切分 | 通常按完整消息保留，摘要 JSON 另行限额 |
| 旧 assistant/reasoning | replacement 中不直接保留 | 远端返回的 assistant 可保留；reasoning 过滤 | 普通 assistant/reasoning 不保留 | assistant 正文/reasoning 进入摘要文本；近期 tail 原样保留 | assistant 原文在近期 tail 保留，旧部分进入 JSON 摘要 |
| 工具调用 | 作为摘要输入，replacement 中不复制 | 工具调用/结果过滤；发送前可替换大 output | 主要由远端 <code>Compaction</code> 承载 | 摘要文本保留调用名、JSON 参数和结果；近期 tail 保留结构化工具消息 | 活动工具循环保留闭合单元，旧工具结果可占位或摘要 |
| 工具结果清理 | 无独立本地 prune 规则 | 发送前固定占位替换部分 output | 同旧远程发送前预缩减 | 独立 prune：保护 40,000，实际清理量大于 20,000 才执行 | 先按指定长读取工具折叠，再按整体预算压缩 |
| 原始历史 | 替换活动历史，原始会话另由 Codex 会话存储 | 远端返回结果替换活动历史 | 新 <code>Compaction</code> 加有限保留项替换活动历史 | 数据库保留 compaction marker、summary 和 tail；过滤器重排模型输入 | DB 保留原始 user/assistant，checkpoint 只作为运行时边界 |
| 重复压缩 | 过滤旧 <code>SUMMARY_PREFIX</code> user message | 依赖远端返回结果 | 追加新的 V2 <code>Compaction</code> | <code>&lt;prior-summary&gt;</code> 与新 <code>&lt;conversation&gt;</code> 合并，旧 pair 隐藏 | 读取最新 checkpoint，旧边界前原文不重复发送 |

Codex 的 <code>TokenBudget</code> 路径不生成摘要；它安装完整初始上下文，并且只在启用对应特性时保留经过 <code>64,000</code> token 截断的 client-authored developer 消息。

## 6. 完整消息结构汇总

### Codex 本地

~~~text
[选中的较旧 user 消息]
→ [中途压缩时插入到最后真实 user/agent 前的初始上下文]
→ [选中的最新 user 消息；user 合计最多 20,000 token]
→ [CompactionSummary]
~~~

### Codex <code>TokenBudget</code>

~~~text
[当前完整初始上下文]
→ [可选的 client-authored developer 消息，最多 64,000 token]
→ [单独保存的当前 turn context reference 与 world-state baseline]
~~~

### Codex 旧远程

~~~text
[远程返回项中通过保留过滤器的 user/hook/assistant/AgentMessage/compaction item，保持相对顺序]
→ [按 initial-context 插入规则插入初始上下文；DoNotInject 时省略]
~~~

### Codex 远程 V2

~~~text
[保留的真实 user/hook、符合条件的 AgentMessage、可选 client-authored developer 及关联 notice]
→ [按中途压缩规则插入到最后真实 user/agent 前的初始上下文]
→ [新的 Compaction item]
~~~

### OpenCode

~~~text
[compaction user marker: compaction part]
→ [summary assistant: Markdown 固定 section]
→ [按 turn 选择的近期 tail]
→ [后续继续执行的 user message]
~~~

### SparkArc 普通聊天

~~~text
[稳定 system_instruction]
→ [最新 context checkpoint：固定 JSON 摘要]
→ [checkpoint 边界后的近期原始 user/assistant]
→ [当前 user message]
~~~

### SparkArc 专有工作模式

~~~text
[稳定 system prompt]
→ [同一条 user prompt；超预算时仅裁剪可恢复区块]
~~~

### SparkArc 手动压缩

~~~text
[更早的旧历史 → UtilityAgent JSON 摘要]
→ [按动态近期预算保留的最近完整 user turn]
→ [新 checkpoint + assistant compaction notice]
~~~

### SparkArc 工具循环

~~~text
[system]
→ [早期 overflow 的 UtilityAgent JSON 摘要]
→ [近期保留的完整消息/工具调用闭合单元]
→ [当前 user message]
→ [当前 user 之后的全部工具消息]
~~~

## 7. 参考来源

### Codex

- OpenAI Codex 本地实现：<code>codex-rs/core/src/compact.rs</code>、<code>codex-rs/core/src/compact_token_budget.rs</code>、<code>codex-rs/core/src/session/context_window.rs</code>、<code>codex-rs/core/src/session/turn.rs</code>、<code>codex-rs/core/src/session/mod.rs</code>。
- OpenAI Codex 旧远程实现：<code>codex-rs/core/src/compact_remote.rs</code>、<code>codex-rs/core/src/compact_remote_request.rs</code>。
- OpenAI Codex V2 实现：<code>codex-rs/core/src/compact_remote_v2.rs</code>、<code>codex-rs/core/src/compact_remote_v2_attempt.rs</code>。
- Codex 压缩提示词：<code>codex-rs/prompts/templates/compact/prompt.md</code>。
- [OpenAI API 上下文压缩文档](https://developers.openai.com/api/docs/guides/compaction)
- [OpenAI API 会话状态文档](https://developers.openai.com/api/docs/guides/conversation-state)

### OpenCode

- 应用层压缩：<code>packages/opencode/src/session/compaction.ts</code>。
- 应用层溢出判断：<code>packages/opencode/src/session/overflow.ts</code>。
- 应用层 compaction Agent 提示词：<code>packages/opencode/src/agent/prompt/compaction.txt</code>。
- 模型消息、工具和附件转换：<code>packages/opencode/src/session/message-v2.ts</code>。
- core 摘要提示词和通用压缩：<code>packages/core/src/session/compaction.ts</code>。

### SparkArc

- 预算和压缩：<code>server/agents/context_budget.py</code>。
- 动态 user 布局：<code>server/agents/prompt_layout.py</code>。
- 摘要模型：<code>server/agents/utility_agent.py</code>。
- 摘要提示词：<code>server/agents/prompts/utility.yaml</code>。
- checkpoint 和原始历史：<code>server/agents/chat_manager.py</code>。
- 手动压缩入口：<code>server/agents/routes/chat.py</code>。
- 工具协议：<code>server/llm/agen_matchbox/tool_protocol.py</code>。
- 长读取结果折叠：<code>server/agents/attachment/chunk_history.py</code>。
