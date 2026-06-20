# SparkArc Unity SDK 中型项目组织指南

本文面向中型以下 RPG、箱庭游戏或剧情驱动型项目，说明如何组织 Unity 侧行为模块，避免把所有剧情行为写成一个静态大类。

## 核心原则

SparkArc 的 `act` 节点只表达剧情意图，不应该直接承载游戏系统实现。

推荐链路：

```text
dlg_json.act
  -> act_name
  -> stories.db / binding_act.func_name
  -> SparkArcActionDispatcher
  -> 某个 SparkArcActionHandler 实例方法
  -> 具体游戏系统
```

这条链路的好处是：剧本数据稳定，Unity 侧实现可以按模块演进，AI 不需要知道具体组件层级。

## 推荐模块拆分

中型项目建议至少按职责拆成这些 Handler：

- `AudioActionHandler`：BGM、音效、环境音、混音快照。
- `CameraActionHandler`：镜头切换、震屏、聚焦角色、Timeline 摄像机。
- `QuestActionHandler`：任务开始、推进、完成、失败。
- `WorldStateActionHandler`：天气、时间、区域状态、门锁、机关。
- `CharacterActionHandler`：NPC 入场、离场、表情、动作、朝向。
- `TimelineActionHandler`：播放 Timeline、等待演出完成、切场。
- `CombatActionHandler`：进入战斗、战斗结算、刷怪波次。

不要把这些方法全部写进 `SparkArcActionDispatcher`，也不要把它们全部写成静态方法。调度器只负责“找映射、转参数、调用目标”，真正逻辑应交给各自系统。

## Handler 写法

```csharp
using SparkArc.Unity;
using UnityEngine;

public class AudioActionHandler : SparkArcActionHandler
{
    [SerializeField] private AudioDirector audioDirector;

    public void PlayBGM(string musicName)
    {
        audioDirector.PlayBGM(musicName);
    }

    public void StopBGM(float fadeSeconds = 1.0f)
    {
        audioDirector.StopBGM(fadeSeconds);
    }
}
```

`SparkArcActionDispatcher` 只扫描 `SparkArcActionHandler` 子类上的实例方法。这样能把可调用范围限制在剧情运行时白名单内，避免剧情数据任意反射调用游戏工程里的所有方法。

## 方法签名建议

当前 SDK 支持这些参数类型：

- `string`
- `int`
- `float`
- `double`
- `bool`
- `string[]`

推荐优先使用少量标量参数：

```csharp
public void ChangeWeather(string type, float duration, string location)
```

如果某个行为参数非常复杂，可以暂时使用 `string` 接 JSON，但正式项目更建议把复杂演出拆成 Timeline、Playable 或 ScriptableObject 配置，由 `act` 只传配置 ID。

## 绑定表规范

前端行为函数绑定最终会导出到 `stories.db` 的 `binding_act` 表：

```text
act_name    剧情脚本里的行为名，例如 bgm
func_name   Unity 方法名，例如 PlayBGM
act_type    分类，例如 audio / camera / quest
act_args    参数示例和候选值
```

示例：

```json
{
  "act_name": "bgm",
  "func_name": "PlayBGM",
  "act_type": "audio",
  "act_args": {
    "musicName": ["town_theme", "battle_theme"]
  }
}
```

对话中写：

```json
"act": {
  "bgm": "town_theme"
}
```

运行时会调用：

```csharp
PlayBGM("town_theme")
```

## 全局注册表

前端全局注册表会导出到 `registry` 表。运行时会用第一个值替换文本或行为参数中的 `{name}` 占位符。

示例：

```json
{
  "name": "place",
  "value": ["沃森区", "太平洲", "狗镇"]
}
```

对话文本：

```text
欢迎来到 {place}
```

运行时默认显示：

```text
欢迎来到 沃森区
```

如果要把注册表作为编辑器枚举候选，而不是运行时默认值，建议后续在工具链中区分 `default` 与 `options`。

## 不推荐写法

不要这样写：

```csharp
public static class AllSparkArcActions
{
    public static void PlayBGM(string name) {}
    public static void ChangeWeather(string type) {}
    public static void StartQuest(string id) {}
    public static void MoveNpc(string id) {}
}
```

问题是：

- 所有系统耦合在一起，越写越难拆。
- 静态方法难以依赖场景对象、存档、Addressables、Timeline、服务生命周期。
- 难以做权限控制，最终容易变成剧情数据任意调用代码。
- 多人协作时冲突严重，音频、任务、镜头都在改同一个文件。

## 自动扫描方法名的建议

后续如果使用 Python 或 Roslyn 扫描 Unity 脚本树，建议只采集满足以下条件的方法：

- 所在类继承 `SparkArcActionHandler`。
- 返回值为 `void`。
- 参数类型属于 SDK 支持范围。
- 方法名唯一，或有额外的 handler/module 限定。

更成熟的做法是增加属性标记：

```csharp
[SparkArcAction("bgm")]
public void PlayBGM(string musicName) {}
```

这样 `act_name` 可以稳定，C# 方法名可以重构，自动扫描也能生成更可靠的 manifest。

## 建议的 Unity 场景结构

```text
SparkArcRuntime
  StoryRepository
  StoryStateStore
  SceneConditionEvaluator
  StoryEffectApplier
  SparkArcActionDispatcher
  AudioActionHandler
  CameraActionHandler
  QuestActionHandler
  WorldStateActionHandler
```

复杂项目可以把各 Handler 放在对应系统对象上，然后显式拖入 `SparkArcActionDispatcher.handlers`。这样比全场景自动扫描更可控，也更容易做测试。
