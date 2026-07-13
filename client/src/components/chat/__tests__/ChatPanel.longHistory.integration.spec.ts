import { defineComponent, nextTick } from 'vue';
import { mount } from '@vue/test-utils';
import ChatPanel from '@/components/chat/ChatPanel.vue';
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
    props: {
      content: { type: String, default: '' },
      streaming: { type: Boolean, default: false },
      deferred: { type: Boolean, default: false },
      maxLiveNodes: { type: Number, default: 320 },
    },
    template: '<div class="markdown-probe">{{ content }}</div>',
  }),
}));

vi.mock('@/components/share/AgentAvatar.vue', () => ({
  default: defineComponent({ name: 'AgentAvatar', template: '<span />' }),
}));

describe('ChatPanel 长历史组件集成', () => {
  it('200 条长历史只把尾部窗口挂载到真实消息列表 DOM', async () => {
    const history = Array.from({ length: 200 }, (_, index) => ({
      id: 'message-' + index,
      role: index % 2 === 0 ? 'user' : 'assistant',
      content: ('第 ' + index + ' 条消息').repeat(120),
    }));
    const wrapper = mount(ChatPanel, {
      props: {
        agentId: 'agent_director',
        history,
      },
      global: {
        plugins: [i18n],
        stubs: {
          AgentRadialPicker: true,
          ChatProgressBoardPopover: true,
          GlobalLoading: true,
          NButton: true,
          NInput: true,
          NPopconfirm: true,
          NTooltip: true,
          NPopover: true,
          SparkAlert: true,
          SparkLoaderAnimation: true,
          ContextCompactionSegment: true,
          ReasoningSegmentBubble: true,
          ToolTraceSegment: true,
        },
      },
    });
    await nextTick();

    const mountedMessages = wrapper.findAll('.chat-msg');
    expect(mountedMessages).toHaveLength(4);
    expect(wrapper.text()).toContain('第 199 条消息');
    expect(wrapper.text()).not.toContain('第 0 条消息');

    wrapper.unmount();
  });
});
