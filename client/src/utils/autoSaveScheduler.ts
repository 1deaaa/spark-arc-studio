export interface AutoSaveSchedulerOptions {
  delay?: number;
  maxWait?: number;
  onError?: (error: unknown) => void;
}

export interface AutoSaveScheduler<T> {
  schedule: (payload: T) => void;
  flush: () => Promise<boolean>;
  cancel: () => void;
  hasPending: () => boolean;
}

/**
 * 创建“最新值优先”的自动保存调度器。
 * 连续输入只保留最后一份载荷，实际写入严格串行，并由 maxWait 保证长时间输入也会周期性落盘。
 */
export function createAutoSaveScheduler<T>(
  persist: (payload: T) => Promise<void>,
  options: AutoSaveSchedulerOptions = {},
): AutoSaveScheduler<T> {
  const delay = Math.max(0, options.delay ?? 800);
  const maxWait = Math.max(delay, options.maxWait ?? 5000);
  let pending: T | undefined;
  let delayTimer: ReturnType<typeof setTimeout> | null = null;
  let maxWaitTimer: ReturnType<typeof setTimeout> | null = null;
  let active: Promise<boolean> = Promise.resolve(true);

  function clearTimers() {
    if (delayTimer) clearTimeout(delayTimer);
    if (maxWaitTimer) clearTimeout(maxWaitTimer);
    delayTimer = null;
    maxWaitTimer = null;
  }

  async function flush(): Promise<boolean> {
    clearTimers();
    if (pending === undefined) return active;

    const payload = pending;
    pending = undefined;
    active = active
      .catch(() => false)
      .then(async () => {
        try {
          await persist(payload);
          return true;
        } catch (error) {
          options.onError?.(error);
          return false;
        }
      });

    const succeeded = await active;
    if (pending !== undefined) {
      const latestSucceeded = await flush();
      return succeeded && latestSucceeded;
    }
    return succeeded;
  }

  function schedule(payload: T) {
    pending = payload;
    if (delayTimer) clearTimeout(delayTimer);
    delayTimer = setTimeout(() => {
      delayTimer = null;
      void flush();
    }, delay);
    if (!maxWaitTimer) {
      maxWaitTimer = setTimeout(() => {
        maxWaitTimer = null;
        void flush();
      }, maxWait);
    }
  }

  function cancel() {
    clearTimers();
    pending = undefined;
  }

  return {
    schedule,
    flush,
    cancel,
    hasPending: () => pending !== undefined,
  };
}
