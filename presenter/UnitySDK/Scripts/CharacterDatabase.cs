using System.Collections.Generic;
using UnityEngine;
using System;

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

        [ContextMenu("Load From DB")]
        public void LoadFromDatabase()
        {
#if UNITY_EDITOR
            if (StoryRepository.Instance == null)
            {
                // 在 Editor 模式下如果没有运行时实例，尝试临时创建一个来读取
                // 但通常 StoryRepository 需要运行时环境。
                // 简单起见，这里假设已经运行，或者直接在运行时点击 ContextMenu。
                // 如果需要在非运行时读取 DB，逻辑会比较复杂（需要单独建立连接）。
                Debug.LogWarning("请在运行时使用此功能，或确保 StoryRepository 已初始化。");
            }
#endif
            if (StoryRepository.Instance != null)
            {
                var loaded = StoryRepository.Instance.LoadCharacters();
                UpdateCharacters(loaded);
            }
        }

        public void UpdateCharacters(List<CharacterData> loadedData)
        {
            // 更新现有条目或添加新条目，保留现有图片引用
            foreach (var data in loadedData)
            {
                int index = characters.FindIndex(c => c.id == data.id);
                if (index >= 0)
                {
                    // 更新名字，保留其他（如 Sprite）
                    var info = characters[index];
                    info.name = data.name;
                    characters[index] = info;
                }
                else
                {
                    characters.Add(new CharacterInfo { id = data.id, name = data.name });
                }
            }
            Debug.Log($"已更新角色数据库，共 {characters.Count} 个角色。");
        }

        public string GetCharacterName(int id)
        {
            var charInfo = characters.Find(c => c.id == id);
            return string.IsNullOrEmpty(charInfo.name) ? "???" : charInfo.name;
        }

        public Sprite GetCharacterPortrait(int id)
        {
            return characters.Find(c => c.id == id).portrait;
        }
    }
}
