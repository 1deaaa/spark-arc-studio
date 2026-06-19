# SparkArc Unity 最小运行时接入示例

这个示例用于验证 SparkArc 的 story DB 可以被 Unity 演出端直接驱动。它不是完整 RPG 框架，而是一条最小闭环：

1. SparkArc 导出的 `stories.db` 放入 Unity 的 `Assets/StreamingAssets/`。
2. 场景中的 `SparkArc_Manager` 读取 `stories`、`characters` 与运行时状态。
3. 玩家用第一人称控制器靠近 NPC。
4. `DialogueTrigger` 根据 `scene_name` 取剧情，并读取数据库里的 `button_text` 显示交互提示。
5. 按 `F` 后由 `DialogueManager` 播放 `dlg_json`，对话结束后执行 `effects` 写回 `StoryStateStore`。

## 运行环境

Unity 工程需要具备：

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

Windows 编辑器下，示例已验证的插件放置方式是：

- `Assets/SparkArc/Plugins/Managed/Mono.Data.Sqlite.dll`
- `Assets/SparkArc/Plugins/Windows/x86_64/sqlite3.dll`

正式分发时建议把 SQLite 依赖整理成 UPM 包或明确的 SDK 插件目录，避免依赖某台机器上的 Unity 安装路径。

## 接入步骤

1. 将 `presenter/UnitySDK/Scripts` 复制到 Unity 项目的 `Assets/SparkArc/Runtime/Scripts`。
2. 将 `presenter/UnitySDK/Examples/MinimalRuntime/Scripts` 复制到 `Assets/SparkArc/Examples/MinimalRuntime/Scripts`。
3. 将 `presenter/UnitySDK/Examples/MinimalRuntime/Editor` 复制到 `Assets/SparkArc/Examples/MinimalRuntime/Editor`。
4. 将 SparkArc 导出的 `stories.db` 放到 `Assets/StreamingAssets/stories.db`。
5. 在 Unity 菜单执行 `SparkArc/Demo/Rebuild Minimal Runtime Scene`。
6. 打开 `Assets/Scenes/SparkArcMinimalRuntime.unity`，点击 Play，靠近 NPC 后按 `F`。

## 场景组成

菜单生成的最小场景包含：

- `SparkArc_Manager`：挂载 `StoryRepository`、`StoryStateStore`、`SceneConditionEvaluator`、`StoryEffectApplier`、`DialogueUI`、`DialogueManager` 与 `SparkArcRuntimeBootstrap`。
- `SparkArc_Canvas`：生成简易对话框、选项按钮与交互提示。
- `Player`：挂载 `CharacterController` 与 `SparkArcFirstPersonController`。
- `NPC_WindriseMessenger`：挂载 `DialogueTrigger`，触发 `windrise_first_meet`。
- `EventSystem`、地面、路径标记与主光源。

## 示例数据库字段

`stories` 表最小需要：

- `scene_name`：触发器使用的剧情入口。
- `button_text`：靠近 NPC 时显示的交互按钮文案。
- `conditions`：进入条件，可为空。
- `effects`：对话播完后的状态写回。
- `trigger_event`：可选触发事件。
- `priority`：剧情候选排序。
- `once_key`：一次性剧情标记。
- `dlg_json`：根级对话节点数组。

`characters` 表最小需要：

- `character_id`：对话节点里的 `chr`。
- `name`：运行时显示名。

注意：SparkArc 通过 SQLAlchemy 的 JSON 类型写入 SQLite 时，`dlg_json`、`conditions`、`effects`、`registry.value` 在部分读取链路下会表现为 UTF-8 `byte[]`。Unity SDK 的 `StoryRepository.ReadText` 已兼容 `byte[]` 与普通字符串。

## 自动验证

示例提供菜单 `SparkArc/Demo/Run Runtime Smoke Probe`，会在运行时读取 `windrise_first_meet` 并直接触发对话。成功时控制台应出现类似日志：

```text
SparkArc Demo Smoke: sceneLoaded=True, dialogues=4, button=按 F 与信使对话
SparkArc Demo Smoke: dialogueRunning=True, current=windrise_first_meet, panelActive=True
```
