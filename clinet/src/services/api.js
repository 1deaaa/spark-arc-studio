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

// 获取项目列表
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