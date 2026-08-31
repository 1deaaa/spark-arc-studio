import { describe, expect, it } from 'vitest';
import {
  selectPresentationIllustrationCandidates,
  selectPresentationIllustrationConceptionCandidates,
} from '../presentationIllustrationPolicy';

type TestNode = {
  illustration_prompt?: string;
  illustration?: string;
  illustration_pending?: string;
};

const select = (nodes: TestNode[], maxPerScene = 2, minNodeGap = 1) => selectPresentationIllustrationCandidates(
  nodes,
  node => node,
  { maxPerScene, minNodeGap },
);

describe('视觉插图候选策略', () => {
  it('遵守每场上限，并保留已有资产', () => {
    const nodes: TestNode[] = [
      { illustration: 'ill-existing' },
      { illustration_prompt: '候选一' },
      { illustration_prompt: '候选二' },
      { illustration_prompt: '候选三' },
    ];

    expect(select(nodes, 2, 0).map(node => node.illustration_prompt)).toEqual(['候选一']);
  });

  it('遵守已有插图和本批次候选之间的最小节点间距', () => {
    const nodes: TestNode[] = [
      { illustration: 'ill-existing' },
      { illustration_prompt: '相邻已有图，不应入选' },
      {},
      { illustration_prompt: '隔一个普通节点，可以入选' },
      { illustration_prompt: '与本批次上一张相邻，不应入选' },
      {},
      { illustration_prompt: '再次隔开，可以入选' },
    ];

    expect(select(nodes, 4, 1).map(node => node.illustration_prompt)).toEqual([
      '隔一个普通节点，可以入选',
      '再次隔开，可以入选',
    ]);
  });

  it('已有手工超量数据不被删除，也不再接受新增候选', () => {
    const nodes: TestNode[] = [
      { illustration: 'ill-one' },
      { illustration: 'ill-two' },
      { illustration: 'ill-manual-over-limit' },
      { illustration_prompt: '不应新增' },
    ];

    expect(select(nodes).map(node => node.illustration_prompt)).toEqual([]);
    expect(nodes[2].illustration).toBe('ill-manual-over-limit');
  });

  it('所有 pending 节点都进入构思候选，不受普通插图节奏策略过滤', () => {
    const nodes: TestNode[] = [
      { illustration: 'ill-existing' },
      { illustration_pending: 'true' },
      {},
      { illustration_pending: 'true' },
      { illustration_pending: 'true' },
    ];

    expect(selectPresentationIllustrationConceptionCandidates(
      nodes,
      node => node,
      { maxPerScene: 1, minNodeGap: 4 },
    ).map(node => node.illustration_pending)).toEqual(['true', 'true', 'true']);
  });

  it('已有描述或图片资产的节点不再进入 pending 构思候选', () => {
    const nodes: TestNode[] = [
      { illustration_pending: 'true', illustration_prompt: '已经补过描述' },
      { illustration_pending: 'true', illustration: 'ill-existing' },
      { illustration_pending: 'true' },
    ];

    expect(selectPresentationIllustrationConceptionCandidates(
      nodes,
      node => node,
      { maxPerScene: 1, minNodeGap: 4 },
    )).toEqual([nodes[2]]);
  });

  it('pending 转为具体描述后，常规图片候选仍遵守预留名额', () => {
    const nodes: TestNode[] = [
      { illustration_pending: 'true', illustration_prompt: '待生成画面' },
      {},
      { illustration_pending: 'true' },
      { illustration_prompt: '新的画面' },
    ];

    expect(select(nodes, 2, 1).map(node => node.illustration_prompt)).toEqual(['待生成画面']);
  });
});
