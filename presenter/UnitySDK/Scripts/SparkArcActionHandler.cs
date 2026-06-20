using UnityEngine;

namespace SparkArc.Unity
{
    /// <summary>
    /// Unity 侧可响应 SparkArc act 行为的组件基类。
    /// 中型项目中建议按音频、任务、镜头、世界状态等模块拆分多个 Handler。
    /// </summary>
    public abstract class SparkArcActionHandler : MonoBehaviour
    {
    }
}
