import { afterEach, describe, expect, it, vi } from 'vitest';
import { LOCALE_SOURCE_STORAGE_KEY, LOCALE_STORAGE_KEY } from '@/i18n/types';

async function loadFreshI18nAt(url: string) {
  window.history.replaceState(null, '', url);
  vi.resetModules();
  return import('../index');
}

function appUrl(pathAndQuery: string) {
  return `${window.location.origin}${pathAndQuery}`;
}

describe('i18n 语言持久化优先级', () => {
  afterEach(() => {
    localStorage.clear();
    vi.resetModules();
  });

  it('App 启动器传入语言时不覆盖客户端内手动选择', async () => {
    localStorage.setItem(LOCALE_STORAGE_KEY, 'ja-JP');
    localStorage.setItem(LOCALE_SOURCE_STORAGE_KEY, 'manual');

    const mod = await loadFreshI18nAt(appUrl('/?spark_locale=en-US#/login'));

    expect(mod.i18n.global.locale.value).toBe('ja-JP');
    expect(localStorage.getItem(LOCALE_STORAGE_KEY)).toBe('ja-JP');
    expect(localStorage.getItem(LOCALE_SOURCE_STORAGE_KEY)).toBe('manual');
  });

  it('没有手动选择时允许启动器语言初始化主端语言', async () => {
    const mod = await loadFreshI18nAt(appUrl('/?spark_locale=ko-KR#/login'));

    expect(mod.i18n.global.locale.value).toBe('ko-KR');
    expect(localStorage.getItem(LOCALE_STORAGE_KEY)).toBe('ko-KR');
    expect(localStorage.getItem(LOCALE_SOURCE_STORAGE_KEY)).toBe('launcher');
  });
});
