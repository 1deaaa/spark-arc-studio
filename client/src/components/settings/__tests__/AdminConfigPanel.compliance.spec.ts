import { mount, flushPromises } from '@vue/test-utils';
import { afterEach, describe, expect, it, vi } from 'vitest';

import AdminConfigPanel from '../AdminConfigPanel.vue';
import { i18n } from '@/i18n';

const { fetchWithAuth } = vi.hoisted(() => ({
  fetchWithAuth: vi.fn(),
}));

vi.mock('@/services/api', () => ({ fetchWithAuth }));

vi.mock('naive-ui', async () => {
  const { defineComponent } = await import('vue');

  const createStub = (name: string) => defineComponent({
    name,
    template: '<div><slot name="trigger" /><slot /></div>',
  });

  return {
    NCard: createStub('NCard'),
    NForm: createStub('NForm'),
    NFormItem: createStub('NFormItem'),
    NSwitch: createStub('NSwitch'),
    NTooltip: createStub('NTooltip'),
    NIcon: createStub('NIcon'),
    NInputGroup: createStub('NInputGroup'),
    NInput: createStub('NInput'),
    NButton: createStub('NButton'),
    NText: createStub('NText'),
    NDivider: createStub('NDivider'),
    NModal: createStub('NModal'),
    NSelect: createStub('NSelect'),
    useMessage: () => ({ error: vi.fn(), success: vi.fn(), warning: vi.fn() }),
    useDialog: () => ({ warning: vi.fn(), create: vi.fn() }),
  };
});

function mockConfigResponse(url: string) {
  if (url.includes('/registration-verification')) {
    return {
      success: true,
      data: {
        enabled: false,
        provider: 'turnstile',
        site_key: '',
        secret_key_set: false,
        supported_providers: ['turnstile'],
      },
    };
  }

  return {
    success: true,
    data: {
      llm_auto_key: false,
      use_sys_llm_config: false,
      llm_key_set: true,
      disable_public_share: false,
      force_public_share_review: true,
    },
  };
}

describe('管理员公开分享审核开关', () => {
  afterEach(() => {
    fetchWithAuth.mockReset();
    i18n.global.locale.value = 'zh-CN';
  });

  it('仅在中文界面显示审核开关', async () => {
    fetchWithAuth.mockImplementation((url: string) => Promise.resolve({
      ok: true,
      json: async () => mockConfigResponse(url),
    }));

    i18n.global.locale.value = 'zh-CN';
    const zhWrapper = mount(AdminConfigPanel, { global: { plugins: [i18n] } });
    await flushPromises();
    expect(zhWrapper.text()).toContain('强制公开前审核');
    zhWrapper.unmount();

    for (const locale of ['en-US', 'ja-JP', 'ko-KR'] as const) {
      i18n.global.locale.value = locale;
      const wrapper = mount(AdminConfigPanel, { global: { plugins: [i18n] } });
      await flushPromises();
      expect(wrapper.text()).not.toContain('forcePublicShareReview');
      expect(wrapper.text()).not.toContain('Require review before publishing');
      wrapper.unmount();
    }
  });
});
