import { defineComponent, nextTick } from 'vue';
import { mount } from '@vue/test-utils';
import { createI18n } from 'vue-i18n';
import { afterEach, describe, expect, it } from 'vitest';
import { isTauriDesktop, isWorkspaceWindow } from '@/composables/usePlatform';
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
  isWorkspaceWindow.value = false;
});

describe('业务窗口控制按钮', () => {
  it('业务窗口显示完整的最小化、最大化和关闭按钮', async () => {
    isTauriDesktop.value = true;
    isWorkspaceWindow.value = true;
    const wrapper = mountControls();
    await nextTick();

    expect(wrapper.find('.win-btn--minimize').exists()).toBe(true);
    expect(wrapper.find('.win-btn--maximize').exists()).toBe(true);
    expect(wrapper.find('.win-btn--close').exists()).toBe(true);
  });

  it('普通桌面窗口仍保留关闭按钮', async () => {
    isTauriDesktop.value = true;
    isWorkspaceWindow.value = false;
    const wrapper = mountControls();
    await nextTick();

    expect(wrapper.find('.win-btn--close').exists()).toBe(true);
  });
});
