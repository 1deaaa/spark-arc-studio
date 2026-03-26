import { describe, expect, it } from 'vitest';

import {
  buildAutoWriteResumeActions,
  collectOverwriteTargets,
  describeAutoWriteState,
} from '../autoWriteState';

describe('autoWriteState utilities', () => {
  it('builds resume next action for chapter paused state', () => {
    const actions = buildAutoWriteResumeActions({
      status: 'chapter_paused',
      availableResumeChapterIndex: 3,
    }, 6);

    expect(actions).toEqual([
      {
        key: 'resume-next',
        startChapterIndex: 3,
        label: '从第 4 章继续',
        intent: 'resume-next',
      },
    ]);
  });

  it('builds restart current action for interrupted state', () => {
    const actions = buildAutoWriteResumeActions({
      status: 'interrupted',
      availableRestartChapterIndex: 1,
    }, 4);

    expect(actions).toEqual([
      {
        key: 'restart-current',
        startChapterIndex: 1,
        label: '从第 2 章重跑',
        intent: 'restart-current',
      },
    ]);
  });

  it('collects overwrite targets from start chapter index', () => {
    const targets = collectOverwriteTargets([
      { chapterIndex: 0, filename: 'A.arc', exists: true },
      { chapterIndex: 1, filename: 'B.arc', exists: false },
      { chapterIndex: 2, filename: 'C.arc', exists: true },
    ], 1);

    expect(targets).toEqual([
      { chapterIndex: 2, filename: 'C.arc', exists: true },
    ]);
  });

  it('describes interrupted state with current chapter title', () => {
    expect(describeAutoWriteState({
      status: 'interrupted',
      currentChapterTitle: '风雪夜归',
    })).toBe('上次运行在 风雪夜归 中断，可从该章重跑。');
  });
});