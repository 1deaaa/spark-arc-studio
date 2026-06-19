using System.Collections;
using UnityEngine;

namespace SparkArc.Unity.Examples
{
    /// <summary>
    /// 运行时烟雾探针，仅用于验证最小示例链路。
    /// </summary>
    public class SparkArcRuntimeSmokeProbe : MonoBehaviour
    {
        public string sceneName = "windrise_first_meet";

        private IEnumerator Start()
        {
            yield return null;

            var scene = StoryRepository.Instance != null ? StoryRepository.Instance.GetScene(sceneName) : null;
            var dialogueCount = scene != null && scene.dialogues != null ? scene.dialogues.Count : -1;
            Debug.Log($"SparkArc Demo Smoke: sceneLoaded={scene != null}, dialogues={dialogueCount}, button={scene?.buttonText}");

            if (DialogueManager.Instance == null || scene == null)
            {
                Debug.LogError("SparkArc Demo Smoke: 运行时组件未就绪，无法触发对话。");
                Destroy(gameObject);
                yield break;
            }

            DialogueManager.Instance.StartScene(sceneName);
            yield return null;

            var ui = DialogueManager.Instance.GetComponent<DialogueUI>();
            var panelActive = ui != null && ui.dialoguePanel != null && ui.dialoguePanel.activeInHierarchy;
            Debug.Log($"SparkArc Demo Smoke: dialogueRunning={DialogueManager.Instance.isDialogueRunning}, current={DialogueManager.Instance.currentScene?.sceneName}, panelActive={panelActive}");
            Destroy(gameObject);
        }
    }
}
