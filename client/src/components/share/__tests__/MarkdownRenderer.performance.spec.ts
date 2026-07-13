import { createPinia } from 'pinia';
import { defineComponent, nextTick } from 'vue';
import { flushPromises, mount } from '@vue/test-utils';
import MarkdownRenderer from '../MarkdownRenderer.vue';

vi.mock('@/components/share/markdownParseWorker', () => ({
  parseMarkdownOffThread: vi.fn(async () => ([
    { type: 'paragraph', children: [{ type: 'text', content: '很长的历史正文' }] },
  ])),
}));

vi.mock('markstream-vue', async () => {
  const actual = await vi.importActual<typeof import('markstream-vue')>('markstream-vue');
  return {
    ...actual,
    MarkdownRender: defineComponent({
      name: 'MarkdownRender',
      inheritAttrs: false,
      props: {
        content: { type: String, default: '' },
        nodes: { type: Array, default: undefined },
        parseCoalesceMs: { type: Number, default: 0 },
        maxLiveNodes: { type: Number, default: 320 },
        batchRendering: { type: Boolean, default: false },
        initialRenderBatchSize: { type: Number, default: 0 },
        renderBatchSize: { type: Number, default: 0 },
        renderBatchDelay: { type: Number, default: 0 },
        renderBatchBudgetMs: { type: Number, default: 0 },
        typewriter: { type: Boolean, default: false },
        final: { type: Boolean, default: true },
      },
      template: '<div class="markdown-render-probe">{{ content }}</div>',
    }),
    enableKatex: vi.fn(),
    enableMermaid: vi.fn(),
    setCustomComponents: vi.fn(),
  };
});

describe('MarkdownRenderer 聊天性能参数', () => {
  it('流式正文直传内容并合并解析，不在包装层同步预解析', () => {
    const wrapper = mount(MarkdownRenderer, {
      props: { content: '正在流式生成', streaming: true, maxLiveNodes: 96 },
      global: { plugins: [createPinia()] },
    });
    const renderer = wrapper.findComponent({ name: 'MarkdownRender' });

    expect(renderer.props('content')).toBe('正在流式生成');
    expect(renderer.props('parseCoalesceMs')).toBe(16);
    expect(renderer.props('maxLiveNodes')).toBe(0);
    expect(renderer.props('batchRendering')).toBe(true);
    expect(renderer.props('typewriter')).toBe(true);
    expect(renderer.props('final')).toBe(false);
  });

  it('历史完成态使用调用方指定的活动节点窗口', () => {
    const wrapper = mount(MarkdownRenderer, {
      props: { content: '历史正文', streaming: false, maxLiveNodes: 96 },
      global: { plugins: [createPinia()] },
    });
    const renderer = wrapper.findComponent({ name: 'MarkdownRender' });

    expect(renderer.props('parseCoalesceMs')).toBe(0);
    expect(renderer.props('maxLiveNodes')).toBe(96);
    expect(renderer.props('batchRendering')).toBe(false);
    expect(renderer.props('final')).toBe(true);
  });

  it('超长历史先等待 Worker 解析，再以完成态分批提交节点', async () => {
    const wrapper = mount(MarkdownRenderer, {
      props: { content: '很长的历史正文', deferred: true, maxLiveNodes: 96 },
      global: { plugins: [createPinia()] },
    });
    expect(wrapper.find('.markdown-content-preparing').exists()).toBe(true);

    await flushPromises();
    await nextTick();
    const renderer = wrapper.findComponent({ name: 'MarkdownRender' });
    expect(renderer.props('final')).toBe(true);
    expect(renderer.props('typewriter')).toBe(false);
    expect(renderer.props('content')).toBe('');
    expect(renderer.props('nodes')).toHaveLength(1);
    expect(renderer.props('batchRendering')).toBe(true);
    expect(renderer.props('initialRenderBatchSize')).toBe(8);
    expect(renderer.props('renderBatchSize')).toBe(24);
    expect(renderer.props('renderBatchDelay')).toBe(8);
    expect(renderer.props('renderBatchBudgetMs')).toBe(4);
  });
});
