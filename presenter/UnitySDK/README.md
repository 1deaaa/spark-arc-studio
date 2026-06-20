# SparkArc Unity SDK 新手接入指南

SparkArc Unity SDK 的目标是把 SparkArc 创作端导出的 `stories.db` 变成 Unity 游戏运行时可以直接消费的剧情数据。

这不是一个只能展示文本的 demo。它的设计目标是：

- 编剧 / 策划在 SparkArc 中写剧情、配置 `act` 行为和全局注册表。
- Unity 开发者在游戏工程里写模块化 C# Handler。
- Unity Editor 扫描可绑定方法，导出行为清单。
- SparkArc 导入行为清单，生成 `binding_act` 映射。
- 游戏运行时读取 `stories.db`，由剧情驱动对话、状态、任务、镜头、BGM 等系统。

## 一、最快跑通：空 URP 项目

### 1. 创建 Unity 项目

1. 打开 Unity Hub。
2. 新建一个 URP 项目。
3. 打开项目后等待编译完成。

### 2. 复制 SDK 文件

把 SparkArc 仓库里的文件复制到 Unity 项目：

```text
presenter/UnitySDK/Scripts  ->  Assets/SparkArc/Runtime/Scripts
presenter/UnitySDK/Editor   ->  Assets/SparkArc/Editor
presenter/UnitySDK/Examples/MinimalRuntime -> Assets/SparkArc/Examples/MinimalRuntime
```

如果你的 Unity 项目还没有这些目录，可以直接新建。

### 3. 安装依赖

Unity 项目需要：

- `Newtonsoft.Json`
- `TextMeshPro`
- `Unity UI`
- `Input System` 或旧输入系统
- `Mono.Data.Sqlite`
- 当前平台对应的原生 `sqlite3`

Unity 6 可在 `Packages/manifest.json` 中加入：

```json
"com.unity.nuget.newtonsoft-json": "3.2.2"
```

Windows 编辑器下，SQLite 插件通常放在：

```text
Assets/SparkArc/Plugins/Managed/Mono.Data.Sqlite.dll
Assets/SparkArc/Plugins/Windows/x86_64/sqlite3.dll
```

### 4. 放入剧情数据库

把 SparkArc 导出的数据库放到：

```text
Assets/StreamingAssets/stories.db
```

### 5. 一键生成示例场景

在 Unity 菜单执行：

```text
SparkArc/Demo/Rebuild Minimal Runtime Scene
```

生成后打开：

```text
Assets/Scenes/SparkArcMinimalRuntime.unity
```

点击 Play，靠近 NPC，按 `F`。如果对话框弹出，就说明最小链路跑通了。

## 二、行为绑定完整链路

SparkArc 的行为系统不是让剧情数据任意调用 C#，而是走一条受控链路：

```text
dlg_json.act
  -> act_name
  -> stories.db / binding_act.func_name
  -> SparkArcActionDispatcher
  -> SparkArcActionHandler 实例方法
  -> 你的游戏系统
```

### 1. 在 Unity 写 Handler

示例：

```csharp
using SparkArc.Unity;
using UnityEngine;

public class AudioActionHandler : SparkArcActionHandler
{
    [SparkArcAction("bgm", ActionType = "audio", Description = "播放指定背景音乐")]
    public void PlayBGM(string musicName)
    {
        Debug.Log($"播放 BGM: {musicName}");
    }
}
```

新手先记住三点：

- 继承 `SparkArcActionHandler`。
- 方法必须是 `public void`。
- 参数尽量用 `string`、`int`、`float`、`double`、`bool` 或 `string[]`。

### 2. 在 Unity 导出行为清单

在 Unity 菜单执行：

```text
SparkArc/Actions/Export Action Manifest
```

它会生成：

```text
Assets/SparkArc/spark_actions.manifest.json
```

这个文件会列出 Unity 工程里可绑定的 C# 行为方法。

### 3. 在 SparkArc 导入清单

回到 SparkArc 前端：

```text
风格与运行时 -> Unity 运行时映射 -> 行为函数绑定
```

点击：

```text
导入 Unity 清单
```

选择 Unity 导出的 `spark_actions.manifest.json`。

SparkArc 会把方法合并进行为绑定列表，例如：

```text
bgm -> PlayBGM
weather -> ChangeWeather
```

保存后，SparkArc 导出 `stories.db` 时会把这些映射写入 `binding_act` 表。

### 4. 在剧本中触发行为

对话节点中写：

```json
"act": {
  "bgm": "town_theme"
}
```

运行时会读取 `binding_act`：

```text
bgm -> PlayBGM
```

然后调用：

```csharp
PlayBGM("town_theme")
```

## 三、场景里需要哪些组件

你可以手动搭建，也可以用示例场景生成器。核心对象建议叫：

```text
SparkArc_Manager
```

挂载组件：

- `StoryRepository`：读取 `stories.db`。
- `StoryStateStore`：保存运行时剧情变量。
- `SceneConditionEvaluator`：判断 `conditions`。
- `StoryEffectApplier`：对话结束后执行 `effects`。
- `SparkArcActionDispatcher`：把 `act` 映射到 C# Handler。
- `DialogueManager`：播放对话树。
- `DialogueUI`：显示对话框、选项和文本。

然后把你的模块 Handler 挂在同一个物体或其他系统物体上，例如：

- `AudioActionHandler`
- `CameraActionHandler`
- `QuestActionHandler`
- `WorldStateActionHandler`

小项目可以让 `SparkArcActionDispatcher` 自动扫描场景里的 Handler。中型项目建议把 Handler 显式拖到 `SparkArcActionDispatcher.handlers` 列表里，更可控。

## 四、NPC 触发对话

在 NPC 或触发区域上挂：

```text
DialogueTrigger
```

常用配置：

- `Scene Name`：填 `stories.db` 中的 `scene_name`。
- `Trigger Mode`：新手建议先用 `Manual`。
- `Interact Hint`：拖入提示 UI。
- `Interact Hint Text`：拖入提示文字。

运行时靠近 NPC，按 `F`，就会开始对应剧情。

如果 `stories` 表里配置了 `button_text`，提示文字会优先显示数据库里的内容。

## 五、全局注册表

SparkArc 前端的全局注册表会导出到 `registry` 表。

例如：

```json
{
  "name": "player_name",
  "value": ["艾莉"]
}
```

对话文本：

```text
你好，{player_name}
```

Unity 运行时会显示：

```text
你好，艾莉
```

行为参数里也可以使用占位符：

```json
"act": {
  "weather": ["sunny", "12", "{place}"]
}
```

## 六、状态条件与效果写回

### 条件

场景可配置 `conditions`，例如：

```json
{
  "all": [
    { "var": "quest.main.step", "op": ">=", "value": 3 },
    { "var": "npc.venti.met", "op": "==", "value": false }
  ]
}
```

如果条件不满足，`DialogueTrigger` 会忽略这场剧情。

### 效果

场景结束后可执行 `effects`：

```json
[
  { "op": "set", "key": "npc.venti.met", "value": true },
  { "op": "set", "key": "quest.main.step", "value": 4 },
  { "op": "mark_played", "key": "cutscene.windrise_intro" }
]
```

如果配置了 `once_key`，场景播放完成后系统会自动标记已播放。

## 七、中型项目怎么组织

不要把所有行为写成一个静态大类。

不要这样：

```csharp
public static class AllActions
{
    public static void PlayBGM(string name) {}
    public static void StartQuest(string id) {}
    public static void ChangeWeather(string type) {}
}
```

推荐这样：

```text
SparkArcRuntime
  StoryRepository
  StoryStateStore
  SparkArcActionDispatcher
  AudioActionHandler
  CameraActionHandler
  QuestActionHandler
  WorldStateActionHandler
```

更详细的模块组织建议见：

```text
presenter/UnitySDK/RuntimeArchitectureGuide.md
```

## 八、常见问题

### Play 后提示找不到 stories.db

检查文件是否在：

```text
Assets/StreamingAssets/stories.db
```

### 提示 SQLite 加载失败

检查是否有：

```text
Assets/SparkArc/Plugins/Managed/Mono.Data.Sqlite.dll
Assets/SparkArc/Plugins/Windows/x86_64/sqlite3.dll
```

### act 触发了但方法没执行

依次检查：

1. Unity 菜单是否执行过 `SparkArc/Actions/Export Action Manifest`。
2. SparkArc 前端是否导入过 `spark_actions.manifest.json`。
3. SparkArc 是否重新导出过 `stories.db`。
4. 场景里是否有 `SparkArcActionDispatcher`。
5. Handler 是否继承 `SparkArcActionHandler`。
6. 方法是否是 `public void`。
7. 方法参数数量和 `act` 参数是否匹配。

### Android 平台怎么读数据库

Android 不允许直接用普通文件流读取 `StreamingAssets` 内的 SQLite。正式项目需要启动时把数据库复制到 `Application.persistentDataPath`，再让 `StoryRepository` 读取持久化路径。

当前 SDK 先覆盖 Editor / Windows 原型链路，移动端分发建议单独做平台适配。
