# 通用大模型管理器 (LLM Manager)

这是一个功能强大且灵活的通用大模型（LLM）管理器。它基于 `LangChain` 和 `SQLAlchemy` 构建，旨在为不同规模和需求的应用提供统一、稳定的大模型接口服务。

该项目的设计目标是支持从个人开发、调试到多用户生产环境的多种复杂场景，并提供了一个图形化界面来简化核心配置的管理。

## ✨ 核心特性

- **多种运行模式**：
  - **无用户/全局单用户模式**：适用于后端服务、个人工具或开发调试，所有请求共享一套由环境变量配置的系统级LLM。
  - **多用户固定平台模式**：适用于需要保证模型质量和来源的场景。所有用户共享系统预设的平台，但可以使用自己的API Key。
  - **多用户自定义平台模式**：提供最大灵活性，允许每个用户自由添加、管理自己的LLM平台和模型。
- **统一的接口**：无论后端配置如何变化，开发者都可以通过简单的 `LLM_Manager.get_user_llm(user_id, usage_key="fast")` 来获取对应用户/用途的LLM实例。
- **多用途选中模型**：为每个用户维护“主模型 / 快速模型 / 推理模型”等多个用途槽位，并允许用户自定义新的用途，按需绑定不同模型。
- **系统与用户隔离**：明确区分“系统平台”和“用户私有平台”，系统平台由配置文件 (`llm_mgr_cfg.yaml`) 统一管理，用户平台数据则存储在数据库中。
- **灵活的密钥管理**：
  - 强烈推荐使用**环境变量**来管理API Key，避免密钥硬编码，提高安全性。
  - 支持用户为共享的系统平台提供自己的API Key，从而分摊成本。
  - 提供 `LLM_AUTO_KEY` 选项，允许在用户未提供密钥时，自动降级使用服务器的密钥（需谨慎使用）。
- **动态模型探测**：内置独立的模型探测工具 (`probe_platform_models`)，可以探测任何兼容OpenAI接口的平台所支持的模型列表。
  - **图形化配置工具**：提供一个基于 `Tkinter` 的GUI工具，用于管理 `llm_mgr_cfg.yaml` 文件，支持添加/编辑平台、管理 API Key（加密写入 YAML；可手动选择环境变量模式）、探测和测试模型，极大降低了配置心智负担。
- **数据库持久化**：使用 SQLite 存储用户配置、平台和模型信息，数据持久可靠。
- **自动配置修正**：当用户的配置失效（如模型或平台被删除），系统会自动回退到第一个可用的默认平台，保证服务的可用性。

## 📂 文件结构

```
.
├── __init__.py            # 包入口，导出主要接口和单例 LLM_Manager
├── manager.py             # AIManager 核心类（组合所有 Mixin）
├── config.py              # 配置加载与全局常量 (USE_SYS_LLM_CONFIG, LLM_AUTO_KEY 等)
├── models.py              # SQLAlchemy 数据库模型
├── security.py            # 安全与加密 (SecurityManager)
├── admin.py               # 平台与模型管理 Mixin (AdminMixin)
├── builder.py             # LLM 实例构建 Mixin (LLMBuilderMixin)
├── user_services.py       # 用户服务 Mixin (UserServicesMixin)
├── usage_services.py      # 用量统计 Mixin (UsageServicesMixin)
├── tracked_model.py       # TrackedChatModel - 自动追踪用量的 LLM 包装器
├── estimate_tokens.py     # Token 用量估算工具
├── utils.py               # 工具函数 (如 probe_platform_models)
├── llm_mgr_cfg.yaml       # 系统平台预设配置文件 (核心配置)
├── llm_mgr_cfg_gui.py     # 图形化配置管理工具
├── llm_config.db          # (自动生成) SQLite 数据库文件
└── README.md              # 本文档
```

- **`manager.py`**: 包含 `AIManager` 类，通过 Mixin 模式组合了 `AdminMixin`、`LLMBuilderMixin`、`UserServicesMixin`、`UsageServicesMixin` 等功能模块。这是与程序交互的主要入口。
- **`llm_mgr_cfg.yaml`**: **初始化配置文件**。用于定义初始的"系统平台"。首次启动时，管理器会将此文件中的平台同步到数据库。后续启动仅增量添加新平台，不会覆盖已有配置。
- **`llm_mgr_cfg_gui.py`**: 一个独立的GUI应用，支持**数据库模式**和 **YAML 模式**两种编辑方式。

## 🛠️ 第一次配置流程 (新手必读)

**注意：** 项目自带的配置文件 (`llm_mgr_cfg.yaml`) 预置了许多主流模型配置，但其中的 API Key 是无效的（占位用的）。

首次使用时，你需要运行配置工具，填入你自己的 API Key。

1.  **设置主加密密钥 (LLM_KEY)**：
    - 系统使用 `LLM_KEY` 加密你的 API Key和所有用户自定义的API Key。你可以设置环境变量，或者直接运行 GUI 工具，它会提示你输入并自动保存。

2.  **启动配置工具**：
    - 在终端进入 `server/llm/llm_mgr` 目录，运行 `python llm_mgr_cfg_gui.py`。
    - 你会看到预置的平台（如 DeepSeek, OpenRouter），但它们的 Key 是无法使用的。

3.  **替换并激活平台**：
    - 选中你打算使用的平台，在右侧填入你的真实 **API Key** 并点击保存。
    - 对于不需要的平台，建议直接删除。

4.  **验证模型**：
    - 点击 **“探测可用模型”**。如果配置正确，右侧会列出该平台支持的所有模型。
    - 在左侧选中一个模型，点击 **“测试选中模型”**，看到“测试成功”即表示配置完成。

5.  **检查用途绑定**：
    - 点击 **“系统用途管理”**。
    - 确保 `main` (主模型)、`fast` (快速模型)、`reason` (推理模型) 绑定的模型是你刚刚配置过 Key 的有效模型。

6.  **最终测试**：
    - 在左侧选中一个模型，点击 **“测试选中模型”**。
    - 如果看到“测试成功”的日志，说明配置已完成！

## ⚙️ 核心概念与运行模式

理解本项目的运行模式至关重要，这直接影响到功能的表现和二次开发。

### 1. 系统用户 (`SYSTEM_USER_ID = "-1"`)

这是一个特殊的虚拟用户ID。当代码中使用 `LLM_Manager.get_user_llm()` (不带`user_id`参数) 或 `LLM_Manager.get_user_llm(user_id="-1")` 时，管理器会进入**系统模式**。

- **目的**：为应用后端、全局服务或开发调试提供一个统一的LLM实例。
- **密钥来源**：优先使用 `llm_mgr_cfg.yaml` 中系统默认平台 `api_key`（YAML 中的 `ENC:` 字段会在程序启动时由 `LLM_KEY` 解密加载）。如果 YAML 中未配置系统平台的密钥或密钥缺失，程序会提示您配置；GUI 会在必要时提示设置 `LLM_KEY` 并可将其写入 `.env` 文件（或提示手动设置环境变量），但默认情况下 GUI 不会为每个平台自动创建单独的环境变量。

### 2. 全局模式开关

在 [`config.py`](config.py) 中有两个重要的全局开关：

- **`USE_SYS_LLM_CONFIG = True` (多用户固定平台模式)**
  - 所有用户都只能看到和使用 `llm_mgr_cfg.yaml` 中定义的系统平台。
  - 用户**不能**创建、修改或删除自己的平台和模型。
  - 用户**可以**为这些系统平台提供自己的API Key，这些Key会安全地存储在数据库的 `llm_sys_platform_keys` 表中，与用户ID关联。
  - 这种模式兼顾了模型的统一管理和成本的分摊。

- **`USE_SYS_LLM_CONFIG = False` (多用户自定义平台模式)**
  - 这是**默认**的模式。
  - 此模式下，用户拥有最大权限。
  - **系统平台依然可见且可用**，但用户获得了“写权限”。
  - 用户可以通过调用 `AIManager` 的 `add_platform`, `add_model` 等方法来创建自己的私有平台和模型。
  - 适用于需要高度自定义的场景。

### 3. 自动密钥降级与优先级 (`LLM_AUTO_KEY`)

系统在获取 API Key 时遵循 **“用户私有 > 系统后备”** 的原则：

1. **用户私有密钥**：如果用户为某个系统平台设置了专属 Key（存储在数据库中），则优先使用。
2. **系统后备密钥**：只有当用户未设置 Key 时，系统才会检查 `LLM_AUTO_KEY`。

- **`LLM_AUTO_KEY = True`**
  - **⚠️这是一个需要特别注意的选项！**
  - 当一个普通用户使用一个**系统平台**但没有提供自己的 API Key 时，如果此选项为 `True`，管理器会自动回退并**使用管理员在 `llm_mgr_cfg.yaml` 中配置的系统平台 Key**（已解密）作为后备 API Key。
  - **优点**：可以为免费用户或未配置的用户提供体验。
  - **风险**：**可能会导致服务器成本意外增加！** 如果你不想为用户免费提供服务，请务必将此项设置为 `False`。

- **`LLM_AUTO_KEY = False`**
  - 更安全的选项。
  - 如果用户没有为系统平台提供自己的API Key，在调用LLM时会直接抛出 `ValueError`，提示用户需要配置API Key。

**推荐设置**：
- 如果你希望 **服务器为用户提供统一服务并承担费用**（即“我固定死所有的模型然后给所有用户提供 API 服务”），请将 `LLM_AUTO_KEY = True`，并在 `llm_mgr_cfg.yaml` 中配置系统默认平台的 API Key（由管理员支付）。
- 如果你希望 **用户必须使用自己的 Key 并付费**（即“我固定死所有模型但用户自己给 API 付钱”），请将 `LLM_AUTO_KEY = False`，并在前端或用户设置中要求用户填写他们的 API Key。

### 4. 多用途模型槽

- **默认用途**：系统会为每个用户自动创建 `main`（主模型）、`fast`（快速模型）、`reason`（推理模型）三个槽位，并在注册时绑定默认平台/模型。
- **自定义用途**：通过接口 `POST /api/ai/user-selection/usage` 或 `AIManager.create_user_usage_slot(...)` 可以新增任意 `usage_key`，并指定初始模型。
- **查询与更新**：
  - `GET /api/ai/user-selection?usage_key=fast` 可查询指定用途；响应中还会包含 `usage_selections` 列表以展示所有用途的当前绑定。
  - `POST /api/ai/user-selection` 支持传入 `usage_key` 字段来更新特定用途的模型。
- **运行时选择**：`LLM_Manager.get_user_llm(user_id, usage_key="reason")` 会直接返回该用途绑定的模型实例；若参数省略，则默认为主模型。


## 🚀 快速上手

### 1. 安装依赖

项目依赖 `langchain`, `sqlalchemy`, `pyyaml`, `requests` 等库。可以通过 `pip` 安装：

```bash
pip install langchain-core langchain-openai sqlalchemy pyyaml requests python-dotenv
```

### 2. 配置 `llm_mgr_cfg.yaml`

这是开始使用的**第一步**，也是最重要的一步。你可以手动编辑，但更推荐使用GUI工具。

#### 2.1. (推荐) 使用GUI工具配置

在终端中运行以下任一命令来启动图形化配置界面：

```bash
python llm_mgr_cfg_gui.py
```

 <!-- 你可以替换成真实的截图 -->

**GUI功能简介**:
- **管理平台**：添加、删除平台，修改平台的`base_url`。
- **设为默认**：将选中的平台移动到配置文件顶部，使其成为系统默认选项。
- **管理API Key**：
    - **推荐方式**：填写 `API Key`，点击“保存 API Key”，工具会使用 `LLM_KEY` 将 Key 加密并存入 `llm_mgr_cfg.yaml`。GUI 不会默认将每个平台的 Key 写入独立系统环境变量；如果需要把某平台 Key 写到环境变量用于运维，请手动设置环境变量并在 YAML 中使用占位符（例如 `{MY_ENV_VAR}`）。
    - **不推荐方式**：只填写`API Key`，工具会警告并允许你将明文Key存入YAML。**这有严重的安全风险！**
- **模型探测**：填写`API Key`后，点击“探测可用模型”可以列出该平台所有兼容OpenAI接口的模型。
- **管理模型**：从探测结果中双击或选择后“添加模型到平台”，可以为模型设置一个易于理解的`显示名称`和可选的`extra_body`（用于传递额外的API参数）。
- **模型测试**：在左侧模型列表中选中一个模型，点击“测试选中模型”，可以快速验证该模型的可用性。

#### 2.2. 手动配置

直接编辑 [`llm_mgr_cfg.yaml`](llm_mgr_cfg.yaml:1) 文件。

- **`api_key`**: 推荐使用 GUI 将 Key 加密保存到 `llm_mgr_cfg.yaml`（默认方式）。如果你更喜欢使用占位符（如 `{OPENAI_API_KEY}`），请在系统中手动设置相应的环境变量，系统会自动解析并加载这些环境变量。
- **`models`**: 支持两种格式：
  1.  **简化格式** (字符串):
      ```yaml
      '通义flash': 'qwen-flash'
      ```
  2.  **完整格式** (字典): 用于需要传递额外参数（如关闭思考、设置top_k等）的场景。
      ```yaml
      '哈基米flash':
        'model_name': 'gemini-2.5-flash'
        'extra_body':
          'thinkingBudget': 0
      ```

### 3. 设置环境变量

在运行你的主应用之前，请确保在系统中设置了你在 `llm_mgr_cfg.yaml` 中引用的环境变量。

例如，如果你的配置是 `api_key: '{GEMINIX_API_KEY}'`，你需要：

- **Windows**:
  ```powershell
  $Env:GEMINIX_API_KEY="your_real_api_key"
  ```
  (为了永久生效，请在系统属性中设置)
- **Linux/macOS**:
  ```bash
  export GEMINIX_API_KEY="your_real_api_key"
  ```
  (为了永久生效，请添加到 `.bashrc` 或 `.zshrc`)

**提示**：GUI工具的“保存 API Key”功能会将 Key 加密保存到 `llm_mgr_cfg.yaml`；如果你选择使用环境变量占位符（如 `{MY_ENV_VAR}`），请确保在系统中手动设置对应的环境变量。GUI 当前不会自动为每个平台写入独立的环境变量。

### 4. 在代码中使用

大模型管理器现已重构为组件化结构，通过 Mixin 模式集成了管理、构建和统计功能。虽然内部结构发生了变化，但对外的核心 API 保持兼容。

你只需要直接引入全局单例 `LLM_Manager` 即可使用（单例在首次引入时会自动完成数据库初始化和配置同步，不再需要手动调用初始化函数）。

```python
from llm.llm_mgr import LLM_Manager

# --- 场景1: 获取指定用户的LLM ---
# 管理器会自动处理该用户的模型选择、API Key等所有配置
try:
    user_llm = LLM_Manager.get_user_llm(user_id="user_123")
    fast_llm = LLM_Manager.get_user_llm(user_id="user_123", usage_key="fast")
    # response = user_llm.invoke("你好")
    # for chunk in user_llm.stream("你好"):
    #     print(chunk.content, end="")
except ValueError as e:
    # 可能是API Key未配置等问题
    print(f"获取LLM失败: {e}")


# --- 场景2: 在后端服务或无用户场景下使用 ---
# 使用特殊的 SYSTEM_USER_ID，密钥来自 llm_mgr_cfg.yaml 中配置的加密 Key
try:
    system_llm = LLM_Manager.get_user_llm() # user_id=None 默认为系统用户
    # response = system_llm.invoke("写一个Python的Hello World")
except ValueError as e:
    print(f"获取系统LLM失败: {e}")


# --- 场景3: 强制使用某个特定的系统内置模型 ---
# 名字必须与 llm_mgr_cfg.yaml 中的显示名完全一致
try:
    qwen_llm = LLM_Manager.get_spec_sys_llm(
        platform_name="阿里云百炼",
        model_display_name="通义flash"
    )
    # response = qwen_llm.invoke("介绍一下通义千问")
except ValueError as e:
    print(f"获取指定LLM失败: {e}")
```

## 📦 双数据源架构：数据库 vs YAML

### 核心概念

系统平台配置支持两种数据源，各有不同的使用场景：

| 数据源 | 存储位置 | 生效方式 | 适用场景 |
|--------|----------|----------|----------|
| **数据库** (推荐) | `llm_config.db` | 修改即时生效 | 生产环境、Web 前端管理、动态修改 |
| **YAML** | `llm_mgr_cfg.yaml` | 需重启服务 | 初始化部署、配置分享、版本控制 |

### 同步策略 (三种触发时机)

1.  **首次启动 (First Initialization)**
    - **触发**：数据库为空。
    - **行为**：YAML 配置完整初始化到数据库。
    - **目的**：为新部署环境提供开箱即用的配置。

2.  **增量同步 (Incremental Sync)**
    - **触发**：后续启动 (默认)。
    - **行为**：仅添加 YAML 中新增的平台和模型，**不覆盖、不删除**数据库中已有的配置。
    - **目的**：允许通过 YAML 分发新模型，同时**保护**管理员在数据库模式下所做的自定义修改。

3.  **强制重置 (Force Reset)**
    - **触发**：GUI "从 YAML 重置" 按钮 或 API 调用。
    - **行为**：以 YAML 为准**覆盖**数据库中的系统平台配置（保留用户的 API Key）。
    - **目的**：当数据库配置混乱或需要恢复标准状态时使用。

### GUI 双模式

GUI 配置工具 (`llm_mgr_cfg_gui.py`) 支持模式切换：

- **📦 数据库模式 (默认)**：修改即时生效，无需重启服务。适合生产环境和 Web 前端管理。
- **📄 YAML 模式**：修改保存到 `llm_mgr_cfg.yaml`，需重启服务生效。适合配置分享和版本控制。

### 前端管理 API

管理员可通过 REST API 直接管理数据库中的系统平台：

```
GET    /api/ai/admin/sys-platforms          # 获取所有系统平台
POST   /api/ai/admin/sys-platform           # 添加系统平台
PUT    /api/ai/admin/sys-platform           # 更新系统平台
DELETE /api/ai/admin/sys-platform           # 删除系统平台
POST   /api/ai/admin/sys-platform/api-key   # 更新平台 API Key
POST   /api/ai/admin/reload-from-yaml       # 从 YAML 强制重置数据库
```

## ⚠️ 重要提示与常见问题

1.  **数据库是运行时权威源**
    - 服务运行时，所有模型配置从**数据库**读取，而非 YAML 文件。
    - 通过 Web 前端或 GUI 数据库模式的修改即时生效。
    - YAML 仅在服务启动时用于初始化，后续不会覆盖数据库中的修改。

2.  **API Key 安全性**
    - **⚠️ 严正警告：绝对禁止**将包含明文 API Key 的 `llm_mgr_cfg.yaml` 或 `.env` 文件提交到公共代码仓库（如 GitHub）。
    - **必须使用 `.gitignore`**：请确保项目根目录下的 `.gitignore` 文件中包含 `*.env`，以防止意外泄露。
    - **最佳实践**：始终使用环境变量。GUI 工具可以帮你轻松实现这一点。

3.  **数据库文件**
    - 默认会在同目录下生成 `llm_config.db`。这是一个SQLite文件，包含了所有用户数据和同步后的系统平台数据。请妥善保管。
    - 如果需要更换数据库，可以修改 `AIManager` 类中的 `create_engine` 部分。

4.  **模型探测失败？**
    - **检查`base_url`**：确保URL正确，并且末尾是否需要 `/v1`。
    - **检查API Key**：确认Key是否正确、有效，且有足够的额度。
    - **检查网络**：确保服务器可以访问目标`base_url`。

5.  **`extra_body` 的使用**
    - `extra_body` 提供了一个强大的机制来传递模型提供商的专有参数。
    - 在GUI中，它必须是合法的JSON格式。在YAML中，它是一个字典。
    - 这些参数会被自动合并到 `ChatOpenAI` 的 `extra_body` 或 `model_kwargs` 中。


## 📊 用量追踪功能

`get_user_llm()` 返回的 LLM 对象是 `TrackedChatModel`，它会**自动记录**每次调用的 Token 消耗和请求次数到数据库，无需手动调用任何记录方法。

### 自动记录

```python
from llm.llm_mgr import LLM_Manager

# 获取 LLM（自动追踪用量）
llm = LLM_Manager.get_user_llm(user_id="user_123", agent_name="agent_muse")

# 正常使用，用量会自动记录到数据库
result = llm.invoke(messages)

# 流式输出也会在结束后自动记录
for chunk in llm.stream(messages):
    print(chunk.content, end="")
```

### 查询 LLM 对象的用量

每个 LLM 对象都可以直接查询自己的用量：

```python
# 获取过去 24 小时的用量
usage_24h = llm.get_usage_last_24h()
print(f"过去24小时: {usage_24h['tokens']} tokens, {usage_24h['requests']} 次请求")

# 获取过去 7 天的用量
usage_week = llm.get_usage_last_week()

# 获取过去 30 天的用量
usage_month = llm.get_usage_last_month()

# 获取所有时间的总用量
usage_total = llm.get_usage_total()

# 获取指定时间范围的用量
from datetime import datetime
usage = llm.get_usage_by_range(
    start_time=datetime(2026, 1, 1),
    end_time=datetime(2026, 1, 31)
)
```

返回的字典格式：
```python
{
    "tokens": 12345,           # 总 Token 数
    "prompt_tokens": 8000,     # 输入 Token 数
    "completion_tokens": 4345, # 输出 Token 数
    "requests": 50,            # 请求次数
    "errors": 2,               # 失败次数
}
```

### 管理器级别的用量查询

`LLM_Manager` 提供了更丰富的用量查询接口：

```python
from datetime import timedelta

# 获取用户过去 24 小时的总用量
usage = LLM_Manager.get_user_usage_last_24h(user_id="user_123")

# 获取用户过去 7 天的总用量
usage = LLM_Manager.get_user_usage_last_week(user_id="user_123")

# 获取用户的所有模型使用统计（按模型分组）
stats = LLM_Manager.get_user_usage_stats(
    user_id="user_123",
    since=timedelta(days=7)  # 可选，限制时间范围
)
# 返回: [{"model_name": "gpt-4", "tokens": 5000, ...}, ...]

# 按 Agent 分组查看用量
by_agent = LLM_Manager.get_usage_by_agent(
    user_id="user_123",
    since=timedelta(hours=24)
)
# 返回: [{"agent_name": "agent_muse", "tokens": 1234, "requests": 10}, ...]

# 获取时间线数据（用于图表）
timeline = LLM_Manager.get_usage_timeline(
    user_id="user_123",
    granularity="hour",  # 或 "day"
    since=timedelta(hours=24)
)
# 返回: [{"time": "2026-01-01 10:00", "tokens": 500, "requests": 5}, ...]

# 清理旧日志（建议定期执行）
deleted = LLM_Manager.purge_old_usage_logs(older_than=timedelta(days=90))
print(f"已清理 {deleted} 条旧日志")
```

### 数据存储

用量数据存储在 `usage_log_entries` 表中，每次 LLM 调用会创建一条记录，包含：
- `user_id` 和 `model_id`
- `prompt_tokens`, `completion_tokens`, `total_tokens`
- `success` (1=成功, 0=失败)
- `agent_name` (调用的 Agent 名称)
- `created_at` (时间戳，用于时间范围查询)

> **注意**: 旧的 `ModelUsageStats` 表已废弃，不再写入数据。如需查询历史汇总，请使用新的时序日志表进行聚合查询。

### Token 估算与计费机制 (Token Estimation & Billing)

为了保证跨平台兼容性和统计的一致性，管理器**不再依赖** LLM API 返回的 Token 统计（因为许多流式接口不返回此数据，或格式极其混乱）。

相反，我们实施了一套**基于本地分词器的混合估算机制**，该机制基于 2025 Q1 的实测数据进行了调优：

1.  **基准分词 (Base Tokenization)**：
    使用工业标准的 `tiktoken` (`cl100k_base` 或 `o200k_base`) 作为基准。这避免了加载数十个不同模型分词器的巨大开销。

2.  **动态修正系数 (Dynamic Correction Factors)**：
    针对不同模型的词表效率差异，引入了修正系数。例如，国产模型（如 Qwen, DeepSeek）对中文进行了深度优化，其 Token 效率远高于标准的 `cl100k`。
    
    系统会分析文本内容，计算 **CJK (中日韩) 字符占比**，并据此在“英文系数”和“中文系数”之间进行**线性插值**：
    
    $$ Factor = F_{zh} \times Ratio_{cjk} + F_{en} \times (1 - Ratio_{cjk}) $$

3.  **计费策略**：
    - **按次计费**：只要产生了调用（包括被中断的流式调用），即视为一次有效请求 (`requests + 1`)。
    - **实时结算**：流式调用会在连接断开或完成时立即进行 Token 估算和入库，确保计费不丢失。
