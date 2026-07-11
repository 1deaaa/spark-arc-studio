import { afterEach, describe, expect, it, vi } from 'vitest';
import { createAutoSaveScheduler } from '../autoSaveScheduler';

describe('统一自动保存调度器', () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it('连续输入只保存最后一份载荷', async () => {
    vi.useFakeTimers();
    const persisted: string[] = [];
    const scheduler = createAutoSaveScheduler<string>(async value => {
      persisted.push(value);
    }, { delay: 800, maxWait: 5000 });

    scheduler.schedule('第一版');
    await vi.advanceTimersByTimeAsync(500);
    scheduler.schedule('第二版');
    await vi.advanceTimersByTimeAsync(799);
    expect(persisted).toEqual([]);
    await vi.advanceTimersByTimeAsync(1);

    expect(persisted).toEqual(['第二版']);
  });

  it('持续输入达到最长等待时间后仍会落盘', async () => {
    vi.useFakeTimers();
    const persisted: number[] = [];
    const scheduler = createAutoSaveScheduler<number>(async value => {
      persisted.push(value);
    }, { delay: 800, maxWait: 5000 });

    for (let index = 1; index <= 10; index += 1) {
      scheduler.schedule(index);
      await vi.advanceTimersByTimeAsync(500);
    }

    expect(persisted).toEqual([10]);
  });

  it('显式刷新立即保存待处理内容', async () => {
    vi.useFakeTimers();
    const persisted: string[] = [];
    const scheduler = createAutoSaveScheduler<string>(async value => {
      persisted.push(value);
    });

    scheduler.schedule('离开页面前刷新');
    expect(await scheduler.flush()).toBe(true);
    expect(persisted).toEqual(['离开页面前刷新']);
  });
});
