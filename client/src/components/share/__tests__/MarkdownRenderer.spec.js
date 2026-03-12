import { describe, expect, it } from 'vitest';
import { mount } from '@vue/test-utils';
import MarkdownRenderer from '../MarkdownRenderer.vue';

describe('MarkdownRenderer', () => {
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
});