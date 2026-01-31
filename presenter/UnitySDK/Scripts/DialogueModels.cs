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
        public JArray dialogues;
        public JToken conditions;
        public string buttonText;
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
