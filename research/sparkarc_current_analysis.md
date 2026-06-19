# SparkArc 现有上下文拼接方式与连贯性机制审计报告

本报告对 SparkArc 项目中现有的上下文拼接机制（特别是 `Scriptwriter` 智能体连续工作时的上下文与连贯性管理逻辑）进行纯客观的静态审计。本报告的所有内容均基于对服务端核心代码（`context_builder.py`、`agent_scriptwriter.py`、`context_provider.py`）的源程序分析。

---

## 一、 Scriptwriter 运行时上下文组装

In现行架构中，无论是手动创作（`production.py` / `compose`）、全自动批处理写作（`auto_write.py`）还是导演智能体委派（`director_graph.py`），`Scriptwriter` 所需的上下文均统一收口至 `context_builder.py` 中的 `build_scriptwriter_context()` 函数。

该函数从项目目录（`大纲.txt`、`梗概.txt`、`世界观.txt`、角色文件夹 `chr/`）以及已生成的 `.arc` 文件中提取并格式化以下数据字段，拼装为上下文包：

```python
return {
    "worldview": worldview,           # 世界观设定全文
    "roles": roles,                   # 项目中全量角色的设定文本拼合
    "chr_map": chr_map,               # {int: str} 角色 ID 与名称的字典，用于 .arc 语法约束
    "full_outline": full_outline,     # 完整的“大纲.txt”原文内容
    "narrative_memory": narrative_memory, # “梗概.txt”全文与“节拍表.txt”摘要的拼合文本
    "context": context,               # 基于“三圈记忆策略”组装的前文内容
    "guidance": scene_guidance,       # 当前要写作场景的具体指导（如大纲中的场景梗概）
    "current_beat": current_beat,     # 当前对应的启发式情感节拍描述
    "current_chapter_index": current_chapter_index,
    "current_scene_index": current_scene_index,
}
```

在 `agent_scriptwriter.py` 中，根据当前设定的输出格式（是剧本格式 `.arc`，还是小说格式 `novel`）传递给对应的 Prompt 模板。

*   **小说模式（novel）**：
    通过 `load_prompt("scriptwriter", "generate_novel")` 加载模板，传入 `length_instruction`、`worldview`、`roles`、`full_outline`、`narrative_memory`、`context`、`guidance`、`style_profile` 和 `feedback`。
*   **剧本模式（arc）**：
    额外传递代表角色映射的 `chr_reference` 以及作为格式示例的 `arc_example`（加载自根目录下的 `ARC_AI_Format.arc`）。

---

## 二、 现有“连续工作连贯性”维持策略：“三圈记忆”

为了在连续场景写作中维持上下文的连贯性，`context_builder.py` 的 `build_scene_context()` 函数负责执行“三圈记忆”裁剪与组装：

### 1. 第一圈：最近戏剧流 (Hard Context)
*   **组装逻辑**：当前正在撰写的章节内，目标场景之前所有已完成场景的 `.arc`（或小说）全文。
*   **目的**：提供极近的前文，确保动作和对话承接上一场景。

### 2. 第二圈：跨章情感锚点 (Sliding Window)
*   **组装逻辑**：前序所有章节的 **最后一个场景（尾声场景）** 的全文。
*   **核心实现**：
    ```python
    tail_scenes: List[str] = []
    for ci in range(current_chapter_index):
        raw = _read_arc_file_safe(arc_files[ci])
        if not raw: continue
        try:
            parsed = parse_arc(raw)
            if parsed:
                # 只取最后一个场景作为章末锚点
                last_scene_arc = serialize_to_arc([parsed[-1]])
                tail_scenes.append(
                    f"【第 {ci} 章 尾声 - {parsed[-1].get('scene', '')}】\n{last_scene_arc}"
                )
        except Exception: continue
    ```
    最终拼接到前文开头：`=== 前序各章节末尾场景（跨章连续性锚点）===`。

### 3. 第三圈：全局叙事线 (Compressed)
*   **组装逻辑**：全局梗概与情感节拍表。独立渲染到提示词中的 `{narrative_memory}`。

---

## 三、 本项目现行架构的问题与上下文注入的不合理之处

基于对代码的静态审计，现行上下文拼接和设定载入策略在长篇小说创作中存在以下问题：

### 1. 跨章记忆的“章尾留存”机制存在严重盲区
在 `build_scene_context` 中，前序章节仅仅保留了每个章节的最后一个场景（尾声场景）的原文。这一逻辑武断地假设所有跨章的核心线索和伏笔都必然出现在各章的结尾。如果一个关键伏笔或重要事件发生在某章的中段（例如第 2 章第 3 个场景，而第 2 章共 10 个场景），在续写第 3 章及之后的章节时，**该场景的微观文本会被彻底遗忘，物理前文中不再包含该伏笔的任何痕迹**。

### 2. 角色设定全量灌入，导致窗口臃肿与注意力消散
`load_character_bundle()` 会将该项目下所有的角色 `txt` 档案拼接成一个长文本（即 `roles` 字段）全量灌入。即使当前场景仅有两位主角在密谈，大模型也要被迫阅读几十个配角甚至背景板路人的生平卡片。这在长篇小说中会导致：
1.  **注意力稀释**：无关角色的特征和设定会干扰模型对当前核心角色动作和语气的一致性把握，极易导致人设漂移（OOC）。
2.  **上下文预算浪费**：随着配角增多，每次生成都携带大量的静态文本，造成极高的 Token 开销。

### 3. GraphRAG 记忆引擎在核心写作管线中处于闲置状态
项目虽然开发了功能完整的 `GraphRAGService`（位于 `server/agents/graphrag/service.py`），具备三元组提取、NetworkX 图构建、社区划分以及基于实体关系的 fact_constraints 提取能力。
但是在最核心的 `Scriptwriter` 智能体的创作逻辑（`write_script` / `write_script_stream`）与 `build_scriptwriter_context` 组装器中，**没有任何调用 GraphRAG 检索服务的接口**。GraphRAG 目前仅在边缘问答界面起作用，最核心的写作流依然在依赖纯文件的物理截断和拼接，无法利用图谱解决长距离实体依赖问题。
