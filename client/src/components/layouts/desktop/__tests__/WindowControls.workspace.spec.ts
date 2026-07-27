import { defineComponent, nextTick } from 'vue';
import { mount } from '@vue/test-utils';
import { createI18n } from 'vue-i18n';
import { afterEach, describe, expect, it } from 'vitest';
import { isTauriDesktop } from '@/composables/usePlatform';
import WindowControls from '@/components/layouts/desktop/WindowControls.vue';

const TooltipStub = defineComponent({
  template: '<div><slot name="trigger" /><slot /></div>',
});

function mountControls() {
  return mount(WindowControls, {
    global: {
      plugins: [createI18n({ legacy: false, locale: 'zh-CN', messages: { 'zh-CN': {} } })],
      stubs: { NTooltip: TooltipStub },
    },
  });
}

afterEach(() => {
  isTauriDesktop.value = false;
});

describe('桌面窗口控制按钮', () => {
  it('桌面客户端显示完整的最小化、最大化和关闭按钮', async () => {
    isTauriDesktop.value = true;
    const wrapper = mountControls();
    await nextTick();

    expect(wrapper.find('.win-btn--minimize').exists()).toBe(true);
    expect(wrapper.find('.win-btn--maximize').exists()).toBe(true);
    expect(wrapper.find('.win-btn--close').exists()).toBe(true);
  });
});
