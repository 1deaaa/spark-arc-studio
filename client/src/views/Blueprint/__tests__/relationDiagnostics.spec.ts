import { describe, expect, it } from 'vitest';
import { buildRelationDiagnostics, getRelationJumps } from '../relationDiagnostics';

describe('移动端关系诊断模型', () => {
  it('识别直接跳转、选项跳转和无效目标', () => {
    const scenes = [
      {
        scene: '开场',
        dia: [{
          next: '相遇',
          opt: [{ dia: [{ next: '不存在的场景' }] }],
        }],
      },
      { scene: '相遇', dia: [] },
    ];

    expect(getRelationJumps(scenes[0])).toEqual([
      { target: '相遇', type: 'direct' },
      { target: '不存在的场景', type: 'option' },
    ]);
    const result = buildRelationDiagnostics(scenes);
    expect(result.brokenJumpCount).toBe(1);
    expect(result.items[0].brokenTargets).toEqual(['不存在的场景']);
    expect(result.items[1].incoming).toEqual(['开场']);
  });

  it('将孤立场景和重名场景列为需要处理的问题', () => {
    const result = buildRelationDiagnostics([
      { scene: '孤岛', dia: [] },
      { scene: '重复', dia: [] },
      { scene: '重复', dia: [] },
    ]);

    expect(result.isolatedCount).toBe(3);
    expect(result.duplicateCount).toBe(2);
    expect(result.issueCount).toBe(3);
    expect(result.items[0].isolated).toBe(true);
    expect(result.items[1].duplicateName).toBe(true);
  });
});
