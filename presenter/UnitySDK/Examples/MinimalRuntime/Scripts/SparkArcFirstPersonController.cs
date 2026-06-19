using UnityEngine;
#if ENABLE_INPUT_SYSTEM
using UnityEngine.InputSystem;
#endif

namespace SparkArc.Unity.Examples
{
    /// <summary>
    /// 最小第一人称控制器，用于验证 SparkArc 剧情运行时接入流程。
    /// </summary>
    [RequireComponent(typeof(CharacterController))]
    public class SparkArcFirstPersonController : MonoBehaviour
    {
        public Transform cameraRoot;
        public float moveSpeed = 4.2f;
        public float lookSensitivity = 0.12f;
        public float gravity = -18f;

        private CharacterController _controller;
        private float _pitch;
        private float _verticalVelocity;

        void Awake()
        {
            _controller = GetComponent<CharacterController>();
            if (cameraRoot == null && Camera.main != null)
            {
                cameraRoot = Camera.main.transform;
            }
        }

        void Start()
        {
            SetCursorLocked(true);
        }

        void Update()
        {
            var dialogueRunning = DialogueManager.Instance != null && DialogueManager.Instance.isDialogueRunning;
            if (dialogueRunning)
            {
                SetCursorLocked(false);
                return;
            }

            if (WasEscapePressed())
            {
                SetCursorLocked(false);
            }
            else if (WasPrimaryPressed())
            {
                SetCursorLocked(true);
            }

            Look();
            Move();
        }

        private void Look()
        {
            if (cameraRoot == null || Cursor.lockState != CursorLockMode.Locked) return;

            var look = ReadLookDelta();
#if ENABLE_INPUT_SYSTEM
            look *= lookSensitivity;
#else
            look *= lookSensitivity * 20f;
#endif
            transform.Rotate(Vector3.up * look.x);
            _pitch = Mathf.Clamp(_pitch - look.y, -82f, 82f);
            cameraRoot.localEulerAngles = new Vector3(_pitch, 0f, 0f);
        }

        private void Move()
        {
            var input = ReadMove();
            var direction = transform.right * input.x + transform.forward * input.y;

            if (_controller.isGrounded && _verticalVelocity < 0f)
            {
                _verticalVelocity = -2f;
            }

            _verticalVelocity += gravity * Time.deltaTime;
            var velocity = direction * moveSpeed + Vector3.up * _verticalVelocity;
            _controller.Move(velocity * Time.deltaTime);
        }

        private static Vector2 ReadMove()
        {
            var move = Vector2.zero;
#if ENABLE_INPUT_SYSTEM
            var keyboard = Keyboard.current;
            if (keyboard != null)
            {
                if (keyboard.aKey.isPressed) move.x -= 1f;
                if (keyboard.dKey.isPressed) move.x += 1f;
                if (keyboard.sKey.isPressed) move.y -= 1f;
                if (keyboard.wKey.isPressed) move.y += 1f;
            }
#endif
#if ENABLE_LEGACY_INPUT_MANAGER
            move.x += Input.GetAxisRaw("Horizontal");
            move.y += Input.GetAxisRaw("Vertical");
#endif
            return Vector2.ClampMagnitude(move, 1f);
        }

        private static Vector2 ReadLookDelta()
        {
#if ENABLE_INPUT_SYSTEM
            var mouse = Mouse.current;
            if (mouse != null) return mouse.delta.ReadValue();
#endif
#if ENABLE_LEGACY_INPUT_MANAGER
            return new Vector2(Input.GetAxis("Mouse X"), Input.GetAxis("Mouse Y"));
#else
            return Vector2.zero;
#endif
        }

        private static bool WasPrimaryPressed()
        {
#if ENABLE_INPUT_SYSTEM
            var mouse = Mouse.current;
            if (mouse != null && mouse.leftButton.wasPressedThisFrame) return true;
#endif
#if ENABLE_LEGACY_INPUT_MANAGER
            if (Input.GetMouseButtonDown(0)) return true;
#endif
            return false;
        }

        private static bool WasEscapePressed()
        {
#if ENABLE_INPUT_SYSTEM
            var keyboard = Keyboard.current;
            if (keyboard != null && keyboard.escapeKey.wasPressedThisFrame) return true;
#endif
#if ENABLE_LEGACY_INPUT_MANAGER
            if (Input.GetKeyDown(KeyCode.Escape)) return true;
#endif
            return false;
        }

        private static void SetCursorLocked(bool locked)
        {
            Cursor.lockState = locked ? CursorLockMode.Locked : CursorLockMode.None;
            Cursor.visible = !locked;
        }
    }
}
