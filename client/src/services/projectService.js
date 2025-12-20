import { fetchWithAuth } from './apiClient';

export async function fetchProjects() {
  const response = await fetchWithAuth('/api/projects');
  if (!response.ok) throw new Error('无法加载项目列表');
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
