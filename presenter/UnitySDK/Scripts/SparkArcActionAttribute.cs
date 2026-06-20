using System;

namespace SparkArc.Unity
{
    /// <summary>
    /// 标记可被 SparkArc 剧情系统绑定的 Unity 行为方法。
    /// 未标记的方法仍可被调度器按方法名调用；标记用于 Editor manifest 提供更友好的 act 建议和说明。
    /// </summary>
    [AttributeUsage(AttributeTargets.Method, AllowMultiple = false, Inherited = false)]
    public sealed class SparkArcActionAttribute : Attribute
    {
        public string ActName { get; }
        public string ActionType { get; set; }
        public string Description { get; set; }

        public SparkArcActionAttribute(string actName = null)
        {
            ActName = actName;
        }
    }
}
