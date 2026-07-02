using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using Newtonsoft.Json.Linq;
using System;

namespace SparkArc.Unity
{
    /// <summary>
    /// 核心对话引擎，管理执行逻辑
    /// </summary>
    public class DialogueManager : MonoBehaviour
    {
        public static DialogueManager Instance { get; private set; }

        [Header("绑定角色配置")]
        public CharacterDatabase characterDB;

        [Header("状态")]
        public bool isDialogueRunning = false;
        public SceneData currentScene;

        private Stack<IEnumerator> _executionStack = new Stack<IEnumerator>();
        private DialogueUI _ui;

        void Awake()
        {
            if (Instance == null) Instance = this;
            _ui = GetComponent<DialogueUI>();
        }

        /// <summary>
        /// 开始一个新场景
        /// </summary>
        public void StartScene(string sceneName)
        {
            var scene = StoryRepository.Instance.GetScene(sceneName);
            if (scene == null) return;
            if (scene.hidden)
            {
                Debug.Log($"SparkArc: 场景 [{sceneName}] 已隐藏，忽略触发。");
                return;
            }

            if (SceneConditionEvaluator.Instance != null && !SceneConditionEvaluator.Instance.CanStart(scene, out var reason))
            {
                Debug.Log($"SparkArc: 场景 [{sceneName}] 条件不满足，忽略触发。原因: {reason}");
                return;
            }

            StopAllCoroutines();
            _executionStack.Clear();
            currentScene = scene;
            isDialogueRunning = true;

            _ui.ShowUI(true);
            _ui.UpdateGuide(scene.guide);
            _ui.UpdateIntro(scene.intro);

            // TODO: trigger_event — 场景触发外部事件回调，待接入游戏事件系统
            // if (!string.IsNullOrEmpty(scene.triggerEvent)) { }

            // TODO: priority — 同触发点多场景优先级排序，待接入场景调度器
            // Debug.Log($"SparkArc: 场景优先级 = {scene.priority}");

            StartCoroutine(ExecuteSequence(scene.dialogues));
        }

        /// <summary>
        /// 执行一个对话数组（用于处理主线和分支）
        /// </summary>
        private IEnumerator ExecuteSequence(JArray dialogues)
        {
            foreach (JObject node in dialogues)
            {
                yield return StartCoroutine(ProcessNode(node));
            }

            // 检查是否有关闭指令或跳转
            if (_executionStack.Count == 0)
            {
                EndDialogue();
            }
        }

        private IEnumerator ProcessNode(JObject node)
        {
            // 1. 处理角色和文本
            int chrId = -1;
            var chrToken = node["chr"];
            if (chrToken != null)
            {
                int.TryParse(chrToken.ToString(), out chrId);
            }
            string speaker = node["speaker"]?.ToString() ?? "";
            string txt = node["txt"]?.ToString() ?? "";
            if (StoryRepository.Instance != null)
            {
                txt = StoryRepository.Instance.ResolveRegistryTokens(txt);
            }
            string chrName = !string.IsNullOrWhiteSpace(speaker)
                ? speaker
                : (characterDB != null ? characterDB.GetCharacterName(chrId) : chrId.ToString());
            if (chrName == "旁白")
            {
                chrName = "";
            }

            // thought: 辅助AI决策的字段，运行时不需要处理
            string thought = node["thought"]?.ToString() ?? "";

            // 2. 处理行为 (Actions)
            if (node.ContainsKey("act"))
            {
                HandleActions(node["act"] as JObject);
            }

            // 3. 显示文本
            yield return StartCoroutine(_ui.TypeText(chrName, txt));

            // 4. 处理选项 (Choices)
            if (node.ContainsKey("opt"))
            {
                yield return StartCoroutine(_ui.WaitForChoice(node["opt"] as JArray, (selectedDia) => {
                    // 当选择后，将子对话压入
                    _executionStack.Push(ExecuteSequence(selectedDia));
                }));

                if (_executionStack.Count > 0)
                {
                    yield return StartCoroutine(_executionStack.Pop());
                }
            }

            // 5. 处理跳转
            if (node.ContainsKey("next"))
            {
                string nextScene = node["next"].ToString();
                StartScene(nextScene);
                yield break; // 停止当前协程，StartScene 会开启新的
            }
        }

        private void HandleActions(JObject acts)
        {
            if (acts == null) return;

            foreach (var property in acts.Properties())
            {
                string func = property.Name;
                string[] args = ParseActionArgs(property.Value);

                // 发送全局广播，SparkArcActionDispatcher 和旧式监听脚本都可以响应。
                DialogueEvents.OnActionTriggered?.Invoke(func, args);
                Debug.Log($"SparkArc: 触发行为 [{func}] 参数: {string.Join(", ", args)}");
            }
        }

        private static string[] ParseActionArgs(JToken value)
        {
            if (value == null || value.Type == JTokenType.Null)
            {
                return Array.Empty<string>();
            }

            if (value.Type == JTokenType.Array)
            {
                var array = value as JArray;
                var args = new List<string>();
                foreach (var item in array)
                {
                    args.Add(item == null || item.Type == JTokenType.Null ? string.Empty : item.ToString());
                }
                return args.ToArray();
            }

            if (value.Type == JTokenType.Object)
            {
                return new[] { value.ToString(Newtonsoft.Json.Formatting.None) };
            }

            return new[] { value.ToString() };
        }

        public void EndDialogue()
        {
            if (StoryEffectApplier.Instance != null)
            {
                StoryEffectApplier.Instance.Apply(currentScene);
            }

            isDialogueRunning = false;
            _ui.ShowUI(false);
            DialogueEvents.OnDialogueEnd?.Invoke();
        }
    }

    public static class DialogueEvents
    {
        public static Action<string, string[]> OnActionTriggered;
        public static Action OnDialogueEnd;
    }
}
