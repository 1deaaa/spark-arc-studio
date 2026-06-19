using UnityEngine;

namespace SparkArc.Unity.Examples
{
    /// <summary>
    /// 最小演示启动器：初始化剧情状态并加载 StreamingAssets/stories.db。
    /// </summary>
    public class SparkArcRuntimeBootstrap : MonoBehaviour
    {
        public int initialQuestStep = 0;

        void Start()
        {
            if (StoryStateStore.Instance != null)
            {
                StoryStateStore.Instance.SetInt("quest.demo.step", initialQuestStep);
            }

            if (StoryRepository.Instance != null)
            {
                StoryRepository.Instance.LoadDatabase();
            }
        }
    }
}
