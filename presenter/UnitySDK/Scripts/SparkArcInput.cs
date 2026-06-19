using UnityEngine;
#if ENABLE_INPUT_SYSTEM
using UnityEngine.InputSystem;
#endif

namespace SparkArc.Unity
{
    /// <summary>
    /// SparkArc 运行时输入适配层。
    /// 在 Unity 新输入系统和旧输入系统之间做最小兼容，避免 SDK 调用方被项目输入设置卡住。
    /// </summary>
    public static class SparkArcInput
    {
        public static bool WasInteractPressed()
        {
#if ENABLE_INPUT_SYSTEM
            var keyboard = Keyboard.current;
            if (keyboard != null && keyboard.fKey.wasPressedThisFrame) return true;
#endif
#if ENABLE_LEGACY_INPUT_MANAGER
            if (Input.GetKeyDown(KeyCode.F)) return true;
#endif
            return false;
        }

        public static bool WasContinuePressed()
        {
#if ENABLE_INPUT_SYSTEM
            var keyboard = Keyboard.current;
            if (keyboard != null)
            {
                if (keyboard.spaceKey.wasPressedThisFrame) return true;
                if (keyboard.enterKey.wasPressedThisFrame) return true;
                if (keyboard.fKey.wasPressedThisFrame) return true;
            }

            var mouse = Mouse.current;
            if (mouse != null && mouse.leftButton.wasPressedThisFrame) return true;
#endif
#if ENABLE_LEGACY_INPUT_MANAGER
            if (Input.GetMouseButtonDown(0)) return true;
            if (Input.GetKeyDown(KeyCode.Space)) return true;
            if (Input.GetKeyDown(KeyCode.Return)) return true;
            if (Input.GetKeyDown(KeyCode.F)) return true;
#endif
            return false;
        }
    }
}
