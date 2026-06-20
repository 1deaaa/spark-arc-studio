using UnityEngine;

namespace SparkArc.Unity.Examples
{
    /// <summary>
    /// 最小演示行为模块。
    /// 正式项目应按 AudioDirector、QuestRuntime、CameraDirector 等职责继续拆分。
    /// </summary>
    public class SparkArcDemoActionHandler : SparkArcActionHandler
    {
        [SparkArcAction("bgm", ActionType = "audio", Description = "播放指定背景音乐")]
        public void PlayBGM(string musicName)
        {
            Debug.Log($"SparkArc Demo Action: PlayBGM({musicName})");
        }

        [SparkArcAction("weather", ActionType = "world", Description = "切换天气、持续时间和地点")]
        public void ChangeWeather(string weatherType, string duration, string location)
        {
            Debug.Log($"SparkArc Demo Action: ChangeWeather({weatherType}, {duration}, {location})");
        }
    }
}
