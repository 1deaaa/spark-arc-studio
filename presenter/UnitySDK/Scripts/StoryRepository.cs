using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using UnityEngine;
using Newtonsoft.Json.Linq;
using System.Data;
using Mono.Data.Sqlite;

namespace SparkArc.Unity
{
    /// <summary>
    /// 负责从 SQLite 数据库加载故事数据
    /// </summary>
    public class StoryRepository : MonoBehaviour
    {
        public static StoryRepository Instance { get; private set; }

        [Header("设置")]
        [Tooltip("数据库文件名，请确保放在 StreamingAssets 文件夹下")]
        public string dbFileName = "stories.db";

        private Dictionary<string, SceneData> _sceneCache = new Dictionary<string, SceneData>();
        private Dictionary<string, ActionBindingData> _actionBindings = new Dictionary<string, ActionBindingData>(StringComparer.OrdinalIgnoreCase);
        private Dictionary<string, RegistryData> _registries = new Dictionary<string, RegistryData>(StringComparer.OrdinalIgnoreCase);
        private string _dbPath;

        void Awake()
        {
            if (Instance == null) Instance = this;
            else Destroy(gameObject);

            // 设置数据库路径
            #if UNITY_EDITOR || UNITY_STANDALONE
            _dbPath = Path.Combine(Application.streamingAssetsPath, dbFileName);
            #elif UNITY_ANDROID
            _dbPath = Path.Combine(Application.persistentDataPath, dbFileName);
            // 注意：Android 需要先从 StreamingAssets 复制到 persistentDataPath，此处简化逻辑
            #else
            _dbPath = Path.Combine(Application.streamingAssetsPath, dbFileName);
            #endif
        }

        public void LoadDatabase()
        {
            _sceneCache.Clear();
            _actionBindings.Clear();
            _registries.Clear();

            if (!File.Exists(_dbPath))
            {
                Debug.LogError($"SparkArc: 数据库文件未找到: {_dbPath}");
                return;
            }

            string connectionString = $"Data Source={_dbPath};Version=3;";
            
            try
            {
                using (var connection = new SqliteConnection(connectionString))
                {
                    connection.Open();
                    LoadRegistries(connection);
                    LoadScenes(connection);
                    LoadActionBindings(connection);
                }
                Debug.Log($"SparkArc: 成功加载 {_sceneCache.Count} 个场景、{_actionBindings.Count} 个行为绑定、{_registries.Count} 个注册表项");
            }
            catch (Exception ex)
            {
                Debug.LogError($"SparkArc: 加载数据库失败: {ex.Message}");
            }
        }

        private void LoadScenes(SqliteConnection connection)
        {
            const string sql = "SELECT chapter, scene_name, guide, intro, button_text, conditions, effects, trigger_event, priority, once_key, dlg_json, hiden FROM stories ORDER BY chapter ASC, progress ASC, id ASC";

            using (var command = new SqliteCommand(sql, connection))
            using (var reader = command.ExecuteReader())
            {
                while (reader.Read())
                {
                    var sceneName = ReadText(reader["scene_name"]);
                    if (string.IsNullOrEmpty(sceneName))
                    {
                        sceneName = $"Chapter_{reader["chapter"]}_{_sceneCache.Count + 1}";
                    }

                    var scene = new SceneData
                    {
                        sceneName = sceneName,
                        guide = ResolveRegistryTokens(ReadText(reader["guide"])),
                        intro = ResolveRegistryTokens(ReadText(reader["intro"])),
                        buttonText = ResolveRegistryTokens(ReadText(reader["button_text"])),
                        hidden = false,
                    };

                    var dlgJson = ReadText(reader["dlg_json"]);
                    scene.dialogues = !string.IsNullOrEmpty(dlgJson) ? JArray.Parse(dlgJson) : new JArray();

                    var condJson = ReadText(reader["conditions"]);
                    if (!string.IsNullOrEmpty(condJson))
                    {
                        try { scene.conditions = JToken.Parse(condJson); } catch { }
                    }

                    var effectsJson = ReadText(reader["effects"]);
                    if (!string.IsNullOrEmpty(effectsJson))
                    {
                        try { scene.effects = JToken.Parse(effectsJson); } catch { }
                    }

                    scene.triggerEvent = ReadText(reader["trigger_event"]);

                    var priorityRaw = reader["priority"];
                    if (priorityRaw != null && priorityRaw != DBNull.Value)
                    {
                        try { scene.priority = Convert.ToInt32(priorityRaw); } catch { scene.priority = 0; }
                    }

                    scene.onceKey = ReadText(reader["once_key"]);

                    var hiddenRaw = reader["hiden"];
                    if (hiddenRaw != null && hiddenRaw != DBNull.Value)
                    {
                        try { scene.hidden = Convert.ToBoolean(hiddenRaw); } catch { scene.hidden = false; }
                    }

                    _sceneCache[sceneName] = scene;
                }
            }
        }

        private void LoadActionBindings(SqliteConnection connection)
        {
            if (!TableExists(connection, "binding_act")) return;

            const string sql = "SELECT act_name, func_name, act_type, act_description, act_args FROM binding_act";
            using (var command = new SqliteCommand(sql, connection))
            using (var reader = command.ExecuteReader())
            {
                while (reader.Read())
                {
                    var actName = ReadText(reader["act_name"]).Trim();
                    var functionName = ReadText(reader["func_name"]).Trim();
                    if (string.IsNullOrEmpty(actName) || string.IsNullOrEmpty(functionName)) continue;

                    var argsJson = ReadText(reader["act_args"]);
                    JObject argsSchema = null;
                    if (!string.IsNullOrWhiteSpace(argsJson))
                    {
                        try { argsSchema = JObject.Parse(argsJson); } catch { }
                    }

                    _actionBindings[actName] = new ActionBindingData
                    {
                        actName = actName,
                        functionName = functionName,
                        actionType = ReadText(reader["act_type"]),
                        description = ReadText(reader["act_description"]),
                        argsSchema = argsSchema,
                    };
                }
            }
        }

        private void LoadRegistries(SqliteConnection connection)
        {
            if (!TableExists(connection, "registry")) return;

            const string sql = "SELECT name, value FROM registry";
            using (var command = new SqliteCommand(sql, connection))
            using (var reader = command.ExecuteReader())
            {
                while (reader.Read())
                {
                    var name = ReadText(reader["name"]).Trim();
                    if (string.IsNullOrEmpty(name)) continue;

                    var valueJson = ReadText(reader["value"]);
                    JArray values = null;
                    if (!string.IsNullOrWhiteSpace(valueJson))
                    {
                        try { values = JArray.Parse(valueJson); } catch { }
                    }

                    _registries[name] = new RegistryData
                    {
                        name = name,
                        values = values ?? new JArray(),
                    };
                }
            }
        }

        private static bool TableExists(SqliteConnection connection, string tableName)
        {
            using (var command = new SqliteCommand("SELECT name FROM sqlite_master WHERE type='table' AND name=@name LIMIT 1", connection))
            {
                command.Parameters.AddWithValue("@name", tableName);
                return command.ExecuteScalar() != null;
            }
        }

        private static string ReadText(object value)
        {
            if (value == null || value == DBNull.Value) return string.Empty;
            if (value is byte[] bytes) return Encoding.UTF8.GetString(bytes);
            return value.ToString() ?? string.Empty;
        }

        public SceneData GetScene(string sceneName)
        {
            if (_sceneCache.TryGetValue(sceneName, out var scene)) return scene;
            Debug.LogWarning($"SparkArc: 找不到场景: {sceneName}");
            return null;
        }

        public List<string> GetAllSceneNames()
        {
            return new List<string>(_sceneCache.Keys);
        }

        public bool TryGetActionBinding(string actName, out ActionBindingData binding)
        {
            if (string.IsNullOrWhiteSpace(actName))
            {
                binding = null;
                return false;
            }
            return _actionBindings.TryGetValue(actName.Trim(), out binding);
        }

        public IReadOnlyDictionary<string, ActionBindingData> GetActionBindings()
        {
            return _actionBindings;
        }

        public bool TryGetRegistry(string name, out RegistryData registry)
        {
            if (string.IsNullOrWhiteSpace(name))
            {
                registry = null;
                return false;
            }
            return _registries.TryGetValue(name.Trim(), out registry);
        }

        public string ResolveRegistryTokens(string value)
        {
            if (string.IsNullOrEmpty(value) || _registries.Count == 0) return value ?? string.Empty;

            var result = value;
            foreach (var item in _registries)
            {
                var replacement = GetRegistryDefaultText(item.Value);
                result = result.Replace("{" + item.Key + "}", replacement);
            }
            return result;
        }

        public string[] ResolveRegistryTokens(string[] values)
        {
            if (values == null) return Array.Empty<string>();
            var resolved = new string[values.Length];
            for (var i = 0; i < values.Length; i++)
            {
                resolved[i] = ResolveRegistryTokens(values[i]);
            }
            return resolved;
        }

        private static string GetRegistryDefaultText(RegistryData registry)
        {
            if (registry == null || registry.values == null || registry.values.Count == 0) return string.Empty;
            var first = registry.values[0];
            return first == null || first.Type == JTokenType.Null ? string.Empty : first.ToString();
        }

        /// <summary>
        /// 从当前数据库加载角色列表
        /// </summary>
        public Dictionary<int, string> LoadCharacters()
        {
            if (string.IsNullOrEmpty(_dbPath))
            {
                #if UNITY_EDITOR || UNITY_STANDALONE
                _dbPath = Path.Combine(Application.streamingAssetsPath, dbFileName);
                #elif UNITY_ANDROID
                _dbPath = Path.Combine(Application.persistentDataPath, dbFileName);
                #endif
            }
            return LoadCharactersFromPath(_dbPath);
        }

        /// <summary>
        /// 静态辅助方法：从指定数据库路径加载角色
        /// </summary>
        public static Dictionary<int, string> LoadCharactersFromPath(string dbPath)
        {
            var characters = new Dictionary<int, string>();
            
            if (!File.Exists(dbPath))
            {
                Debug.LogError($"SparkArc: 数据库文件未找到: {dbPath}");
                return characters;
            }

            try
            {
                using (var connection = new SqliteConnection($"Data Source={dbPath};Version=3;"))
                {
                    connection.Open();
                    // 优先读取 characters 表
                    const string sql = "SELECT character_id, name FROM characters";
                    
                    using (var command = new SqliteCommand(sql, connection))
                    using (var reader = command.ExecuteReader())
                    {
                        while (reader.Read())
                        {
                            int id = Convert.ToInt32(reader["character_id"]);
                            string name = reader["name"]?.ToString() ?? "Unknown";
                            if (!characters.ContainsKey(id))
                            {
                                characters.Add(id, name);
                            }
                        }
                    }
                }
            }
            catch (Exception ex)
            {
                Debug.LogError($"SparkArc: 加载角色失败: {ex.Message}");
            }
            
            return characters;
        }
    }
}
