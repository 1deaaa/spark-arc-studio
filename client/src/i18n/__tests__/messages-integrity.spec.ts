import { describe, it, expect } from 'vitest';
import { i18n } from '@/i18n';
import zhCN from '@/i18n/locales/zh-CN';

describe('i18n messages integrity', () => {
  it('zhCN module should have mcpConnectCard in components', () => {
    const components = (zhCN as Record<string, unknown>).components as Record<string, unknown>;
    console.log('zhCN.components keys count:', Object.keys(components).length);
    console.log('zhCN.components keys:', Object.keys(components));
    expect('mcpConnectCard' in components).toBe(true);
  });

  it('zh-CN in i18n should have mcpConnectCard in components', () => {
    const msgs = i18n.global.getLocaleMessage('zh-CN') as Record<string, unknown>;
    const components = msgs.components as Record<string, unknown>;
    console.log('i18n zh-CN components keys count:', Object.keys(components).length);
    expect('mcpConnectCard' in components).toBe(true);
  });

  it('t() should resolve mcpConnectCard.title', () => {
    const result = i18n.global.t('components.mcpConnectCard.title');
    expect(result).not.toBe('components.mcpConnectCard.title');
    expect(result).toBeTruthy();
  });
});
