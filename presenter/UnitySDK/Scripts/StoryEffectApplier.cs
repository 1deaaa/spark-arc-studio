using System;
using Newtonsoft.Json.Linq;
using UnityEngine;

namespace SparkArc.Unity
{
    /// <summary>
    /// 最小效果执行器：负责在场景结束时写回 StoryStateStore。
    /// 当前仅支持 set / unset / add / mark_played / unlock 这些最常见操作。
    /// </summary>
    public class StoryEffectApplier : MonoBehaviour
    {
        public static StoryEffectApplier Instance { get; private set; }

        void Awake()
        {
            if (Instance == null) Instance = this;
            else Destroy(gameObject);
        }

        public void Apply(SceneData scene)
        {
            if (scene == null) return;

            if (scene.effects is JArray array)
            {
                foreach (var item in array)
                {
                    ApplyEffect(item as JObject);
                }
            }
            else if (scene.effects is JObject single)
            {
                ApplyEffect(single);
            }

            if (!string.IsNullOrWhiteSpace(scene.onceKey) && StoryStateStore.Instance != null)
            {
                StoryStateStore.Instance.MarkPlayed(scene.onceKey);
            }
        }

        private void ApplyEffect(JObject effect)
        {
            if (effect == null || StoryStateStore.Instance == null) return;

            var op = effect.Value<string>("op")?.Trim().ToLowerInvariant() ?? "set";
            var key = effect.Value<string>("key")?.Trim();
            if (string.IsNullOrWhiteSpace(key)) return;

            var value = effect["value"];
            switch (op)
            {
                case "set":
                    StoryStateStore.Instance.Set(key, value);
                    break;
                case "unset":
                    StoryStateStore.Instance.Set(key, JValue.CreateNull());
                    break;
                case "add":
                    ApplyAdd(key, value);
                    break;
                case "mark_played":
                case "unlock":
                    StoryStateStore.Instance.SetBool(key, true);
                    break;
                default:
                    Debug.LogWarning($"SparkArc: 未支持的 effect 操作 [{op}]，key={key}");
                    break;
            }
        }

        private void ApplyAdd(string key, JToken value)
        {
            var current = StoryStateStore.Instance.Get(key);
            var delta = ToDouble(value, 0);
            var baseValue = ToDouble(current, 0);
            var result = baseValue + delta;

            if (Math.Abs(result % 1) < 0.000001)
            {
                StoryStateStore.Instance.SetInt(key, (int)Math.Round(result));
            }
            else
            {
                StoryStateStore.Instance.Set(key, new JValue(result));
            }
        }

        private static double ToDouble(JToken token, double fallback)
        {
            if (token == null) return fallback;
            return double.TryParse(token.ToString(), out var parsed) ? parsed : fallback;
        }
    }
}
