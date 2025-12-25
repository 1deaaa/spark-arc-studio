import { fetchWithAuth } from './apiClient';

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
export async function fetchCharacters(projectName) {
  if (!projectName) return [];
  const response = await fetchWithAuth(`/api/characters/${encodeURIComponent(projectName)}`);
  return response.ok ? await response.json() : [];
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

export async function getMuseHistory(projectName) {
  const response = await fetchWithAuth(`/api/history/muse/${encodeURIComponent(projectName)}`);
  const result = await response.json();
  if (!response.ok || result.success === false) throw new Error(result.error || '获取灵感历史失败');
  return result.history;
}

export async function deleteMuseHistory(projectName, entryId) {
  const response = await fetchWithAuth(`/api/history/muse/${encodeURIComponent(projectName)}/${entryId}`, {
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
export async function getStyleProfile(projectName) {
  const response = await fetchWithAuth(`/api/ai/style-profile?projectName=${encodeURIComponent(projectName)}`);
  if (!response.ok) return response.status === 404 ? null : { error: true };
  const result = await response.json();
  return result.style_profile;
}

export async function generateBridge(projectName, prevScene, nextScene, options = {}) {
  const response = await fetchWithAuth('/api/bridge/generate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ projectName, prevScene, nextScene, pacing: options.pacing || 'Normal' }),
  });
  const result = await response.json();
  if (!response.ok || result.success === false) throw new Error(result.error || '生成衔接失败');
  return result.transition;
}
