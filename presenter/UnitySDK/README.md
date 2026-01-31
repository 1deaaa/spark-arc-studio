# SparkArc Unity SDK 配置指南

欢迎使用 SparkArc 对话系统 Unity SDK！本 SDK 旨在帮助开发者快速将 Web 编辑器生成的剧本导入到 Unity 中运行。

## 🚀 快速上手

### 1. 准备工作
- 确保你的 Unity 项目中已导入 `Newtonsoft.Json` (可通过 Unity Package Manager 安装 "Json .NET" 或手动导入 DLL)。
- 在项目中创建 `StreamingAssets` 文件夹 (如果还没有)。

### 2. 导入数据
- 将编辑器导出的 `stories.db` 文件放入项目的 `Assets/StreamingAssets/` 目录下。

### 3. 环境配置
1. 在场景中创建一个空物体，命名为 `SparkArc_Manager`。
2. 挂载以下组件：
   - `StoryRepository`: 负责读取数据库。
   - `DialogueManager`: 核心逻辑。
   - `DialogueUI`: 负责界面显示。
3. **配置角色**：
   - 在 Project 窗口右键 -> `Create` -> `SparkArc` -> `Character Database`。
   - 在新创建的 Asset 中，点击 `+` 号添加角色（例如：ID: 1, Name: "我"）。
   - 将此 Asset 拖入 `DialogueManager` 的 `Character DB` 槽位。

### 4. UI 绑定
1. 在 Canvas 下创建一个对话面板。
2. 将面板中的 `Text` 组组件分别拖入 `DialogueUI` 对应的槽位：
   - `Name Text`: 显示说话人名字。
   - `Content Text`: 显示对话正文。
   - `Choice Container`: 用于放置选项按钮的父物体 (通常带 LayoutGroup)。
   - `Choice Button Prefab`: 你的选项按钮预制体。

### 5. 触发对话
- 在你的 NPC 或触发区域挂载 `DialogueTrigger` 脚本。
- 在 `Scene Name` 中填入编辑器中定义的场景名称 (例如 `Chapter_1_1`)。
- 设置 `Trigger Mode` 为 `Manual` (靠近按 E) 或 `OnEnter` (走进去就触发)。

---

## 🛠️ 进阶功能

### 处理自定义行为 (Actions)
在编辑器中定义的 `@act func:arg` 会通过 `DialogueEvents.OnActionTriggered` 事件广播。你可以写一个脚本来监听它：

```csharp
void OnEnable() {
    DialogueEvents.OnActionTriggered += HandleMyAction;
}

void HandleMyAction(string func, string[] args) {
    if (func == "bgm") {
        // 播放背景音乐逻辑
    }
}
```

### 数据库初始化
在游戏启动时，请确保调用一次加载：
```csharp
StoryRepository.Instance.LoadDatabase();
```

---

## 📝 注意事项
- **Android 平台**：由于 Android 不允许直接通过文件流读取 StreamingAssets 内的 SQLite，你可能需要使用协程将文件复制到 `Application.persistentDataPath` 之后再打开。
- **SQLite 库**：本 SDK 默认使用 `Mono.Data.Sqlite`，如果你的环境报错，请确保 `Mono.Data.Sqlite.dll` 和 `sqlite3.dll` 在项目中。
