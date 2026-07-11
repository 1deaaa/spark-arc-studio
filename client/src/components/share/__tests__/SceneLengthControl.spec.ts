import { mount } from '@vue/test-utils';
import { createI18n } from 'vue-i18n';
import { describe, expect, it } from 'vitest';

import SceneLengthControl from '../SceneLengthControl.vue';
import zhCN from '../../../i18n/locales/zh-CN';

const i18n = createI18n({
  legacy: false,
  locale: 'zh-CN',
  messages: { 'zh-CN': zhCN },
});

const SparkSegmentStub = {
  props: ['modelValue', 'options'],
  emits: ['update:modelValue'],
  template: `
    <div>
      <button
        v-for="option in options"
        :key="option.value"
        :data-value="option.value"
        @click="$emit('update:modelValue', option.value)"
      >{{ option.label }}</button>
    </div>
  `,
};

function mountControl(props: Record<string, unknown>) {
  return mount(SceneLengthControl, {
    props,
    global: {
      plugins: [i18n],
      stubs: {
        SparkSegment: SparkSegmentStub,
        NTooltip: { template: '<span><slot name="trigger" /><slot /></span>' },
        NIcon: { template: '<i />' },
      },
    },
  });
}

describe('SceneLengthControl', () => {
  it('按项目模式显示对应的标准档软目标', () => {
    const script = mountControl({ modelValue: 'standard', workspaceMode: 'script' });
    const novel = mountControl({ modelValue: 'standard', workspaceMode: 'novel' });

    expect(script.text()).toContain('约 20-35 个有效叙事单元');
    expect(novel.text()).toContain('约 1000-1800 个中文字符');
    expect(script.text()).toContain('约 ±30% 浮动');
  });

  it('选择充实档时发出稳定枚举值', async () => {
    const wrapper = mountControl({ modelValue: 'standard', workspaceMode: 'script' });

    await wrapper.get('[data-value="expanded"]').trigger('click');

    expect(wrapper.emitted('update:modelValue')).toEqual([['expanded']]);
  });
});
