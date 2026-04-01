using System;
using System.Collections.Generic;
using Newtonsoft.Json.Linq;
using UnityEngine;

namespace SparkArc.Unity
{
    /// <summary>
    /// 轻量全局剧情状态仓库。
    /// 用于给条件判定、一次性剧情、外部系统回调提供统一状态来源。
    /// </summary>
    public class StoryStateStore : MonoBehaviour
    {
        public static StoryStateStore Instance { get; private set; }

        private readonly Dictionary<string, JToken> _state = new Dictionary<string, JToken>(StringComparer.OrdinalIgnoreCase);
        private readonly HashSet<string> _playedKeys = new HashSet<string>(StringComparer.OrdinalIgnoreCase);

        void Awake()
        {
            if (Instance == null) Instance = this;
            else Destroy(gameObject);
        }

        public bool TryGet(string key, out JToken value)
        {
            if (string.IsNullOrWhiteSpace(key))
            {
                value = null;
                return false;
            }
            return _state.TryGetValue(key, out value);
        }

        public JToken Get(string key)
        {
            return TryGet(key, out var value) ? value : null;
        }

        public void Set(string key, JToken value)
        {
            if (string.IsNullOrWhiteSpace(key)) return;
            _state[key] = value?.DeepClone();
        }

        public void SetBool(string key, bool value) => Set(key, new JValue(value));
        public void SetInt(string key, int value) => Set(key, new JValue(value));
        public void SetFloat(string key, float value) => Set(key, new JValue(value));
        public void SetString(string key, string value) => Set(key, new JValue(value ?? string.Empty));

        public bool HasPlayed(string key)
        {
            if (string.IsNullOrWhiteSpace(key)) return false;
            return _playedKeys.Contains(key);
        }

        public void MarkPlayed(string key)
        {
            if (string.IsNullOrWhiteSpace(key)) return;
            _playedKeys.Add(key);
        }

        public void ClearState()
        {
            _state.Clear();
            _playedKeys.Clear();
        }
    }
}
