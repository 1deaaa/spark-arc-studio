using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;
using TMPro; // 推荐使用 TextMeshPro
using System;
using Newtonsoft.Json.Linq;

namespace SparkArc.Unity
{
    /// <summary>
    /// 处理 UI 显示逻辑
    /// </summary>
    public class DialogueUI : MonoBehaviour
    {
        [Header("UI 组件")]
        public GameObject dialoguePanel;
        public TextMeshProUGUI nameText;
        public TextMeshProUGUI contentText;
        public TextMeshProUGUI guideText;
        public TextMeshProUGUI introText;
        
        [Header("选项设置")]
        public Transform choiceContainer;
        public GameObject choiceButtonPrefab;

        [Header("打字机设置")]
        public float typingSpeed = 0.05f;
        
        private bool _isWaitingForInput = false;

        public void ShowUI(bool show)
        {
            if (dialoguePanel) dialoguePanel.SetActive(show);
        }

        public void UpdateGuide(string text)
        {
            if (guideText) guideText.text = text;
        }

        public void UpdateIntro(string text)
        {
            if (introText)
            {
                introText.text = text;
                introText.gameObject.SetActive(!string.IsNullOrEmpty(text));
            }
        }

        public IEnumerator TypeText(string speaker, string text)
        {
            if (nameText) nameText.text = speaker;
            if (contentText)
            {
                contentText.text = "";
                foreach (char c in text)
                {
                    contentText.text += c;
                    yield return new WaitForSeconds(typingSpeed);
                }
            }

            // 等待玩家点击继续
            _isWaitingForInput = true;
            while (_isWaitingForInput)
            {
                if (SparkArcInput.WasContinuePressed())
                {
                    _isWaitingForInput = false;
                }
                yield return null;
            }
        }

        public IEnumerator WaitForChoice(JArray options, Action<JArray> onChoiceSelected)
        {
            // 清理旧按钮
            foreach (Transform child in choiceContainer) Destroy(child.gameObject);

            JArray selectedBranch = null;

            // 创建新按钮
            for (int i = 0; i < options.Count; i++)
            {
                var opt = options[i] as JObject;
                var btnObj = Instantiate(choiceButtonPrefab, choiceContainer);
                btnObj.SetActive(true);
                var btnText = btnObj.GetComponentInChildren<TextMeshProUGUI>();
                if (btnText) btnText.text = opt["optn"].ToString();

                var btn = btnObj.GetComponent<Button>();
                var branch = opt["dia"] as JArray;
                btn.onClick.AddListener(() => {
                    selectedBranch = branch;
                });
            }

            // 等待选择
            while (selectedBranch == null)
            {
                yield return null;
            }

            // 清理并回调
            foreach (Transform child in choiceContainer) Destroy(child.gameObject);
            onChoiceSelected?.Invoke(selectedBranch);
        }
    }
}
