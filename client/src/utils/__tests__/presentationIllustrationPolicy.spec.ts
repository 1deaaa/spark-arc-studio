import { describe, expect, it } from 'vitest';
import { selectPresentationIllustrationCandidates } from '../presentationIllustrationPolicy';

type TestNode = {
  illustration_prompt?: string;
  illustration?: string;
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
});
