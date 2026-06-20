using System;
using System.Collections.Generic;
using System.Globalization;
using System.Reflection;
using UnityEngine;

namespace SparkArc.Unity
{
    /// <summary>
    /// SparkArc act 行为调度器。
    /// 只会扫描 SparkArcActionHandler 组件上的实例方法，用 binding_act 将剧情 act 名映射到 Unity 方法名。
    /// </summary>
    public class SparkArcActionDispatcher : MonoBehaviour
    {
        public static SparkArcActionDispatcher Instance { get; private set; }

        [Tooltip("为空时自动扫描当前场景中所有 SparkArcActionHandler。中型项目建议在这里显式拖入各模块 Handler。")]
        public SparkArcActionHandler[] handlers;

        [Tooltip("找不到 binding_act 时，是否退回使用 act 名作为方法名。示例项目默认开启，正式项目建议关闭。")]
        public bool fallbackToActName = true;

        private readonly Dictionary<string, ActionEndpoint> _endpoints = new Dictionary<string, ActionEndpoint>(StringComparer.OrdinalIgnoreCase);

        void Awake()
        {
            if (Instance == null) Instance = this;
            else Destroy(gameObject);
        }

        void OnEnable()
        {
            DialogueEvents.OnActionTriggered += Dispatch;
        }

        void OnDisable()
        {
            DialogueEvents.OnActionTriggered -= Dispatch;
        }

        void Start()
        {
            RebuildEndpoints();
        }

        public void RebuildEndpoints()
        {
            _endpoints.Clear();
            var sourceHandlers = handlers != null && handlers.Length > 0
                ? handlers
                : FindObjectsOfType<SparkArcActionHandler>();

            foreach (var handler in sourceHandlers)
            {
                if (handler == null) continue;
                RegisterHandler(handler);
            }

            Debug.Log($"SparkArc: 已注册 {_endpoints.Count} 个 Unity 行为方法。");
        }

        public bool Dispatch(string actName, string[] args)
        {
            if (string.IsNullOrWhiteSpace(actName))
            {
                return false;
            }

            var binding = ResolveBinding(actName);
            var functionName = binding != null ? binding.functionName : actName;
            if (string.IsNullOrWhiteSpace(functionName))
            {
                Debug.LogWarning($"SparkArc: 行为 [{actName}] 未配置 Unity 函数名。");
                return false;
            }

            if (!_endpoints.TryGetValue(functionName, out var endpoint))
            {
                Debug.LogWarning($"SparkArc: 找不到 Unity 行为方法 [{functionName}]，act={actName}");
                return false;
            }

            var resolvedArgs = StoryRepository.Instance != null
                ? StoryRepository.Instance.ResolveRegistryTokens(args)
                : (args ?? Array.Empty<string>());

            if (!TryBuildArguments(endpoint.Parameters, resolvedArgs, out var invokeArgs))
            {
                Debug.LogWarning($"SparkArc: 行为方法 [{functionName}] 参数不匹配，act={actName}，参数=[{string.Join(", ", resolvedArgs)}]");
                return false;
            }

            try
            {
                endpoint.Method.Invoke(endpoint.Target, invokeArgs);
                Debug.Log($"SparkArc: 已执行行为 [{actName}] -> {endpoint.Target.GetType().Name}.{endpoint.Method.Name}({string.Join(", ", resolvedArgs)})");
                return true;
            }
            catch (Exception ex)
            {
                var inner = ex.InnerException != null ? ex.InnerException.Message : ex.Message;
                Debug.LogError($"SparkArc: 执行行为 [{actName}] 失败: {inner}");
                return false;
            }
        }

        private ActionBindingData ResolveBinding(string actName)
        {
            if (StoryRepository.Instance != null && StoryRepository.Instance.TryGetActionBinding(actName, out var binding))
            {
                return binding;
            }

            if (fallbackToActName)
            {
                return new ActionBindingData { actName = actName, functionName = actName };
            }

            Debug.LogWarning($"SparkArc: 找不到行为绑定: {actName}");
            return null;
        }

        private void RegisterHandler(SparkArcActionHandler handler)
        {
            var methods = handler.GetType().GetMethods(BindingFlags.Instance | BindingFlags.Public | BindingFlags.DeclaredOnly);
            foreach (var method in methods)
            {
                if (method.IsSpecialName) continue;
                if (IsUnityLifecycleMethod(method.Name)) continue;
                if (method.ReturnType != typeof(void)) continue;

                var parameters = method.GetParameters();
                if (!AreSupportedParameters(parameters)) continue;

                if (_endpoints.ContainsKey(method.Name))
                {
                    Debug.LogWarning($"SparkArc: Unity 行为方法名重复 [{method.Name}]，已保留第一个注册项。");
                    continue;
                }

                var endpoint = new ActionEndpoint(handler, method, parameters);
                _endpoints[method.Name] = endpoint;

                var attr = method.GetCustomAttribute<SparkArcActionAttribute>();
                if (attr != null && !string.IsNullOrWhiteSpace(attr.ActName) && !_endpoints.ContainsKey(attr.ActName))
                {
                    _endpoints[attr.ActName] = endpoint;
                }
            }
        }

        private static bool IsUnityLifecycleMethod(string methodName)
        {
            switch (methodName)
            {
                case "Awake":
                case "OnEnable":
                case "Start":
                case "Update":
                case "LateUpdate":
                case "FixedUpdate":
                case "OnDisable":
                case "OnDestroy":
                    return true;
                default:
                    return false;
            }
        }

        private static bool AreSupportedParameters(ParameterInfo[] parameters)
        {
            foreach (var parameter in parameters)
            {
                var type = parameter.ParameterType;
                if (type != typeof(string)
                    && type != typeof(int)
                    && type != typeof(float)
                    && type != typeof(double)
                    && type != typeof(bool)
                    && type != typeof(string[]))
                {
                    return false;
                }
            }
            return true;
        }

        private static bool TryBuildArguments(ParameterInfo[] parameters, string[] args, out object[] invokeArgs)
        {
            args = args ?? Array.Empty<string>();
            invokeArgs = new object[parameters.Length];

            if (parameters.Length == 1 && parameters[0].ParameterType == typeof(string[]))
            {
                invokeArgs[0] = args;
                return true;
            }

            if (args.Length < RequiredParameterCount(parameters) || args.Length > parameters.Length)
            {
                return false;
            }

            for (var i = 0; i < parameters.Length; i++)
            {
                if (i >= args.Length)
                {
                    invokeArgs[i] = parameters[i].DefaultValue;
                    continue;
                }

                if (!TryConvert(args[i], parameters[i].ParameterType, out invokeArgs[i]))
                {
                    return false;
                }
            }

            return true;
        }

        private static int RequiredParameterCount(ParameterInfo[] parameters)
        {
            var count = 0;
            foreach (var parameter in parameters)
            {
                if (!parameter.HasDefaultValue) count++;
            }
            return count;
        }

        private static bool TryConvert(string raw, Type type, out object value)
        {
            if (type == typeof(string))
            {
                value = raw ?? string.Empty;
                return true;
            }

            if (type == typeof(int) && int.TryParse(raw, NumberStyles.Integer, CultureInfo.InvariantCulture, out var intValue))
            {
                value = intValue;
                return true;
            }

            if (type == typeof(float) && float.TryParse(raw, NumberStyles.Float, CultureInfo.InvariantCulture, out var floatValue))
            {
                value = floatValue;
                return true;
            }

            if (type == typeof(double) && double.TryParse(raw, NumberStyles.Float, CultureInfo.InvariantCulture, out var doubleValue))
            {
                value = doubleValue;
                return true;
            }

            if (type == typeof(bool) && bool.TryParse(raw, out var boolValue))
            {
                value = boolValue;
                return true;
            }

            value = null;
            return false;
        }

        private readonly struct ActionEndpoint
        {
            public readonly SparkArcActionHandler Target;
            public readonly MethodInfo Method;
            public readonly ParameterInfo[] Parameters;

            public ActionEndpoint(SparkArcActionHandler target, MethodInfo method, ParameterInfo[] parameters)
            {
                Target = target;
                Method = method;
                Parameters = parameters;
            }
        }
    }
}
