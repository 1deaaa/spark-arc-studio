using System;
using System.Collections.Generic;
using Newtonsoft.Json.Linq;

namespace SparkArc.Unity
{
    /// <summary>
    /// 场景数据模型
    /// </summary>
    [Serializable]
    public class SceneData
    {
        public string sceneName;
        public string guide;
        public string intro;
        public JArray dialogues;
        public JToken conditions;
        public JToken effects;
        public string triggerEvent;
        public int priority;
        public string onceKey;
        public string buttonText;
        public bool hidden;
    }

    /// <summary>
    /// act 行为与 Unity C# 方法之间的绑定关系。
    /// </summary>
    [Serializable]
    public class ActionBindingData
    {
        public string actName;
        public string functionName;
        public string actionType;
        public string description;
        public JObject argsSchema;
    }

    /// <summary>
    /// 全局注册表项，可用于对话文本和行为参数中的 {name} 占位符。
    /// </summary>
    [Serializable]
    public class RegistryData
    {
        public string name;
        public JArray values;
    }

    /// <summary>
    /// 对话节点类型
    /// </summary>
    public enum NodeType
    {
        Dialogue,
        Choice,
        Action,
        Next
    }
}
