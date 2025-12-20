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

export async function analyzeStyle(projectName, file) {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('projectName', projectName);
  const response = await fetchWithAuth('/api/ai/style-analyze', { method: 'POST', body: formData });
  const result = await response.json();
  if (!response.ok || result.success === false) throw new Error(result.error || '文风分析失败');
  return result.style_profile;
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

export async function generateOutline(projectName, context, guidance, options = {}) {
  const response = await fetchWithAuth('/api/ai/outline', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      projectName, context, guidance,
      chapterCount: options.chapterCount ?? 5,
      saveToProject: options.saveToProject ?? true,
      saveToHistory: options.saveToHistory ?? true,
    }),
  });
  const result = await response.json();
  if (!response.ok || result.success === false) throw new Error(result.error || '生成大纲失败');
  return result.outline;
}
