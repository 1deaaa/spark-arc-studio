# SparkArc 长篇小说创作流深度研究与改进方案

时间：2026-06-18  
范围：SparkArc 现有上下文链路调查 + 2025-2026 年长篇故事生成论文、开源项目、官方长上下文能力趋势  
目标：提升 Scriptwriter、Critic、Director、GraphRAG 在长篇小说/互动剧本创作中的连贯性、可控性与文学质量

---

## 0. 核心结论

SparkArc 当前的上下文拼接方式可以概括为：

> “项目宪法全量注入 + 当前章前文 + 前序章节尾场锚点 + 梗概/节拍表压缩记忆 + 少量按需查阅工具”。

这套方式短篇或中篇还能工作，但长篇小说会遇到明显瓶颈：

1. **连续性主要依赖原文邻近性**，没有显式维护“角色状态、关系状态、事件账本、伏笔账本、时间线、世界规则约束”。
2. **GraphRAG 是字符分片后抽三元组**，不是以场景、事件、角色关系为基本单位；人物或事件横跨分片时，关系很容易断裂。
3. **Scriptwriter 的输入是全量设定 + 简单前文**，缺少“当前场景相关历史”的动态召回和压缩。
4. **Auto-write 每场写完后没有结构化吸收输出**，下一场靠文件读取和尾场锚点续上，而不是靠可查询的故事状态机。
5. **Critic 可以审稿，但结果没有变成长期质量记忆和可执行修订工单**。
6. **2026 年 1M 上下文已不罕见，256K 应视为最低工程假设**；但长上下文只能降低“拿不到信息”的问题，不能自动解决“该看什么、怎么更新状态、如何证据化检查”的问题。

改造方向不是推翻现有架构，而是在现有收口层上新增一个统一的：

> **StoryMemoryFacade / NarrativeStatePipeline：故事状态与上下文编排层**

让 Scriptwriter、Critic、Director、GraphRAG 都围绕同一份结构化故事状态工作。最关键的变化是把当前 `build_scene_context()` 升级为：

> **SceneTaskPack：当前场景任务包**

它应由以下内容组成：

- 项目宪法：题材、POV、风格、禁忌、世界规则。
- 当前章节/场景目标：来自大纲、节拍、导演意图。
- 当前场景登场角色状态卡：动机、情绪、伤病、资源、关系、已知信息边界。
- 相关历史证据：不是全书摘要，而是与当前事件/角色/伏笔相关的原文片段与结构化事实。
- 近邻原文：当前章已写内容、上一场/上一章必要桥接。
- 写作约束：必须呼应、禁止矛盾、待推进伏笔、节奏目标。
- 输出后处理契约：生成后抽取状态增量，更新故事状态。

---

## 1. 本地现状还原

### 1.1 Scriptwriter 生产入口

正式业务入口在：

- `server/agents/routes/production.py`
- `/api/scriptwriter/compose/stream`

`build_scriptwriter_context_pack()` 当前会：

- 读取世界观全文。
- 读取全量角色档案。
- 读取完整大纲。
- 读取叙事记忆：梗概 + 节拍表。
- 解析当前 `.arc` 文件，定位目标场景，把目标场景之前的内容序列化成 `canonical_context`。
- 保留 `selected_character_ids` 参数，但已不再用它过滤角色，角色改为全量注入。

关键含义：手动续写/改写时，Scriptwriter 拿到的主要是全局设定 + 当前文件内前文。它没有自动拿到“本场相关历史事件账本”或“相关人物状态变化链”。

### 1.2 Auto-write 连续生成链路

Auto-write 在：

- `server/agents/routes/auto_write.py`

它会在任务开始时一次性预加载：

- `worldview`
- `roles`
- `full_outline`
- `narrative_memory`
- `style_profile`
- `story_tags`

每个场景生成时调用：

- `build_scene_context(user_id, project_name, current_chapter_index=i, current_scene_index=scene_idx)`

然后将 `context_str`、全量世界观、全量角色、完整大纲、叙事记忆、当前场景任务 `scene_goal` 传入：

- `ScriptwriterAgent.write_script_stream()`

Auto-write 还有一个 “Pre-flight 侦查阶段”：

- `writer.research_references(scene_goal, full_outline, user_id, project_name)`
- 让模型最多几轮调用只读工具 `list_chapters` / `read_chapter_scene`
- 如果模型判断需要远端伏笔场景，就把查到的内容追加到 `context_str`

这说明当前系统已经意识到“前序章末尾场景不够”，但解决方式仍然是让模型临时自觉查阅。它没有一个稳定的、可测试的“相关历史召回器”。

### 1.3 三圈记忆策略

`server/agents/routes/context_builder.py` 的 `build_scene_context()` 明确写了三圈记忆：

1. Hard Context：当前章节内，目标场景之前所有已完成场景全文。
2. Sliding Window：前序各章节最后一个场景全文。
3. Compressed：调用方通过 `narrative_memory` 注入；此函数不处理。

实现上：

- 前序章节只取每章最后一个场景。
- 当前章取目标场景之前的场景。
- 压缩记忆是梗概 + 节拍表，不是由已写正文实时提取出来的状态摘要。

风险：

- 第 1 章埋下的戒指、第 3 章的一句承诺、第 7 章的人物伤势，如果不在章尾场景或全局大纲中，被第 20 章使用时很容易丢。
- “当前情感节拍”目前按章节索引做启发式估算，不是大纲场景级绑定，长篇中会偏离。
- `accumulated_context` 在 auto-write 中存在变量，但核心连续性实际还是由 `build_scene_context()` 和文件读取决定。

### 1.4 Scriptwriter Prompt 输入

`server/agents/prompts/scriptwriter.yaml` 的 `base.user_context` 注入：

- 世界观背景：`{worldview}`
- 全局大纲：`{full_outline}`
- 叙事记忆：`{narrative_memory}`
- 登场角色对照表：`{chr_reference}`
- 角色详细档案：`{roles}`
- 作者文风档案：`{style_profile}`
- 前文剧本：`{context}`
- 当前场景指导：`{guidance}`
- 修正意见：`{feedback}`

这套 prompt 的优点是信息完整，缺点是“全量信息”和“当前任务相关信息”没有区分层级。长篇时，大纲和角色档案越来越长，模型会被噪音淹没；即使有 1M 上下文，也会产生注意力稀释、证据定位不稳和成本过高。

### 1.5 聊天/导演委派时的 Scriptwriter 上下文

`server/agents/context_provider.py` 中 `agent_scriptwriter` 的对话/委派上下文会注入：

- 世界观设定。
- 角色详细档案全量。
- 全局大纲。
- 叙事记忆。
- 场景文件列表。

这和生产链路保持了数据来源一致，但聊天/委派时没有自动附带“当前要写的具体场景上下文包”。Director 委派如果只传任务描述，Scriptwriter 往往要靠全局材料和工具自觉补齐。

### 1.6 其他 Agent 的上下文

Showrunner：

- 主要注入故事结构：梗概、节拍表、大纲摘要。
- 更适合规划，不适合校验已写正文的细粒度事实。

Lorebook：

- 注入世界观 + 角色详情。
- 更适合设定构建，不负责持续吸收正文中的状态变化。

Critic：

- 能看到较完整创作上下文，也可使用 GraphRAG。
- 但当前 Critic 更像“当次审稿专家”，没有把审核发现转成长期可执行状态，例如 `fix_tickets`、一致性错误账本、风格退化曲线。

Director：

- 能看到项目整体状态和文件列表。
- 目前更像任务调度器，不是围绕结构化故事状态进行规划和验收的“制作总控”。

### 1.7 GraphRAG 现状

`server/agents/graphrag/service.py` 当前要点：

- 使用 `RecursiveCharacterTextSplitter`。
- 默认 `chunk_size=1200`，`chunk_overlap=160`。
- 默认最多 `120` 个 chunk。
- 每 chunk 抽三元组。
- 有角色别名归一化。
- 查询时抽取问题实体，匹配图节点，返回局部图 + 全局核心实体，并生成写作约束。

优点：

- 已经有项目级图谱服务。
- 有 freshness 机制。
- 有别名映射。
- 工具入口已收口到 `graph_rag_tool`，且只读，安全边界不错。

核心问题：

- 分片单位是字符，不是叙事单位。
- 三元组缺少明确的时序、场景、版本、置信度、证据跨度。
- 如果“人物 A 在 chunk 开头出现，人物 B 在 chunk 末尾出现，中间关系在跨 chunk 处表达”，抽取很容易漏掉。
- 关系合并主要靠实体名，不足以处理“关系状态随时间改变”：敌对、合作、误解、和解、背叛都可能同时存在，但应有时间线。
- 查询结果是“事实约束”，还没有变成 Scriptwriter 当前场景任务包的一等输入。

---

## 2. 2025-2026 研究共识

### 2.1 StoryWriter：事件图式大纲 + 动态历史压缩 + 多 Agent

来源：

- arXiv: https://arxiv.org/abs/2506.16445
- GitHub: https://github.com/THU-KEG/StoryWriter

核心做法：

- Outline Agent 生成基于事件的丰富大纲，包含事件、人物、事件关系。
- Planning Agent 做章节规划。
- Writing Agent 根据当前事件动态压缩历史，生成并反思新内容。
- 重点不是单纯扩大上下文，而是让每个写作单元围绕“当前事件”获取相关历史。

对 SparkArc 的启发：

- 当前大纲应该升级为事件图，而不是纯章节/场景文本树。
- Scriptwriter 不应只拿“当前章前文 + 前章尾场”，而应拿“当前事件相关的历史压缩”。
- Director 委派时，应传递事件节点和场景契约，而不是自然语言任务描述。

### 2.2 Learning to Reason for Long-Form Story Generation：章节级 Story-Information

来源：

- arXiv: https://arxiv.org/abs/2503.22828
- OpenReview: https://openreview.net/forum?id=dr3eg5ehR2

核心做法：

- 任务是 Next-Chapter Prediction。
- 模型基于浓缩的故事信息生成下一章详细计划。
- 章节输入不是全书原文，而是结构化的 Story-Information，例如全局 sketch、此前章节摘要、人物卡、上一章原文、下一章 synopsis。

对 SparkArc 的启发：

- 你现在的 `narrative_memory` 太粗，应该拆成章节/场景级可更新记忆。
- “上一章原文 + 下一章 synopsis + 动态人物卡”比“前序各章最后一场”更可靠。
- 先让模型生成“本场执行计划/约束清单”，再写正文，比直接把所有材料塞进 prompt 更稳。

### 2.3 Guiding Generative Storytelling with Knowledge Graphs：KG 作为叙事中央仓库

来源：

- arXiv: https://arxiv.org/abs/2505.24803

核心做法：

- 用知识图谱增强 LLM 故事生成，改善叙事质量，并支持用户驱动修改。
- KG 把角色、地点、物品、事件等作为可控结构，而不是只做向量检索。
- 对行动导向、结构化叙事尤其有效。

对 SparkArc 的启发：

- GraphRAG 不应只存“实体-关系-实体”三元组，还要存事件、场景、物品状态、角色状态、地点状态。
- 图谱应从“问答工具”升级为“写作状态数据库”。
- 用户修改设定或剧情时，应能更新 KG，并影响后续生成。

### 2.4 Lost in Stories：一致性错误分类与证据化检测

来源：

- arXiv: https://arxiv.org/abs/2603.05890
- Hugging Face paper page: https://huggingface.co/papers/2603.05890

核心发现：

- 长故事一致性错误可以系统分类。
- 论文提出 ConStory-Bench 和 ConStory-Checker。
- 错误常见于事实与时间维度，也会发生在人物、世界规则、叙事风格等方面。
- 检测应给出明确文本证据，而不是只说“有点不一致”。

对 SparkArc 的启发：

- Critic 应升级为证据化一致性检查器。
- 审稿结果应包含：错误类型、冲突片段、证据来源、严重程度、修复建议、可执行 patch ticket。
- 长篇生成质量评估不能只看 AI 味、流畅度和局部逻辑。

### 2.5 Towards Human-Level Book-Writing Capability：多分辨率 planning scaffold

来源：

- arXiv: https://arxiv.org/abs/2605.17064

核心做法：

- 从人类小说构造多分辨率规划脚手架。
- 从高层 premise 到章节结构，再到场景结构，最后展开成正文。
- 强调书籍级生成需要层级计划，而不是单层 prompt。

对 SparkArc 的启发：

- 你现有 Showrunner 的梗概/节拍/大纲是正确方向，但需要继续细化到“场景功能、叙事焦点、视角、冲突推进、伏笔状态”。
- Scriptwriter 的输入应显式包含当前场景在全书中的功能，而不仅是场景描述。

### 2.6 StoryBox / TaleFrame：顶层规划 + 角色模拟 + 细粒度控制

来源：

- StoryBox arXiv: https://arxiv.org/abs/2510.11618
- StoryBox GitHub: https://github.com/amcghm/StoryBox
- TaleFrame arXiv: https://arxiv.org/abs/2512.02402

核心做法：

- StoryBox 倾向混合式：顶层规划约束整体方向，底层角色模拟推动局部情节。
- TaleFrame 强调细粒度控制，把实体、事件、关系、大纲拆开，支持交互式调整。

对 SparkArc 的启发：

- Lorebook 不应只管理静态设定，还应支持角色当前状态模拟。
- Muse / Showrunner / Scriptwriter 之间可以围绕同一个事件-关系模型协作。
- 用户在 UI 中修改一个人物关系或事件，应能影响大纲、图谱、当前写作包，而不是只改一份文本。

### 2.7 StoryAlign / POLARIS / Retell, Reward, Repeat：故事专用评估与奖励

来源：

- StoryAlign: https://arxiv.org/abs/2605.04831
- POLARIS: https://arxiv.org/abs/2606.04095
- Retell, Reward, Repeat: https://arxiv.org/abs/2601.17226

核心趋势：

- 故事生成需要专用 reward / judge，而不是通用 helpfulness judge。
- 奖励维度包括连贯性、角色发展、叙事张力、原创性、风格、节奏、情感弧光。
- 长篇生成还需要锚定参考注入和长度泛化训练/评估。

对 SparkArc 的启发：

- Critic 的输出要结构化，并可长期聚合。
- 可以建立项目级“质量仪表盘”：重复度、节奏拖沓、角色弧线停滞、伏笔未回收、一致性错误密度。
- 评估要进入自动写作闭环，而不是生成完才手工看。

---

## 3. 长上下文时代的重新定位

截至 2026 年，主流模型长上下文能力已经进入 256K 到 1M 级别，部分官方生态已稳定提供 1M 级上下文。工程假设必须变化：

- 不能再把 32K/64K 当作上限设计。
- 256K 应作为日常最低可用上下文预算。
- 1M 可以用于项目级长文审阅、全章/多章重写、全局一致性扫描。

但长上下文不会自动解决以下问题：

1. **注意力不是数据库索引**：信息在 1M prompt 中存在，不代表模型会准确使用。
2. **成本与延迟仍然真实存在**：每场都塞几十万 token 会拖慢自动写作。
3. **版本状态仍需结构化更新**：模型看过事实，不代表下一场能自动维护状态。
4. **冲突需要证据化检测**：长上下文更容易让模型“看似知道”，但仍会忽略中段事实。
5. **用户可控性来自结构，而非长度**：作者想改一个伏笔或人物关系时，需要命中具体状态节点。

因此推荐采用：

> 长上下文作为“可用原文池”，结构化状态作为“决策索引”，动态任务包作为“当前写作工作台”。

---

## 4. SparkArc 现有架构下的主要问题

### 4.1 Scriptwriter 缺少当前场景相关历史压缩

当前：

- 全量大纲、全量角色、全量世界观。
- 当前章前文。
- 前序章尾场。
- 梗概/节拍表。

缺少：

- 与当前场景登场人物相关的历史事件。
- 与当前物品/地点/组织相关的状态变化。
- 当前场景必须回收或推进的伏笔。
- 当前人物彼此“知道什么/不知道什么”。
- 当前场景与未来章节的约束。

后果：

- 模型容易写出“局部顺滑但全局错位”的正文。
- 长篇中人物关系、秘密、承诺、伤势、资源数量很容易漂移。

### 4.2 角色全量注入会从“安全”变成“噪音”

全量角色档案在短篇中避免遗漏，但长篇中会产生：

- 角色多时，当前场景只涉及 2-4 人，全量角色会稀释注意力。
- 静态档案无法反映正文已发生变化。
- 角色关系不是静态字段，而是随剧情变化。

应改为：

- 全量角色只作为后备低优先级材料。
- 当前场景角色状态卡作为高优先级材料。
- 角色关系按时间线和证据更新。

### 4.3 三圈记忆过于粗糙

“前序各章最后一个场景”是一种廉价连续性锚点，但它无法覆盖：

- 早期伏笔。
- 非章尾关键事件。
- 中段人物关系转折。
- 物品/线索的出现与转移。
- 设定规则的首次说明。

更好的机制是：

- 近邻原文：上一场、当前章前文。
- 结构摘要：上一章摘要、当前章节摘要。
- 事件召回：与当前事件相关的历史事件链。
- 实体状态：角色/物品/地点状态卡。
- 伏笔账本：待回收与已回收线索。

### 4.4 GraphRAG 不是叙事状态图

当前 GraphRAG 的角色更接近“项目文本问答索引”。它还不是“故事状态图”。主要缺失：

- 叙事单元：Book / Chapter / Scene / Beat / Event。
- 状态节点：CharacterState / RelationshipState / ObjectState / LocationState。
- 时序边：before / after / causes / reveals / foreshadows / resolves。
- 证据跨度：source file、scene id、line range、原文片段。
- 状态版本：同一关系在不同章节的状态变化。
- 冲突处理：新抽取事实与旧事实冲突时进入待确认，而不是简单覆盖或并存。

### 4.5 Auto-write 没有“写后吸收”

每场写完后目前主要做：

- 清洗格式。
- 保存文件。
- 更新任务状态。

缺少：

- 抽取本场事件。
- 更新角色状态。
- 更新关系状态。
- 更新伏笔状态。
- 更新章节摘要。
- 更新一致性风险。
- 生成下一场写作约束。

长篇连续创作必须有 “write -> extract -> validate -> update memory -> next scene”。

### 4.6 Critic 没有形成闭环

Critic 如果只是输出意见，价值会停在“读后感”。更理想的是：

- 审稿输出结构化。
- 每个问题都有证据。
- 每个问题能转成修订工单。
- 修订后能复检。
- 长期问题能沉淀到风格/质量记忆。

### 4.7 Director 调度缺少结构化契约

Director 现在可以委派 Agent，但更理想的委派不是：

> “请写第几章第几场”

而是：

> “请执行 scene_contract：本场事件、冲突、角色状态、必须呼应、禁止矛盾、输出长度、完成标准”。

这样 Scriptwriter 的输出更可测，Critic 也能按契约验收。

---

## 5. 改进总架构

推荐新增统一收口层：

```text
server/agents/story_memory/
  facade.py                 # StoryMemoryFacade，对外统一入口
  models.py                 # NarrativeState / SceneTaskPack / FactClaim / FixTicket
  extractor.py              # 从正文抽取事件、状态、伏笔、关系
  retriever.py              # 当前场景相关历史召回
  composer.py               # 组装 Scriptwriter 场景任务包
  validator.py              # 一致性检查与冲突检测
  persistence.py            # 读写项目级状态文件/索引
```

它不是替代现有 `context_builder.py`，而是让 `context_builder.py` 从“字符串拼接器”升级为“调用 StoryMemoryFacade 的场景任务包组装器”。

### 5.1 新的核心数据结构

#### NarrativeState

项目级状态总表：

```json
{
  "version": "1.0",
  "project": "项目名",
  "book": {
    "premise": "",
    "themes": [],
    "pov": "",
    "style_constraints": []
  },
  "chapters": [],
  "scenes": [],
  "events": [],
  "characters": [],
  "relationships": [],
  "objects": [],
  "locations": [],
  "foreshadows": [],
  "world_rules": [],
  "quality_memory": []
}
```

#### SceneState

每个场景应有稳定 ID：

```json
{
  "scene_id": "ch01-sc02",
  "chapter_id": "ch01",
  "title": "",
  "outline_goal": "",
  "narrative_function": "推进冲突/揭示秘密/关系转折/伏笔回收",
  "pov": "",
  "characters": [],
  "events": [],
  "summary": "",
  "source_path": "",
  "source_hash": ""
}
```

#### CharacterState

```json
{
  "character_id": "1",
  "name": "角色名",
  "static_profile_ref": "chr/1.txt",
  "current_status": {
    "location": "",
    "physical": "",
    "emotion": "",
    "goal": "",
    "resources": [],
    "secrets_known": [],
    "secrets_hidden": []
  },
  "last_seen_scene": "ch03-sc04",
  "arc_progress": "",
  "evidence": []
}
```

#### RelationshipState

```json
{
  "a": "角色A",
  "b": "角色B",
  "state": "互不信任/合作/误解/敌对/暧昧",
  "since_scene": "ch02-sc01",
  "why": "",
  "known_to": ["角色A", "角色B"],
  "evidence": []
}
```

#### ForeshadowLedger

```json
{
  "foreshadow_id": "fs-001",
  "introduced_scene": "ch01-sc01",
  "description": "",
  "status": "open/payoff_due/resolved/abandoned",
  "payoff_target": "ch08-sc03",
  "related_entities": [],
  "evidence": []
}
```

#### SceneTaskPack

Scriptwriter 真正应消费的任务包：

```json
{
  "scene_contract": {
    "scene_id": "ch05-sc03",
    "title": "",
    "goal": "",
    "narrative_function": "",
    "pov": "",
    "tone": "",
    "length_target": ""
  },
  "high_priority_context": {
    "current_chapter_so_far": "",
    "previous_scene": "",
    "active_character_cards": [],
    "relationship_cards": [],
    "must_keep_facts": [],
    "must_advance": [],
    "must_not_violate": []
  },
  "retrieved_evidence": [],
  "global_context": {
    "worldview": "",
    "outline_slice": "",
    "style_profile": ""
  },
  "post_write_requirements": {
    "extract_state_delta": true,
    "run_consistency_check": true
  }
}
```

### 5.2 新的生成管线

```text
Showrunner 生成/维护事件图式大纲
        ↓
StoryMemoryFacade 构建 NarrativeState
        ↓
Director 选择下一场 scene_contract
        ↓
StoryMemoryFacade.compose_scene_task_pack()
        ↓
Scriptwriter 根据 SceneTaskPack 写作
        ↓
StoryMemoryFacade.extract_state_delta()
        ↓
Critic/Validator 证据化一致性检查
        ↓
状态更新 + fix_tickets + 下一场约束
```

---

## 6. GraphRAG 改造方案

### 6.1 分片单位从字符改为叙事单元

当前：

- `RecursiveCharacterTextSplitter(chunk_size=1200, overlap=160)`

建议改为混合索引：

1. **Scene Chunk**：每个 `.arc` 场景是一级 chunk。
2. **Event Chunk**：每场中抽取 1-N 个事件。
3. **Entity Card**：角色/地点/物品/组织的当前状态卡。
4. **Evidence Span**：原文证据片段，用 source_path + scene_id + line_range 标记。
5. **Fallback Token Chunk**：只在非结构化长文本上使用 TokenTextSplitter。

这样可以解决“关键人物切在开头和尾部”的问题：人物关系不是靠字符窗口碰巧同框，而是由场景级抽取、事件级抽取和实体合并共同建立。

### 6.2 抽取目标从三元组升级为叙事声明

三元组不够表达状态变化。应抽取：

- `FactClaim`：事实声明。
- `StateChange`：状态变化。
- `Event`：事件。
- `RelationChange`：关系变化。
- `Foreshadow`：伏笔。
- `WorldRule`：世界规则。
- `ConflictCandidate`：潜在冲突。

示例：

```json
{
  "type": "relation_change",
  "subject": "林烬",
  "object": "沈棠",
  "from": "互相试探",
  "to": "暂时结盟",
  "scene_id": "ch04-sc02",
  "evidence": "两人约定在钟楼交换情报……",
  "confidence": 0.82
}
```

### 6.3 图谱边必须带时序和证据

边属性建议：

- relation_type
- status
- valid_from_scene
- valid_until_scene
- source_scene_ids
- evidence_spans
- confidence
- last_updated

这样同一对人物可以有多条历史关系，而不是被合并成一条模糊边。

### 6.4 查询模式从问答变为写作约束生成

当前 GraphRAG query 返回 answer + fact_constraints。建议增加：

- `query_mode="scene_task_pack"`
- 输入：scene_id、characters、outline_goal、objects、location。
- 输出：
  - must_keep_facts
  - relevant_events
  - active_relationships
  - open_foreshadows
  - conflict_risks
  - evidence_snippets

这些字段直接进入 Scriptwriter prompt，而不是让模型读一段普通问答结果。

### 6.5 GraphRAG 构建不应只由 UI 手动触发

当前工具层禁止 Agent build/refresh/reset 是正确的安全边界。但在 auto-write 管线内，写完场景后应由后端内部状态管线更新轻量 NarrativeState，不必每次重建重型 GraphRAG。

推荐两层：

- **轻量 StoryMemory 增量更新**：每场写完立即抽取并写入。
- **重型 GraphRAG 重建/刷新**：用户 UI 或后台节流触发，用于全项目索引。

---

## 7. Scriptwriter 改造方案

### 7.1 `build_scene_context()` 升级为 `build_scene_task_pack()`

保留现有函数兼容，但新增：

```python
def build_scene_task_pack(
    user_id: str,
    project_name: str,
    current_chapter_index: int,
    current_scene_index: int,
    scene_guidance: str = "",
    export_format: str = "arc",
) -> dict:
    ...
```

内部调用：

- `StoryMemoryFacade.load_state()`
- `StoryMemoryFacade.resolve_scene_contract()`
- `StoryMemoryFacade.retrieve_relevant_history()`
- `StoryMemoryFacade.compose_scriptwriter_prompt_context()`

最终仍返回给 `ScriptwriterAgent.write_script_stream()` 所需字段，以减少改动面。

### 7.2 Prompt 输入分层

Scriptwriter prompt 应把上下文显式分优先级：

1. **最高优先级：当前场景契约**
2. **高优先级：必须保持的事实/角色状态/关系状态/伏笔**
3. **中优先级：近邻原文**
4. **中优先级：相关历史证据**
5. **低优先级：全局设定/完整大纲/全量角色**

不要把全量角色和当前场景角色混在同一层。

### 7.3 当前场景角色卡

每场只把当前登场角色卡放在高优先级区：

- 此刻位置。
- 此刻目标。
- 情绪状态。
- 已知秘密。
- 隐瞒信息。
- 与同场角色关系。
- 上一次出场发生了什么。
- 本场必须推进的角色弧线。

全量角色档案可以作为后备材料，或只注入摘要。

### 7.4 写作前先生成微型执行计划

可以让 Scriptwriter 在 `<conception>` 中遵循固定短结构：

- 本场冲突。
- 人物状态。
- 必须呼应。
- 禁止矛盾。
- 情绪推进。

不需要长思维链，但要让模型先“对齐任务包”。

### 7.5 写完后强制状态抽取

`write_script_stream()` 完成后，Auto-write / Production 应调用：

- `StoryMemoryFacade.extract_state_delta(scene_text, scene_contract)`
- `StoryMemoryFacade.validate_delta()`
- `StoryMemoryFacade.apply_delta()`

这一步是长篇连续性的核心。

---

## 8. Critic 改造方案

### 8.1 Critic 输出 `fix_tickets`

新增结构：

```json
{
  "ticket_id": "fix-001",
  "severity": "high",
  "category": "temporal/factual/character/world_rule/style/pacing",
  "scene_id": "ch07-sc02",
  "problem": "",
  "evidence": [
    {"scene_id": "ch02-sc01", "quote": ""},
    {"scene_id": "ch07-sc02", "quote": ""}
  ],
  "suggested_fix": "",
  "target_agent": "agent_scriptwriter",
  "status": "open"
}
```

### 8.2 一致性检查分类

参考 ConStory-Bench 思路，SparkArc 可先落地五类：

- 时间线与因果。
- 人物状态与动机。
- 世界规则与设定。
- 事实细节。
- 叙事风格与视角。

每条问题必须带证据，不允许只输出泛泛评价。

### 8.3 Critic 与 Scriptwriter 闭环

推荐流程：

```text
Scriptwriter 写场景
    ↓
Critic.validate_scene(scene_text, scene_task_pack, narrative_state)
    ↓
生成 fix_tickets
    ↓
低风险问题自动传回 Scriptwriter rewrite
高风险问题交给用户确认
    ↓
复检
```

---

## 9. Showrunner / Director / Lorebook 改造方案

### 9.1 Showrunner：大纲升级为事件图

现有大纲应扩展字段：

- scene_id
- event_id
- involved_characters
- location
- conflict
- turning_point
- foreshadow_in
- foreshadow_out
- relationship_changes
- required_payoff
- narrative_function

这样 Scriptwriter 不需要从自然语言大纲里猜“本场到底要干什么”。

### 9.2 Director：按 scene_contract 委派

Director 委派 Scriptwriter 时，应先从 StoryMemoryFacade 获取 scene_contract：

```json
{
  "chapter": "三 · 暗潮",
  "scene": "3-2 交易破裂",
  "goal": "让主角发现盟友隐瞒线索，但暂不摊牌",
  "must_keep": [],
  "must_advance": [],
  "acceptance_criteria": []
}
```

Director 的验收不再只看“写了没有”，还看 contract 是否满足。

### 9.3 Lorebook：静态设定 + 动态状态分离

Lorebook 保持静态真相源：

- 世界观。
- 人物原始设定。
- 地点/组织/规则。

StoryMemory 维护动态状态：

- 当前人物位置、关系、秘密、伤势。
- 物品归属。
- 伏笔状态。

二者不要混成一份文本。

### 9.4 Muse：灵感进入事件候选池

Muse 产生的灵感不应只是一段文本，可转为：

- candidate_event
- candidate_conflict
- candidate_foreshadow
- candidate_character_turn

由 Showrunner 或用户确认后进入事件图。

---

## 10. 分期落地路线

### 阶段一：低风险增强，1-2 周

目标：不大改数据库，不动主链路，只增强上下文任务包。

任务：

1. 新增 `server/agents/story_memory/` 基础模块，先用 JSON 文件持久化到项目目录。
2. 每场写完后生成 `scene_summary`，写入 `.story_memory/scenes.json`。
3. 为当前场景登场角色生成临时 `character_state_cards`。
4. `build_scene_context()` 增加相关历史召回：
   - 当前登场角色上一次出场。
   - 当前场景涉及的 open foreshadows。
   - 当前章节上一场。
   - 上一章摘要。
5. Scriptwriter prompt 增加“当前场景任务包”高优先级区。
6. Critic 输出结构化 `fix_tickets`，先不自动修复。

验证：

- 构造 6 章样例，早期埋伏笔，中后期回收。
- 检查任务包是否召回伏笔。
- 检查角色状态卡是否被注入。

### 阶段二：结构化状态与增量更新，3-6 周

目标：建立真正 NarrativeState。

任务：

1. 从 `.arc` 场景抽取事件、角色状态、关系变化、物品状态、伏笔。
2. 状态增量进入待确认/自动确认机制。
3. GraphRAG 构建增加 scene/event/entity 混合 chunk。
4. `graph_rag_tool` 增加 writing_guardrails 的结构化返回。
5. Auto-write 每场执行：
   - 写作。
   - 状态抽取。
   - 一致性校验。
   - 更新下一场约束。
6. Director 委派改用 scene_contract。

验证：

- 多章连续生成后，随机抽查角色状态、关系变化、伏笔状态。
- Critic 能指出冲突并给证据。

### 阶段三：全局评估与修订闭环，6-10 周

目标：质量可测、可迭代。

任务：

1. 建立长篇创作回归基准：
   - 角色一致性。
   - 伏笔回收。
   - 时间线。
   - 世界规则。
   - 文风稳定。
2. Critic 自动生成 fix_tickets。
3. Scriptwriter 根据 fix_tickets 做局部修订。
4. 修订后复检并关闭 ticket。
5. 建立项目级质量仪表盘。

### 阶段四：高级能力，长期

目标：接近论文中的 book-scale workflow。

任务：

1. Showrunner 事件图式大纲。
2. 角色模拟驱动的局部情节建议。
3. 多版本剧情分支状态管理。
4. 故事专用 reward/judge。
5. 用户可视化编辑 NarrativeState。

---

## 11. 与现有收口层的对接方式

### 后端

优先接入：

- `server/agents/routes/context_builder.py`
- `server/agents/project_content.py`
- `server/agents/agent_factory.py`
- `server/agents/agent_tools.py`
- `server/agents/tools/registry.py`
- `server/agents/routes/streaming_utils.py`
- `server/agents/routes/execution_core.py`

不要把 StoryMemory 逻辑散落到路由里。路由只负责调用 Facade。

### 前端

如果要展示状态：

- 长耗时状态构建走 `createStreamingTask`。
- 聊天工具事件仍走 `chatStore`。
- 用户可见文案走 i18n。

### 数据迁移

第一阶段建议先用项目目录 JSON，降低风险。等模型稳定后再考虑数据库模型：

- 修改 `server/core/models.py`
- 用 `server/gen_migration.py` 自动生成迁移
- 不手写迁移

---

## 12. 最小测试方案

### 12.1 架构契约测试

新增或扩展：

- `server/test/architecture/test_common_infrastructure_contracts.py`
- `server/test/architecture/test_agent_prompt_contracts.py`
- `server/test/architecture/test_tool_registry_contracts.py`

覆盖：

- StoryMemoryFacade 是唯一入口。
- Scriptwriter 上下文构建走 SceneTaskPack。
- GraphRAG 写作约束返回结构稳定。
- Critic fix_tickets 字段稳定。

### 12.2 业务回归测试

不放入 architecture 目录，建议新建：

- `server/test/story_memory/`

测试：

1. 场景写后能抽取事件。
2. 角色状态能随场景变化。
3. 伏笔 open -> resolved 状态可更新。
4. 当前场景任务包能召回早期相关事件。
5. 冲突事实能生成 ticket。

### 12.3 长篇样例基准

构造一个小型项目：

- 8 章。
- 每章 2-3 场。
- 5 个角色。
- 3 条伏笔。
- 2 个世界规则。
- 2 次关系反转。

评估：

- 召回率：任务包是否包含应该包含的历史事实。
- 冲突率：生成是否违背状态。
- 修复率：Critic ticket 是否能被 Scriptwriter 修复。
- 文学质量：重复、节奏、对白自然度、视角稳定。

---

## 13. 优先级建议

最高优先级：

1. `SceneTaskPack`。
2. 写后状态抽取。
3. 当前场景角色状态卡。
4. 伏笔账本。
5. Critic 证据化 fix_tickets。

中优先级：

1. GraphRAG 叙事单元分片。
2. 事件图式大纲。
3. Director scene_contract 委派。
4. 质量仪表盘。

低优先级：

1. 完整角色模拟。
2. 自训练 reward model。
3. 多版本剧情分支图。

---

## 14. 结论

SparkArc 当前架构已经有很好的收口层，因此上下文创作流的升级不需要伤筋动骨。真正需要改变的是核心抽象：

从：

> “把世界观、角色、大纲、前文拼成一个 prompt”

升级为：

> “围绕当前场景契约，从结构化故事状态中动态组装高优先级写作任务包，并在写完后增量更新状态”。

这也是 2025-2026 年长篇故事生成研究的共同方向：事件图、动态压缩、角色状态、知识图谱、证据化一致性检查、多分辨率规划脚手架。长上下文让我们有能力保留更多原文，但真正提升创作质量的，是让每个 Agent 围绕同一个可更新、可检索、可验证的叙事状态工作。

