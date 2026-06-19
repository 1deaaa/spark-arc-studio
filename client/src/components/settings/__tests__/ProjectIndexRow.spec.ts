import { describe, expect, it, vi } from 'vitest';
import { mount } from '@vue/test-utils';
import { defineComponent, nextTick } from 'vue';

import ProjectIndexRow from '../ProjectIndexRow.vue';
import { i18n } from '@/i18n';

vi.mock('naive-ui', async () => {
  const actual = await vi.importActual<typeof import('naive-ui')>('naive-ui');
  return {
    ...actual,
    NSwitch: defineComponent({
      name: 'MockSwitch',
      emits: ['update:value'],
      template: '<button class="mock-switch" />',
    }),
    NTooltip: defineComponent({
      name: 'MockTooltip',
      template: '<span class="mock-tooltip"><slot name="trigger" /></span>',
    }),
    NPopover: defineComponent({
      name: 'MockPopover',
      props: {
        show: { type: Boolean, default: false },
      },
      template: '<span class="mock-popover"><slot name="trigger" /><span v-if="show" class="popover-content"><slot /></span></span>',
    }),
    NIcon: defineComponent({
      name: 'MockIcon',
      template: '<span class="mock-icon"><slot /></span>',
    }),
  };
});

describe('ProjectIndexRow 错误提示展示', () => {
  it('长错误会收起为红点并可通过点击展开 tooltip', async () => {
    const longError = '索引构建失败：' + '当前块内容过长，需要检查附件切分与嵌入契约。'.repeat(8);

    const wrapper = mount(ProjectIndexRow, {
      props: {
        kind: 'semantic',
        label: '语义索引',
        enabled: true,
        tags: [
          {
            key: 'error',
            label: longError,
            tone: 'error',
            title: longError,
          },
          {
            key: 'status',
            label: '已最新',
            tone: 'success',
          },
        ],
        refreshable: true,
        refreshTooltip: '刷新',
        refreshDisabledTooltip: '请先启用',
        refreshBusyTooltip: '正在刷新',
      },
      global: {
        plugins: [i18n],
      },
    });

    const errorDot = wrapper.find('.status-pill-error-dot');
    expect(errorDot.exists()).toBe(true);
    expect(wrapper.text()).not.toContain(longError);

    await errorDot.trigger('click');
    await nextTick();

    expect(wrapper.find('.popover-content').text()).toContain(longError);
  });
});
