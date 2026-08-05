import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../apiClient', () => ({
  fetchWithAuth: vi.fn(),
}));

import { fetchWithAuth } from '../apiClient';
import { fetchGraphRAGCharacterGraph } from '../graphragService';

describe('GraphRAG 角色子图服务', () => {
  beforeEach(() => {
    vi.mocked(fetchWithAuth).mockReset();
  });

  it('把后端蛇形字段规范化为角色画布协议', async () => {
    vi.mocked(fetchWithAuth).mockResolvedValue(new Response(JSON.stringify({
      projectName: 'demo',
      enabled: true,
      graph_ready: true,
      needs_rebuild: false,
      build_state: {
        status: 'ready',
        progress: { nodes: 4, edges: 2 },
      },
      metadata: { built_at: '2026-08-05T00:00:00Z', nodes: 4, edges: 2 },
      nodes: [
        { id: 1, label: '沈棠', entity_type: 'character', graph_name: '阿棠', in_graph: true, degree: 1 },
      ],
      edges: [
        {
          id: '1:2', source: 1, target: 2, relation: '盟友', evidence_count: 2,
          sources: ['角色/沈棠'], evidence_samples: ['并肩调查旧案'],
        },
      ],
    }), { status: 200 }));

    const result = await fetchGraphRAGCharacterGraph('demo');

    expect(fetchWithAuth).toHaveBeenCalledWith('/api/graphrag/character-graph?projectName=demo');
    expect(result.nodes[0]).toEqual({
      id: '1', label: '沈棠', entityType: 'character', graphName: '阿棠', inGraph: true, degree: 1,
    });
    expect(result.edges[0]).toEqual({
      id: '1:2', source: '1', target: '2', relation: '盟友', evidenceCount: 2,
      sources: ['角色/沈棠'], evidenceSamples: ['并肩调查旧案'],
    });
  });
});
