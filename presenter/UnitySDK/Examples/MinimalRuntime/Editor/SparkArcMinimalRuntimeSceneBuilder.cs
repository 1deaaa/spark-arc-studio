#if UNITY_EDITOR
using System.IO;
using SparkArc.Unity.Examples;
using TMPro;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.InputSystem.UI;
using UnityEngine.SceneManagement;
using UnityEngine.UI;

namespace SparkArc.Unity.EditorTools
{
    /// <summary>
    /// 一键重建最小 Unity 运行时接入示例场景。
    /// </summary>
    public static class SparkArcMinimalRuntimeSceneBuilder
    {
        private const string ScenePath = "Assets/Scenes/SparkArcMinimalRuntime.unity";
        private const string ExampleRoot = "Assets/SparkArc/Examples/MinimalRuntime";
        private const string CharacterDbPath = ExampleRoot + "/SparkArcDemoCharacters.asset";
        private const string ChineseFontAssetPath = ExampleRoot + "/Fonts/SparkArcChinese SDF.asset";
        private const string DemoDbPath = "Assets/StreamingAssets/stories.db";

        private static TMP_FontAsset _chineseFont;

        [MenuItem("SparkArc/Demo/Rebuild Minimal Runtime Scene")]
        public static void Rebuild()
        {
            EnsureFolders();
            EnsureDemoDatabase();

            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            scene.name = "SparkArcMinimalRuntime";

            var materials = CreateMaterials();
            CreateEnvironment(materials);
            CreateLighting();

            var characterDb = CreateCharacterDatabase();
            var manager = CreateSparkArcManager(characterDb);
            var ui = manager.GetComponent<DialogueUI>();

            var hint = CreateDialogueCanvas(ui);
            CreatePlayer();
            CreateNpc(hint.panel, hint.text);
            CreateEventSystem();

            EditorSceneManager.SaveScene(scene, ScenePath);
            EditorBuildSettings.scenes = new[]
            {
                new EditorBuildSettingsScene(ScenePath, true)
            };
            AssetDatabase.SaveAssets();
            AssetDatabase.Refresh();
            Debug.Log("SparkArc: 最小 Unity 运行时接入示例场景已生成。打开 Assets/Scenes/SparkArcMinimalRuntime.unity 后点击 Play，靠近 NPC 按 F。");
        }

        [MenuItem("SparkArc/Demo/Create Demo Story DB")]
        public static void CreateDemoStoryDb()
        {
            EnsureFolders();
            EnsureDemoDatabase(true);
            AssetDatabase.Refresh();
            Debug.Log($"SparkArc: 示例 stories.db 已生成: {DemoDbPath}");
        }

        [MenuItem("SparkArc/Demo/Run Runtime Smoke Probe")]
        public static void RunRuntimeSmokeProbe()
        {
            if (!EditorApplication.isPlaying)
            {
                Debug.LogWarning("SparkArc: 请先进入 Play Mode，再运行烟雾探针。");
                return;
            }

            var sceneName = "windrise_first_meet";
            var scene = StoryRepository.Instance != null ? StoryRepository.Instance.GetScene(sceneName) : null;
            var dialogueCount = scene != null && scene.dialogues != null ? scene.dialogues.Count : -1;
            Debug.Log($"SparkArc Demo Smoke: sceneLoaded={scene != null}, dialogues={dialogueCount}, button={scene?.buttonText}");

            if (DialogueManager.Instance == null || scene == null)
            {
                Debug.LogError("SparkArc Demo Smoke: 运行时组件未就绪，无法触发对话。");
                return;
            }

            var dispatched = SparkArcActionDispatcher.Instance != null
                && SparkArcActionDispatcher.Instance.Dispatch("bgm", new[] { "town_theme" });
            Debug.Log($"SparkArc Demo Smoke: actionDispatched={dispatched}");

            DialogueManager.Instance.StartScene(sceneName);

            var ui = DialogueManager.Instance.GetComponent<DialogueUI>();
            var panelActive = ui != null && ui.dialoguePanel != null && ui.dialoguePanel.activeInHierarchy;
            Debug.Log($"SparkArc Demo Smoke: dialogueRunning={DialogueManager.Instance.isDialogueRunning}, current={DialogueManager.Instance.currentScene?.sceneName}, panelActive={panelActive}");
        }

        private static void EnsureFolders()
        {
            EnsureFolder("Assets/SparkArc");
            EnsureFolder("Assets/SparkArc/Examples");
            EnsureFolder(ExampleRoot);
            EnsureFolder(ExampleRoot + "/Fonts");
            EnsureFolder(ExampleRoot + "/Materials");
            EnsureFolder("Assets/Scenes");
            EnsureFolder("Assets/StreamingAssets");
        }

        private static void EnsureFolder(string path)
        {
            if (AssetDatabase.IsValidFolder(path)) return;
            var parent = Path.GetDirectoryName(path)?.Replace("\\", "/");
            var name = Path.GetFileName(path);
            if (!string.IsNullOrEmpty(parent) && !AssetDatabase.IsValidFolder(parent))
            {
                EnsureFolder(parent);
            }
            AssetDatabase.CreateFolder(parent ?? "Assets", name);
        }

        private static void EnsureDemoDatabase(bool overwrite = false)
        {
            var fullPath = Path.GetFullPath(DemoDbPath);
            if (!overwrite && File.Exists(fullPath)) return;

            var directory = Path.GetDirectoryName(fullPath);
            if (!string.IsNullOrEmpty(directory))
            {
                Directory.CreateDirectory(directory);
            }

            if (File.Exists(fullPath))
            {
                File.Delete(fullPath);
            }

            using (var connection = new Mono.Data.Sqlite.SqliteConnection($"Data Source={fullPath};Version=3;"))
            {
                connection.Open();
                ExecuteSql(connection, "CREATE TABLE stories (id INTEGER PRIMARY KEY AUTOINCREMENT, chapter INTEGER NOT NULL, scene_name TEXT NOT NULL, button_text TEXT, progress REAL NOT NULL DEFAULT 0, guide TEXT NOT NULL, conditions TEXT, effects TEXT, trigger_event TEXT, priority INTEGER NOT NULL DEFAULT 0, once_key TEXT, intro TEXT, dlg_json TEXT NOT NULL, hiden INTEGER)");
                ExecuteSql(connection, "CREATE TABLE characters (id INTEGER PRIMARY KEY AUTOINCREMENT, character_id INTEGER NOT NULL, name TEXT NOT NULL, description TEXT, content TEXT, avatar_path TEXT)");
                ExecuteSql(connection, "CREATE TABLE binding_act (id INTEGER PRIMARY KEY AUTOINCREMENT, act_type TEXT, act_name TEXT NOT NULL, func_name TEXT NOT NULL, act_description TEXT, act_args TEXT)");
                ExecuteSql(connection, "CREATE TABLE registry (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, value TEXT NOT NULL)");

                ExecuteSql(connection, "INSERT INTO characters (character_id, name) VALUES (-1, '旁白'), (0, '林照'), (1, '遥')");
                ExecuteSql(connection, "INSERT INTO registry (name, value) VALUES ('player_name', '[\"林照\"]'), ('place', '[\"雾港\"]'), ('lost_name', '[\"阿策\"]')");
                ExecuteSql(connection, "INSERT INTO binding_act (act_type, act_name, func_name, act_description, act_args) VALUES ('audio', 'bgm', 'PlayBGM', '切换叙事环境音乐', '{\"musicName\":[\"harbor_alarm\",\"quiet_signal\"]}'), ('world', 'weather', 'ChangeWeather', '切换雾港天气和时段', '{\"weatherType\":[\"dense_fog\",\"clear_night\"],\"duration\":\"8\",\"location\":\"{place}\"}')");

                var dialogues = "[{\"id\":1,\"chr\":-1,\"txt\":\"雾港的宵禁钟敲到第三声，港口的雾却没有散。它像一封没有署名的信，把整座城封在潮湿的信封里。\",\"act\":{\"bgm\":\"harbor_alarm\"}},{\"id\":2,\"chr\":1,\"txt\":\"林照，别往海堤走。明天的你会在那里捡到一枚旧怀表，然后把所有人都忘了。\",\"act\":{\"weather\":[\"dense_fog\",\"8\",\"{place}\"]}},{\"id\":3,\"chr\":0,\"txt\":\"你是谁？还有，你怎么知道我弟弟 {lost_name} 的怀表？\"},{\"id\":4,\"chr\":1,\"txt\":\"我叫遥，是从明天凌晨逃回来的。广播塔会在零点发出错误的疏散令；{lost_name} 正被困在塔下的旧换乘井。\"},{\"id\":5,\"chr\":-1,\"txt\":\"遥递来一张被海水浸透的车票，背面只写着一行字：别让恐惧替你选择。\"},{\"id\":6,\"chr\":0,\"txt\":\"我该相信你吗？\",\"opt\":[{\"optn\":\"登上广播塔，向全城公开真相\",\"dia\":[{\"id\":7,\"chr\":0,\"txt\":\"把频道切到公共频段。雾港的人有权知道，他们不是被雾困住，而是被谎言困住。\"},{\"id\":8,\"chr\":1,\"txt\":\"好。我去打开备用电源。钟声停下前，别回头。\"}]},{\"optn\":\"先去换乘井救出阿策\",\"dia\":[{\"id\":9,\"chr\":0,\"txt\":\"真相可以等十分钟，阿策不能。带路。\"},{\"id\":10,\"chr\":1,\"txt\":\"那就沿着蓝灯走。它们会熄灭两次，第三次亮起时，你会看见他。\"}]}]}]";
                var effects = "[{\"op\":\"set\",\"key\":\"quest.fogport.signal_started\",\"value\":true},{\"op\":\"set\",\"key\":\"quest.fogport.step\",\"value\":2},{\"op\":\"mark_played\",\"key\":\"fogport.last_signal\"}]";
                using (var command = connection.CreateCommand())
                {
                    command.CommandText = "INSERT INTO stories (chapter, scene_name, button_text, progress, guide, conditions, effects, trigger_event, priority, once_key, intro, dlg_json, hiden) VALUES (1, @scene, @button, 1, @guide, NULL, @effects, NULL, 0, @onceKey, @intro, @dlg, 0)";
                    command.Parameters.AddWithValue("@scene", "fogport_last_signal");
                    command.Parameters.AddWithValue("@button", "按 F 阅读遥的来信");
                    command.Parameters.AddWithValue("@guide", "雾港宵禁前夜：决定先公开真相，还是先救出阿策。");
                    command.Parameters.AddWithValue("@effects", effects);
                    command.Parameters.AddWithValue("@onceKey", "fogport.last_signal");
                    command.Parameters.AddWithValue("@intro", "《雾港来信》· 第一幕：最后的信号");
                    command.Parameters.AddWithValue("@dlg", dialogues);
                    command.ExecuteNonQuery();
                }
            }
        }

        private static void ExecuteSql(Mono.Data.Sqlite.SqliteConnection connection, string sql)
        {
            using (var command = connection.CreateCommand())
            {
                command.CommandText = sql;
                command.ExecuteNonQuery();
            }
        }

        private static DemoMaterials CreateMaterials()
        {
            return new DemoMaterials
            {
                Ground = CreateMaterial("Ground", new Color(0.30f, 0.34f, 0.30f)),
                Npc = CreateMaterial("Npc", new Color(0.25f, 0.48f, 0.92f)),
                Player = CreateMaterial("Player", new Color(0.75f, 0.76f, 0.78f)),
                Marker = CreateMaterial("Marker", new Color(1.00f, 0.82f, 0.38f)),
            };
        }

        private static Material CreateMaterial(string name, Color color)
        {
            var path = $"{ExampleRoot}/Materials/{name}.mat";
            var material = AssetDatabase.LoadAssetAtPath<Material>(path);
            if (material == null)
            {
                material = new Material(Shader.Find("Universal Render Pipeline/Lit") ?? Shader.Find("Standard"));
                AssetDatabase.CreateAsset(material, path);
            }
            material.color = color;
            EditorUtility.SetDirty(material);
            return material;
        }

        private static void CreateEnvironment(DemoMaterials materials)
        {
            var ground = GameObject.CreatePrimitive(PrimitiveType.Plane);
            ground.name = "Demo_Ground";
            ground.transform.localScale = new Vector3(6f, 1f, 6f);
            ground.GetComponent<Renderer>().sharedMaterial = materials.Ground;

            for (var i = 0; i < 4; i++)
            {
                var marker = GameObject.CreatePrimitive(PrimitiveType.Cube);
                marker.name = $"Demo_Waypoint_{i + 1}";
                marker.transform.position = new Vector3((i - 1.5f) * 1.8f, 0.08f, 2.1f + i * 0.7f);
                marker.transform.localScale = new Vector3(0.25f, 0.16f, 0.25f);
                marker.GetComponent<Renderer>().sharedMaterial = materials.Marker;
            }
        }

        private static void CreateLighting()
        {
            var lightObj = new GameObject("Directional Light");
            lightObj.transform.rotation = Quaternion.Euler(50f, -35f, 0f);
            var light = lightObj.AddComponent<Light>();
            light.type = LightType.Directional;
            light.intensity = 1.3f;

            var cameraObj = new GameObject("Main Camera");
            cameraObj.tag = "MainCamera";
            cameraObj.transform.position = new Vector3(0f, 1.65f, -5f);
            cameraObj.transform.rotation = Quaternion.Euler(8f, 0f, 0f);
            cameraObj.AddComponent<Camera>();
            cameraObj.AddComponent<AudioListener>();
        }

        private static CharacterDatabase CreateCharacterDatabase()
        {
            var db = AssetDatabase.LoadAssetAtPath<CharacterDatabase>(CharacterDbPath);
            if (db == null)
            {
                db = ScriptableObject.CreateInstance<CharacterDatabase>();
                AssetDatabase.CreateAsset(db, CharacterDbPath);
            }

            db.characters.Clear();
            db.characters.Add(new CharacterDatabase.CharacterInfo { id = -1, name = "旁白" });
            db.characters.Add(new CharacterDatabase.CharacterInfo { id = 0, name = "旅行者" });
            db.characters.Add(new CharacterDatabase.CharacterInfo { id = 1, name = "风丘信使" });
            EditorUtility.SetDirty(db);
            return db;
        }

        private static TMP_FontAsset GetChineseFont()
        {
            if (_chineseFont != null) return _chineseFont;

            _chineseFont = AssetDatabase.LoadAssetAtPath<TMP_FontAsset>(ChineseFontAssetPath);
            if (_chineseFont != null) return _chineseFont;

            _chineseFont = TMP_FontAsset.CreateFontAsset("Microsoft YaHei", "Regular", 90);
            if (_chineseFont == null)
            {
                Debug.LogError("SparkArc: 未找到可用的中文字体，无法创建对话字体资源。");
                return null;
            }

            _chineseFont.name = "SparkArcChinese SDF";
            AssetDatabase.CreateAsset(_chineseFont, ChineseFontAssetPath);
            return _chineseFont;
        }

        private static GameObject CreateSparkArcManager(CharacterDatabase characterDb)
        {
            var manager = new GameObject("SparkArc_Manager");
            manager.AddComponent<StoryRepository>().dbFileName = "stories.db";
            manager.AddComponent<StoryStateStore>();
            manager.AddComponent<SceneConditionEvaluator>();
            manager.AddComponent<StoryEffectApplier>();
            manager.AddComponent<SparkArcDemoActionHandler>();
            manager.AddComponent<SparkArcActionDispatcher>();
            manager.AddComponent<SparkArcRuntimeBootstrap>();
            var ui = manager.AddComponent<DialogueUI>();
            var dialogueManager = manager.AddComponent<DialogueManager>();
            dialogueManager.characterDB = characterDb;
            return manager;
        }

        private static (GameObject panel, TMP_Text text) CreateDialogueCanvas(DialogueUI ui)
        {
            var canvasObj = new GameObject("SparkArc_Canvas");
            var canvas = canvasObj.AddComponent<Canvas>();
            canvas.renderMode = RenderMode.ScreenSpaceOverlay;
            canvas.sortingOrder = 100;
            var scaler = canvasObj.AddComponent<CanvasScaler>();
            scaler.uiScaleMode = CanvasScaler.ScaleMode.ScaleWithScreenSize;
            scaler.referenceResolution = new Vector2(1920f, 1080f);
            scaler.matchWidthOrHeight = 0.5f;
            canvasObj.AddComponent<GraphicRaycaster>();

            var dialoguePanel = CreatePanel(canvasObj.transform, "Dialogue_Panel", new Color(0.03f, 0.05f, 0.08f, 0.86f));
            var panelRect = dialoguePanel.GetComponent<RectTransform>();
            panelRect.anchorMin = new Vector2(0.12f, 0.05f);
            panelRect.anchorMax = new Vector2(0.88f, 0.33f);
            panelRect.offsetMin = Vector2.zero;
            panelRect.offsetMax = Vector2.zero;

            var guideText = CreateText(dialoguePanel.transform, "Guide_Text", 26, FontStyles.Bold, new Color(1f, 0.86f, 0.55f));
            SetRect(guideText.rectTransform, new Vector2(0.04f, 0.78f), new Vector2(0.96f, 0.94f));

            var introText = CreateText(dialoguePanel.transform, "Intro_Text", 20, FontStyles.Italic, new Color(0.78f, 0.84f, 0.90f));
            SetRect(introText.rectTransform, new Vector2(0.04f, 0.62f), new Vector2(0.96f, 0.78f));

            var nameText = CreateText(dialoguePanel.transform, "Name_Text", 28, FontStyles.Bold, new Color(0.90f, 0.72f, 0.36f));
            SetRect(nameText.rectTransform, new Vector2(0.04f, 0.42f), new Vector2(0.32f, 0.60f));

            var contentText = CreateText(dialoguePanel.transform, "Content_Text", 30, FontStyles.Normal, Color.white);
            contentText.textWrappingMode = TextWrappingModes.Normal;
            SetRect(contentText.rectTransform, new Vector2(0.04f, 0.12f), new Vector2(0.78f, 0.42f));

            var choiceContainer = new GameObject("Choice_Container");
            choiceContainer.transform.SetParent(dialoguePanel.transform, false);
            var choiceRect = choiceContainer.AddComponent<RectTransform>();
            SetRect(choiceRect, new Vector2(0.80f, 0.10f), new Vector2(0.96f, 0.58f));
            var layout = choiceContainer.AddComponent<VerticalLayoutGroup>();
            layout.spacing = 10f;
            layout.childControlHeight = true;
            layout.childForceExpandHeight = false;
            choiceContainer.AddComponent<ContentSizeFitter>().verticalFit = ContentSizeFitter.FitMode.PreferredSize;

            var choiceButton = CreateChoiceButton(dialoguePanel.transform);
            choiceButton.SetActive(false);

            var hintPanel = CreatePanel(canvasObj.transform, "Interact_Hint", new Color(0.02f, 0.03f, 0.05f, 0.74f));
            var hintRect = hintPanel.GetComponent<RectTransform>();
            hintRect.anchorMin = new Vector2(0.39f, 0.60f);
            hintRect.anchorMax = new Vector2(0.61f, 0.69f);
            hintRect.offsetMin = Vector2.zero;
            hintRect.offsetMax = Vector2.zero;

            var hintText = CreateText(hintPanel.transform, "Interact_Hint_Text", 28, FontStyles.Bold, Color.white);
            hintText.alignment = TextAlignmentOptions.Center;
            SetRect(hintText.rectTransform, Vector2.zero, Vector2.one);
            hintPanel.SetActive(false);

            ui.dialoguePanel = dialoguePanel;
            ui.guideText = guideText;
            ui.introText = introText;
            ui.nameText = nameText;
            ui.contentText = contentText;
            ui.choiceContainer = choiceContainer.transform;
            ui.choiceButtonPrefab = choiceButton;
            ui.typingSpeed = 0.025f;
            dialoguePanel.SetActive(false);

            return (hintPanel, hintText);
        }

        private static GameObject CreatePanel(Transform parent, string name, Color color)
        {
            var obj = new GameObject(name);
            obj.transform.SetParent(parent, false);
            obj.AddComponent<RectTransform>();
            var image = obj.AddComponent<Image>();
            image.color = color;
            return obj;
        }

        private static TextMeshProUGUI CreateText(Transform parent, string name, int size, FontStyles style, Color color)
        {
            var obj = new GameObject(name);
            obj.transform.SetParent(parent, false);
            var text = obj.AddComponent<TextMeshProUGUI>();
            text.font = GetChineseFont();
            text.fontSize = size;
            text.fontStyle = style;
            text.color = color;
            text.alignment = TextAlignmentOptions.Left;
            text.raycastTarget = false;
            return text;
        }

        private static GameObject CreateChoiceButton(Transform parent)
        {
            var obj = CreatePanel(parent, "Choice_Button_Template", new Color(1f, 0.82f, 0.40f, 0.18f));
            var rect = obj.GetComponent<RectTransform>();
            rect.sizeDelta = new Vector2(260f, 56f);
            var button = obj.AddComponent<Button>();
            var colors = button.colors;
            colors.normalColor = new Color(1f, 0.82f, 0.40f, 0.22f);
            colors.highlightedColor = new Color(1f, 0.86f, 0.50f, 0.42f);
            button.colors = colors;

            var label = CreateText(obj.transform, "Choice_Label", 22, FontStyles.Normal, Color.white);
            label.alignment = TextAlignmentOptions.Center;
            SetRect(label.rectTransform, Vector2.zero, Vector2.one);
            return obj;
        }

        private static void SetRect(RectTransform rect, Vector2 min, Vector2 max)
        {
            rect.anchorMin = min;
            rect.anchorMax = max;
            rect.offsetMin = Vector2.zero;
            rect.offsetMax = Vector2.zero;
        }

        private static void CreatePlayer()
        {
            var player = GameObject.CreatePrimitive(PrimitiveType.Capsule);
            player.name = "Player";
            player.tag = "Player";
            player.transform.position = new Vector3(0f, 1f, -3.8f);
            Object.DestroyImmediate(player.GetComponent<CapsuleCollider>());
            var controller = player.AddComponent<CharacterController>();
            controller.height = 1.8f;
            controller.radius = 0.32f;
            controller.center = new Vector3(0f, 0.9f, 0f);
            var fps = player.AddComponent<SparkArcFirstPersonController>();

            var camera = GameObject.FindWithTag("MainCamera");
            camera.transform.SetParent(player.transform, false);
            camera.transform.localPosition = new Vector3(0f, 1.62f, 0f);
            camera.transform.localRotation = Quaternion.identity;
            fps.cameraRoot = camera.transform;
        }

        private static void CreateNpc(GameObject hintPanel, TMP_Text hintText)
        {
            var npc = new GameObject("NPC_WindriseMessenger");
            npc.transform.position = new Vector3(0f, 0f, 3.8f);

            var visual = GameObject.CreatePrimitive(PrimitiveType.Capsule);
            visual.name = "Visual";
            visual.transform.SetParent(npc.transform, false);
            visual.transform.localPosition = new Vector3(0f, 1f, 0f);
            visual.transform.localScale = new Vector3(0.55f, 1f, 0.55f);
            Object.DestroyImmediate(visual.GetComponent<CapsuleCollider>());
            visual.GetComponent<Renderer>().sharedMaterial = AssetDatabase.LoadAssetAtPath<Material>($"{ExampleRoot}/Materials/Npc.mat");

            var trigger = npc.AddComponent<SphereCollider>();
            trigger.isTrigger = true;
            trigger.radius = 2.2f;

            var dialogueTrigger = npc.AddComponent<DialogueTrigger>();
            dialogueTrigger.sceneName = "fogport_last_signal";
            dialogueTrigger.mode = DialogueTrigger.TriggerMode.Manual;
            dialogueTrigger.interactHint = hintPanel;
            dialogueTrigger.interactHintText = hintText;
            dialogueTrigger.fallbackHintText = "按 F 阅读来信";

            var labelRoot = new GameObject("Name_Label");
            labelRoot.transform.SetParent(npc.transform, false);
            labelRoot.transform.localPosition = new Vector3(0f, 2.25f, 0f);
            var label = labelRoot.AddComponent<TextMeshPro>();
            label.font = GetChineseFont();
            label.text = "遥";
            label.fontSize = 3f;
            label.alignment = TextAlignmentOptions.Center;
            label.color = new Color(1f, 0.86f, 0.58f);
        }

        private static void CreateEventSystem()
        {
            var eventSystem = new GameObject("EventSystem");
            eventSystem.AddComponent<EventSystem>();
            eventSystem.AddComponent<InputSystemUIInputModule>();
        }

        private struct DemoMaterials
        {
            public Material Ground;
            public Material Npc;
            public Material Player;
            public Material Marker;
        }
    }
}
#endif
