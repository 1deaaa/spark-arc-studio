import { fetchWithAuth } from './apiClient';

type ProjectApiResult = {
  success?: boolean;
  message?: string;
  [key: string]: unknown;
};

type ProjectWorkspaceMode = 'script' | 'novel';

export async function fetchProjects(): Promise<string[]> {
  const response = await fetchWithAuth('/api/projects');
  if (!response.ok) throw new Error('无法加载项目列表');
  return await response.json() as string[];
}

export async function createProject(projectName: string, workspaceMode: ProjectWorkspaceMode = 'script'): Promise<ProjectApiResult> {
  const response = await fetchWithAuth('/api/projects', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ projectName, workspaceMode }),
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

export async function renameProject(projectName: string, newName: string): Promise<ProjectApiResult & { newName?: string }> {
  const response = await fetchWithAuth(`/api/projects/${projectName}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ newName }),
  });
  if (!response.ok) {
    const result = await response.json() as ProjectApiResult;
    throw new Error(result.message || '重命名项目失败');
  }
  return await response.json() as ProjectApiResult & { newName?: string };
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

/** 导出项目为 .spark 文件（触发浏览器下载） */
export async function exportProjectAsSpark(projectName: string): Promise<void> {
  const response = await fetchWithAuth(`/api/project/${encodeURIComponent(projectName)}/export`);
  if (!response.ok) {
    const result = await response.json().catch(() => ({ message: '导出失败' })) as ProjectApiResult;
    throw new Error(result.message || '导出失败');
  }
  // 从 Content-Disposition 提取文件名（优先 RFC 5987 filename*）
  const disposition = response.headers.get('Content-Disposition') || '';
  let filename = `${projectName}.spark`;
  const utf8Match = disposition.match(/filename\*=UTF-8''(.+?)(?:;|$)/);
  if (utf8Match) {
    filename = decodeURIComponent(utf8Match[1]);
  } else {
    const match = disposition.match(/filename="?([^"]+)"?/);
    if (match) filename = match[1];
  }

  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

type ImportProjectResult = ProjectApiResult & { projectName?: string };

/** 从 .spark 文件导入项目，返回新项目名 */
export async function importProjectFromSpark(file: File): Promise<ImportProjectResult> {
  const formData = new FormData();
  formData.append('file', file);
  const response = await fetchWithAuth('/api/project/import', {
    method: 'POST',
    body: formData,
  });
  const result = await response.json() as ImportProjectResult;
  if (!response.ok || result.success === false) {
    throw new Error(result.message || '导入失败');
  }
  return result;
}
