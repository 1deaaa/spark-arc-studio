import { afterEach, describe, expect, it, vi } from 'vitest';
import { mount } from '@vue/test-utils';
import { defineComponent, nextTick, ref } from 'vue';
import { useChatActions } from '@/composables/useChatActions';

function setScrollMetrics(el: HTMLElement, metrics: { scrollTop: number; scrollHeight: number; clientHeight: number }) {
  let scrollTop = metrics.scrollTop;
  Object.defineProperties(el, {
    scrollTop: {
      configurable: true,
      get: () => scrollTop,
      set: (value) => { scrollTop = Number(value) || 0; },
    },
    scrollHeight: {
      configurable: true,
      get: () => metrics.scrollHeight,
    },
    clientHeight: {
      configurable: true,
      get: () => metrics.clientHeight,
    },
  });
}

function mountHarness(editImplementation?: (id: string | number, content: string) => Promise<unknown>) {
  const send = vi.fn(async () => undefined);
  const clear = vi.fn(async () => undefined);
  const editMessage = vi.fn(editImplementation || (async () => undefined));
  const deleteMessage = vi.fn(async () => undefined);

  const Harness = defineComponent({
    template: '<div ref="listEl"><div class="chat-list-content" /></div>',
    setup(_, { expose }) {
      const listEl = ref<HTMLElement | null>(null);
      const sending = ref(false);
      const history = ref<any[]>([]);
      const actions = useChatActions({
        getSending: () => sending.value,
        getHistory: () => history.value,
        send,
        clear,
        editMessage,
        deleteMessage,
      }, {
        listRef: listEl,
      });

      expose({ actions, listEl, sending, history, editMessage });
      return { listEl };
    },
  });

  return mount(Harness);
}

function installResizeObserverMock() {
  const callbacks: Array<() => void> = [];
  let frameId = 0;
  class ResizeObserverMock {
    constructor(private readonly callback: () => void) {
      callbacks.push(callback);
    }
    observe() {}
    disconnect() {}
  }
  vi.stubGlobal('ResizeObserver', ResizeObserverMock);
  vi.stubGlobal('requestAnimationFrame', (callback: FrameRequestCallback) => {
    const id = ++frameId;
    queueMicrotask(() => callback(0));
    return id;
  });
  vi.stubGlobal('cancelAnimationFrame', () => undefined);
  return callbacks;
}

function mountDelayedListHarness() {
  const Harness = defineComponent({
    template: '<div v-if="listVisible" ref="listEl"><div class="chat-list-content" /></div>',
    setup(_, { expose }) {
      const listEl = ref<HTMLElement | null>(null);
      const listVisible = ref(false);
      const sending = ref(true);
      const actions = useChatActions({
        getSending: () => sending.value,
        getHistory: () => [],
        send: async () => undefined,
        clear: async () => undefined,
        editMessage: async () => undefined,
        deleteMessage: async () => undefined,
      }, { listRef: listEl });

      expose({ actions, listEl, listVisible, sending });
      return { listEl, listVisible };
    },
  });

  return mount(Harness);
}

describe('useChatActions 聊天自动滚动开关', () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  it('消息列表进入页面后自动定位到最新消息', async () => {
    const wrapper = mountHarness();
    const exposed = wrapper.vm as any;
    const el = exposed.listEl as HTMLElement;
    setScrollMetrics(el, { scrollTop: 0, scrollHeight: 1000, clientHeight: 320 });

    await nextTick();
    await nextTick();

    expect(el.scrollTop).toBe(1000);
  });

  it('程序滚动触发 scroll 事件时不会误关闭后续自动下滑', async () => {
    vi.useFakeTimers();
    vi.setSystemTime(0);
    vi.spyOn(performance, 'now').mockReturnValue(0);

    const wrapper = mountHarness();
    await nextTick();
    await nextTick();

    const exposed = wrapper.vm as any;
    const el = exposed.listEl as HTMLElement;
    setScrollMetrics(el, { scrollTop: 20, scrollHeight: 1000, clientHeight: 320 });

    exposed.actions.scrollToBottom();
    await nextTick();
    expect(el.scrollTop).toBe(1000);

    setScrollMetrics(el, { scrollTop: 260, scrollHeight: 1000, clientHeight: 320 });
    el.dispatchEvent(new Event('scroll'));

    vi.mocked(performance.now).mockReturnValue(200);
    setScrollMetrics(el, { scrollTop: 260, scrollHeight: 1200, clientHeight: 320 });
    exposed.actions.scrollToBottom();
    await nextTick();

    expect(el.scrollTop).toBe(1200);
  });

  it('用户主动上滚后仍会暂停非强制自动下滑', async () => {
    vi.spyOn(performance, 'now').mockReturnValue(1000);

    const wrapper = mountHarness();
    await nextTick();
    await nextTick();

    const exposed = wrapper.vm as any;
    const el = exposed.listEl as HTMLElement;
    setScrollMetrics(el, { scrollTop: 0, scrollHeight: 1000, clientHeight: 320 });

    el.dispatchEvent(new WheelEvent('wheel', { deltaY: -30 }));
    el.dispatchEvent(new Event('scroll'));
    exposed.actions.scrollToBottom();
    await nextTick();

    expect(el.scrollTop).toBe(0);

    exposed.actions.scrollToBottom(true);
    await nextTick();

    expect(el.scrollTop).toBe(1000);
  });

  it('用户在程序滚动保护窗口内主动上滚，也会暂停后续非强制自动下滑', async () => {
    vi.useFakeTimers();
    vi.setSystemTime(0);
    vi.spyOn(performance, 'now').mockReturnValue(0);

    const wrapper = mountHarness();
    await nextTick();
    await nextTick();

    const exposed = wrapper.vm as any;
    const el = exposed.listEl as HTMLElement;
    setScrollMetrics(el, { scrollTop: 20, scrollHeight: 1000, clientHeight: 320 });

    exposed.actions.scrollToBottom();
    await nextTick();
    expect(el.scrollTop).toBe(1000);

    vi.mocked(performance.now).mockReturnValue(80);
    el.dispatchEvent(new WheelEvent('wheel'));
    setScrollMetrics(el, { scrollTop: 260, scrollHeight: 1000, clientHeight: 320 });
    el.dispatchEvent(new Event('scroll'));

    setScrollMetrics(el, { scrollTop: 260, scrollHeight: 1200, clientHeight: 320 });
    exposed.actions.scrollToBottom();
    await nextTick();

    expect(el.scrollTop).toBe(260);
  });

  it('流式回复被上滚打断后暂停跟随，手动触底后在本轮恢复跟随', async () => {
    vi.spyOn(performance, 'now').mockReturnValue(1000);

    const wrapper = mountHarness();
    await nextTick();
    await nextTick();

    const exposed = wrapper.vm as any;
    const el = exposed.listEl as HTMLElement;
    setScrollMetrics(el, { scrollTop: 650, scrollHeight: 1000, clientHeight: 320 });

    exposed.sending = true;
    await nextTick();
    await nextTick();

    // 即使仍处于距底部 60px 的阈值内，明确的向上滚轮意图也必须立即打断。
    setScrollMetrics(el, { scrollTop: 640, scrollHeight: 1000, clientHeight: 320 });
    el.dispatchEvent(new WheelEvent('wheel', { deltaY: -30 }));
    el.dispatchEvent(new Event('scroll'));

    setScrollMetrics(el, { scrollTop: 640, scrollHeight: 1200, clientHeight: 320 });
    exposed.actions.scrollToBottom();
    await nextTick();
    expect(el.scrollTop).toBe(640);

    // 用户手动回到底部后，本轮应重新跟随新增长的正文。
    setScrollMetrics(el, { scrollTop: 880, scrollHeight: 1200, clientHeight: 320 });
    el.dispatchEvent(new Event('scroll'));
    setScrollMetrics(el, { scrollTop: 880, scrollHeight: 1400, clientHeight: 320 });
    exposed.actions.scrollToBottom();
    await nextTick();
    expect(el.scrollTop).toBe(1400);
  });

  it('流式回复开始后才挂载的消息列表仍能识别用户上滚和重新触底', async () => {
    vi.spyOn(performance, 'now').mockReturnValue(1000);

    const wrapper = mountDelayedListHarness();
    await nextTick();
    const exposed = wrapper.vm as any;

    exposed.listVisible = true;
    await nextTick();
    await nextTick();

    const el = exposed.listEl as HTMLElement;
    setScrollMetrics(el, { scrollTop: 680, scrollHeight: 1000, clientHeight: 320 });
    el.dispatchEvent(new WheelEvent('wheel', { deltaY: -40 }));
    setScrollMetrics(el, { scrollTop: 520, scrollHeight: 1000, clientHeight: 320 });
    el.dispatchEvent(new Event('scroll'));

    setScrollMetrics(el, { scrollTop: 520, scrollHeight: 1200, clientHeight: 320 });
    exposed.actions.scrollToBottom();
    await nextTick();
    expect(el.scrollTop).toBe(520);

    setScrollMetrics(el, { scrollTop: 880, scrollHeight: 1200, clientHeight: 320 });
    el.dispatchEvent(new Event('scroll'));
    setScrollMetrics(el, { scrollTop: 880, scrollHeight: 1400, clientHeight: 320 });
    exposed.actions.scrollToBottom();
    await nextTick();
    expect(el.scrollTop).toBe(1400);
  });

  it('编辑重发在请求尚未完成时就恢复自动跟随', async () => {
    let resolveEdit!: () => void;
    const editRequest = new Promise<void>(resolve => { resolveEdit = resolve; });
    const wrapper = mountHarness(async () => editRequest);
    await nextTick();
    await nextTick();

    const exposed = wrapper.vm as any;
    const el = exposed.listEl as HTMLElement;
    setScrollMetrics(el, { scrollTop: 0, scrollHeight: 1000, clientHeight: 320 });
    el.dispatchEvent(new Event('scroll'));
    exposed.actions.editingContent.value = '编辑后的内容';

    const savePromise = exposed.actions.saveEdit('message-1');
    await nextTick();
    expect(exposed.editMessage).toHaveBeenCalledWith('message-1', '编辑后的内容');
    expect(el.scrollTop).toBe(1000);

    resolveEdit();
    await savePromise;
  });

  it('消息内容尺寸变化时立即跟随底部，且不覆盖用户主动上滚', async () => {
    const callbacks = installResizeObserverMock();
    const wrapper = mountHarness();
    await nextTick();
    await nextTick();

    const exposed = wrapper.vm as any;
    const el = exposed.listEl as HTMLElement;
    setScrollMetrics(el, { scrollTop: 680, scrollHeight: 1000, clientHeight: 320 });
    exposed.sending = true;
    await nextTick();

    setScrollMetrics(el, { scrollTop: 680, scrollHeight: 1250, clientHeight: 320 });
    callbacks.at(-1)?.();
    await nextTick();
    await nextTick();
    expect(el.scrollTop).toBe(1250);

    el.dispatchEvent(new WheelEvent('wheel', { deltaY: -40 }));
    setScrollMetrics(el, { scrollTop: 500, scrollHeight: 1400, clientHeight: 320 });
    el.dispatchEvent(new Event('scroll'));
    callbacks.at(-1)?.();
    await nextTick();
    await nextTick();
    expect(el.scrollTop).toBe(500);
  });
});
