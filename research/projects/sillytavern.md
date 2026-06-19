# SillyTavern: Open-source Lorebook Keyword-Triggered Memory

*   **项目官网链接：** [https://github.com/SillyTavern/SillyTavern](https://github.com/SillyTavern/SillyTavern)
*   **流行时间：** 2023–2026年 (全球开源角色扮演、互动叙事前端的第一标杆)
*   **核心领域：** 开源世界观书 (Lorebook)、关键词正则触发、递归扫描、Token 预算插入深度管理

---

## 一、 核心目标与开源痛点

在开源的本地部署大模型（如 LLaMA-3、Mistral 等）上进行长时间的角色扮演（Roleplay）和长篇互动叙事时，本地模型对长距离上下文的“注意力保持能力”普遍显著弱于商业閉源大模型。如果直接塞入几万字设定，本地大模型会立刻发生严重的“复读”、“人设崩溃”和“遗忘”。

SillyTavern 开源社区设计了名为 **“世界观书 (Lorebook)”** 的检索与注入机制。它通过高精度的关键词触发、递归扫描以拉取嵌套设定，并精细管理插入深度，从而在仅有 8k–16k 物理窗口的本地大模型上实现了极强的人设锚定和细节延续。

---

## 二、 系统架构设计 (Architecture)

SillyTavern 的 Lorebook 核心逻辑运行在前端会话控制器中：

```mermaid
graph TD
    UserMsg[用户最新输入/续写 Request] -->|拼合| RecentChat[最近几轮会话上下文]
    
    subgraph Lorebook 检索引擎 (Regex Keyword Scanning)
        RecentChat -->|1. 关键词正则扫描| KeyScanner[正则扫描器 Regex Scanner]
        LorebookDB[Lorebook JSON 数据库] -->|提供规则集| KeyScanner
        
        KeyScanner -->|匹配成功 (如触发 '魔法')| ActiveEntries[一级激活条目]
        ActiveEntries -->|2. 递归扫描其内容| KeyScanner
        KeyScanner -->|触发二级关键词 (如 '梅林')| RecurEntries[二级激活条目]
    end
    
    RecurEntries & ActiveEntries -->|3. 插入控制| ContextCompiler[上下文拼装器]
    RecentChat -->|最近正文| ContextCompiler
    
    ContextCompiler -->|依据 Depth & Allocation 分配 Token 权重| FinalPrompt[拼装后的 Final Prompt]
```

---

## 三、 核心机制与算法细节

### 1. 正则关键词扫描与递归触发 (Recursive Keyword Triggering)
*   **一级扫描**：每条 Lorebook 条目（例如“梅林学院”）都绑定了一个“触发词列表（Keywords）”，支持正则表达式（如 `/梅林|魔法院/i`）。当最近的 $N$ 轮历史对话中匹配到这些词时，该条目即被激活。
*   **二级递归扫描**：被激活条目的“内容文本”可能会包含其他条目的关键词。SillyTavern 会对已激活条目的文本进行**二次递归扫描**。例如，“梅林学院”的内容中提到了“梅林院长”。系统会进一步激活“梅林院长”的条目，实现关联记忆的一并召回。

### 2. 精细化插入控制 (Depth, Order & Target)
为了防止 Lorebook 抢占太多 Token，SillyTavern 提供了极其精细的上下文装配参数：
*   **插入深度 (Insertion Depth)**：决定该条目应该插在上下文的什么位置。通常，插在越靠近最近对话（即最底部）的位置，LLM 的注意力越集中，但可能会打断对话连贯度；插在顶部则作为背景规则。
*   **插入顺序 (Insertion Order)**：当多个 Lorebook 被触发时，确定它们的排列顺序。
*   **Token 限制 (Token Budget limit)**：设置 Lorebook 最多只能占用比如 20% 的上下文，超出则按优先级截断，保证给最近对话留够空间。

---

## 四、 工程实现与数据流设计 (Engineering & Prompts)

在 SillyTavern 的 JSON 表征中，一个典型的 Lorebook 条目定义如下：

```json
{
  "key": ["梅林", "merlin"],
  "content": "梅林是梅林学院的创始人。他性格怪异，留着白色长须，喜欢喝烈酒，暗中持有‘预言之球’。",
  "comment": "Merlin Character Info",
  "selective": true,          // 是否仅在有触发词时激活
  "secondary_keys": ["学院"], // 辅助触发词，提高精确度
  "insertion_order": 100,
  "insertion_depth": 4        // 插入在最近第 4 轮对话之前
}
```

### 开源与工业价值：
SillyTavern 的 Lorebook 机制是开源社区在长上下文窗口匮乏时代摸索出的**“降维打击”**方案。其“关键词正则匹配 + 递归扫描 + 插入深度精细分配”的组合拳，能够让极小的本地模型在长篇对话中始终不偏离核心设定，其分层分配上下文的思想非常值得商业小说系统借鉴。
