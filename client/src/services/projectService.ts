import { fetchWithAuth } from './apiClient';

type ProjectApiResult = {
  success?: boolean;
  message?: string;
  [key: string]: unknown;
};

export async function fetchProjects(): Promise<string[]> {
  const response = await fetchWithAuth('/api/projects');
  if (!response.ok) throw new Error('无法加载项目列表');
  return await response.json() as string[];
}

export async function createProject(projectName: string): Promise<ProjectApiResult> {
  const response = await fetchWithAuth('/api/projects', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ projectName }),
  });
  if (!response.ok) {
    const result = await response.json() as ProjectApiResult;
    throw new Error(result.message || '创建项目失败');
  }
  return await response.json() as ProjectApiResult;
}

export async function deleteProject(projectName: string): Promise<ProjectApiResult> {
  const response = await fetchWithAuth(`/api/projects/${projectName}`, {
    method: 'DELETE',
  });
  if (!response.ok) {
    const result = await response.json() as ProjectApiResult;
    throw new Error(result.message || '删除项目失败');
  }
  return await response.json() as ProjectApiResult;
}

export async function exportProjectToSQLite(projectName: string, reset = true): Promise<ProjectApiResult> {
  const response = await fetchWithAuth('/api/export-to-sqlite', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ projectName, reset }),
  });
  const result = await response.json() as ProjectApiResult;
  if (!response.ok || result.success === false) {
    throw new Error(result.message || '导出失败');
  }
  return result;
}
