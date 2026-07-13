import { defineComponent, nextTick } from 'vue';
import { mount } from '@vue/test-utils';
import ChatMessageList from '../ChatMessageList.vue';
import { i18n } from '@/i18n';

vi.mock('naive-ui', async () => {
  const actual = await vi.importActual<typeof import('naive-ui')>('naive-ui');
  return {
    ...actual,
    useMessage: () => ({ success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() }),
  };
});

vi.mock('@/components/share/MarkdownRenderer.vue', () => ({
  default: defineComponent({
    name: 'MarkdownRenderer',
    props: { content: { type: String, default: '' }, streaming: { type: Boolean, default: false } },
    template: '<div class="mock-markdown">{{ content }}</div>',
  }),
}));

vi.mock('@/components/share/AgentAvatar.vue', () => ({
  default: defineComponent({ name: 'AgentAvatar', template: '<span />' }),
}));

function rect(width: number, height: number): DOMRect {
  return { width, height, top: 0, left: 0, right: width, bottom: height, x: 0, y: 0, toJSON: () => ({}) } as DOMRect;
}

describe('ChatMessageList 真实虚拟时间线', () => {
  beforeEach(() => {
    vi.spyOn(HTMLElement.prototype, 'clientHeight', 'get').mockImplementation(function getClientHeight(this: HTMLElement) {
      return this.classList?.contains('markstream-virtual-timeline') ? 640 : 96;
    });
    vi.spyOn(HTMLElement.prototype, 'clientWidth', 'get').mockReturnValue(360);
    vi.spyOn(HTMLElement.prototype, 'offsetHeight', 'get').mockImplementation(function getOffsetHeight(this: HTMLElement) {
      const inlineMinHeight = Number.parseFloat(this.style?.minHeight || '');
      return Number.isFinite(inlineMinHeight) && inlineMinHeight > 0 ? inlineMinHeight : 96;
    });
    vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockImplementation(function getRect(this: HTMLElement) {
      const height = this.classList?.contains('markstream-virtual-timeline') ? 640 : this.offsetHeight;
      return rect(360, height);
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('200 条长历史只挂载移动视口附近项，流式尾项更新不重建 DOM', async () => {
    const history = Array.from({ length: 200 }, (_, index) => ({
      id: `message-${index}`,
      role: index % 2 === 0 ? 'user' : 'assistant',
      content: `第 ${index} 条消息`.repeat(80),
      segments: index % 2 === 0 ? undefined : [{ type: 'text', text: `第 ${index} 条回复`.repeat(120) }],
    }));
    const wrapper = mount(ChatMessageList, {
      props: { history, sending: true, threadKey: 'mobile-long-history' },
      global: {
        plugins: [i18n],
        stubs: {
          NButton: true,
          NTooltip: true,
          NPopover: true,
          NInput: true,
          SparkAlert: true,
          ContextCompactionSegment: true,
          ToolTraceSegment: true,
        },
      },
    });

    await nextTick();
    await new Promise(resolve => setTimeout(resolve, 32));
    await nextTick();

    const mountedItems = wrapper.findAll('.markstream-virtual-timeline__item');
    expect(mountedItems.length).toBeGreaterThan(0);
    expect(mountedItems.length).toBeLessThan(12);

    const tailSelector = '[data-markstream-item-key="message:db:message-199"]';
    const tailBefore = wrapper.find(tailSelector).element;
    const nextHistory = history.slice();
    nextHistory[199] = {
      ...history[199],
      content: `${history[199].content} 新增流式内容`,
      segments: [{ type: 'text', text: `${history[199].segments?.[0]?.text} 新增流式内容` }],
    };
    await wrapper.setProps({ history: nextHistory });
    await nextTick();

    expect(wrapper.find(tailSelector).element).toBe(tailBefore);
  });
});
