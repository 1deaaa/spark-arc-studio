import { defineComponent, nextTick, ref } from 'vue';
import { mount } from '@vue/test-utils';
import { useProgressiveIdleList } from '@/composables/useProgressiveIdleList';

type IdleCallback = (deadline: IdleDeadline) => void;

function installIdleQueue() {
  const callbacks = new Map<number, IdleCallback>();
  let nextId = 1;
  const requestIdleCallback = vi.fn((callback: IdleCallback) => {
    const id = nextId++;
    callbacks.set(id, callback);
    return id;
  });
  const cancelIdleCallback = vi.fn((id: number) => callbacks.delete(id));

  vi.stubGlobal('requestIdleCallback', requestIdleCallback);
  vi.stubGlobal('cancelIdleCallback', cancelIdleCallback);
  Object.defineProperty(window, 'requestIdleCallback', { configurable: true, value: requestIdleCallback });
  Object.defineProperty(window, 'cancelIdleCallback', { configurable: true, value: cancelIdleCallback });

  const runNext = async () => {
    const entry = callbacks.entries().next().value as [number, IdleCallback] | undefined;
    if (!entry) return false;
    callbacks.delete(entry[0]);
    entry[1]({ didTimeout: false, timeRemaining: () => 16 } as IdleDeadline);
    await nextTick();
    return true;
  };

  return { callbacks, cancelIdleCallback, runNext };
}

describe('useProgressiveIdleList', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('等待显式释放后，在空闲片段分批挂载最近内容', async () => {
    const idle = installIdleQueue();
    const source = ref(Array.from({ length: 14 }, (_, index) => index));
    let api: ReturnType<typeof useProgressiveIdleList<number>> | null = null;

    const wrapper = mount(defineComponent({
      setup() {
        api = useProgressiveIdleList(() => source.value, {
          initialBatchSize: 4,
          batchSize: 5,
        });
        return () => null;
      },
    }));

    api!.block();
    expect(api!.pending.value).toBe(true);
    expect(api!.visibleItems.value).toEqual([]);
    expect(idle.callbacks.size).toBe(0);

    api!.release();
    expect(api!.visibleItems.value).toEqual([]);
    expect(idle.callbacks.size).toBe(1);

    await idle.runNext();
    expect(api!.pending.value).toBe(false);
    expect(api!.visibleItems.value).toEqual([10, 11, 12, 13]);

    await idle.runNext();
    expect(api!.visibleItems.value).toEqual([5, 6, 7, 8, 9, 10, 11, 12, 13]);

    await idle.runNext();
    expect(api!.visibleItems.value).toEqual(source.value);
    expect(idle.callbacks.size).toBe(0);

    wrapper.unmount();
  });

  it('新一轮切换会取消上一轮尚未执行的空闲任务', () => {
    const idle = installIdleQueue();
    const source = ref(Array.from({ length: 12 }, (_, index) => index));
    let api: ReturnType<typeof useProgressiveIdleList<number>> | null = null;

    const wrapper = mount(defineComponent({
      setup() {
        api = useProgressiveIdleList(() => source.value, { initialBatchSize: 3 });
        return () => null;
      },
    }));

    api!.block();
    api!.release();
    expect(idle.callbacks.size).toBe(1);

    api!.block();
    expect(idle.cancelIdleCallback).toHaveBeenCalledTimes(1);
    expect(idle.callbacks.size).toBe(0);
    expect(api!.visibleItems.value).toEqual([]);

    wrapper.unmount();
  });

  it('异步历史到达后仍按批次挂载，而不是一次性进入 DOM', async () => {
    const idle = installIdleQueue();
    const source = ref<number[]>([]);
    let api: ReturnType<typeof useProgressiveIdleList<number>> | null = null;

    const wrapper = mount(defineComponent({
      setup() {
        api = useProgressiveIdleList(() => source.value, { initialBatchSize: 2 });
        return () => null;
      },
    }));

    api!.block();
    api!.release();
    expect(api!.pending.value).toBe(false);

    source.value = [1, 2, 3, 4, 5];
    expect(api!.pending.value).toBe(true);
    expect(api!.visibleItems.value).toEqual([]);

    await idle.runNext();
    expect(api!.visibleItems.value).toEqual([4, 5]);

    wrapper.unmount();
  });
});
