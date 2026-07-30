import { describe, expect, it } from 'vitest';
import {
  addVisitedIndex,
  filterItemsByVisited,
  normalizeVisitedIndexes,
} from '@/utils/playerProgress';

describe('播放器渐进目录进度', () => {
  it('将旧缓存迁移为从开头到当前位置的已访问集合', () => {
    expect(normalizeVisitedIndexes(undefined, 2, 5)).toEqual([0, 1, 2]);
  });

  it('去重、排序并移除越界索引，同时保留当前位置', () => {
    expect(normalizeVisitedIndexes([3, 1, 1, -1, 8], 2, 5)).toEqual([1, 2, 3]);
  });

  it('只在关闭完整目录时过滤未访问项目', () => {
    const items = ['第一幕', '第二幕', '第三幕'];
    expect(filterItemsByVisited(items, [0, 2], false)).toEqual(['第一幕', '第三幕']);
    expect(filterItemsByVisited(items, [0], true)).toEqual(items);
  });

  it('访问新项目后立即将其加入目录', () => {
    expect(addVisitedIndex([0], 2, 4)).toEqual([0, 2]);
  });
});
