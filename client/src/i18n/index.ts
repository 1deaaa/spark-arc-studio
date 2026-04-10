import { createI18n } from 'vue-i18n';
import zhCN from './locales/zh-CN';
import enUS from './locales/en-US';
import jaJP from './locales/ja-JP';
import {
  DEFAULT_LOCALE,
  LOCALE_STORAGE_KEY,
  normalizeLocale,
  type AppLocale,
} from './types';

export type LocaleMessages = typeof zhCN;

const messages = {
  'zh-CN': zhCN,
  'en-US': enUS,
  'ja-JP': jaJP,
} as const;

function resolveInitialLocale(): AppLocale {
  if (typeof window === 'undefined') {
    return DEFAULT_LOCALE;
  }

  try {
    const stored = localStorage.getItem(LOCALE_STORAGE_KEY);
    if (stored) {
      return normalizeLocale(stored);
    }
  } catch {
    // ignore
  }

  const fromNavigator = navigator.languages?.[0] || navigator.language;
  return normalizeLocale(fromNavigator);
}

export const i18n = createI18n({
  legacy: false,
  locale: resolveInitialLocale(),
  fallbackLocale: DEFAULT_LOCALE,
  messages,
});

export function setI18nLocale(locale: AppLocale): void {
  i18n.global.locale.value = locale;

  if (typeof document !== 'undefined') {
    document.documentElement.lang = locale;
  }

  if (typeof window !== 'undefined') {
    try {
      localStorage.setItem(LOCALE_STORAGE_KEY, locale);
    } catch {
      // ignore
    }
  }
}
