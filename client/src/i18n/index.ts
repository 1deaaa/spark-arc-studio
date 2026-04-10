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

const localeMessages: Record<string, LocaleMessages> = {
  'zh-CN': zhCN,
  'zh': zhCN,    // BCP 47 语言标签回退别名
  'en-US': enUS,
  'en': enUS,    // BCP 47 语言标签回退别名
  'ja-JP': jaJP,
  'ja': jaJP,    // BCP 47 语言标签回退别名
};

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
  // 保留显式回退决策：zh→zh-CN, ja→ja-JP, en→en-US
  fallbackLocale: {
    zh: ['zh-CN'],
    ja: ['ja-JP'],
    en: ['en-US'],
    default: ['zh-CN'],
  },
  // 仅在开发环境启用告警，避免生产环境日志噪音
  fallbackWarn: import.meta.env.DEV,
  missingWarn: import.meta.env.DEV,
  messages: {},
});

// createI18n 对大型嵌套 messages 做深拷贝时会丢失深层 key
// 改用 setLocaleMessage 逐个注册，确保完整注册
for (const [locale, msg] of Object.entries(localeMessages)) {
  i18n.global.setLocaleMessage(locale, msg);
}

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
