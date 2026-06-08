export const SUPPORTED_LOCALES = ['zh-CN', 'en-US', 'ja-JP', 'ko-KR'] as const;

export type AppLocale = (typeof SUPPORTED_LOCALES)[number];

export const DEFAULT_LOCALE: AppLocale = 'zh-CN';
export const LOCALE_STORAGE_KEY = 'spark_locale';
export const LOCALE_SOURCE_STORAGE_KEY = 'spark_locale_source';
export const LOCALE_QUERY_PARAM = 'spark_locale';

export type LocaleSource = 'auto' | 'launcher' | 'manual';

export function isSupportedLocale(value: string): value is AppLocale {
  return SUPPORTED_LOCALES.includes(value as AppLocale);
}

export function normalizeLocale(value: string | null | undefined): AppLocale {
  if (!value) return DEFAULT_LOCALE;

  const trimmed = String(value).trim();
  if (isSupportedLocale(trimmed)) {
    return trimmed;
  }

  const lower = trimmed.toLowerCase();
  if (lower.startsWith('zh')) return 'zh-CN';
  if (lower.startsWith('ja')) return 'ja-JP';
  if (lower.startsWith('en')) return 'en-US';
  if (lower.startsWith('ko')) return 'ko-KR';

  return DEFAULT_LOCALE;
}

export function isPersistentLocaleSource(value: string | null | undefined): boolean {
  return value === 'manual' || value === 'launcher';
}
