import { fetchWithAuth } from './apiClient';
import { consumeSSEReader, parseSSEEventPayload } from '@/utils/streamingRuntime';

async function fetchSSEAndGetResult(url, body, options = {}) {
  const response = await fetchWithAuth(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal: options.signal,
  });

  if (!response.ok) {
    let errorMsg = '请求失败';
    try {
      const result = await response.json();
      errorMsg = result.error || errorMsg;
    } catch (e) { }
    throw new Error(errorMsg);
  }

  let finalResult = null;
  await consumeSSEReader(response.body.getReader(), {
    signal: options.signal,
    onEvent: async (evt) => {
      const data = parseSSEEventPayload(evt?.data || '');
      if (evt?.event === 'done') {
        finalResult = data;
        return;
      }
      if (evt?.event === 'error') {
        throw new Error(data.error || data.message || data.raw || 'Stream Error');
      }
    },
  });

  if (!finalResult) {
    // If stream ended without 'done' but also no error, check if we might have missed it or it's empty
    // But since we control the backend, we expect 'done' event.
    // However, if the connection closed early?
    throw new Error("连接断开或未收到结果");
  }

  return finalResult;
}

// --- 文件与项目操作 ---
export async function fetchFileTree(projectName) {
  const response = await fetchWithAuth(`/api/story-files/${projectName}`);
  if (!response.ok) throw new Error('无法加载文件树');
  return await response.json();
}

export async function fetchStoryFile(projectName, filePath) {
  const encoded = String(filePath).split('/').map(encodeURIComponent).join('/');
  const response = await fetchWithAuth(`/api/file-content/${encodeURIComponent(projectName)}/${encoded}`);
  if (!response.ok) throw new Error('无法加载剧本文件');
  return await response.json();
}

export async function saveStory(projectName, filename, data) {
  const response = await fetchWithAuth('/api/save-story', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ projectName, filename, data }),
  });
  const result = await response.json();
  if (!response.ok || result.success === false) throw new Error(result.message || '保存失败');
  return result;
}

// 上传剧本文件到当前项目 stories 目录
export async function uploadStory(projectName, file) {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('projectName', projectName);

  const response = await fetchWithAuth('/api/upload-story', {
    method: 'POST',
    body: formData,
  });
  const result = await response.json();
  if (!response.ok || result.success === false) {
    throw new Error(result.message || '上传失败');
  }
  return result;
}

export async function createFileOrFolder(projectName, type, path) {
  const response = await fetchWithAuth('/api/file-operations/create', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ projectName, type, path }),
  });
  if (!response.ok) {
    const result = await response.json();
    throw new Error(result.message || '创建失败');
  }
  return await response.json();
}

export async function deleteFileOrFolder(projectName, path) {
  const response = await fetchWithAuth('/api/file-operations/delete', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ projectName, path }),
  });
  if (!response.ok) {
    const result = await response.json();
    throw new Error(result.message || '删除失败');
  }
  return await response.json();
}

export async function renameFileOrFolder(projectName, oldPath, newPath) {
  const response = await fetchWithAuth('/api/file-operations/rename', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ projectName, oldPath, newPath }),
  });
  if (!response.ok) {
    const result = await response.json();
    throw new Error(result.message || '重命名失败');
  }
  return await response.json();
}

export async function moveFileOrFolder(projectName, sourcePath, targetPath) {
  const response = await fetchWithAuth('/api/file-operations/move', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ projectName, sourcePath, targetPath }),
  });
  const result = await response.json();
  if (!response.ok || result.success === false) {
    throw new Error(result.message || '移动失败');
  }
  return result;
}

export async function saveStoriesOrder(projectName, dirPath, order) {
  const response = await fetchWithAuth('/api/file-operations/save-order', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ projectName, dirPath, order }),
  });
  const result = await response.json();
  if (!response.ok || result.success === false) {
    throw new Error(result.message || '保存排序失败');
  }
  return result;
}

// --- 角色、蓝图、绑定、注册表 ---

/**
 * 获取角色列表
 * @param {string} projectName - 项目名称
 * @param {boolean} includeContent - 是否包含角色设定内容（编辑器用）
 * @returns {Promise<Array>} 角色数组 [{id, name, desc, content?}]
 */
export async function fetchCharacters(projectName, includeContent = false) {
  if (!projectName) return [];
  let url = `/api/characters?projectName=${encodeURIComponent(projectName)}`;
  if (includeContent) url += '&includeContent=true';

  const response = await fetchWithAuth(url);
  if (!response.ok) return [];

  const result = await response.json();
  // 后端直接返回数组
  return Array.isArray(result) ? result : [];
}

/**
 * 创建新角色
 */
export async function createCharacter(projectName, name) {
  const response = await fetchWithAuth('/api/characters', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ projectName, name }),
  });
  const result = await response.json();
  if (!response.ok || result.success === false) {
    throw new Error(result.error || result.message || '创建角色失败');
  }
  return result;
}

/**
 * 保存角色设定内容
 */
export async function saveCharacter(projectName, id, content) {
  const response = await fetchWithAuth('/api/characters', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ projectName, id, content }),
  });
  const result = await response.json();
  if (!response.ok || result.success === false) {
    throw new Error(result.error || result.message || '保存角色失败');
  }
  return result;
}

/**
 * 重命名角色
 */
export async function renameCharacter(projectName, id, newName) {
  const response = await fetchWithAuth('/api/characters/rename', {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ projectName, id, newName }),
  });
  const result = await response.json();
  if (!response.ok || result.success === false) {
    throw new Error(result.error || result.message || '重命名角色失败');
  }
  return result;
}

/**
 * 删除角色
 */
export async function deleteCharacter(projectName, id) {
  const response = await fetchWithAuth(
    `/api/characters?projectName=${encodeURIComponent(projectName)}&id=${id}`,
    { method: 'DELETE' }
  );
  const result = await response.json();
  if (!response.ok || result.success === false) {
    throw new Error(result.error || result.message || '删除角色失败');
  }
  return result;
}

export async function fetchBlueprint(projectName) {
  const response = await fetchWithAuth(`/api/blueprint/${encodeURIComponent(projectName)}`);
  if (!response.ok) {
    if (response.status === 404) return {};
    throw new Error('无法加载蓝图数据');
  }
  return await response.json();
}

export async function saveBlueprint(projectName, data) {
  const response = await fetchWithAuth(`/api/blueprint/${encodeURIComponent(projectName)}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  const result = await response.json();
  if (!response.ok || result.success === false) throw new Error(result.message || '保存蓝图失败');
  return result;
}

export async function fetchBindings(projectName) {
  const response = await fetchWithAuth(`/api/bindings/${encodeURIComponent(projectName)}`);
  return response.ok ? await response.json() : [];
}

export async function saveBindings(projectName, data) {
  const response = await fetchWithAuth(`/api/bindings/${encodeURIComponent(projectName)}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  return await response.json();
}

export async function fetchActionBindings(projectName) {
  const response = await fetchWithAuth(`/api/action-bindings/${encodeURIComponent(projectName)}`);
  return response.ok ? await response.json() : [];
}

export async function saveActionBindings(projectName, data) {
  const response = await fetchWithAuth(`/api/action-bindings/${encodeURIComponent(projectName)}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  const result = await response.json();
  if (!response.ok || result.success === false) throw new Error(result.message || '保存行为函数绑定失败');
  return result;
}

export async function fetchRegistries(projectName) {
  const response = await fetchWithAuth(`/api/registries/${encodeURIComponent(projectName)}`);
  return response.ok ? await response.json() : [];
}

export async function saveRegistries(projectName, data) {
  const response = await fetchWithAuth(`/api/registries/${encodeURIComponent(projectName)}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  const result = await response.json();
  if (!response.ok || result.success === false) throw new Error(result.message || '保存注册表失败');
  return result;
}

// --- 历史记录 ---
export async function getOutlineHistory(projectName) {
  const response = await fetchWithAuth(`/api/history/outline/${encodeURIComponent(projectName)}`);
  const result = await response.json();
  if (!response.ok || result.success === false) throw new Error(result.error || '获取历史失败');
  return result.history;
}

export async function deleteOutlineHistory(projectName, entryId) {
  const response = await fetchWithAuth(`/api/history/outline/${encodeURIComponent(projectName)}/${entryId}`, {
    method: 'DELETE',
  });
  const result = await response.json();
  if (!response.ok || result.success === false) throw new Error(result.error || '删除历史失败');
  return result;
}

export async function restoreOutlineFromHistory(projectName, entryId) {
  const response = await fetchWithAuth(`/api/history/outline/${encodeURIComponent(projectName)}/${entryId}/restore`, {
    method: 'POST',
  });
  const result = await response.json();
  if (!response.ok || result.success === false) throw new Error(result.error || '恢复失败');
  return result.outline;
}

// --- 全局灵感系统 (用户级别，非项目级别) ---

/**
 * 获取所有灵感（全局）
 * @returns {Promise<{inspirations: Array, unread_count: number}>}
 */
export async function getInspirations() {
  const response = await fetchWithAuth('/api/inspirations');
  const result = await response.json();
  if (!response.ok || result.success === false) throw new Error(result.error || '获取灵感失败');
  return { inspirations: result.inspirations, unreadCount: result.unread_count };
}

/**
 * 获取未读灵感数量
 */
export async function getInspirationUnreadCount() {
  const response = await fetchWithAuth('/api/inspirations/unread-count');
  const result = await response.json();
  if (!response.ok || result.success === false) throw new Error(result.error || '获取未读数失败');
  return result.count;
}

/**
 * 创建新灵感
 * @param {string} source - 灵感原始文本
 * @param {string} content - 扩展内容（可选）
 * @param {Object} tags - 四维标签 {styles, genres, tones, worldviews}
 */
export async function createInspiration(source, content = '', tags = null) {
  const response = await fetchWithAuth('/api/inspirations', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ source, content, tags }),
  });
  const result = await response.json();
  if (!response.ok || result.success === false) throw new Error(result.error || '创建灵感失败');
  return result;
}

/**
 * 更新灵感
 * @param {string} entryId - 灵感ID
 * @param {Object} updates - {content?, tags?, status?}
 */
export async function updateInspiration(entryId, updates) {
  const response = await fetchWithAuth(`/api/inspirations/${entryId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(updates),
  });
  const result = await response.json();
  if (!response.ok || result.success === false) throw new Error(result.error || '更新灵感失败');
  return result;
}

/**
 * 标记灵感为已读
 */
export async function markInspirationRead(entryId) {
  const response = await fetchWithAuth(`/api/inspirations/${entryId}/read`, {
    method: 'POST',
  });
  const result = await response.json();
  if (!response.ok || result.success === false) throw new Error(result.error || '标记已读失败');
  return result;
}

/**
 * 删除灵感
 */
export async function deleteInspiration(entryId) {
  const response = await fetchWithAuth(`/api/inspirations/${entryId}`, {
    method: 'DELETE',
  });
  const result = await response.json();
  if (!response.ok || result.success === false) throw new Error(result.error || '删除失败');
  return result;
}


export async function getOutline(projectName) {
  const response = await fetchWithAuth(`/api/outline/${encodeURIComponent(projectName)}`);
  const result = await response.json();
  if (!response.ok || result.success === false) throw new Error(result.error || '获取大纲失败');
  return result.outline;
}

export async function saveOutline(projectName, outline, saveToHistory = false) {
  const response = await fetchWithAuth(`/api/outline/${encodeURIComponent(projectName)}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ outline, saveToHistory }),
  });
  const result = await response.json();
  if (!response.ok || result.success === false) throw new Error(result.error || '保存大纲失败');
  return result;
}

export async function exportOutlineToFiles(projectName, options = {}) {
  const response = await fetchWithAuth(`/api/outline/${encodeURIComponent(projectName)}/export-to-files`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(options),
  });
  const result = await response.json();
  if (response.status === 409) return { success: false, error: 'CONFLICT', existing: result.existing };
  if (!response.ok || result.success === false) throw new Error(result.error || '导出失败');
  return result;
}

// --- 文风与衔接 ---
export async function getStyleProfile(projectName, styleName) {
  let url = '/api/ai/style-profile?';
  if (styleName) url += `styleName=${encodeURIComponent(styleName)}`;
  else if (projectName) url += `projectName=${encodeURIComponent(projectName)}`;

  const response = await fetchWithAuth(url);
  if (!response.ok) return response.status === 404 ? null : { error: true };
  const result = await response.json();
  return result.style_profile;
}

export async function generateBridge(projectName, prevScene, nextScene, options = {}) {
  const result = await fetchSSEAndGetResult('/api/scriptwriter/compose/stream', {
    operation: 'bridge',
    mode: 'bridge',
    projectName,
    prevScene,
    nextScene,
    pacing: options.pacing || 'Normal',
    mood: options.mood,
    guidance: options.guidance,
    characters: options.characters
  }, options);
  return result.dialogues || result.transition || [];
}
