import { defineStore } from 'pinia';
import { computed, ref } from 'vue';
import { i18n, setI18nLocale } from '@/i18n';
import {
  DEFAULT_LOCALE,
  LOCALE_SOURCE_STORAGE_KEY,
  LOCALE_STORAGE_KEY,
  isPersistentLocaleSource,
  normalizeLocale,
  type LocaleSource,
  type AppLocale,
} from '@/i18n/types';

function readStoredLocale(): AppLocale {
  if (typeof window === 'undefined') {
    return DEFAULT_LOCALE;
  }

  try {
    const source = localStorage.getItem(LOCALE_SOURCE_STORAGE_KEY);
    const stored = localStorage.getItem(LOCALE_STORAGE_KEY);
    if (stored && isPersistentLocaleSource(source)) {
      return normalizeLocale(stored);
    }
  } catch {
    // ignore
  }

  return normalizeLocale(navigator.languages?.[0] || navigator.language);
}

export const useLocaleStore = defineStore('locale', () => {
  const locale = ref<AppLocale>(readStoredLocale());

  function applyLocale(nextLocale: AppLocale, source: LocaleSource = 'manual'): void {
    locale.value = nextLocale;
    setI18nLocale(nextLocale, source);
  }

  function setLocale(nextLocale: string): void {
    applyLocale(normalizeLocale(nextLocale), 'manual');
  }

  const currentLocale = computed(() => locale.value);

  // 初始化时强制同步一次，确保 i18n / html lang / localStorage 一致。
  let initialSource: LocaleSource = 'auto';
  try {
    const storedSource = localStorage.getItem(LOCALE_SOURCE_STORAGE_KEY);
    if (storedSource === 'manual' || storedSource === 'launcher') {
      initialSource = storedSource;
    }
  } catch {
    // ignore
  }
  applyLocale(normalizeLocale(i18n.global.locale.value), initialSource);

  return {
    locale: currentLocale,
    setLocale,
  };
});
