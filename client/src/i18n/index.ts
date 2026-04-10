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

const messages: Record<string, LocaleMessages> = {
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
  // 使用决策图：zh→zh-CN, ja→ja-JP, en→en-US
  // 消除 BCP 47 语言标签层级回退导致的 "Not found in 'zh'" 警告
  fallbackLocale: {
    zh: ['zh-CN'],
    ja: ['ja-JP'],
    en: ['en-US'],
    default: ['zh-CN'],
  },
  // 抑制回退时的控制台警告（key 在完整 locale 中实际存在）
  fallbackWarn: false,
  // 抑制 BCP 47 短 locale（zh/en/ja）回退时的 missing 警告
  // 这些警告是误报：key 在 zh-CN/en-US/ja-JP 中存在，但 BCP 47 层级回退到 zh/en/ja 时找不到
  missingWarn: false,
  // 开发环境下真正缺失 key 时报告错误
  missing: (locale: string, key: string) => {
    if (import.meta.env.DEV) {
      // BCP 47 短 locale 回退导致的误报：zh/en/ja 中的 missing 不报告
      const shortLocales = new Set(['zh', 'en', 'ja']);
      if (shortLocales.has(locale)) return key;
      // 完整 locale 中缺失 → 真正的问题
      console.error(`[i18n] 缺失翻译 key: '${key}' (locale: '${locale}')`);
    }
    return key;
  },
  messages: {},
});

// createI18n 对大型嵌套 messages 做深拷贝时会丢失深层 key
// 改用 setLocaleMessage 逐个注册，确保完整注册
const allLocales: Record<string, LocaleMessages> = {
  'zh-CN': zhCN,
  'zh': zhCN,
  'en-US': enUS,
  'en': enUS,
  'ja-JP': jaJP,
  'ja': jaJP,
};
for (const [locale, msg] of Object.entries(allLocales)) {
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
