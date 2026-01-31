using UnityEngine;

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
            if (DialogueManager.Instance != null)
            {
                DialogueManager.Instance.StartScene(sceneName);
            }
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
                else
                {
                    _canInteract = true;
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
