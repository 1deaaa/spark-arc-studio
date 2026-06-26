using System;

namespace SparkArc.Unity
{
    /// <summary>
    /// 标记可被 SparkArc 剧情系统绑定的 Unity 行为方法。
    /// 
    /// 【设计考量与约束限制】
    /// 1. 规避 IL2CPP 裁剪 (Stripping)：直接通过文本配置反射调用静态方法，在打包时极易被 Unity 编译器作为 Dead Code 剥离。
    ///    本 SDK 强制使用挂载在场景/预制体组件上的实例方法，通过 Prefab 的资源依赖引用来保证方法免受剥离。
    /// 2. 生命周期与上下文安全：剧情表现方法通常需要依赖场景对象（如灯光、音源）。实例方法生命周期随场景加卸载自动销毁，避免了静态方法下的空指针雷区。
    /// 3. 安全白名单沙盒：剧情运行时仅扫描调度器中显式拖入注册的 Handler 实例白名单，限制反射的作用域边界。
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
