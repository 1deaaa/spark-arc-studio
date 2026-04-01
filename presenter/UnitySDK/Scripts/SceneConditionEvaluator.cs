using System;
using Newtonsoft.Json.Linq;
using UnityEngine;

namespace SparkArc.Unity
{
    /// <summary>
    /// 轻量场景条件求值器。
    /// 先支持最常见的 RPG 需求：
    /// 1. 旧式 key-value 全等匹配
    /// 2. all / any / not 组合
    /// 3. var + op + value 比较表达式
    /// 4. once / played 一次性条件
    /// </summary>
    public class SceneConditionEvaluator : MonoBehaviour
    {
        public static SceneConditionEvaluator Instance { get; private set; }

        void Awake()
        {
            if (Instance == null) Instance = this;
            else Destroy(gameObject);
        }

        public bool CanStart(SceneData scene, out string reason)
        {
            if (scene == null)
            {
                reason = "scene is null";
                return false;
            }

            if (scene.hidden)
            {
                reason = $"scene '{scene.sceneName}' is hidden";
                return false;
            }

            return Evaluate(scene.conditions, out reason);
        }

        public bool Evaluate(JToken conditions, out string reason)
        {
            reason = string.Empty;
            if (conditions == null || conditions.Type == JTokenType.Null) return true;

            try
            {
                return EvaluateToken(conditions, out reason);
            }
            catch (Exception ex)
            {
                reason = $"conditions parse error: {ex.Message}";
                Debug.LogWarning($"SparkArc: 条件判定异常: {reason}");
                return false;
            }
        }

        private bool EvaluateToken(JToken token, out string reason)
        {
            reason = string.Empty;
            if (token == null || token.Type == JTokenType.Null) return true;

            if (token.Type == JTokenType.Boolean)
            {
                var result = token.Value<bool>();
                if (!result) reason = "boolean condition is false";
                return result;
            }

            if (token.Type != JTokenType.Object)
            {
                reason = $"unsupported condition token: {token.Type}";
                return false;
            }

            var obj = (JObject)token;

            // 新式逻辑组合
            if (obj.ContainsKey("all") || obj.ContainsKey("any") || obj.ContainsKey("not"))
            {
                if (obj.TryGetValue("all", out var allToken) && allToken is JArray allArray)
                {
                    foreach (var child in allArray)
                    {
                        if (!EvaluateToken(child, out reason)) return false;
                    }
                }

                if (obj.TryGetValue("any", out var anyToken) && anyToken is JArray anyArray && anyArray.Count > 0)
                {
                    var matched = false;
                    foreach (var child in anyArray)
                    {
                        if (EvaluateToken(child, out _))
                        {
                            matched = true;
                            break;
                        }
                    }
                    if (!matched)
                    {
                        reason = "none of 'any' conditions matched";
                        return false;
                    }
                }

                if (obj.TryGetValue("not", out var notToken) && notToken is JArray notArray)
                {
                    foreach (var child in notArray)
                    {
                        if (EvaluateToken(child, out _))
                        {
                            reason = "one of 'not' conditions matched";
                            return false;
                        }
                    }
                }

                return true;
            }

            // 新式表达式：{ var, op, value }
            if (obj.ContainsKey("var"))
            {
                return EvaluateExpression(obj, out reason);
            }

            // 一次性 / 已播放判定
            if (obj.TryGetValue("once", out var onceToken))
            {
                var onceKey = onceToken?.ToString();
                var result = !StoryStateStore.Instance || !StoryStateStore.Instance.HasPlayed(onceKey);
                if (!result) reason = $"once key '{onceKey}' already played";
                return result;
            }

            if (obj.TryGetValue("played", out var playedToken))
            {
                var playedKey = playedToken?.ToString();
                var result = StoryStateStore.Instance != null && StoryStateStore.Instance.HasPlayed(playedKey);
                if (!result) reason = $"played key '{playedKey}' not satisfied";
                return result;
            }

            // 旧式兼容：{ "quest.step": 3, "npc1_met": true }
            foreach (var property in obj.Properties())
            {
                if (!EvaluateLegacyEquals(property.Name, property.Value, out reason))
                {
                    return false;
                }
            }
            return true;
        }

        private bool EvaluateLegacyEquals(string key, JToken expected, out string reason)
        {
            reason = string.Empty;
            if (StoryStateStore.Instance == null)
            {
                var fallback = IsLooseTruthy(expected);
                if (!fallback) reason = $"state store missing, key '{key}' expected {expected}";
                return fallback;
            }

            if (!StoryStateStore.Instance.TryGet(key, out var current))
            {
                var fallback = IsLooseTruthy(expected);
                if (!fallback) reason = $"missing state key '{key}'";
                return fallback;
            }

            if (JToken.DeepEquals(NormalizeToken(current), NormalizeToken(expected))) return true;
            reason = $"state '{key}' mismatch: expected {expected}, got {current}";
            return false;
        }

        private bool EvaluateExpression(JObject expression, out string reason)
        {
            reason = string.Empty;
            var key = expression.Value<string>("var") ?? string.Empty;
            var op = expression.Value<string>("op") ?? "==";
            var expected = expression["value"];

            var current = StoryStateStore.Instance != null ? StoryStateStore.Instance.Get(key) : null;
            if (current == null)
            {
                reason = $"missing state key '{key}'";
                return false;
            }

            switch (op)
            {
                case "==":
                    if (JToken.DeepEquals(NormalizeToken(current), NormalizeToken(expected))) return true;
                    reason = $"state '{key}' != expected value";
                    return false;
                case "!=":
                    if (!JToken.DeepEquals(NormalizeToken(current), NormalizeToken(expected))) return true;
                    reason = $"state '{key}' should not equal expected value";
                    return false;
                case ">":
                case ">=":
                case "<":
                case "<=":
                    return CompareNumeric(current, expected, op, key, out reason);
                case "contains":
                    if (current is JArray arr)
                    {
                        foreach (var item in arr)
                        {
                            if (JToken.DeepEquals(NormalizeToken(item), NormalizeToken(expected))) return true;
                        }
                    }
                    reason = $"state '{key}' does not contain expected value";
                    return false;
                default:
                    reason = $"unsupported operator '{op}'";
                    return false;
            }
        }

        private bool CompareNumeric(JToken current, JToken expected, string op, string key, out string reason)
        {
            reason = string.Empty;
            if (!double.TryParse(current.ToString(), out var left) || !double.TryParse(expected?.ToString(), out var right))
            {
                reason = $"state '{key}' numeric compare failed";
                return false;
            }

            switch (op)
            {
                case ">": if (left > right) return true; break;
                case ">=": if (left >= right) return true; break;
                case "<": if (left < right) return true; break;
                case "<=": if (left <= right) return true; break;
            }

            reason = $"state '{key}' compare {left} {op} {right} failed";
            return false;
        }

        private static JToken NormalizeToken(JToken token)
        {
            if (token == null) return JValue.CreateNull();
            return token.Type == JTokenType.String ? new JValue(token.ToString().Trim()) : token;
        }

        private static bool IsLooseTruthy(JToken token)
        {
            if (token == null || token.Type == JTokenType.Null) return true;
            if (token.Type == JTokenType.Boolean) return token.Value<bool>();
            var text = token.ToString().Trim();
            return string.IsNullOrEmpty(text);
        }
    }
}
