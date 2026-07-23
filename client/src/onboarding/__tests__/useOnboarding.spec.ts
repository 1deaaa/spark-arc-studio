import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  destroy: vi.fn(),
  start: vi.fn(),
  engine: {
    isActive: { value: true },
  },
}));

vi.mock('../engine/OnboardingEngine', () => ({
  getOnboardingEngine: () => ({
    ...mocks.engine,
    destroy: mocks.destroy,
    start: mocks.start,
  }),
}));

vi.mock('vue', async (importOriginal) => {
  const vue = await importOriginal<typeof import('vue')>();
  return { ...vue, onUnmounted: vi.fn() };
});

import { useOnboarding } from '../engine/useOnboarding';

describe('useOnboarding 页面教程重放', () => {
  beforeEach(() => {
    mocks.destroy.mockClear();
    mocks.start.mockClear();
  });

  it('只允许页面标题入口启动 page-* 场景', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => undefined);
    const { replayPage } = useOnboarding();

    replayPage('mobile-workspace');

    expect(mocks.destroy).not.toHaveBeenCalled();
    expect(mocks.start).not.toHaveBeenCalled();
    expect(warn).toHaveBeenCalledOnce();
    warn.mockRestore();
  });

  it('重看页面教程时终止旧场景并只启动指定页面', () => {
    const { replayPage } = useOnboarding();

    replayPage('page-world');

    expect(mocks.destroy).toHaveBeenCalledOnce();
    expect(mocks.start).toHaveBeenCalledOnce();
    expect(mocks.start).toHaveBeenCalledWith('page-world');
  });
});
