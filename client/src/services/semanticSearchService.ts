/**
 * 语义检索配置 API
 */
import { fetchWithAuth } from './apiClient';

export interface SemanticSearchBuildProgress {
  total_files: number;
  done_files: number;
  total_chunks: number;
  embedded_chunks: number;
  changed_files: number;
  removed_files: number;
  reused_files: number;
}

export interface SemanticSearchBuildState {
  status: string;
  stage: string;
  error: string;
  started_at: string;
  finished_at: string;
  progress: SemanticSearchBuildProgress;
}

export interface SemanticSearchProjectStatus {
  projectName: string;
  enabled: boolean;
  indexExists: boolean;
  needsRebuild: boolean;
  buildState: SemanticSearchBuildState;
}

export interface SemanticSearchStatusResponse {
  projects: SemanticSearchProjectStatus[];
  embedding_ready: boolean;
  embedding_model_name: string;
  default_enabled: boolean;
  embedding_contract?: EmbeddingContract;
}

export interface SemanticSearchSingleStatusResponse extends SemanticSearchProjectStatus {
  embedding_ready: boolean;
  embedding_model_name: string;
}

export interface SemanticSearchToggleResponse extends SemanticSearchProjectStatus {
  success: boolean;
  settings?: Record<string, unknown>;
}

export interface EmbeddingTestResult {
  success: boolean;
  dims?: number;
  model_name?: string;
  platform_name?: string;
  embedding_contract?: EmbeddingContract;
  error?: string;
}

export interface EmbeddingContract {
  version: string;
  model: string;
  dimensions: number;
  metric: string;
  normalize: boolean;
  query_instruction: string;
  max_context_tokens: number;
}

export interface LocalEmbeddingStatus {
  configured: boolean;
  running: boolean;
  alive: boolean;
  pid?: number | null;
  base_url?: string;
  model?: string;
  display_model?: string;
  dimensions?: number;
  command?: string[];
  startup?: {
    phase: string;
    message?: string;
    progress?: number;
    error?: string;
    updated_at?: string;
  };
}

export interface LocalEmbeddingResponse {
  success: boolean;
  status: LocalEmbeddingStatus;
  enabled?: boolean;
  embedding_contract?: EmbeddingContract;
  error?: string;
}

type RawSemanticSearchProjectStatus = {
  projectName?: string;
  project_name?: string;
  enabled: boolean;
  indexExists?: boolean;
  index_exists?: boolean;
  needsRebuild?: boolean;
  needs_rebuild?: boolean;
  buildState?: Partial<SemanticSearchBuildState>;
  build_state?: Partial<SemanticSearchBuildState>;
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

type RawSemanticSearchToggleResponse = Omit<SemanticSearchToggleResponse, 'projectName' | 'enabled' | 'indexExists' | 'needsRebuild' | 'buildState'> & RawSemanticSearchProjectStatus & {
  detail?: string;
};

const emptyBuildState = (): SemanticSearchBuildState => ({
  status: 'not_built',
  stage: 'idle',
  error: '',
  started_at: '',
  finished_at: '',
  progress: {
    total_files: 0,
    done_files: 0,
    total_chunks: 0,
    embedded_chunks: 0,
    changed_files: 0,
    removed_files: 0,
    reused_files: 0,
  },
});

function normalizeBuildState(raw?: Partial<SemanticSearchBuildState>): SemanticSearchBuildState {
  const base = emptyBuildState();
  const progress: Partial<SemanticSearchBuildProgress> = raw?.progress ?? {};
  return {
    status: raw?.status ?? base.status,
    stage: raw?.stage ?? base.stage,
    error: raw?.error ?? base.error,
    started_at: raw?.started_at ?? base.started_at,
    finished_at: raw?.finished_at ?? base.finished_at,
    progress: {
      total_files: Number(progress.total_files ?? base.progress.total_files),
      done_files: Number(progress.done_files ?? base.progress.done_files),
      total_chunks: Number(progress.total_chunks ?? base.progress.total_chunks),
      embedded_chunks: Number(progress.embedded_chunks ?? base.progress.embedded_chunks),
      changed_files: Number(progress.changed_files ?? base.progress.changed_files),
      removed_files: Number(progress.removed_files ?? base.progress.removed_files),
      reused_files: Number(progress.reused_files ?? base.progress.reused_files),
    },
  };
}

function normalizeProjectStatus(project: RawSemanticSearchProjectStatus): SemanticSearchProjectStatus {
  return {
    projectName: project.projectName ?? project.project_name ?? '',
    enabled: Boolean(project.enabled),
    indexExists: Boolean(project.indexExists ?? project.index_exists),
    needsRebuild: Boolean(project.needsRebuild ?? project.needs_rebuild),
    buildState: normalizeBuildState(project.buildState ?? project.build_state),
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
    ...normalizeProjectStatus(result),
  };
}

export async function enableSemanticSearch(projectName: string): Promise<SemanticSearchToggleResponse> {
  const response = await fetchWithAuth('/api/semantic-search/enable', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ projectName }),
  });
  const result = await response.json() as RawSemanticSearchToggleResponse;
  if (!response.ok) throw new Error(result.detail || '启用语义检索失败');
  return {
    ...result,
    ...normalizeProjectStatus(result),
  };
}

export interface SemanticSearchRefreshResponse extends SemanticSearchToggleResponse {
  triggered: boolean;
}

type RawSemanticSearchRefreshResponse = RawSemanticSearchToggleResponse & {
  triggered?: boolean;
};

export async function refreshSemanticSearchProject(projectName: string): Promise<SemanticSearchRefreshResponse> {
  const response = await fetchWithAuth('/api/semantic-search/refresh', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ projectName }),
  });
  const result = await response.json() as RawSemanticSearchRefreshResponse;
  if (!response.ok) throw new Error(result.detail || '刷新语义检索失败');
  return {
    ...result,
    ...normalizeProjectStatus(result),
    triggered: Boolean(result.triggered),
  };
}

export async function disableSemanticSearch(projectName: string): Promise<SemanticSearchToggleResponse> {
  const response = await fetchWithAuth('/api/semantic-search/disable', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ projectName }),
  });
  const result = await response.json() as RawSemanticSearchToggleResponse;
  if (!response.ok) throw new Error(result.detail || '禁用语义检索失败');
  return {
    ...result,
    ...normalizeProjectStatus(result),
  };
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

export async function fetchLocalEmbeddingStatus(): Promise<LocalEmbeddingResponse> {
  const response = await fetchWithAuth('/api/semantic-search/local-embedding');
  const result = await response.json() as LocalEmbeddingResponse & { detail?: string };
  if (!response.ok) throw new Error(result.detail || result.error || '获取本地嵌入状态失败');
  return result;
}

export async function setLocalEmbeddingEnabled(enabled: boolean): Promise<LocalEmbeddingResponse> {
  const response = await fetchWithAuth('/api/semantic-search/local-embedding', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ enabled }),
  });
  const result = await response.json() as LocalEmbeddingResponse & { detail?: string };
  if (!response.ok) throw new Error(result.detail || result.error || '更新本地嵌入状态失败');
  return result;
}
