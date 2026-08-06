import { mount } from '@vue/test-utils';
import { createI18n } from 'vue-i18n';
import { describe, expect, it } from 'vitest';
import zhCN from '@/i18n/locales/zh-CN';
import WorldviewMarkdownEditor from '../WorldviewMarkdownEditor.vue';

function mountEditor(markdown: string) {
  const i18n = createI18n({
    legacy: false,
    locale: 'zh-CN',
    messages: { 'zh-CN': zhCN },
  });
  return mount(WorldviewMarkdownEditor, {
    props: {
      modelValue: markdown,
      saveStatus: 'saved',
    },
    global: { plugins: [i18n] },
  });
}

describe('世界观可视化编辑器', () => {
  it('将二级标题显示为模块，并把字段列表显示为表单', () => {
    const wrapper = mountEditor('# 世界设定\n\n## 战力体系\n\n- 力量来源：灵气\n- 使用代价：寿命');
    expect(wrapper.findAll('.section-nav-item')).toHaveLength(1);
    expect(wrapper.find('.section-nav-item').text()).toContain('战力体系');
    expect(wrapper.findAll('.field-row')).toHaveLength(2);
    expect(wrapper.find('.field-editor').text()).toContain('力量来源');
    expect(wrapper.find('.raw-source-collapse').exists()).toBe(true);
  });

  it('旧版纯文本保持为完整的未分组正文', () => {
    const markdown = '# 世界设定\n\n- 这仍然只是旧版自由文本：需要完整保留\n\n普通段落。';
    const wrapper = mountEditor(markdown);
    expect(wrapper.find('.section-nav-item').text()).toContain('未分组设定');
    expect(wrapper.findAll('.field-row')).toHaveLength(0);
    expect((wrapper.find('.section-prose-input textarea').element as HTMLTextAreaElement).value).toBe(markdown);
  });
});
