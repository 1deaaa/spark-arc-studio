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
            int chrId = node["chr"]?.Value<int>() ?? -1;
            string txt = node["txt"]?.ToString() ?? "";
            string chrName = characterDB != null ? characterDB.GetCharacterName(chrId) : chrId.ToString();

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
            foreach (var property in acts.Properties())
            {
                string func = property.Name;
                string[] args;
                
                if (property.Value.Type == JTokenType.Array)
                    args = property.Value.ToObject<string[]>();
                else
                    args = property.Value.ToString().Split(new[] { ' ' }, StringSplitOptions.RemoveEmptyEntries);

                // 发送全局广播，让其他组件响应行为
                DialogueEvents.OnActionTriggered?.Invoke(func, args);
                Debug.Log($"SparkArc: 触发行为 [{func}] 参数: {string.Join(", ", args)}");
            }
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
