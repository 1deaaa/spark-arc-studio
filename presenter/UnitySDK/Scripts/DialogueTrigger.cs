using UnityEngine;
using TMPro;

namespace SparkArc.Unity
{
    /// <summary>
    /// 对话触发器，挂载在 NPC 或触发区域上
    /// </summary>
    public class DialogueTrigger : MonoBehaviour
    {
        [Header("配置")]
        [Tooltip("要触发的场景名称 (scene_name)")]
        public string sceneName;

        public enum TriggerMode { Manual, OnEnter, OnStart }
        public TriggerMode mode = TriggerMode.Manual;

        [Header("交互提示 (可选)")]
        public GameObject interactHint;
        public TMP_Text interactHintText;
        public string fallbackHintText = "交互";

        private bool _canInteract = false;

        void Start()
        {
            if (mode == TriggerMode.OnStart)
            {
                Trigger();
            }
        }

        void Update()
        {
            if (_canInteract && mode == TriggerMode.Manual)
            {
                if (Input.GetKeyDown(KeyCode.E))
                {
                    Trigger();
                }
            }
        }

        public void Trigger()
        {
            if (!CanTriggerNow()) return;
            if (DialogueManager.Instance != null)
            {
                DialogueManager.Instance.StartScene(sceneName);
            }
        }

        private bool CanTriggerNow()
        {
            if (string.IsNullOrWhiteSpace(sceneName)) return false;
            if (StoryRepository.Instance == null) return true;
            var scene = StoryRepository.Instance.GetScene(sceneName);
            if (scene == null) return false;
            if (scene.hidden) return false;
            if (SceneConditionEvaluator.Instance != null && !SceneConditionEvaluator.Instance.CanStart(scene, out _))
            {
                return false;
            }
            return true;
        }

        private void UpdateInteractHintText()
        {
            if (interactHintText == null) return;
            var defaultText = string.IsNullOrWhiteSpace(fallbackHintText) ? "交互" : fallbackHintText;
            if (StoryRepository.Instance == null || string.IsNullOrWhiteSpace(sceneName))
            {
                interactHintText.text = defaultText;
                return;
            }

            var scene = StoryRepository.Instance.GetScene(sceneName);
            var buttonText = scene != null && !string.IsNullOrWhiteSpace(scene.buttonText)
                ? scene.buttonText
                : defaultText;
            interactHintText.text = buttonText;
        }

        void OnTriggerEnter2D(Collider2D other) => CheckEnter(other.gameObject);
        void OnTriggerEnter(Collider other) => CheckEnter(other.gameObject);

        private void CheckEnter(GameObject obj)
        {
            if (obj.CompareTag("Player"))
            {
                if (mode == TriggerMode.OnEnter)
                {
                    Trigger();
                }
                else if (CanTriggerNow())
                {
                    _canInteract = true;
                    UpdateInteractHintText();
                    if (interactHint) interactHint.SetActive(true);
                }
            }
        }

        void OnTriggerExit2D(Collider2D other) => CheckExit(other.gameObject);
        void OnTriggerExit(Collider other) => CheckExit(other.gameObject);

        private void CheckExit(GameObject obj)
        {
            if (obj.CompareTag("Player"))
            {
                _canInteract = false;
                if (interactHint) interactHint.SetActive(false);
            }
        }
    }
}
