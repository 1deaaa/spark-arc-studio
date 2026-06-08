import { beforeAll, describe, expect, it } from 'vitest';
import { flushPromises, mount } from '@vue/test-utils';
import MarkdownRenderer from '../MarkdownRenderer.vue';

describe('MarkdownRenderer', () => {
  beforeAll(() => {
    if (!globalThis.ResizeObserver) {
      globalThis.ResizeObserver = class ResizeObserver {
        observe() {}
        unobserve() {}
        disconnect() {}
      };
    }
  });

  it('renders GitHub style pipe tables', () => {
    const wrapper = mount(MarkdownRenderer, {
      props: {
        content: '| 列1 | 列2 |\n| --- | :---: |\n| A | B |\n| C | D |',
      },
    });

    const table = wrapper.find('table');
    expect(table.exists()).toBe(true);
    expect(wrapper.findAll('thead th')).toHaveLength(2);
    expect(wrapper.findAll('tbody tr')).toHaveLength(2);
    expect(table.text()).toContain('列1');
    expect(table.text()).toContain('D');
  });

  async function waitForMarkdownRender() {
    await flushPromises();
    await new Promise(resolve => setTimeout(resolve, 0));
    await flushPromises();
  }

  it('渲染行内 LaTeX 公式 \\(...\\)', async () => {
    const wrapper = mount(MarkdownRenderer, {
      props: { content: '公式 \\(E=mc^2\\) 很有名' },
    });
    await waitForMarkdownRender();
    const html = wrapper.html();
    // KaTeX 渲染结果应包含 .katex 类
    expect(html).toContain('katex');
    // 不应残留原始公式定界符
    expect(html).not.toContain('\\(E=mc^2\\)');
  });

  it('渲染块级 LaTeX 公式 $$...$$', async () => {
    const wrapper = mount(MarkdownRenderer, {
      props: { content: '块级公式：\n$$\\int_0^1 x^2 dx$$\n结束' },
    });
    await waitForMarkdownRender();
    const html = wrapper.html();
    expect(html).toContain('katex');
    // 块级公式应为 displayMode
    expect(html).toContain('katex-display');
  });

  it('LaTeX 公式与 Markdown 混合使用不冲突', async () => {
    const wrapper = mount(MarkdownRenderer, {
      props: { content: '## 标题\n行内 \\(\\alpha+\\beta\\) 和 **粗体** 混排' },
    });
    await waitForMarkdownRender();
    const html = wrapper.html();
    expect(html).toContain('katex');
    expect(wrapper.find('strong').text()).toBe('粗体');
  });

  it('识别 Mermaid 图表代码块', async () => {
    const wrapper = mount(MarkdownRenderer, {
      props: { content: '```mermaid\ngraph TD\nA[开始] --> B[结束]\n```' },
    });
    await waitForMarkdownRender();

    expect(wrapper.find('.mermaid-block-container').exists()).toBe(true);
    expect(wrapper.html()).not.toContain('<code');
  });
});
