using System;
using System.Data.SQLite;
using System.IO;
using Newtonsoft.Json.Linq;

namespace DialogSystem.Services
{
    /// <summary>
    /// 统一管理故事数据的加载逻辑，便于在 UI 与对话引擎之间复用同一份数据源。
        public class StoryRepository
        {
            public string DefaultDatabasePath { get; }
            public string CurrentSourceLabel { get; private set; }
            public JArray JsonSource { get; private set; }
    
            public StoryRepository()
            {
                var baseDir = AppDomain.CurrentDomain.BaseDirectory;
                DefaultDatabasePath = Path.Combine(baseDir, "stories.db");
            }
        public bool LoadDefaultSource(out string errorMessage)
        {
            // 默认仅尝试从 SQLite 加载，不再支持旧版 .story 文件
            if (LoadFromSqlite(DefaultDatabasePath, out errorMessage))
                return true;

            if (string.IsNullOrEmpty(errorMessage))
                errorMessage = "未找到默认数据源 (stories.db)。";
            return false;
        }

        public bool LoadFromSqlite(string path, out string errorMessage)
        {
            errorMessage = null;
            if (string.IsNullOrWhiteSpace(path) || !File.Exists(path))
            {
                errorMessage = $"未找到 SQLite 文件: {path}";
                return false;
            }

            try
            {
                var scenes = new JArray();
                using (var connection = new SQLiteConnection($"Data Source={path};Version=3;Read Only=True;"))
                {
                    connection.Open();
                    const string sql = "SELECT chapter, scene_name, guide, intro, button_text, conditions, effects, trigger_event, priority, once_key, dlg_json, hiden, progress, id FROM stories ORDER BY chapter ASC, progress ASC, id ASC";
                    using (var command = new SQLiteCommand(sql, connection))
                    using (var reader = command.ExecuteReader())
                    {
                        var sceneNameOrdinal = reader.GetOrdinal("scene_name");
                        var guideOrdinal = reader.GetOrdinal("guide");
                        var introOrdinal = reader.GetOrdinal("intro");
                        var buttonOrdinal = reader.GetOrdinal("button_text");
                        var condOrdinal = reader.GetOrdinal("conditions");
                        var effectsOrdinal = reader.GetOrdinal("effects");
                        var triggerEventOrdinal = reader.GetOrdinal("trigger_event");
                        var priorityOrdinal = reader.GetOrdinal("priority");
                        var onceKeyOrdinal = reader.GetOrdinal("once_key");
                        var dlgOrdinal = reader.GetOrdinal("dlg_json");
                        var hiddenOrdinal = reader.GetOrdinal("hiden");

                        while (reader.Read())
                        {
                            var sceneName = reader.IsDBNull(sceneNameOrdinal) ? string.Empty : reader.GetString(sceneNameOrdinal);
                            if (string.IsNullOrWhiteSpace(sceneName))
                            {
                                var chapterValue = reader["chapter"]?.ToString() ?? "0";
                                sceneName = $"Chapter_{chapterValue}_{scenes.Count + 1}";
                            }

                            var scene = new JObject
                            {
                                ["scene"] = sceneName,
                                ["guide"] = reader.IsDBNull(guideOrdinal) ? string.Empty : reader.GetString(guideOrdinal),
                            };

                            var dialogJson = reader.IsDBNull(dlgOrdinal) ? null : reader.GetString(dlgOrdinal);
                            if (!string.IsNullOrWhiteSpace(dialogJson))
                            {
                                try { scene["dia"] = JArray.Parse(dialogJson); }
                                catch { scene["dia"] = new JArray(); }
                            }
                            else
                            {
                                scene["dia"] = new JArray();
                            }

                            if (!reader.IsDBNull(introOrdinal))
                            {
                                var intro = reader.GetString(introOrdinal);
                                if (!string.IsNullOrWhiteSpace(intro))
                                    scene["intro"] = intro;
                            }

                            if (!reader.IsDBNull(buttonOrdinal))
                            {
                                var btn = reader.GetString(buttonOrdinal);
                                if (!string.IsNullOrWhiteSpace(btn))
                                    scene["button_text"] = btn;
                            }

                            if (!reader.IsDBNull(condOrdinal))
                            {
                                var condText = reader.GetString(condOrdinal);
                                if (!string.IsNullOrWhiteSpace(condText))
                                {
                                    try { scene["conditions"] = JToken.Parse(condText); }
                                    catch { }
                                }
                            }

                            if (!reader.IsDBNull(effectsOrdinal))
                            {
                                var effectsText = reader.GetString(effectsOrdinal);
                                if (!string.IsNullOrWhiteSpace(effectsText))
                                {
                                    try { scene["effects"] = JToken.Parse(effectsText); }
                                    catch { }
                                }
                            }

                            if (!reader.IsDBNull(triggerEventOrdinal))
                            {
                                var triggerEvent = reader.GetString(triggerEventOrdinal);
                                if (!string.IsNullOrWhiteSpace(triggerEvent))
                                    scene["trigger_event"] = triggerEvent;
                            }

                            if (!reader.IsDBNull(priorityOrdinal))
                            {
                                scene["priority"] = reader.GetInt32(priorityOrdinal);
                            }

                            if (!reader.IsDBNull(onceKeyOrdinal))
                            {
                                var onceKey = reader.GetString(onceKeyOrdinal);
                                if (!string.IsNullOrWhiteSpace(onceKey))
                                    scene["once_key"] = onceKey;
                            }

                            if (hiddenOrdinal >= 0 && !reader.IsDBNull(hiddenOrdinal))
                            {
                                var hiddenValue = reader.GetValue(hiddenOrdinal);
                                scene["hiden"] = Convert.ToBoolean(hiddenValue);
                            }

                            scenes.Add(scene);
                        }
                    }
                }

                if (scenes.Count == 0)
                {
                    errorMessage = "SQLite 数据库中没有任何场景。";
                    return false;
                }

                JsonSource = scenes;
                CurrentSourceLabel = $"SQLite: {Path.GetFileName(path)}";
                return true;
            }
            catch (Exception ex)
            {
                errorMessage = $"读取 SQLite 失败: {ex.Message}";
                return false;
            }
        }

        public JObject GetSceneObj(string sceneName)
        {
            if (JsonSource == null || string.IsNullOrWhiteSpace(sceneName))
                return null;

            foreach (var obj in JsonSource)
            {
                if (obj["scene"] != null && obj["scene"].ToString() == sceneName)
                    return obj as JObject;
            }
            return null;
        }
    }
}
