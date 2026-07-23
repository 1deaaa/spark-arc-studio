import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { flushPromises, mount } from '@vue/test-utils';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { i18n } from '@/i18n';
import SearchProviderSettings from '../SearchProviderSettings.vue';

const { fetchWithAuth } = vi.hoisted(() => ({
  fetchWithAuth: vi.fn(),
}));

vi.mock('@/services/api', () => ({ fetchWithAuth }));

vi.mock('naive-ui', async () => {
  const { defineComponent } = await import('vue');
  const createStub = (name: string) => defineComponent({
    name,
    template: '<div><slot name="header" /><slot name="prefix" /><slot name="icon" /><slot /></div>',
  });
  return {
    NButton: createStub('NButton'),
    NCard: createStub('NCard'),
    NCheckbox: createStub('NCheckbox'),
    NForm: createStub('NForm'),
    NFormItem: createStub('NFormItem'),
    NIcon: createStub('NIcon'),
    NInput: createStub('NInput'),
    NRadioButton: createStub('NRadioButton'),
    NRadioGroup: createStub('NRadioGroup'),
    NTabPane: createStub('NTabPane'),
    NTabs: createStub('NTabs'),
    NTag: createStub('NTag'),
    useMessage: () => ({ error: vi.fn(), success: vi.fn() }),
  };
});

function userSearchView(systemServiceEnabled = true) {
  return {
    system_service_enabled: systemServiceEnabled,
    providers: [
      {
        provider: 'exa',
        default_url: 'https://mcp.exa.ai/mcp',
        system: { enabled: systemServiceEnabled, url: 'https://mcp.exa.ai/mcp', api_key_set: false },
        user: { configured: false, url: '', api_key_set: false },
        effective: {
          available: systemServiceEnabled,
          source: systemServiceEnabled ? 'system' : 'unavailable',
          url: systemServiceEnabled ? 'https://mcp.exa.ai/mcp' : '',
          api_key_set: false,
        },
      },
      {
        provider: 'tavily',
        default_url: 'https://mcp.tavily.com/mcp',
        system: { enabled: systemServiceEnabled, url: 'https://mcp.tavily.com/mcp', api_key_set: false },
        user: { configured: true, url: 'https://mcp.1dea.top/tavily', api_key_set: true },
        effective: {
          available: true,
          source: 'user',
          url: 'https://mcp.1dea.top/tavily',
          api_key_set: true,
        },
      },
    ],
  };
}

describe('联网搜索配置模块', () => {
  afterEach(() => {
    fetchWithAuth.mockReset();
    i18n.global.locale.value = 'zh-CN';
  });

  it('位于模型平台列表之后且不再挂在管理员配置面板', () => {
    const aiManagerSource = readFileSync(resolve(process.cwd(), 'src/components/settings/AIManager.vue'), 'utf8');
    const adminSource = readFileSync(resolve(process.cwd(), 'src/components/settings/AdminConfigPanel.vue'), 'utf8');

    const moduleIndex = aiManagerSource.indexOf('<SearchProviderSettings');
    expect(moduleIndex).toBeGreaterThan(aiManagerSource.indexOf('<n-collapse'));
    expect(moduleIndex).toBeLessThan(aiManagerSource.indexOf('<!-- 添加平台弹窗 -->'));
    expect(adminSource).not.toContain('SearchProviderSettings');
  });

  it('普通用户读取个人覆盖和系统回退状态', async () => {
    fetchWithAuth.mockResolvedValue({
      ok: true,
      json: async () => userSearchView(true),
    });

    const wrapper = mount(SearchProviderSettings, {
      props: { isAdmin: false, systemServiceEnabled: true },
      global: { plugins: [i18n] },
    });
    await flushPromises();

    expect(fetchWithAuth).toHaveBeenCalledWith('/api/ai/search-providers');
    expect(wrapper.text()).toContain('联网搜索服务');
    expect(wrapper.text()).toContain('系统托管已开启');
    expect(wrapper.text()).toContain('个人配置');
    expect(wrapper.text()).not.toContain('保存系统搜索配置');
  });
});
