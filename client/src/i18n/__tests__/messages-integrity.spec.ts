import { describe, it, expect } from 'vitest';
import { i18n } from '@/i18n';
import zhCN from '@/i18n/locales/zh-CN';
import enUS from '@/i18n/locales/en-US';
import jaJP from '@/i18n/locales/ja-JP';

// 已从 productHomeDesktop 迁移到 components 的共享组件
const sharedComponentKeys = [
  'chatPanel',
  'chatMessageList',
  'directorAutoWrite',
  'termsModal',
  'projectSelector',
  'outlineNode',
  'agentModelCard',
  'mcpConnectCard',
  'lorebookEditor',
  'scriptGenModal',
] as const;

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

  it('共享组件词条应全部在 components 下', () => {
    const components = (zhCN as Record<string, unknown>).components as Record<string, unknown>;
    for (const key of sharedComponentKeys) {
      expect(key in components, `components.${key} 应存在`).toBe(true);
    }
  });

  it('productHomeDesktop 不应包含共享组件词条', () => {
    const phd = (zhCN as Record<string, unknown>).productHomeDesktop as Record<string, unknown>;
    for (const key of sharedComponentKeys) {
      expect(key in phd, `productHomeDesktop.${key} 不应存在`).toBe(false);
    }
  });

  it('directorAutoWrite 新 key 名应可解析', () => {
    const keys = ['writingTitle', 'chapterComplete', 'stopping', 'stopWriting', 'preparing', 'chapterProgress'];
    for (const key of keys) {
      const fullKey = `components.directorAutoWrite.${key}`;
      const result = i18n.global.t(fullKey);
      expect(result, `${fullKey} 应可解析`).not.toBe(fullKey);
    }
  });

  it('三语 components 顶层 key 应一致', () => {
    const zhKeys = Object.keys((zhCN as Record<string, unknown>).components as Record<string, unknown>).sort();
    const enKeys = Object.keys((enUS as Record<string, unknown>).components as Record<string, unknown>).sort();
    const jaKeys = Object.keys((jaJP as Record<string, unknown>).components as Record<string, unknown>).sort();
    expect(enKeys).toEqual(zhKeys);
    expect(jaKeys).toEqual(zhKeys);
  });
});
