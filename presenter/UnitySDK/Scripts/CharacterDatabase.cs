using System.Collections.Generic;
using UnityEngine;
using System;
#if UNITY_EDITOR
using UnityEditor;
#endif

namespace SparkArc.Unity
{
    /// <summary>
    /// 角色数据库，将 ID 映射为名称
    /// </summary>
    [CreateAssetMenu(fileName = "CharacterDatabase", menuName = "SparkArc/Character Database")]
    public class CharacterDatabase : ScriptableObject
    {
        [Serializable]
        public struct CharacterInfo
        {
            public int id;
            public string name;
            public Sprite portrait; // 可选：角色头像
        }

        public List<CharacterInfo> characters = new List<CharacterInfo>();

        public string GetCharacterName(int id)
        {
            var charInfo = characters.Find(c => c.id == id);
            return string.IsNullOrEmpty(charInfo.name) ? "???" : charInfo.name;
        }

        public Sprite GetCharacterPortrait(int id)
        {
            return characters.Find(c => c.id == id).portrait;
        }

        [ContextMenu("Load From DB")]
        public void LoadFromDatabase()
        {
            Dictionary<int, string> loadedChars = null;

            if (Application.isPlaying)
            {
                if (StoryRepository.Instance != null)
                {
                    loadedChars = StoryRepository.Instance.LoadCharacters();
                }
            }
            else
            {
                // Editor 模式下手动构建路径
                string dbPath = System.IO.Path.Combine(Application.streamingAssetsPath, "stories.db");
                loadedChars = StoryRepository.LoadCharactersFromPath(dbPath);
            }

            if (loadedChars == null || loadedChars.Count == 0)
            {
                Debug.LogWarning("SparkArc: 未从数据库加载到任何角色数据。");
                return;
            }

            // 更新列表，保留现有的 Sprite 引用
            foreach (var kvp in loadedChars)
            {
                int id = kvp.Key;
                string name = kvp.Value;

                int index = characters.FindIndex(c => c.id == id);
                if (index != -1)
                {
                    // 更新名字，保留头像
                    var info = characters[index];
                    info.name = name;
                    characters[index] = info;
                }
                else
                {
                    // 新增角色
                    characters.Add(new CharacterInfo { id = id, name = name });
                }
            }
            
            // 可选：清理已不存在的角色? 
            // 建议保留，防止误删手动配置的特殊角色

            Debug.Log($"SparkArc: 已更新角色列表，当前共 {characters.Count} 个角色。");
            
            #if UNITY_EDITOR
            EditorUtility.SetDirty(this);
            #endif
        }
    }
}
