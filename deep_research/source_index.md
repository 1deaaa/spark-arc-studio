# 来源索引

## 2025-2026 重点论文 / 项目

1. [StoryWriter: A Multi-Agent Framework for Long Story Generation](https://arxiv.org/abs/2506.16445)
   - 关键词：事件图式大纲、章节规划、动态历史压缩、写作代理。
   - 对 SparkArc 的直接启发：把 `build_scene_context()` 从“当前章 + 前章尾场”升级为“当前事件相关历史动态压缩”；Showrunner 大纲升级为事件图。
   - 官方实现：[THU-KEG/StoryWriter](https://github.com/THU-KEG/StoryWriter)

2. [Guiding Generative Storytelling with Knowledge Graphs](https://arxiv.org/abs/2505.24803)
   - 关键词：知识图谱辅助叙事、角色/地点/事件的结构化控制。
   - 对 SparkArc 的直接启发：GraphRAG 不应只做字符分片三元组问答，应升级为角色、地点、物品、事件的叙事状态仓库。

3. [TaleFrame: An Interactive Story Generation System with Fine-Grained Control and Large Language Models](https://arxiv.org/abs/2512.02402)
   - 关键词：实体、事件、关系、故事大纲四元拆分。
   - 对 SparkArc 的直接启发：UI 与后端都应允许用户编辑实体、事件、关系、大纲，而不是只编辑长文本。

4. [StoryBox: Collaborative Multi-Agent Simulation for Hybrid Bottom-Up Long-Form Story Generation Using Large Language Models](https://arxiv.org/abs/2510.11618)
   - 关键词：底层角色模拟 + 顶层规划的混合叙事。
   - 对 SparkArc 的直接启发：Lorebook 可保持静态设定，StoryMemory 维护动态角色状态，二者分离。
   - 官方实现：[amcghm/StoryBox](https://github.com/amcghm/StoryBox)

5. [Lost in Stories: Consistency Bugs in Long Story Generation by LLMs](https://arxiv.org/abs/2603.05890)
   - 关键词：长篇叙事一致性错误、角色/事实/时间/世界规则、显式证据化检测。
   - 对 SparkArc 的直接启发：Critic 应输出证据化一致性错误和可执行 `fix_tickets`，不要只给泛泛评价。

6. [Narrative Theory-Driven LLM Methods for Automatic Story Generation and Understanding: A Survey](https://arxiv.org/abs/2602.15851)
   - 关键词：叙事理论驱动、任务与指标分类、理论化评估。
   - 对 SparkArc 的直接启发：质量评估要覆盖叙事功能、情节推进、角色弧光，而不只是局部语言流畅度。

7. [Retell, Reward, Repeat: Reinforcement Learning for Narrative Theory-Informed Story Generation](https://arxiv.org/abs/2601.17226)
   - 关键词：基于叙事理论的 RL 奖励与对齐。
   - 对 SparkArc 的直接启发：长期可考虑故事专用 judge/reward，但短期应先沉淀 Critic 结构化评分。

8. [POLARIS: Guiding Small Models to Write Long Stories](https://arxiv.org/abs/2606.04095)
   - 关键词：LLM-as-a-judge 奖励、锚定参考注入、长文长度泛化。
   - 对 SparkArc 的直接启发：长篇生成要有锚定参考和质量奖励，而不是只靠 prompt。

9. [Towards Human-Level Book-Writing Capability](https://arxiv.org/abs/2605.17064)
   - 关键词：多分辨率 planning scaffold、从粗到细的书籍生成。
   - 对 SparkArc 的直接启发：Showrunner 的梗概/节拍/大纲方向正确，但需要进一步细化到章节、场景、事件、叙事功能。

10. [StoryAlign: Evaluating and Training Reward Models for Story Generation](https://arxiv.org/abs/2605.04831)
    - 关键词：故事生成专用 reward / judge。
    - 对 SparkArc 的直接启发：可为 Critic 建立故事专用评价维度与项目级质量仪表盘。

11. [THU-KEG/StoryWriter](https://github.com/THU-KEG/StoryWriter)
    - 关键词：StoryWriter 官方开源实现。

12. [amcghm/StoryBox](https://github.com/amcghm/StoryBox)
    - 关键词：StoryBox 官方开源实现。

13. [Learning to Reason for Long-Form Story Generation](https://arxiv.org/abs/2503.22828)
    - 关键词：Next-Chapter Prediction、章节计划、浓缩故事信息、人物卡、上一章原文、下一章 synopsis。
    - 对 SparkArc 的直接启发：Scriptwriter 每章/每场前应先得到浓缩 Story-Information，而不是只塞全量材料。

## 官方长上下文能力参考

1. [Google Gemini 2.5 Pro 官方文档](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/gemini/2-5-pro)
   - 关键词：长上下文、生产可用模型。
   - 对 SparkArc 的直接启发：应把 256K 以上上下文作为工程基线，但仍需要结构化状态和动态检索。

2. [Google Gemini 2.5 官方发布博客](https://blog.google/innovation-and-ai/models-and-research/google-deepmind/gemini-model-thinking-updates-march-2025/)
   - 关键词：thinking model、长上下文、推理能力。
   - 对 SparkArc 的直接启发：模型能力提升应转化为更强的计划、校验、状态抽取管线，而不是仅增加 prompt 长度。
