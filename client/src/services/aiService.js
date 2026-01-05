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

// ==================== Model Management ====================

/**
 * 添加自定义模型
 * @param {number} platformId - 平台 ID
 * @param {string} modelName - 模型标识 (API 使用的名称)
 * @param {string} displayName - 显示名称
 * @param {string|null} extraBody - extra_body JSON 字符串 (可选)
 */
export async function createModel(platformId, modelName, displayName, extraBody = null) {
  const response = await fetchWithAuth('/api/ai/model', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      platform_id: platformId,
      model_name: modelName,
      display_name: displayName,
      extra_body: extraBody
    }),
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.detail || result.error || '添加模型失败');
  invalidatePlatformsModelsCache();
  return result;
}

/**
 * 更新模型 (显示名称和 extra_body)
 * @param {number} modelId - 模型 ID
 * @param {string|null} displayName - 新的显示名称 (可选)
 * @param {string|null} extraBody - extra_body JSON 字符串 (可选)
 */
export async function updateModel(modelId, displayName = null, extraBody = null) {
  const response = await fetchWithAuth('/api/ai/model', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      id: modelId,
      display_name: displayName,
      extra_body: extraBody
    }),
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.detail || result.error || '更新模型失败');
  invalidatePlatformsModelsCache();
  return result;
}

/**
 * 删除模型
 * @param {number} modelId - 模型 ID
 */
export async function deleteModel(modelId) {
  const response = await fetchWithAuth(`/api/ai/model?id=${modelId}`, {
    method: 'DELETE',
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.detail || result.error || '删除模型失败');
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

  const contentType = (response.headers.get('content-type') || '').toLowerCase();

  if (!response.ok) {
    let errorMsg = '文风分析失败';
    try {
      const result = await response.json();
      errorMsg = result.error || errorMsg;
    } catch (e) { }
    throw new Error(errorMsg);
  }

  // SSE is required here; if the backend/proxy returns HTML/JSON, surface it clearly.
  if (!contentType.includes('text/event-stream')) {
    let details = '';
    try {
      details = await response.text();
    } catch (e) {}
    throw new Error(`服务未返回事件流 (content-type: ${contentType || 'unknown'})${details ? `: ${details.slice(0, 200)}` : ''}`);
  }

  if (!response.body) {
    throw new Error('浏览器不支持流式响应 (response.body 为空)');
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let finalProfile = null;

  const processEventBlock = (block) => {
    // An SSE "event" is separated by a blank line.
    // We only care about all `data:` lines.
    const lines = block.split(/\r?\n/);
    const dataLines = [];

    for (const rawLine of lines) {
      const line = rawLine.trimEnd();
      if (!line) continue;
      // Accept both `data:xxx` and `data: xxx`
      if (line.startsWith('data:')) {
        dataLines.push(line.slice(5).replace(/^\s*/, ''));
      }
    }

    if (dataLines.length === 0) return;

    const payload = dataLines.join('\n');
    let data;
    try {
      data = JSON.parse(payload);
    } catch (e) {
      // If backend ever sends non-JSON, keep it visible.
      throw new Error(`无法解析事件流数据: ${payload.slice(0, 200)}`);
    }

    if (onProgress) onProgress(data);

    if (data.step === 'error') {
      throw new Error(data.message || '文风分析失败');
    }

    if (data.style_profile) {
      finalProfile = data.style_profile;
    }
  };

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });

    // Split by blank line (supports \n\n and \r\n\r\n)
    const parts = buffer.split(/\r?\n\r?\n/);
    buffer = parts.pop() || '';

    for (const block of parts) {
      if (!block.trim()) continue;
      processEventBlock(block);
    }
  }

  // Flush remaining buffer
  if (buffer.trim()) {
    processEventBlock(buffer);
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
export async function igniteMuse(projectName, inspiration, options = {}) {
  const { style, genres, tones, worldviews, lengthHint } = options;
  const response = await fetchWithAuth('/api/ai/muse', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      projectName,
      inspiration,
      style: style || null,
      genres: genres || null,
      tones: tones || null,
      worldviews: worldviews || null,
      lengthHint: lengthHint || null
    }),
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
  await fetchWithAuth('/api/synopsis', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ projectName, synopsis }),
  });
}

export async function generateSynopsis(projectName, logline, guidance, styleProfile = null) {
  const response = await fetchWithAuth('/api/ai/synopsis', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ projectName, logline, guidance, style_profile: styleProfile }),
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

export async function generateBeatSheet(projectName, synopsis, guidance, styleProfile = null) {
  const response = await fetchWithAuth('/api/ai/beat-sheet', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ projectName, synopsis, guidance, style_profile: styleProfile }),
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
      style_profile: options.styleProfile || null,
    }),
  });
  const result = await response.json();
  if (!response.ok || result.success === false) throw new Error(result.error || '生成大纲失败');
  return result.outline;
}
