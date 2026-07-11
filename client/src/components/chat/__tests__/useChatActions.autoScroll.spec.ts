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

function mountHarness() {
  const send = vi.fn(async () => undefined);
  const clear = vi.fn(async () => undefined);
  const editMessage = vi.fn(async () => undefined);
  const deleteMessage = vi.fn(async () => undefined);

  const Harness = defineComponent({
    template: '<div ref="listEl" />',
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

      expose({ actions, listEl, sending, history });
      return { listEl };
    },
  });

  return mount(Harness);
}

describe('useChatActions 聊天自动滚动开关', () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.useRealTimers();
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

  it('流式回复被上滚打断后本轮不再恢复，下一轮回复才重新启用', async () => {
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
    exposed.actions.scrollToBottom(true);
    await nextTick();
    expect(el.scrollTop).toBe(640);

    // 本轮即使用户手动回到底部，也不再重新跟随新增长的正文。
    setScrollMetrics(el, { scrollTop: 880, scrollHeight: 1200, clientHeight: 320 });
    el.dispatchEvent(new Event('scroll'));
    setScrollMetrics(el, { scrollTop: 880, scrollHeight: 1400, clientHeight: 320 });
    exposed.actions.scrollToBottom();
    await nextTick();
    expect(el.scrollTop).toBe(880);

    exposed.sending = false;
    await nextTick();
    exposed.sending = true;
    await nextTick();
    await nextTick();
    expect(el.scrollTop).toBe(1400);
  });
});
