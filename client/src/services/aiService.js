import { fetchWithAuth, fetchWithSWR, cache } from './apiClient';

export const invalidatePlatformsModelsCache = () => cache.clear('platforms_models');

export const invalidateUserSelectionCache = (usageKey) => {
  const key = usageKey || 'null';
  cache.clear(`selection_${key}`);
  if (!usageKey) {
    cache.clear('selection_main');
  }
};

export async function fetchUserPlatformsAndModels(options = {}) {
  const { onData, force } = typeof options === 'function' ? { onData: options } : options;
  if (force) invalidatePlatformsModelsCache();
  return fetchWithSWR('/api/ai/user-platforms-models', 'platforms_models', onData);
}

export async function fetchUserSelection(usageKey, options = {}) {
  const { onData, force } = typeof options === 'function' ? { onData: options } : options;
  const key = usageKey || 'null';
  if (force) invalidateUserSelectionCache(usageKey);
  const url = usageKey ? `/api/ai/user-selection?usage_key=${encodeURIComponent(usageKey)}` : '/api/ai/user-selection';
  return fetchWithSWR(url, `selection_${key}`, onData);
}

export async function saveUserSelection(platformId, modelId, usageKey) {
  const response = await fetchWithAuth('/api/ai/user-selection', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ platform_id: platformId, model_id: modelId, usage_key: usageKey }),
  });
  const result = await response.json();
  if (!response.ok || result.success === false) throw new Error(result.error || '保存失败');
  invalidateUserSelectionCache(usageKey);
  return result;
}

export async function createUserUsageSlot(usageKey, usageLabel, platformId, modelId) {
  const response = await fetchWithAuth('/api/ai/user-selection/usage', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ usage_key: usageKey, usage_label: usageLabel, platform_id: platformId, model_id: modelId }),
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || '创建用途失败');
  invalidateUserSelectionCache(null);
  invalidatePlatformsModelsCache();
  return result;
}

export async function deleteUserUsageSlot(usageKey) {
  const response = await fetchWithAuth('/api/ai/user-selection/usage', {
    method: 'DELETE',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ usage_key: usageKey }),
  });
  const result = await response.json();
  if (!response.ok || result.success === false) throw new Error(result.error || '删除失败');
  invalidateUserSelectionCache(null);
  return result;
}

export async function renameUserUsageSlot(usageKey, newUsageKey, newLabel) {
  const response = await fetchWithAuth('/api/ai/user-selection/usage', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ usage_key: usageKey, new_usage_key: newUsageKey, new_usage_label: newLabel }),
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || '编辑用途失败');
  invalidateUserSelectionCache(null);
  invalidatePlatformsModelsCache();
  return result;
}

export async function analyzeStyle(projectName, file, styleName) {
  const formData = new FormData();
  formData.append('file', file);
  if (projectName) formData.append('projectName', projectName);
  if (styleName) formData.append('styleName', styleName);
  
  const response = await fetchWithAuth('/api/ai/style-analyze', { method: 'POST', body: formData });
  const result = await response.json();
  if (!response.ok || result.success === false) throw new Error(result.error || '文风分析失败');
  return result.style_profile;
}

export async function analyzeStyleStream(projectName, file, styleName, onProgress) {
  const formData = new FormData();
  formData.append('file', file);
  if (projectName) formData.append('projectName', projectName);
  if (styleName) formData.append('styleName', styleName);
  
  const response = await fetchWithAuth('/api/ai/style-analyze-stream', { method: 'POST', body: formData });

  if (!response.ok) {
    let errorMsg = '文风分析失败';
    try {
        const result = await response.json();
        errorMsg = result.error || errorMsg;
    } catch (e) {}
    throw new Error(errorMsg);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let finalProfile = null;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop(); // Keep the last incomplete line

    for (const line of lines) {
      if (line.trim() === '') continue;
      if (line.startsWith('data: ')) {
        const dataStr = line.slice(6);
        try {
          // Handle potential double encoding if server sends json string inside json
          // My server code sends: yield {"data": json.dumps(progress)}
          // But SSE format is: data: <content>\n\n
          // Wait, EventSourceResponse handles the formatting.
          // If I yield {"data": ...}, EventSourceResponse might format it as `data: ...`
          // Let's check how EventSourceResponse works.
          // Usually it expects a generator yielding strings or dicts.
          // If dict, it converts to SSE format.
          // If I yield {"data": json_str}, it will output `data: json_str\n\n`
          
          const data = JSON.parse(dataStr);
          if (onProgress) onProgress(data);
          
          if (data.style_profile) {
              finalProfile = data.style_profile;
          }
        } catch (e) {
          console.error('Failed to parse SSE data', e);
        }
      }
    }
  }
  
  return finalProfile;
}

export async function getStyles() {
  const response = await fetchWithAuth('/api/ai/styles');
  const result = await response.json();
  if (!response.ok || result.success === false) throw new Error(result.error || '获取风格列表失败');
  return result.styles;
}

export async function deleteStyle(styleName) {
  const response = await fetchWithAuth(`/api/ai/styles/${encodeURIComponent(styleName)}`, { method: 'DELETE' });
  const result = await response.json();
  if (!response.ok || result.success === false) throw new Error(result.error || '删除风格失败');
  return result;
}

export async function applyStyle(styleName, projectName) {
  const response = await fetchWithAuth('/api/ai/style-apply', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ styleName, projectName }),
  });
  const result = await response.json();
  if (!response.ok || result.success === false) throw new Error(result.error || '应用风格失败');
  return result;
}

export async function refreshPlatformsAndModels() {
  invalidatePlatformsModelsCache();
  return fetchUserPlatformsAndModels({ force: true });
}

export async function refreshUserSelection(usageKey) {
  invalidateUserSelectionCache(usageKey);
  return fetchUserSelection(usageKey, { force: true });
}

// AI Agent 操作
export async function igniteMuse(projectName, inspiration) {
  const response = await fetchWithAuth('/api/ai/muse', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ projectName, inspiration }),
  });
  if (!response.ok) throw new Error('灵感种子 响应失败');
  return response.body.getReader();
}

export async function fetchSynopsis(projectName) {
  const response = await fetchWithAuth(`/api/synopsis/${projectName}`);
  const result = await response.json();
  return result.synopsis;
}

export async function saveSynopsis(projectName, synopsis) {
  await fetchWithAuth(`/api/synopsis/${projectName}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ synopsis }),
  });
}

export async function generateSynopsis(projectName, logline, guidance) {
  const response = await fetchWithAuth('/api/ai/synopsis', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ projectName, logline, guidance }),
  });
  const result = await response.json();
  if (!response.ok || result.success === false) throw new Error(result.error || '生成梗概失败');
  return result.synopsis;
}

export async function fetchBeatSheet(projectName) {
  const response = await fetchWithAuth(`/api/beat-sheet/${projectName}`);
  const result = await response.json();
  return result.beat_sheet;
}

export async function saveBeatSheet(projectName, beatSheet) {
  await fetchWithAuth('/api/beat-sheet', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ projectName, beatSheet }),
  });
}

export async function generateBeatSheet(projectName, synopsis, guidance) {
  const response = await fetchWithAuth('/api/ai/beat-sheet', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ projectName, synopsis, guidance }),
  });
  const result = await response.json();
  if (!response.ok || result.success === false) throw new Error(result.error || '生成节拍表失败');
  return result.beat_sheet;
}

export async function generateOutline(projectName, context, guidance, options = {}) {
  const response = await fetchWithAuth('/api/ai/outline', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      projectName, context, guidance,
      beatSheet: options.beatSheet,
      chapterCount: options.chapterCount ?? 5,
      saveToProject: options.saveToProject ?? true,
      saveToHistory: options.saveToHistory ?? true,
    }),
  });
  const result = await response.json();
  if (!response.ok || result.success === false) throw new Error(result.error || '生成大纲失败');
  return result.outline;
}
