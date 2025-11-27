// 封装一个带认证的 fetch 请求
async function fetchWithAuth(url, options = {}) {
  // 使用 credentials: 'include' 确保发送和接收 cookies
  const response = await fetch(url, { ...options, credentials: 'include' });
  if (response.status === 401) {
    // 如果认证失败，抛出错误
    throw new Error('认证失败');
  }
  return response;
}

// --- 简单前端内存缓存 ---
// 改为 LocalStorage 持久化缓存 + Stale-While-Revalidate 策略
// 策略：优先返回缓存(通过回调)，同时发起网络请求，若数据有变更则再次回调并更新缓存

function getCacheKey(key) {
  return `spark_cache_${key}`;
}

function loadFromCache(key) {
  try {
    const json = localStorage.getItem(getCacheKey(key));
    if (json) return JSON.parse(json);
  } catch (e) {
    console.warn('Load cache failed', e);
  }
  return null;
}

function saveToCache(key, data) {
  try {
    localStorage.setItem(getCacheKey(key), JSON.stringify(data));
  } catch (e) {
    console.warn('Save cache failed', e);
  }
}

function clearCache(key) {
  try {
    localStorage.removeItem(getCacheKey(key));
  } catch (e) {}
}

function isDifferent(a, b) {
  return JSON.stringify(a) !== JSON.stringify(b);
}

// 通用 SWR 获取函数
// onData: (data) => void. 会被调用 1次(仅网络) 或 2次(缓存+网络更新)
async function _fetchWithSWR(url, cacheKey, onData) {
  // 1. 尝试读取缓存并立即回调
  const cached = loadFromCache(cacheKey);
  if (cached && onData) {
    onData(cached);
  }

  // 2. 发起网络请求
  const response = await fetchWithAuth(url);
  if (!response.ok) {
    throw new Error('网络请求失败');
  }
  const networkData = await response.json();

  // 3. 比较差异，如果有变化（或无缓存）则更新缓存并回调
  if (!cached || isDifferent(cached, networkData)) {
    saveToCache(cacheKey, networkData);
    if (onData) {
      onData(networkData);
    }
  }
  
  return networkData;
}

export function invalidatePlatformsModelsCache() {
  clearCache('platforms_models');
}

export function invalidateUserSelectionCache(usageKey) {
  if (usageKey) {
    clearCache(`selection_${usageKey}`);
  } else {
    // 清除所有 selection 相关的缓存比较麻烦，这里简单处理：
    // 实际业务中通常只用 'main' 或 null(all)
    clearCache('selection_null'); 
    clearCache('selection_main');
    // 如果有更多动态 key，可能需要遍历 localStorage 清理，暂略
  }
}

// 获取用户所有可用平台及对应的模型列表
// 支持传入 onData 回调以实现“先显示缓存后更新”
export async function fetchUserPlatformsAndModels(optionsOrOnData = {}) {
  let onData = null;
  let force = false;

  if (typeof optionsOrOnData === 'function') {
    onData = optionsOrOnData;
  } else if (typeof optionsOrOnData === 'object') {
    onData = optionsOrOnData.onData;
    force = optionsOrOnData.force;
  }

  if (force) invalidatePlatformsModelsCache();
  
  return _fetchWithSWR('/api/ai/user-platforms-models', 'platforms_models', onData);
}

// 获取用户模型选择详情（包含所有用途）
export async function fetchUserSelection(usageKey, optionsOrOnData = {}) {
  let onData = null;
  let force = false;

  if (typeof optionsOrOnData === 'function') {
    onData = optionsOrOnData;
  } else if (typeof optionsOrOnData === 'object') {
    onData = optionsOrOnData.onData;
    force = optionsOrOnData.force;
  }

  const key = usageKey || 'null';
  if (force) invalidateUserSelectionCache(usageKey);

  const url = usageKey ? `/api/ai/user-selection?usage_key=${encodeURIComponent(usageKey)}` : '/api/ai/user-selection';
  return _fetchWithSWR(url, `selection_${key}`, onData);
}
export async function fetchProjects() {
  const response = await fetchWithAuth('/api/projects');
  if (!response.ok) {
    throw new Error('无法加载项目列表');
  }
  return await response.json();
}

export async function createProject(projectName) {
  const response = await fetchWithAuth('/api/projects', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ projectName }),
  });
  if (!response.ok) {
    const result = await response.json();
    throw new Error(result.message || '创建项目失败');
  }
  return await response.json();
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

export async function deleteProject(projectName) {
  const response = await fetchWithAuth(`/api/projects/${projectName}`, {
    method: 'DELETE',
  });
  if (!response.ok) {
    const result = await response.json();
    throw new Error(result.message || '删除项目失败');
  }
  return await response.json();
}

// 获取剧本文件内容
export async function fetchStoryFile(projectName, filePath) {
  const encoded = String(filePath)
    .split('/')
    .map(encodeURIComponent)
    .join('/');
  const response = await fetchWithAuth(`/api/file-content/${encodeURIComponent(projectName)}/${encoded}`);
  if (!response.ok) {
    throw new Error('无法加载剧本文件');
  }
  return await response.json();
}

// 获取文件树
export async function fetchFileTree(projectName) {
  const response = await fetchWithAuth(`/api/story-files/${projectName}`);
  if (!response.ok) {
    throw new Error('无法加载文件树');
  }
  return await response.json();
}

// 保存当前 .story 文件
export async function saveStory(projectName, filename, data) {
  const response = await fetchWithAuth('/api/save-story', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ projectName, filename, data }),
  });
  const result = await response.json();
  if (!response.ok || result.success === false) {
    throw new Error(result.message || '保存失败');
  }
  return result;
}

// 上传 .story 文件到当前项目 stories 目录
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

// 获取当前登录用户信息
export async function getUserInfo() {
  const response = await fetchWithAuth('/api/user/info');
  const result = await response.json();
  if (!response.ok || result.success === false) {
    throw new Error(result.message || '获取用户信息失败');
  }
  return result.user;
}

// 登出
export async function logout() {
  const response = await fetchWithAuth('/api/logout', { method: 'POST', headers: { 'Content-Type': 'application/json' } });
  if (!response.ok) {
    let msg = '';
    try { msg = await response.text(); } catch {}
    throw new Error(msg || response.statusText || '登出失败');
  }
  // 兼容 204/空响应
  return { success: true };
}

// 需要在其他模块中直连受保护接口时可复用
export { fetchWithAuth };

// 登录
export async function loginUser(username, password, remember = true) {
  const response = await fetchWithAuth('/api/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password, remember }),
  });
  const result = await response.json();
  if (!response.ok || result.success === false) {
    throw new Error(result.message || '登录失败');
  }
  return result;
}

// 注册
export async function registerUser(username, password) {
  const response = await fetchWithAuth('/api/register', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  });
  const result = await response.json();
  if (!response.ok || result.success === false) {
    throw new Error(result.message || '注册失败');
  }
  return result;
}

// 角色：获取项目内的角色列表 [{ id, name }]
export async function fetchCharacters(projectName) {
  if (!projectName) return [];
  const response = await fetchWithAuth(`/api/characters/${encodeURIComponent(projectName)}`);
  if (!response.ok) {
    // 后端未配置角色时返回空列表
    return [];
  }
  return await response.json();
}

// 获取蓝图数据
export async function fetchBlueprint(projectName) {
  const response = await fetchWithAuth(`/api/blueprint/${encodeURIComponent(projectName)}`);
  if (!response.ok) {
    if (response.status === 404) return {}; // Not found is ok, return empty object
    throw new Error('无法加载蓝图数据');
  }
  return await response.json();
}

// 保存蓝图数据
export async function saveBlueprint(projectName, data) {
  const response = await fetchWithAuth(`/api/blueprint/${encodeURIComponent(projectName)}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  const result = await response.json();
  if (!response.ok || result.success === false) {
    throw new Error(result.message || '保存蓝图失败');
  }
  return result;
}

// 获取角色绑定
export async function fetchBindings(projectName) {
  const response = await fetchWithAuth(`/api/bindings/${encodeURIComponent(projectName)}`);
  if (!response.ok) return [];
  return await response.json();
}

// 保存角色绑定
export async function saveBindings(projectName, data) {
  const response = await fetchWithAuth(`/api/bindings/${encodeURIComponent(projectName)}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  const result = await response.json();
  if (!response.ok || result.success === false) {
    throw new Error(result.message || '保存角色绑定失败');
  }
  return result;
}

// 获取行为函数绑定
export async function fetchActionBindings(projectName) {
  const response = await fetchWithAuth(`/api/action-bindings/${encodeURIComponent(projectName)}`);
  if (!response.ok) return [];
  return await response.json();
}

// 保存行为函数绑定
export async function saveActionBindings(projectName, data) {
  const response = await fetchWithAuth(`/api/action-bindings/${encodeURIComponent(projectName)}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  const result = await response.json();
  if (!response.ok || result.success === false) {
    throw new Error(result.message || '保存行为函数绑定失败');
  }
  return result;
}

// 获取全局注册表
export async function fetchRegistries(projectName) {
  const response = await fetchWithAuth(`/api/registries/${encodeURIComponent(projectName)}`);
  if (!response.ok) return [];
  return await response.json();
}

// 保存全局注册表
export async function saveRegistries(projectName, data) {
  const response = await fetchWithAuth(`/api/registries/${encodeURIComponent(projectName)}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  const result = await response.json();
  if (!response.ok || result.success === false) {
    throw new Error(result.message || '保存注册表失败');
  }
  return result;
}

// 导出项目到 SQLite
export async function exportProjectToSQLite(projectName, reset = true) {
  const response = await fetchWithAuth('/api/export-to-sqlite', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ projectName, reset }),
  });
  const result = await response.json();
  if (!response.ok || result.success === false) {
    throw new Error(result.message || '导出失败');
  }
  return result;
}

// [Removed duplicate definitions]

// 保存用户模型选择
export async function saveUserSelection(platformId, modelId, usageKey) {
  const response = await fetchWithAuth('/api/ai/user-selection', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ platform_id: platformId, model_id: modelId, usage_key: usageKey }),
  });
  const result = await response.json();
  if (!response.ok || result.success === false) {
    throw new Error(result.error || '保存失败');
  }
  // invalidate cache for this usageKey
  try { invalidateUserSelectionCache(usageKey); } catch (e) {}
  return result;
}

// 创建新的用途插槽
export async function createUserUsageSlot(usageKey, usageLabel, platformId, modelId) {
  const response = await fetchWithAuth('/api/ai/user-selection/usage', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ 
      usage_key: usageKey, 
      usage_label: usageLabel,
      platform_id: platformId,
      model_id: modelId
    }),
  });
  const result = await response.json();
  if (!response.ok) {
    throw new Error(result.error || '创建用途失败');
  }
  // new slot created: invalidate usage cache
  try { invalidateUserSelectionCache(null); invalidatePlatformsModelsCache(); } catch (e) {}
  return result;
}

// --- AI Agent APIs ---

// Muse Agent: Ignite Inspiration
export async function igniteMuse(projectName, inspiration) {
  const response = await fetchWithAuth('/api/ai/muse', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ projectName, inspiration }),
  });
  
  if (!response.ok) {
    throw new Error('Muse Agent failed to respond');
  }
  
  // Return the stream reader
  return response.body.getReader();
}

// Showrunner Agent: Generate Beat Sheet
export async function generateBeatSheet(projectName, context, guidance) {
  const response = await fetchWithAuth('/api/ai/beat-sheet', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ projectName, context, guidance }),
  });
  
  const result = await response.json();
  if (!response.ok || result.success === false) {
    throw new Error(result.error || 'Failed to generate beat sheet');
  }
  return result.beat_sheet;
}

// Showrunner Agent: Generate Story Outline (树状结构)
export async function generateOutline(projectName, context, guidance, options = {}) {
  const response = await fetchWithAuth('/api/ai/outline', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      projectName,
      context,
      guidance,
      saveToProject: options.saveToProject ?? true,
      saveToHistory: options.saveToHistory ?? true,
    }),
  });
  
  const result = await response.json();
  if (!response.ok || result.success === false) {
    throw new Error(result.error || 'Failed to generate outline');
  }
  return result.outline;
}

// ==================== 大纲 API ====================

// 获取当前大纲
export async function getOutline(projectName) {
  const response = await fetchWithAuth(`/api/outline/${encodeURIComponent(projectName)}`);
  const result = await response.json();
  if (!response.ok || result.success === false) {
    throw new Error(result.error || 'Failed to fetch outline');
  }
  return result.outline;
}

// 保存大纲
export async function saveOutline(projectName, outline, saveToHistory = false) {
  const response = await fetchWithAuth(`/api/outline/${encodeURIComponent(projectName)}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ outline, saveToHistory }),
  });
  
  const result = await response.json();
  if (!response.ok || result.success === false) {
    throw new Error(result.error || 'Failed to save outline');
  }
  return result;
}

// ==================== 灵感历史 API ====================

// 获取灵感历史
export async function getMuseHistory(projectName) {
  const response = await fetchWithAuth(`/api/history/muse/${encodeURIComponent(projectName)}`);
  const result = await response.json();
  if (!response.ok || result.success === false) {
    throw new Error(result.error || 'Failed to fetch muse history');
  }
  return result.history;
}

// 删除单条灵感历史
export async function deleteMuseHistory(projectName, entryId) {
  const response = await fetchWithAuth(`/api/history/muse/${encodeURIComponent(projectName)}/${entryId}`, {
    method: 'DELETE',
  });
  const result = await response.json();
  if (!response.ok || result.success === false) {
    throw new Error(result.error || 'Failed to delete muse history');
  }
  return result;
}

// ==================== 大纲历史 API ====================

// 获取大纲历史
export async function getOutlineHistory(projectName) {
  const response = await fetchWithAuth(`/api/history/outline/${encodeURIComponent(projectName)}`);
  const result = await response.json();
  if (!response.ok || result.success === false) {
    throw new Error(result.error || 'Failed to fetch outline history');
  }
  return result.history;
}

// 删除单条大纲历史
export async function deleteOutlineHistory(projectName, entryId) {
  const response = await fetchWithAuth(`/api/history/outline/${encodeURIComponent(projectName)}/${entryId}`, {
    method: 'DELETE',
  });
  const result = await response.json();
  if (!response.ok || result.success === false) {
    throw new Error(result.error || 'Failed to delete outline history');
  }
  return result;
}

// 从历史恢复大纲
export async function restoreOutlineFromHistory(projectName, entryId) {
  const response = await fetchWithAuth(`/api/history/outline/${encodeURIComponent(projectName)}/${entryId}/restore`, {
    method: 'POST',
  });
  const result = await response.json();
  if (!response.ok || result.success === false) {
    throw new Error(result.error || 'Failed to restore outline');
  }
  return result.outline;
}

// Style Agent: Analyze File
export async function analyzeStyle(projectName, file) {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('projectName', projectName);

  const response = await fetchWithAuth('/api/ai/style-analyze', {
    method: 'POST',
    body: formData,
  });
  
  const result = await response.json();
  if (!response.ok || result.success === false) {
    throw new Error(result.error || 'Style analysis failed');
  }
  return result.style_profile;
}

// Style Agent: Get Profile
export async function getStyleProfile(projectName) {
  const response = await fetchWithAuth(`/api/ai/style-profile?projectName=${encodeURIComponent(projectName)}`);
  const result = await response.json();
  if (!response.ok) {
    // 404 is expected if no profile exists
    if (response.status === 404) return null;
    throw new Error(result.message || 'Failed to fetch style profile');
  }
  return result.style_profile;
}

// 删除用途槽
export async function deleteUserUsageSlot(usageKey) {
  const response = await fetchWithAuth('/api/ai/user-selection/usage', {
    method: 'DELETE',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ usage_key: usageKey }),
  });
  const result = await response.json();
  if (!response.ok || result.success === false) {
    throw new Error(result.error || '删除用途失败');
  }
  // invalidate caches
  try { invalidateUserSelectionCache(null); invalidatePlatformsModelsCache(); } catch (e) {}
  return result;
}

// 编辑用途槽（重命名 key 或修改 label）
export async function renameUserUsageSlot(usageKey, newUsageKey, newLabel) {
  const response = await fetchWithAuth('/api/ai/user-selection/usage', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ usage_key: usageKey, new_usage_key: newUsageKey, new_usage_label: newLabel }),
  });
  const result = await response.json();
  if (!response.ok) {
    throw new Error(result.error || '编辑用途失败');
  }
  try { invalidateUserSelectionCache(null); invalidatePlatformsModelsCache(); } catch (e) {}
  return result;
}

// 强制刷新接口（供页面在需要时调用）
export async function refreshPlatformsAndModels() {
  invalidatePlatformsModelsCache();
  return fetchUserPlatformsAndModels({ force: true });
}

export async function refreshUserSelection(usageKey) {
  invalidateUserSelectionCache(usageKey);
  return fetchUserSelection(usageKey, { force: true });
}