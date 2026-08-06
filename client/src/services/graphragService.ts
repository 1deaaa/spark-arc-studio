/**
 * GraphRAG（项目知识图谱）配置 API
 *
 * 与 semanticSearchService 保持对称：
 * - 单项目 / 全部项目状态查询
 * - 启用 / 禁用 / 刷新 / 重置
 * - 用户级默认开关
 *
 * AI 端只读 status/query；触发构建仅由本服务驱动。
 */
import { fetchWithAuth } from './apiClient';

export interface GraphRAGBuildProgress {
  total_chunks: number;
  done_chunks: number;
  triplets_collected: number;
  source_docs: number;
  nodes: number;
  edges: number;
}

export interface GraphRAGBuildState {
  status: string;
  stage: string;
  error: string;
  started_at: string;
  finished_at: string;
  progress: GraphRAGBuildProgress;
}

export interface GraphRAGProjectMetadata {
  built_at: string;
  source_docs: number;
  chunks: number;
  triplets: number;
  nodes: number;
  edges: number;
}

export interface GraphRAGProjectStatus {
  projectName: string;
  enabled: boolean;
  graphReady: boolean;
  metadataReady: boolean;
  needsRebuild: boolean;
  buildState: GraphRAGBuildState;
  metadata: GraphRAGProjectMetadata;
}

export interface GraphRAGStatusResponse {
  projects: GraphRAGProjectStatus[];
  default_enabled: boolean;
}

export interface GraphRAGSingleStatusResponse extends GraphRAGProjectStatus {}

export interface GraphRAGToggleResponse extends GraphRAGProjectStatus {
  success: boolean;
}

export interface GraphRAGRefreshResponse extends GraphRAGToggleResponse {
  triggered: boolean;
}

export interface GraphRAGResetResponse extends GraphRAGToggleResponse {
  removed: boolean;
}

export interface GraphRAGCharacterNode {
  id: string;
  label: string;
  entityType: 'character';
  graphName: string;
  inGraph: boolean;
  degree: number;
}

export interface GraphRAGCharacterEdge {
  id: string;
  source: string;
  target: string;
  relation: string;
  evidenceCount: number;
  sources: string[];
  evidenceSamples: string[];
}

export interface GraphRAGCharacterGraph {
  projectName: string;
  enabled: boolean;
  graphReady: boolean;
  needsRebuild: boolean;
  buildState: GraphRAGBuildState;
  metadata: GraphRAGProjectMetadata;
  nodes: GraphRAGCharacterNode[];
  edges: GraphRAGCharacterEdge[];
}

type RawGraphRAGProjectStatus = {
  projectName?: string;
  project_name?: string;
  enabled: boolean;
  graphReady?: boolean;
  graph_ready?: boolean;
  metadataReady?: boolean;
  metadata_ready?: boolean;
  needsRebuild?: boolean;
  needs_rebuild?: boolean;
  buildState?: Partial<GraphRAGBuildState>;
  build_state?: Partial<GraphRAGBuildState>;
  metadata?: Partial<GraphRAGProjectMetadata>;
};

type RawGraphRAGStatusResponse = Omit<GraphRAGStatusResponse, 'projects'> & {
  detail?: string;
  projects: RawGraphRAGProjectStatus[];
};

type RawGraphRAGSingleStatusResponse = RawGraphRAGProjectStatus & {
  detail?: string;
};

type RawGraphRAGToggleResponse = RawGraphRAGProjectStatus & {
  detail?: string;
  success?: boolean;
  triggered?: boolean;
  removed?: boolean;
};

type RawGraphRAGCharacterGraph = {
  projectName?: string;
  project_name?: string;
  enabled?: boolean;
  graphReady?: boolean;
  graph_ready?: boolean;
  needsRebuild?: boolean;
  needs_rebuild?: boolean;
  buildState?: Partial<GraphRAGBuildState>;
  build_state?: Partial<GraphRAGBuildState>;
  metadata?: Partial<GraphRAGProjectMetadata>;
  nodes?: Array<{
    id?: string | number;
    label?: string;
    entity_type?: string;
    entityType?: string;
    graph_name?: string;
    graphName?: string;
    in_graph?: boolean;
    inGraph?: boolean;
    degree?: number;
  }>;
  edges?: Array<{
    id?: string;
    source?: string | number;
    target?: string | number;
    relation?: string;
    evidence_count?: number;
    evidenceCount?: number;
    sources?: string[];
    evidence_samples?: string[];
    evidenceSamples?: string[];
  }>;
  detail?: string;
};

const emptyBuildState = (): GraphRAGBuildState => ({
  status: 'not_built',
  stage: 'idle',
  error: '',
  started_at: '',
  finished_at: '',
  progress: {
    total_chunks: 0,
    done_chunks: 0,
    triplets_collected: 0,
    source_docs: 0,
    nodes: 0,
    edges: 0,
  },
});

const emptyMetadata = (): GraphRAGProjectMetadata => ({
  built_at: '',
  source_docs: 0,
  chunks: 0,
  triplets: 0,
  nodes: 0,
  edges: 0,
});

function normalizeBuildState(raw?: Partial<GraphRAGBuildState>): GraphRAGBuildState {
  const base = emptyBuildState();
  const progress: Partial<GraphRAGBuildProgress> = raw?.progress ?? {};
  return {
    status: raw?.status ?? base.status,
    stage: raw?.stage ?? base.stage,
    error: raw?.error ?? base.error,
    started_at: raw?.started_at ?? base.started_at,
    finished_at: raw?.finished_at ?? base.finished_at,
    progress: {
      total_chunks: Number(progress.total_chunks ?? base.progress.total_chunks),
      done_chunks: Number(progress.done_chunks ?? base.progress.done_chunks),
      triplets_collected: Number(progress.triplets_collected ?? base.progress.triplets_collected),
      source_docs: Number(progress.source_docs ?? base.progress.source_docs),
      nodes: Number(progress.nodes ?? base.progress.nodes),
      edges: Number(progress.edges ?? base.progress.edges),
    },
  };
}

function normalizeMetadata(raw?: Partial<GraphRAGProjectMetadata>): GraphRAGProjectMetadata {
  const base = emptyMetadata();
  return {
    built_at: raw?.built_at ?? base.built_at,
    source_docs: Number(raw?.source_docs ?? base.source_docs),
    chunks: Number(raw?.chunks ?? base.chunks),
    triplets: Number(raw?.triplets ?? base.triplets),
    nodes: Number(raw?.nodes ?? base.nodes),
    edges: Number(raw?.edges ?? base.edges),
  };
}

function normalizeProjectStatus(project: RawGraphRAGProjectStatus): GraphRAGProjectStatus {
  return {
    projectName: project.projectName ?? project.project_name ?? '',
    enabled: Boolean(project.enabled),
    graphReady: Boolean(project.graphReady ?? project.graph_ready),
    metadataReady: Boolean(project.metadataReady ?? project.metadata_ready),
    needsRebuild: Boolean(project.needsRebuild ?? project.needs_rebuild),
    buildState: normalizeBuildState(project.buildState ?? project.build_state),
    metadata: normalizeMetadata(project.metadata),
  };
}

function normalizeCharacterGraph(result: RawGraphRAGCharacterGraph): GraphRAGCharacterGraph {
  return {
    projectName: result.projectName ?? result.project_name ?? '',
    enabled: Boolean(result.enabled),
    graphReady: Boolean(result.graphReady ?? result.graph_ready),
    needsRebuild: Boolean(result.needsRebuild ?? result.needs_rebuild),
    buildState: normalizeBuildState(result.buildState ?? result.build_state),
    metadata: normalizeMetadata(result.metadata),
    nodes: Array.isArray(result.nodes)
      ? result.nodes
        .filter(node => String(node.entityType ?? node.entity_type ?? 'character') === 'character')
        .map(node => ({
          id: String(node.id ?? ''),
          label: String(node.label ?? ''),
          entityType: 'character' as const,
          graphName: String(node.graphName ?? node.graph_name ?? ''),
          inGraph: Boolean(node.inGraph ?? node.in_graph),
          degree: Number(node.degree ?? 0),
        }))
      : [],
    edges: Array.isArray(result.edges)
      ? result.edges.map(edge => ({
          id: String(edge.id ?? `${edge.source ?? ''}:${edge.target ?? ''}`),
          source: String(edge.source ?? ''),
          target: String(edge.target ?? ''),
          relation: String(edge.relation ?? ''),
          evidenceCount: Number(edge.evidenceCount ?? edge.evidence_count ?? 0),
          sources: Array.isArray(edge.sources) ? edge.sources.map(String) : [],
          evidenceSamples: Array.isArray(edge.evidenceSamples ?? edge.evidence_samples)
            ? (edge.evidenceSamples ?? edge.evidence_samples ?? []).map(String)
            : [],
        }))
      : [],
  };
}

export async function fetchGraphRAGStatus(): Promise<GraphRAGStatusResponse> {
  const response = await fetchWithAuth('/api/graphrag/status');
  const result = await response.json() as RawGraphRAGStatusResponse;
  if (!response.ok) throw new Error(result.detail || '获取知识图谱状态失败');
  return {
    ...result,
    projects: Array.isArray(result.projects) ? result.projects.map(normalizeProjectStatus) : [],
  };
}

export async function fetchGraphRAGSingleStatus(projectName: string): Promise<GraphRAGSingleStatusResponse> {
  const response = await fetchWithAuth(`/api/graphrag/status?projectName=${encodeURIComponent(projectName)}`);
  const result = await response.json() as RawGraphRAGSingleStatusResponse;
  if (!response.ok) throw new Error(result.detail || '获取知识图谱状态失败');
  return normalizeProjectStatus(result);
}

export async function fetchGraphRAGCharacterGraph(projectName: string): Promise<GraphRAGCharacterGraph> {
  const response = await fetchWithAuth(`/api/graphrag/character-graph?projectName=${encodeURIComponent(projectName)}`);
  const result = await response.json() as RawGraphRAGCharacterGraph;
  if (!response.ok) throw new Error(result.detail || '获取角色关系图失败');
  return normalizeCharacterGraph(result);
}

export async function enableCharacterGraph(projectName: string): Promise<GraphRAGToggleResponse> {
  const response = await fetchWithAuth('/api/graphrag/character-graph/enable', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ projectName }),
  });
  const result = await response.json() as RawGraphRAGToggleResponse;
  if (!response.ok) throw new Error(result.detail || '启用角色关系图失败');
  return { success: Boolean(result.success ?? true), ...normalizeProjectStatus(result) };
}

export async function refreshCharacterGraph(projectName: string): Promise<GraphRAGRefreshResponse> {
  const response = await fetchWithAuth('/api/graphrag/character-graph/refresh', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ projectName }),
  });
  const result = await response.json() as RawGraphRAGToggleResponse;
  if (!response.ok) throw new Error(result.detail || '刷新角色关系图失败');
  return { success: Boolean(result.success ?? true), ...normalizeProjectStatus(result), triggered: Boolean(result.triggered) };
}

export async function enableGraphRAG(projectName: string): Promise<GraphRAGToggleResponse> {
  const response = await fetchWithAuth('/api/graphrag/enable', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ projectName }),
  });
  const result = await response.json() as RawGraphRAGToggleResponse;
  if (!response.ok) throw new Error(result.detail || '启用知识图谱失败');
  return {
    success: Boolean(result.success ?? true),
    ...normalizeProjectStatus(result),
  };
}

export async function refreshGraphRAGProject(projectName: string): Promise<GraphRAGRefreshResponse> {
  const response = await fetchWithAuth('/api/graphrag/refresh', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ projectName }),
  });
  const result = await response.json() as RawGraphRAGToggleResponse;
  if (!response.ok) throw new Error(result.detail || '刷新知识图谱失败');
  return {
    success: Boolean(result.success ?? true),
    ...normalizeProjectStatus(result),
    triggered: Boolean(result.triggered),
  };
}

export async function disableGraphRAG(projectName: string): Promise<GraphRAGToggleResponse> {
  const response = await fetchWithAuth('/api/graphrag/disable', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ projectName }),
  });
  const result = await response.json() as RawGraphRAGToggleResponse;
  if (!response.ok) throw new Error(result.detail || '禁用知识图谱失败');
  return {
    success: Boolean(result.success ?? true),
    ...normalizeProjectStatus(result),
  };
}

export async function resetGraphRAGProject(projectName: string): Promise<GraphRAGResetResponse> {
  const response = await fetchWithAuth('/api/graphrag/reset', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ projectName }),
  });
  const result = await response.json() as RawGraphRAGToggleResponse;
  if (!response.ok) throw new Error(result.detail || '重置知识图谱失败');
  return {
    success: Boolean(result.success ?? true),
    ...normalizeProjectStatus(result),
    removed: Boolean(result.removed),
  };
}

export async function setGraphRAGDefaults(defaultEnabled: boolean): Promise<{ success: boolean; default_enabled: boolean }> {
  const response = await fetchWithAuth('/api/graphrag/defaults', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ defaultEnabled }),
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.detail || '设置默认配置失败');
  return result;
}
