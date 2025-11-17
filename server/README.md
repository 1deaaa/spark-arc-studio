# 通用大模型管理器 (LLM Manager)

这是一个功能强大且灵活的通用大模型（LLM）管理器。它基于 `LangChain` 和 `SQLAlchemy` 构建，旨在为不同规模和需求的应用提供统一、稳定的大模型接口服务。

该项目的设计目标是支持从个人开发、调试到多用户生产环境的多种复杂场景，并提供了一个图形化界面来简化核心配置的管理。

## ✨ 核心特性

- **多种运行模式**：
  - **无用户/全局单用户模式**：适用于后端服务、个人工具或开发调试，所有请求共享一套由环境变量配置的系统级LLM。
  - **多用户固定平台模式**：适用于需要保证模型质量和来源的场景。所有用户共享系统预设的平台，但可以使用自己的API Key。
  - **多用户自定义平台模式**：提供最大灵活性，允许每个用户自由添加、管理自己的LLM平台和模型。
- **统一的接口**：无论后端配置如何变化，开发者都可以通过简单的 `LLM_Manager.get_user_llm(user_id)` 来获取对应用户的LLM实例。
- **系统与用户隔离**：明确区分“系统平台”和“用户私有平台”，系统平台由配置文件 (`llm_mgr_cfg.yaml`) 统一管理，用户平台数据则存储在数据库中。
- **灵活的密钥管理**：
  - 强烈推荐使用**环境变量**来管理API Key，避免密钥硬编码，提高安全性。
  - 支持用户为共享的系统平台提供自己的API Key，从而分摊成本。
  - 提供 `LLM_AUTO_KEY` 选项，允许在用户未提供密钥时，自动降级使用服务器的密钥（需谨慎使用）。
- **动态模型探测**：内置独立的模型探测工具 (`probe_platform_models`)，可以探测任何兼容OpenAI接口的平台所支持的模型列表。
- **图形化配置工具**：提供一个基于 `Tkinter` 的GUI工具，用于管理 `llm_mgr_cfg.yaml` 文件，支持添加/编辑平台、管理API Key（可自动写入环境变量）、探测和测试模型，极大降低了配置心智负担。
- **数据库持久化**：使用 SQLite 存储用户配置、平台和模型信息，数据持久可靠。
- **自动配置修正**：当用户的配置失效（如模型或平台被删除），系统会自动回退到第一个可用的默认平台，保证服务的可用性。

## 📂 文件结构

```
.
├── llm_mgr.py             # 核心管理器模块
├── llm_mgr_cfg.yaml       # 系统平台预设配置文件 (核心配置)
├── llm_mgr_cfg_gui.py     # 图形化配置管理工具
├── llm_config.db          # (自动生成) SQLite数据库文件
└── README.md              # 本文档
```

- **`llm_mgr.py`**: 包含 `AIManager` 类，是与程序交互的主要入口。它处理所有的逻辑，包括数据库操作、配置加载、LLM实例创建等。
- **`llm_mgr_cfg.yaml`**: **核心配置文件**。用于定义所有“系统平台”。应用启动时，管理器会自动将此文件中的平台同步到数据库。**这是管理系统级模型的唯一入口**。
- **`llm_mgr_cfg_gui.py`**: 一个独立的GUI应用，用于可视化地编辑 `llm_mgr_cfg.yaml`。通过 `python llm_mgr.py` 或 `python llm_mgr_cfg_gui.py` 启动。

## ⚙️ 核心概念与运行模式

理解本项目的运行模式至关重要，这直接影响到功能的表现和二次开发。

### 1. 系统用户 (`SYSTEM_USER_ID = "-1"`)

这是一个特殊的虚拟用户ID。当代码中使用 `LLM_Manager.get_user_llm()` (不带`user_id`参数) 或 `LLM_Manager.get_user_llm(user_id="-1")` 时，管理器会进入**系统模式**。

- **目的**：为应用后端、全局服务或开发调试提供一个统一的LLM实例。
- **密钥来源**：**必须**来自系统环境变量。管理器会根据 `llm_mgr_cfg.yaml` 中的配置查找对应的环境变量。如果找不到，程序将抛出异常。

### 2. 全局模式开关

在 [`llm_mgr.py`](llm_mgr.py:1) 的顶部有两个重要的全局开关：

- **`USE_SYS_LLM_CONFIG = True` (多用户固定平台模式)**
  - 这是**默认且推荐**的模式。
  - 所有用户都只能看到和使用 `llm_mgr_cfg.yaml` 中定义的系统平台。
  - 用户**不能**创建、修改或删除自己的平台和模型。
  - 用户**可以**为这些系统平台提供自己的API Key，这些Key会安全地存储在数据库的 `llm_sys_platform_keys` 表中，与用户ID关联。
  - 这种模式兼顾了模型的统一管理和成本的分摊。

- **`USE_SYS_LLM_CONFIG = False` (多用户自定义平台模式)**
  - 此模式下，用户拥有最大权限。
  - 用户除了可以使用系统平台外，还可以通过调用 `AIManager` 的 `add_platform`, `add_model` 等方法来创建自己的私有平台和模型。
  - 适用于需要高度自定义的场景。

### 3. 自动密钥降级 (`LLM_AUTO_KEY`)

- **`LLM_AUTO_KEY = True`**
  - **⚠️这是一个需要特别注意的选项！**
  - 当一个普通用户使用一个**系统平台**但没有提供自己的API Key时，如果此选项为`True`，管理器会自动去加载**服务器的环境变量**作为该用户的API Key。
  - **优点**：可以为免费用户或未配置的用户提供体验。
  - **风险**：**可能会导致服务器成本意外增加！** 如果你不想为用户免费提供服务，请务必将此项设置为 `False`。

- **`LLM_AUTO_KEY = False`**
  - 更安全的选项。
  - 如果用户没有为系统平台提供自己的API Key，在调用LLM时会直接抛出 `ValueError`，提示用户需要配置API Key。

## 🚀 快速上手

### 1. 安装依赖

项目依赖 `langchain`, `sqlalchemy`, `pyyaml`, `requests` 等库。可以通过 `pip` 安装：

```bash
pip install langchain langchain-openai sqlalchemy pyyaml requests
```

### 2. 配置 `llm_mgr_cfg.yaml`

这是开始使用的**第一步**，也是最重要的一步。你可以手动编辑，但更推荐使用GUI工具。

#### 2.1. (推荐) 使用GUI工具配置

在终端中运行以下任一命令来启动图形化配置界面：

```bash
python llm_mgr.py
# 或者
python llm_mgr_cfg_gui.py
```

 <!-- 你可以替换成真实的截图 -->

**GUI功能简介**:
- **管理平台**：添加、删除平台，修改平台的`base_url`。
- **设为默认**：将选中的平台移动到配置文件顶部，使其成为系统默认选项。
- **管理API Key**：
    - **推荐方式**：填写`API Key`和`环境变量名`，点击“保存API Key”，工具会自动将Key写入系统环境变量（Windows/Linux/macOS均支持），并在YAML中存为 `{ENV_VAR}` 格式。
    - **不推荐方式**：只填写`API Key`，工具会警告并允许你将明文Key存入YAML。**这有严重的安全风险！**
- **模型探测**：填写`API Key`后，点击“探测可用模型”可以列出该平台所有兼容OpenAI接口的模型。
- **管理模型**：从探测结果中双击或选择后“添加模型到平台”，可以为模型设置一个易于理解的`显示名称`和可选的`extra_body`（用于传递额外的API参数）。
- **模型测试**：在左侧模型列表中选中一个模型，点击“测试选中模型”，可以快速验证该模型的可用性。

#### 2.2. 手动配置

直接编辑 [`llm_mgr_cfg.yaml`](llm_mgr_cfg.yaml:1) 文件。

- **`api_key`**: **强烈建议**使用环境变量占位符格式，如 `{OPENAI_API_KEY}`。程序在运行时会自动替换。
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

**提示**：使用GUI工具的“保存API Key”功能可以自动完成这一步！

### 4. 在代码中使用

首先，在你的应用启动时，执行初始化。这会确保配置文件和数据库同步。

```python
from llm_mgr import init_default_llm, LLM_Manager

# 在应用启动时调用一次
init_default_llm()
```

然后，在需要使用LLM的地方，获取全局唯一的 `LLM_Manager` 实例。

```python
from llm_mgr import LLM_Manager

# --- 场景1: 获取指定用户的LLM ---
# 管理器会自动处理该用户的模型选择、API Key等所有配置
try:
    user_llm = LLM_Manager.get_user_llm(user_id="user_123")
    # response = user_llm.invoke("你好")
    # for chunk in user_llm.stream("你好"):
    #     print(chunk.content, end="")
except ValueError as e:
    # 可能是API Key未配置等问题
    print(f"获取LLM失败: {e}")


# --- 场景2: 在后端服务或无用户场景下使用 ---
# 使用特殊的 SYSTEM_USER_ID，此时密钥必须来自环境变量
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

## ⚠️ 重要提示与常见问题

1.  **`llm_mgr_cfg.yaml` 是权威数据源**
    - 每当应用启动执行 `initialize_defaults()` 时，程序会以 `llm_mgr_cfg.yaml` 为准，对数据库中的**系统平台**(`is_sys=1`)进行**强制同步**。
    - 这意味着：
        - 你在YAML中**删除**一个平台，数据库中对应的系统平台也会被删除。
        - 你在YAML中**修改**一个模型的`model_name`，数据库也会同步更新。
        - **不要**尝试在数据库中直接修改系统平台，这些修改会在下次启动时被覆盖。

2.  **API Key 安全性**
    - **绝对不要**将包含明文API Key的 `llm_mgr_cfg.yaml` 文件提交到公共代码仓库（如GitHub）。
    - **最佳实践**：始终使用环境变量。GUI工具可以帮你轻松实现这一点。

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

