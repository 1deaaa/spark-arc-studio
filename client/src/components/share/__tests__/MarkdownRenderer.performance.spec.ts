import { createPinia } from 'pinia';
import { defineComponent } from 'vue';
import { mount } from '@vue/test-utils';
import MarkdownRenderer from '../MarkdownRenderer.vue';

vi.mock('markstream-vue', async () => {
  const actual = await vi.importActual<typeof import('markstream-vue')>('markstream-vue');
  return {
    ...actual,
    MarkdownRender: defineComponent({
      name: 'MarkdownRender',
      inheritAttrs: false,
      props: {
        content: { type: String, default: '' },
        parseCoalesceMs: { type: Number, default: 0 },
        maxLiveNodes: { type: Number, default: 320 },
        batchRendering: { type: Boolean, default: false },
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
});
