import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch, type ComputedRef, type Ref } from 'vue';

type CancelIdleWork = () => void;

type ProgressiveIdleListOptions = {
  initialBatchSize?: number;
  batchSize?: number;
  idleTimeout?: number;
  hydrateOnMount?: boolean;
  autoComplete?: boolean;
  beforeBatch?: (firstBatch: boolean) => unknown;
  afterBatch?: (snapshot: unknown, firstBatch: boolean) => void;
};

function scheduleIdleWork(callback: () => void, timeout: number): CancelIdleWork {
  if (typeof window !== 'undefined' && typeof window.requestIdleCallback === 'function') {
    const handle = window.requestIdleCallback(callback, { timeout });
    return () => window.cancelIdleCallback(handle);
  }

  const handle = globalThis.setTimeout(callback, 0);
  return () => globalThis.clearTimeout(handle);
}

/**
 * 在交互动画结束后分批挂载列表，避免一次创建大量 Vue 节点长时间占用主线程。
 * `block` 与 `release` 分离，使调用方可以用真实的动画完成事件控制释放时机。
 */
export function useProgressiveIdleList<T>(
  source: () => T[],
  options: ProgressiveIdleListOptions = {},
): {
  visibleItems: ComputedRef<T[]>;
  pending: Ref<boolean>;
  block: () => void;
  release: () => void;
  showAll: () => void;
  loadMore: () => void;
} {
  const initialBatchSize = Math.max(1, options.initialBatchSize ?? 6);
  const batchSize = Math.max(1, options.batchSize ?? 6);
  const idleTimeout = Math.max(50, options.idleTimeout ?? 400);
  const autoComplete = options.autoComplete !== false;

  const initialLength = source().length;
  const pending = ref(Boolean(options.hydrateOnMount && initialLength > 0));
  const blocked = ref(false);
  const awaitingSource = ref(Boolean(options.hydrateOnMount && initialLength === 0));
  // 首次渲染前就截断列表，不能等 mounted 后再隐藏，否则长历史已经完成整棵 DOM 挂载。
  const visibleStart = ref(options.hydrateOnMount ? initialLength : 0);
  let epoch = 0;
  let cancelIdleWork: CancelIdleWork | null = null;

  const cancelScheduledWork = () => {
    cancelIdleWork?.();
    cancelIdleWork = null;
  };

  const scheduleNextBatch = (currentEpoch: number, firstBatch: boolean) => {
    cancelScheduledWork();
    cancelIdleWork = scheduleIdleWork(() => {
      cancelIdleWork = null;
      if (currentEpoch !== epoch || blocked.value) return;

      const snapshot = options.beforeBatch?.(firstBatch);
      const total = source().length;
      visibleStart.value = Math.max(
        0,
        firstBatch ? total - initialBatchSize : visibleStart.value - batchSize,
      );
      pending.value = false;

      nextTick(() => {
        if (currentEpoch !== epoch || blocked.value) return;
        options.afterBatch?.(snapshot, firstBatch);
        if (autoComplete && visibleStart.value > 0) {
          scheduleNextBatch(currentEpoch, false);
        }
      });
    }, idleTimeout);
  };

  const startHydration = () => {
    const total = source().length;
    if (total <= 0) {
      visibleStart.value = 0;
      pending.value = false;
      awaitingSource.value = true;
      return;
    }

    awaitingSource.value = false;
    pending.value = true;
    visibleStart.value = total;
    scheduleNextBatch(epoch, true);
  };

  const block = () => {
    epoch += 1;
    cancelScheduledWork();
    blocked.value = true;
    awaitingSource.value = true;
    pending.value = true;
    visibleStart.value = source().length;
  };

  const release = () => {
    if (!blocked.value) return;
    blocked.value = false;
    startHydration();
  };

  const showAll = () => {
    epoch += 1;
    cancelScheduledWork();
    blocked.value = false;
    awaitingSource.value = false;
    pending.value = false;
    visibleStart.value = 0;
  };

  const loadMore = () => {
    if (blocked.value || pending.value || visibleStart.value <= 0 || cancelIdleWork) return;
    scheduleNextBatch(epoch, false);
  };

  watch(
    () => source().length,
    (length) => {
      if (length === 0) {
        visibleStart.value = 0;
        pending.value = false;
        return;
      }
      if (!blocked.value && awaitingSource.value && length > 0) {
        startHydration();
      }
    },
    { flush: 'sync' },
  );

  onMounted(() => {
    if (options.hydrateOnMount) startHydration();
  });

  onBeforeUnmount(() => {
    epoch += 1;
    cancelScheduledWork();
  });

  const visibleItems = computed(() => {
    if (blocked.value) return [];
    return source().slice(visibleStart.value);
  });

  return { visibleItems, pending, block, release, showAll, loadMore };
}
