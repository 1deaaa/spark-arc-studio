using System;
using System.Collections.Generic;
using System.IO;
using UnityEngine;
using Newtonsoft.Json.Linq;
using System.Data;
using Mono.Data.Sqlite;

namespace SparkArc.Unity
{
    public struct CharacterData
    {
        public int id;
        public string name;
    }

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
                    const string sql = "SELECT chapter, scene_name, caption, button_text, conditions, dlg_json FROM stories ORDER BY chapter ASC, progress ASC, id ASC";
                    
                    using (var command = new SqliteCommand(sql, connection))
                    using (var reader = command.ExecuteReader())
                    {
                        while (reader.Read())
                        {
                            var sceneName = reader["scene_name"]?.ToString();
                            if (string.IsNullOrEmpty(sceneName))
                            {
                                sceneName = $"Chapter_{reader["chapter"]}_{_sceneCache.Count + 1}";
                            }

                            var scene = new SceneData
                            {
                                sceneName = sceneName,
                                guide = reader["caption"]?.ToString() ?? "",
                                buttonText = reader["button_text"]?.ToString() ?? "",
                            };

                            var dlgJson = reader["dlg_json"]?.ToString();
                            scene.dialogues = !string.IsNullOrEmpty(dlgJson) ? JArray.Parse(dlgJson) : new JArray();

                            var condJson = reader["conditions"]?.ToString();
                            if (!string.IsNullOrEmpty(condJson))
                            {
                                try { scene.conditions = JToken.Parse(condJson); } catch { }
                            }

                            _sceneCache[sceneName] = scene;
                        }
                    }
                }
                Debug.Log($"SparkArc: 成功加载 {_sceneCache.Count} 个场景");
            }
            catch (Exception ex)
            {
                Debug.LogError($"SparkArc: 加载数据库失败: {ex.Message}");
            }
        }

        public List<CharacterData> LoadCharacters()
        {
            var list = new List<CharacterData>();
            if (!File.Exists(_dbPath)) return list;

            string connectionString = $"Data Source={_dbPath};Version=3;";
            try
            {
                using (var connection = new SqliteConnection(connectionString))
                {
                    connection.Open();
                    // 检查表是否存在
                    using (var cmd = new SqliteCommand("SELECT name FROM sqlite_master WHERE type='table' AND name='characters';", connection))
                    {
                        var tableName = cmd.ExecuteScalar();
                        if (tableName == null) return list;
                    }

                    const string sql = "SELECT character_id, name FROM characters";
                    using (var command = new SqliteCommand(sql, connection))
                    using (var reader = command.ExecuteReader())
                    {
                        while (reader.Read())
                        {
                            list.Add(new CharacterData
                            {
                                id = Convert.ToInt32(reader["character_id"]),
                                name = reader["name"]?.ToString()
                            });
                        }
                    }
                }
            }
            catch (Exception ex)
            {
                Debug.LogError($"SparkArc: 加载角色失败: {ex.Message}");
            }
            return list;
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
    }
}
