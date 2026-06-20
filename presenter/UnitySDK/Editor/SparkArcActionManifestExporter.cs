#if UNITY_EDITOR
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using Newtonsoft.Json;
using UnityEditor;
using UnityEngine;

namespace SparkArc.Unity.EditorTools
{
    /// <summary>
    /// 扫描当前 Unity 工程中可被 SparkArc 绑定的行为方法，并导出给 SparkArc 前端使用。
    /// </summary>
    public static class SparkArcActionManifestExporter
    {
        private const string DefaultManifestPath = "Assets/SparkArc/spark_actions.manifest.json";

        [MenuItem("SparkArc/Actions/Export Action Manifest")]
        public static void ExportManifest()
        {
            var manifest = BuildManifest();
            var json = JsonConvert.SerializeObject(manifest, Formatting.Indented);
            var fullPath = Path.GetFullPath(DefaultManifestPath);
            var directory = Path.GetDirectoryName(fullPath);
            if (!string.IsNullOrEmpty(directory))
            {
                Directory.CreateDirectory(directory);
            }

            File.WriteAllText(fullPath, json);
            AssetDatabase.Refresh();
            Debug.Log($"SparkArc: 已导出 Unity 行为清单，共 {manifest.actions.Count} 个方法。路径: {DefaultManifestPath}");
        }

        public static SparkArcActionManifest BuildManifest()
        {
            var actions = new List<SparkArcActionManifestItem>();
            foreach (var type in GetHandlerTypes())
            {
                foreach (var method in type.GetMethods(BindingFlags.Instance | BindingFlags.Public | BindingFlags.DeclaredOnly))
                {
                    if (!IsSupportedActionMethod(method)) continue;

                    var attr = method.GetCustomAttribute<SparkArcActionAttribute>();
                    var actName = string.IsNullOrWhiteSpace(attr?.ActName) ? ToSnakeCase(method.Name) : attr.ActName.Trim();
                    actions.Add(new SparkArcActionManifestItem
                    {
                        act_name = actName,
                        func_name = method.Name,
                        handler_type = type.FullName,
                        act_type = string.IsNullOrWhiteSpace(attr?.ActionType) ? null : attr.ActionType.Trim(),
                        act_description = string.IsNullOrWhiteSpace(attr?.Description) ? null : attr.Description.Trim(),
                        parameters = method.GetParameters().Select(ToParameterItem).ToList(),
                        act_args = BuildArgsExample(method.GetParameters()),
                    });
                }
            }

            actions.Sort((left, right) => string.Compare(left.act_name, right.act_name, StringComparison.OrdinalIgnoreCase));
            return new SparkArcActionManifest
            {
                schema = "sparkarc.unity.actions@1",
                generated_at = DateTime.UtcNow.ToString("O"),
                actions = actions,
            };
        }

        private static IEnumerable<Type> GetHandlerTypes()
        {
            foreach (var assembly in AppDomain.CurrentDomain.GetAssemblies())
            {
                Type[] types;
                try
                {
                    types = assembly.GetTypes();
                }
                catch (ReflectionTypeLoadException ex)
                {
                    types = ex.Types.Where(t => t != null).ToArray();
                }

                foreach (var type in types)
                {
                    if (type == null || type.IsAbstract) continue;
                    if (typeof(SparkArcActionHandler).IsAssignableFrom(type)) yield return type;
                }
            }
        }

        private static bool IsSupportedActionMethod(MethodInfo method)
        {
            if (method.IsSpecialName || method.ReturnType != typeof(void)) return false;
            if (IsUnityLifecycleMethod(method.Name)) return false;
            return method.GetParameters().All(parameter => IsSupportedParameterType(parameter.ParameterType));
        }

        private static bool IsSupportedParameterType(Type type)
        {
            return type == typeof(string)
                || type == typeof(int)
                || type == typeof(float)
                || type == typeof(double)
                || type == typeof(bool)
                || type == typeof(string[]);
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

        private static SparkArcActionParameterItem ToParameterItem(ParameterInfo parameter)
        {
            return new SparkArcActionParameterItem
            {
                name = parameter.Name,
                type = ToFriendlyTypeName(parameter.ParameterType),
                optional = parameter.HasDefaultValue,
                default_value = parameter.HasDefaultValue ? parameter.DefaultValue : null,
            };
        }

        private static Dictionary<string, object> BuildArgsExample(ParameterInfo[] parameters)
        {
            var result = new Dictionary<string, object>();
            foreach (var parameter in parameters)
            {
                result[parameter.Name] = BuildExampleValue(parameter.ParameterType, parameter.Name);
            }
            return result;
        }

        private static object BuildExampleValue(Type type, string parameterName)
        {
            if (type == typeof(string[])) return new[] { parameterName };
            if (type == typeof(int)) return 1;
            if (type == typeof(float) || type == typeof(double)) return 1.0;
            if (type == typeof(bool)) return true;
            return parameterName;
        }

        private static string ToFriendlyTypeName(Type type)
        {
            if (type == typeof(string)) return "string";
            if (type == typeof(int)) return "int";
            if (type == typeof(float)) return "float";
            if (type == typeof(double)) return "double";
            if (type == typeof(bool)) return "bool";
            if (type == typeof(string[])) return "string[]";
            return type.Name;
        }

        private static string ToSnakeCase(string value)
        {
            if (string.IsNullOrWhiteSpace(value)) return string.Empty;
            var chars = new List<char>();
            for (var i = 0; i < value.Length; i++)
            {
                var current = value[i];
                if (char.IsUpper(current) && i > 0)
                {
                    chars.Add('_');
                }
                chars.Add(char.ToLowerInvariant(current));
            }
            return new string(chars.ToArray());
        }
    }

    [Serializable]
    public class SparkArcActionManifest
    {
        public string schema;
        public string generated_at;
        public List<SparkArcActionManifestItem> actions;
    }

    [Serializable]
    public class SparkArcActionManifestItem
    {
        public string act_name;
        public string func_name;
        public string handler_type;
        public string act_type;
        public string act_description;
        public List<SparkArcActionParameterItem> parameters;
        public Dictionary<string, object> act_args;
    }

    [Serializable]
    public class SparkArcActionParameterItem
    {
        public string name;
        public string type;
        public bool optional;
        public object default_value;
    }
}
#endif
