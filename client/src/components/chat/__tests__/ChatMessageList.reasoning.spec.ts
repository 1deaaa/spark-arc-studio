import { describe, expect, it, vi } from 'vitest';
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
    template: '<div class="mock-markdown">{{ content }}</div>',
  }),
}));

vi.mock('@/components/share/AgentAvatar.vue', () => ({
  default: defineComponent({
    name: 'AgentAvatar',
    template: '<span class="mock-agent-avatar" />',
  }),
}));

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
});
