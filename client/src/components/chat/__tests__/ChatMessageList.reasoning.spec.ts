import { afterEach, describe, expect, it, vi } from 'vitest';
import { mount } from '@vue/test-utils';
import { defineComponent, nextTick } from 'vue';
import ChatMessageList from '../ChatMessageList.vue';
import { i18n } from '@/i18n';

vi.mock('naive-ui', async () => {
  const actual = await vi.importActual<typeof import('naive-ui')>('naive-ui');
  return {
    ...actual,
    useMessage: () => ({
      success: vi.fn(),
      error: vi.fn(),
      warning: vi.fn(),
      info: vi.fn(),
    }),
  };
});

vi.mock('@/components/share/MarkdownRenderer.vue', () => ({
  default: defineComponent({
    name: 'MarkdownRenderer',
    props: {
      content: { type: String, default: '' },
      streaming: { type: Boolean, default: false },
    },
    template: '<div class="mock-markdown"><div class="node-slot">{{ content }}</div></div>',
  }),
}));

vi.mock('@/components/share/AgentAvatar.vue', () => ({
  default: defineComponent({
    name: 'AgentAvatar',
    template: '<span class="mock-agent-avatar" />',
  }),
}));

afterEach(() => {
  vi.restoreAllMocks();
  vi.useRealTimers();
});

describe('ChatMessageList 深度思考块展开性能契约', () => {
  it('长思考内容展开和收起不会触发递归渲染，并保留 Markdown 渲染', async () => {
    vi.useFakeTimers();
    const longReasoning = Array.from({ length: 260 }, (_, index) => (
      `### 推理段 ${index + 1}\n- 这是用于复现移动端长内容展开的测试文本。\n`
    )).join('\n');

    const wrapper = mount(ChatMessageList, {
      props: {
        history: [
          {
            id: 'assistant-1',
            role: 'assistant',
            content: '',
            segments: [
              {
                type: 'reasoning',
                text: longReasoning,
                source_agent: 'agent_director',
              },
              {
                type: 'text',
                text: '正文已经生成。',
              },
            ],
          },
        ],
        sending: false,
      },
      global: {
        plugins: [i18n],
        stubs: {
          NButton: defineComponent({ template: '<button><slot /><slot name="icon" /></button>' }),
          NTooltip: defineComponent({ template: '<span><slot name="trigger" /><slot /></span>' }),
          NPopover: defineComponent({ template: '<span><slot name="trigger" /><slot /></span>' }),
          NInput: defineComponent({ template: '<textarea />' }),
          SparkAlert: defineComponent({ template: '<div><slot /></div>' }),
          ContextCompactionSegment: true,
          ToolTraceSegment: true,
        },
      },
    });

    const toggle = wrapper.find('.reasoning-toggle');
    expect(toggle.exists()).toBe(true);

    await toggle.trigger('click');
    await nextTick();
    vi.runOnlyPendingTimers();
    await nextTick();

    const panel = wrapper.find('.reasoning-content-wrapper');
    expect(panel.classes()).toContain('is-expanded');
    expect(wrapper.find('.mock-markdown').text()).toContain('推理段 260');
    expect(wrapper.find('.reasoning-bubble').exists()).toBe(true);
    expect(wrapper.find('.reasoning-block').exists()).toBe(true);
    expect(wrapper.find('.reasoning-bubble').classes()).toContain('reasoning-bubble');

    await toggle.trigger('click');
    await nextTick();
    vi.runOnlyPendingTimers();
    await nextTick();

    expect(wrapper.find('.reasoning-content-wrapper').classes()).not.toContain('is-expanded');
  });

  it('展开动画过程中再次点击可以立即切换为收起状态', async () => {
    vi.useFakeTimers();
    const wrapper = mount(ChatMessageList, {
      props: {
        history: [
          {
            id: 'assistant-2',
            role: 'assistant',
            content: '',
            segments: [
              {
                type: 'reasoning',
                text: '第一行\n\n第二行\n\n第三行',
                source_agent: 'agent_director',
              },
            ],
          },
        ],
        sending: false,
      },
      global: {
        plugins: [i18n],
        stubs: {
          NButton: defineComponent({ template: '<button><slot /><slot name="icon" /></button>' }),
          NTooltip: defineComponent({ template: '<span><slot name="trigger" /><slot /></span>' }),
          NPopover: defineComponent({ template: '<span><slot name="trigger" /><slot /></span>' }),
          NInput: defineComponent({ template: '<textarea />' }),
          SparkAlert: defineComponent({ template: '<div><slot /></div>' }),
          ContextCompactionSegment: true,
          ToolTraceSegment: true,
        },
      },
    });

    const toggle = wrapper.find('.reasoning-toggle');
    await toggle.trigger('click');
    await nextTick();
    await toggle.trigger('click');
    await nextTick();

    const panel = wrapper.find('.reasoning-content-wrapper');
    expect(panel.classes()).toContain('is-closing');

    vi.runOnlyPendingTimers();
    await nextTick();
    expect(wrapper.find('.reasoning-content-wrapper').classes()).not.toContain('is-expanded');
  });

  it('流式思考首次自动展开，并在正文开始输出后自动收起', async () => {
    vi.useFakeTimers();
    vi.spyOn(window, 'requestAnimationFrame').mockImplementation((callback: FrameRequestCallback) => {
      callback(performance.now());
      return 1;
    });

    const reasoningSegment = {
      type: 'reasoning',
      text: '第一段流式推理\n第二段流式推理',
      source_agent: 'agent_director',
    };

    const wrapper = mount(ChatMessageList, {
      props: {
        history: [
          {
            id: 'assistant-4',
            role: 'assistant',
            content: '',
            segments: [reasoningSegment],
          },
        ],
        sending: true,
      },
      global: {
        plugins: [i18n],
        stubs: {
          NButton: defineComponent({ template: '<button><slot /><slot name="icon" /></button>' }),
          NTooltip: defineComponent({ template: '<span><slot name="trigger" /><slot /></span>' }),
          NPopover: defineComponent({ template: '<span><slot name="trigger" /><slot /></span>' }),
          NInput: defineComponent({ template: '<textarea />' }),
          SparkAlert: defineComponent({ template: '<div><slot /></div>' }),
          ContextCompactionSegment: true,
          ToolTraceSegment: true,
        },
      },
    });

    await nextTick();
    await Promise.resolve();
    await nextTick();
    vi.runOnlyPendingTimers();
    await nextTick();

    expect(wrapper.find('.reasoning-content-wrapper').classes()).toContain('is-expanded');

    await wrapper.setProps({
      history: [
        {
          id: 'assistant-4',
          role: 'assistant',
          content: '正文已经开始输出。',
          segments: [
            reasoningSegment,
            {
              type: 'text',
              text: '正文已经开始输出。',
            },
          ],
        },
      ],
      sending: true,
    });

    await nextTick();
    vi.runOnlyPendingTimers();
    await nextTick();

    expect(wrapper.find('.reasoning-content-wrapper').classes()).not.toContain('is-expanded');
  });

  it('流式思考窗口随内容撑高到五行后保持稳定', async () => {
    vi.useFakeTimers();
    vi.spyOn(window, 'requestAnimationFrame').mockImplementation((callback: FrameRequestCallback) => {
      callback(performance.now());
      return 1;
    });
    const actualGetComputedStyle = window.getComputedStyle.bind(window);
    vi.spyOn(window, 'getComputedStyle').mockImplementation((element: Element) => {
      const style = actualGetComputedStyle(element);
      return new Proxy(style, {
        get(target, property, receiver) {
          if (element.classList?.contains('reasoning-inner')) {
            if (property === 'paddingTop') return '4px';
            if (property === 'paddingBottom') return '8px';
            if (property === 'borderTopWidth') return '1px';
            if (property === 'borderBottomWidth') return '0px';
            if (property === 'lineHeight') return '20px';
            if (property === 'fontSize') return '15px';
          }
          if (element.classList?.contains('reasoning-markdown')) {
            if (property === 'lineHeight') return '20px';
            if (property === 'fontSize') return '15px';
          }
          const value = Reflect.get(target, property, receiver);
          return typeof value === 'function' ? value.bind(target) : value;
        },
      }) as CSSStyleDeclaration;
    });
    vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockImplementation(function getMockRect(this: HTMLElement) {
      const el = this;
      const lineCount = Math.max(1, (el.textContent || '').split('\n').length);
      const contentHeight = (lineCount * 20) + 4;
      if (el.classList?.contains('reasoning-inner')) {
        return { width: 420, height: contentHeight + 9, top: 0, left: 0, right: 420, bottom: contentHeight + 9, x: 0, y: 0, toJSON: () => ({}) } as DOMRect;
      }
      if (el.classList?.contains('node-slot')) {
        return { width: 420, height: contentHeight, top: 0, left: 0, right: 420, bottom: contentHeight, x: 0, y: 0, toJSON: () => ({}) } as DOMRect;
      }
      return { width: 420, height: 0, top: 0, left: 0, right: 420, bottom: 0, x: 0, y: 0, toJSON: () => ({}) } as DOMRect;
    });

    const wrapper = mount(ChatMessageList, {
      props: {
        history: [
          {
            id: 'assistant-5',
            role: 'assistant',
            content: '',
            segments: [
              {
                type: 'reasoning',
                text: '第一段流式推理',
                source_agent: 'agent_director',
              },
            ],
          },
        ],
        sending: true,
      },
      global: {
        plugins: [i18n],
        stubs: {
          NButton: defineComponent({ template: '<button><slot /><slot name="icon" /></button>' }),
          NTooltip: defineComponent({ template: '<span><slot name="trigger" /><slot /></span>' }),
          NPopover: defineComponent({ template: '<span><slot name="trigger" /><slot /></span>' }),
          NInput: defineComponent({ template: '<textarea />' }),
          SparkAlert: defineComponent({ template: '<div><slot /></div>' }),
          ContextCompactionSegment: true,
          ToolTraceSegment: true,
        },
      },
    });

    await nextTick();
    await Promise.resolve();
    await nextTick();
    vi.runOnlyPendingTimers();
    await nextTick();

    const panel = wrapper.find('.reasoning-content-wrapper');
    expect(panel.attributes('style')).toContain('--reasoning-panel-height: 32px');

    await wrapper.setProps({
      history: [
        {
          id: 'assistant-5',
          role: 'assistant',
          content: '',
          segments: [
            {
              type: 'reasoning',
              text: Array.from({ length: 20 }, (_, index) => `第 ${index + 1} 段流式推理`).join('\n'),
              source_agent: 'agent_director',
            },
          ],
        },
      ],
      sending: true,
    });
    await nextTick();
    await nextTick();

    expect(wrapper.find('.reasoning-content-wrapper').attributes('style')).toContain('--reasoning-panel-height: 113px');

    await wrapper.setProps({
      history: [
        {
          id: 'assistant-5',
          role: 'assistant',
          content: '',
          segments: [
            {
              type: 'reasoning',
              text: Array.from({ length: 80 }, (_, index) => `第 ${index + 1} 段流式推理`).join('\n'),
              source_agent: 'agent_director',
            },
          ],
        },
      ],
      sending: true,
    });
    await nextTick();
    await nextTick();

    expect(wrapper.find('.reasoning-content-wrapper').attributes('style')).toContain('--reasoning-panel-height: 113px');
  });

  it('首次展开按实际渲染节点高度落定，且测量时不把真实面板改成 auto', async () => {
    vi.useFakeTimers();
    const rafCallbacks: FrameRequestCallback[] = [];
    vi.spyOn(window, 'requestAnimationFrame').mockImplementation((callback: FrameRequestCallback) => {
      rafCallbacks.push(callback);
      return rafCallbacks.length;
    });

    let livePanel: HTMLElement | null = null;
    let livePanelAutoSeen = false;

    vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockImplementation(function getMockRect(this: HTMLElement) {
      const el = this;
      const panel = el.closest?.('.reasoning-content-wrapper') as HTMLElement | null;
      if (livePanel && panel === livePanel && panel.style.height === 'auto') {
        livePanelAutoSeen = true;
      }
      if (el.classList?.contains('reasoning-inner')) {
        return { width: 420, height: 613, top: 0, left: 0, right: 420, bottom: 613, x: 0, y: 0, toJSON: () => ({}) } as DOMRect;
      }
      if (el.classList?.contains('node-slot')) {
        return { width: 420, height: 314, top: 0, left: 0, right: 420, bottom: 314, x: 0, y: 0, toJSON: () => ({}) } as DOMRect;
      }
      return { width: 420, height: 0, top: 0, left: 0, right: 420, bottom: 0, x: 0, y: 0, toJSON: () => ({}) } as DOMRect;
    });

    const wrapper = mount(ChatMessageList, {
      props: {
        history: [
          {
            id: 'assistant-3',
            role: 'assistant',
            content: '',
            segments: [
              {
                type: 'reasoning',
                text: '第一段较长推理内容\n\n第二段较长推理内容',
                source_agent: 'agent_director',
              },
            ],
          },
        ],
        sending: false,
      },
      global: {
        plugins: [i18n],
        stubs: {
          NButton: defineComponent({ template: '<button><slot /><slot name="icon" /></button>' }),
          NTooltip: defineComponent({ template: '<span><slot name="trigger" /><slot /></span>' }),
          NPopover: defineComponent({ template: '<span><slot name="trigger" /><slot /></span>' }),
          NInput: defineComponent({ template: '<textarea />' }),
          SparkAlert: defineComponent({ template: '<div><slot /></div>' }),
          ContextCompactionSegment: true,
          ToolTraceSegment: true,
        },
      },
    });

    livePanel = wrapper.find('.reasoning-content-wrapper').element as HTMLElement;

    await wrapper.find('.reasoning-toggle').trigger('click');
    await nextTick();
    expect(livePanel.style.height).not.toBe('auto');

    const callback = rafCallbacks.shift();
    expect(callback).toBeTruthy();
    callback?.(performance.now());
    await Promise.resolve();
    await Promise.resolve();
    await nextTick();
    await nextTick();

    expect(livePanelAutoSeen).toBe(false);
    expect(livePanel.getAttribute('style')).toContain('--reasoning-panel-height: 314px');

    vi.runOnlyPendingTimers();
    await nextTick();
    expect(wrapper.find('.reasoning-content-wrapper').classes()).toContain('is-expanded');
  });
});
