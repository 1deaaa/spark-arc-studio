/**
 * 语义检索配置 API
 */
import { fetchWithAuth } from './apiClient';

export interface SemanticSearchProjectStatus {
  projectName: string;
  enabled: boolean;
}

export interface SemanticSearchStatusResponse {
  projects: SemanticSearchProjectStatus[];
  embedding_ready: boolean;
  embedding_model_name: string;
  default_enabled: boolean;
}

export interface SemanticSearchSingleStatusResponse {
  projectName: string;
  enabled: boolean;
  embedding_ready: boolean;
  embedding_model_name: string;
  index_exists: boolean;
}

export interface EmbeddingTestResult {
  success: boolean;
  dims?: number;
  model_name?: string;
  platform_name?: string;
  error?: string;
}

type RawSemanticSearchProjectStatus = {
  projectName?: string;
  project_name?: string;
  enabled: boolean;
};

type RawSemanticSearchStatusResponse = Omit<SemanticSearchStatusResponse, 'projects'> & {
  detail?: string;
  projects: RawSemanticSearchProjectStatus[];
};

type RawSemanticSearchSingleStatusResponse = Omit<SemanticSearchSingleStatusResponse, 'projectName'> & {
  detail?: string;
  projectName?: string;
  project_name?: string;
};

function normalizeProjectStatus(project: RawSemanticSearchProjectStatus): SemanticSearchProjectStatus {
  return {
    projectName: project.projectName ?? project.project_name ?? '',
    enabled: Boolean(project.enabled),
  };
}

export async function fetchSemanticSearchStatus(): Promise<SemanticSearchStatusResponse> {
  const response = await fetchWithAuth('/api/semantic-search/status');
  const result = await response.json() as RawSemanticSearchStatusResponse;
  if (!response.ok) throw new Error(result.detail || '获取语义检索状态失败');
  return {
    ...result,
    projects: Array.isArray(result.projects) ? result.projects.map(normalizeProjectStatus) : [],
  };
}

export async function fetchSemanticSearchSingleStatus(projectName: string): Promise<SemanticSearchSingleStatusResponse> {
  const response = await fetchWithAuth(`/api/semantic-search/status?projectName=${encodeURIComponent(projectName)}`);
  const result = await response.json() as RawSemanticSearchSingleStatusResponse;
  if (!response.ok) throw new Error(result.detail || '获取语义检索状态失败');
  return {
    ...result,
    projectName: result.projectName ?? result.project_name ?? '',
  };
}

export async function enableSemanticSearch(projectName: string): Promise<{ success: boolean; enabled: boolean }> {
  const response = await fetchWithAuth('/api/semantic-search/enable', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ projectName }),
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.detail || '启用语义检索失败');
  return result;
}

export async function disableSemanticSearch(projectName: string): Promise<{ success: boolean; enabled: boolean }> {
  const response = await fetchWithAuth('/api/semantic-search/disable', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ projectName }),
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.detail || '禁用语义检索失败');
  return result;
}

export async function testSemanticEmbedding(): Promise<EmbeddingTestResult> {
  const response = await fetchWithAuth('/api/semantic-search/test-embedding', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  });
  const result = await response.json();
  return result;
}

export async function setSemanticSearchDefaults(defaultEnabled: boolean): Promise<{ success: boolean; default_enabled: boolean }> {
  const response = await fetchWithAuth('/api/semantic-search/defaults', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ defaultEnabled }),
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.detail || '设置默认配置失败');
  return result;
}
