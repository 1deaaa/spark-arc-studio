# SparkArc 长篇创作流研究笔记

## 本地现状

- Scriptwriter 正式业务流入口：`server/agents/routes/production.py` 的 `/api/scriptwriter/compose/stream`。
- 生产端上下文包：`build_scriptwriter_context_pack()` 读取世界观、全量角色、完整大纲、叙事记忆，并解析当前 `.arc` 文件，把目标场景之前内容序列化为 `context`。
- Auto-write：`server/agents/routes/auto_write.py` 每个场景调用 `build_scene_context()`，再传给 `write_script_stream()`。
- Scriptwriter prompt：`scriptwriter.yaml` 的 user 中动态注入 `story_tags/worldview/full_outline/narrative_memory/chr_reference/roles/style_profile/context/guidance/feedback`。
- 连续性机制：主要是当前章前文 + 前序各章最后一个场景 + 梗概/节拍表；没有显式“写作状态机/角色状态时间线/伏笔状态表”。
- graph RAG：`GraphRAGService` 用 1200 字符 chunk、160 overlap、最多 120 chunks、每 chunk 抽三元组，工具只读 query/status。

## 外部高相关来源

- StoryWriter: A Multi-Agent Framework for Long Story Generation, arXiv 2506.16445, 2025-06-19。
  - 事件图式大纲、章节规划、当前事件相关历史动态压缩、输出重写。
- Learning to Reason for Long-Form Story Generation, COLM 2025 / arXiv 2503.22828。
  - 章节 i 的 Story-Information：全局 sketch、此前章节摘要、基于已写章节的人物卡、上一章原文、下一章 synopsis。
- Lost in Stories: Consistency Bugs in Long Story Generation by LLMs, arXiv 2603.05890, 2026-03-06。
  - 长故事一致性错误类型：角色、事实、叙事、时间、世界规则等；错误常出现在后段，与早中段事实错位。
- Guiding Generative Storytelling with Knowledge Graphs, arXiv 2505.24803。
  - 用知识图谱作为叙事元素中央仓库，动态保证角色/地点/物品/事件连续性。
- A Survey on LLMs for Story Generation, Findings EMNLP 2025。
  - 分类：独立生成 vs 作者辅助、多 Agent、outline-based、DOME、CollabStory 等。

## 初步问题假设

1. 现有上下文是“全量塞入 + 简单三圈记忆”，缺少按当前场景目标动态筛选/压缩历史。
2. 角色全量注入避免遗漏，但长篇时会变成噪音；缺少“当前场景角色状态卡/关系状态/已知信息边界”。
3. GraphRAG chunk 以字符分块，实体跨 chunk 时关系抽取容易断裂；没有场景级/事件级 canonical unit。
4. Auto-write 逐场景生成后没有把输出即时结构化成剧情状态、角色状态、伏笔账本，再喂给下一场。
5. Critic 审稿关注 AI 味与逻辑，但没有形成可执行的“修订闭环”和长期质量记忆。
