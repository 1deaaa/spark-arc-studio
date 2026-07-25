import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { flushPromises, mount } from '@vue/test-utils';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { i18n } from '@/i18n';
import SparkSegment from '@/components/share/SparkSegment.vue';
import SearchProviderSettings from '../SearchProviderSettings.vue';

const { fetchWithAuth } = vi.hoisted(() => ({
  fetchWithAuth: vi.fn(),
}));

vi.mock('@/services/api', () => ({ fetchWithAuth }));

vi.mock('naive-ui', async () => {
  const { defineComponent } = await import('vue');
  const createStub = (name: string) => defineComponent({
    name,
    template: '<div><slot name="header" /><slot name="prefix" /><slot name="icon" /><slot /><slot name="suffix" /></div>',
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

  it('作为模型平台管理卡片下方的独立同级卡片', () => {
    const aiManagerSource = readFileSync(resolve(process.cwd(), 'src/components/settings/AIManager.vue'), 'utf8');
    const adminSource = readFileSync(resolve(process.cwd(), 'src/components/settings/AdminConfigPanel.vue'), 'utf8');

    const moduleIndex = aiManagerSource.indexOf('<SearchProviderSettings');
    expect(moduleIndex).toBeGreaterThan(aiManagerSource.lastIndexOf('</n-modal>'));
    expect(aiManagerSource.indexOf('</template>', moduleIndex)).toBeGreaterThan(moduleIndex);
    expect(aiManagerSource).toMatch(/<\/div>\s*<SearchProviderSettings/);
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
    expect(wrapper.text()).toContain('保存我的搜索配置');
    expect(wrapper.findAll('.provider-toolbar')).toHaveLength(2);
    expect(wrapper.findAll('.search-provider-section')).toHaveLength(2);
    expect(wrapper.findAllComponents(SparkSegment)).toHaveLength(2);
    expect(wrapper.text()).not.toContain('保存系统搜索配置');
  });

  it('使用紧凑自适应列并复用统一分段选择器', () => {
    const source = readFileSync(resolve(process.cwd(), 'src/components/settings/SearchProviderSettings.vue'), 'utf8');

    expect(source).toContain('<SparkSegment');
    expect(source).not.toContain('<n-radio-button');
    expect(source).toContain(':animated="false"');
    expect(source).toContain('repeat(auto-fit, minmax(min(260px, 100%), 1fr))');
    expect(source).toContain('repeat(auto-fit, minmax(min(240px, 100%), 360px))');
    expect(source).toContain('.n-tabs-pane-wrapper');
    expect(source).toContain('height: auto !important');
  });
});
