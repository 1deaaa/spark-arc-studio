import { createI18n } from 'vue-i18n';
import zhCN from './locales/zh-CN';
import enUS from './locales/en-US';
import jaJP from './locales/ja-JP';
import koKR from './locales/ko-KR';
import onboardingZhCN from '../onboarding/i18n/onboarding.zh-CN';
import onboardingEnUS from '../onboarding/i18n/onboarding.en-US';
import onboardingJaJP from '../onboarding/i18n/onboarding.ja-JP';
import onboardingKoKR from '../onboarding/i18n/onboarding.ko-KR';
import {
  DEFAULT_LOCALE,
  LOCALE_QUERY_PARAM,
  LOCALE_SOURCE_STORAGE_KEY,
  LOCALE_STORAGE_KEY,
  isPersistentLocaleSource,
  normalizeLocale,
  type LocaleSource,
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
  'ko-KR': koKR,
  'ko': koKR,    // BCP 47 语言标签回退别名
};

function resolveInitialLocale(): AppLocale {
  if (typeof window === 'undefined') {
    return DEFAULT_LOCALE;
  }

  try {
    const fromQuery = new URL(window.location.href).searchParams.get(LOCALE_QUERY_PARAM);
    if (fromQuery) {
      const normalized = normalizeLocale(fromQuery);
      localStorage.setItem(LOCALE_STORAGE_KEY, normalized);
      localStorage.setItem(LOCALE_SOURCE_STORAGE_KEY, 'launcher');
      return normalized;
    }

    const source = localStorage.getItem(LOCALE_SOURCE_STORAGE_KEY);
    const stored = localStorage.getItem(LOCALE_STORAGE_KEY);
    if (stored && isPersistentLocaleSource(source)) {
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
  // 保留显式回退决策：zh→zh-CN, ja→ja-JP, en→en-US, ko→ko-KR
  fallbackLocale: {
    zh: ['zh-CN'],
    ja: ['ja-JP'],
    en: ['en-US'],
    ko: ['ko-KR'],
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

// 合并 onboarding 引导词条到各语言消息
const onboardingMessages: Record<string, Record<string, unknown>> = {
  'zh-CN': onboardingZhCN,
  'zh': onboardingZhCN,
  'en-US': onboardingEnUS,
  'en': onboardingEnUS,
  'ja-JP': onboardingJaJP,
  'ja': onboardingJaJP,
  'ko-KR': onboardingKoKR,
  'ko': onboardingKoKR,
};
for (const [locale, onboardingMsg] of Object.entries(onboardingMessages)) {
  const existing = i18n.global.getLocaleMessage(locale);
  i18n.global.setLocaleMessage(locale, { ...existing, ...onboardingMsg });
}

export function setI18nLocale(locale: AppLocale, source: LocaleSource = 'manual'): void {
  i18n.global.locale.value = locale;

  if (typeof document !== 'undefined') {
    document.documentElement.lang = locale;
  }

  if (typeof window !== 'undefined') {
    try {
      localStorage.setItem(LOCALE_STORAGE_KEY, locale);
      localStorage.setItem(LOCALE_SOURCE_STORAGE_KEY, source);
    } catch {
      // ignore
    }
  }
}
