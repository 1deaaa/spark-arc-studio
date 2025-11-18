using System;
using System.Data.SQLite;
using System.IO;
using Newtonsoft.Json.Linq;

namespace DialogSystem.Services
{
    /// <summary>
    /// 统一管理故事数据的加载逻辑，便于在 UI 与对话引擎之间复用同一份数据源。
    /// </summary>
    public class StoryRepository
    {
        public string DefaultStoryPath { get; }
        public string DefaultDatabasePath { get; }
        public string CurrentSourceLabel { get; private set; }
        public JArray JsonSource { get; private set; }

        public StoryRepository()
        {
            var baseDir = AppDomain.CurrentDomain.BaseDirectory;
            DefaultStoryPath = Path.Combine(baseDir, "测试故事.story");
            DefaultDatabasePath = Path.Combine(baseDir, "stories.db");
        }

        public bool LoadDefaultSource(out string errorMessage)
        {
            if (LoadFromSqlite(DefaultDatabasePath, out errorMessage))
                return true;

            if (LoadFromStoryFile(DefaultStoryPath, out var storyError))
                return true;

            if (!string.IsNullOrEmpty(errorMessage))
                errorMessage += Environment.NewLine;
            errorMessage += storyError;
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
                    const string sql = "SELECT chapter, scene_name, caption, button_text, conditions, dlg_json, hiden, progress, id FROM stories ORDER BY chapter ASC, progress ASC, id ASC";
                    using (var command = new SQLiteCommand(sql, connection))
                    using (var reader = command.ExecuteReader())
                    {
                        var sceneNameOrdinal = reader.GetOrdinal("scene_name");
                        var captionOrdinal = reader.GetOrdinal("caption");
                        var buttonOrdinal = reader.GetOrdinal("button_text");
                        var condOrdinal = reader.GetOrdinal("conditions");
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
                                ["cap"] = reader.IsDBNull(captionOrdinal) ? string.Empty : reader.GetString(captionOrdinal),
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

        public bool LoadFromStoryFile(string path, out string errorMessage)
        {
            errorMessage = null;
            if (string.IsNullOrWhiteSpace(path) || !File.Exists(path))
            {
                errorMessage = $"未找到 Story 文件: {path}";
                return false;
            }

            try
            {
                var raw = File.ReadAllText(path);
                var parsed = JArray.Parse(raw);
                if (parsed == null || parsed.Count == 0)
                {
                    errorMessage = "Story 文件为空。";
                    return false;
                }

                JsonSource = parsed;
                CurrentSourceLabel = $"Story: {Path.GetFileName(path)}";
                return true;
            }
            catch (Exception ex)
            {
                errorMessage = $"读取 Story 文件失败: {ex.Message}";
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
