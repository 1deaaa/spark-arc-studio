import { defineStore } from 'pinia';
import { computed, ref } from 'vue';
import { i18n, setI18nLocale } from '@/i18n';
import {
  DEFAULT_LOCALE,
  LOCALE_STORAGE_KEY,
  normalizeLocale,
  type AppLocale,
} from '@/i18n/types';

function readStoredLocale(): AppLocale {
  if (typeof window === 'undefined') {
    return DEFAULT_LOCALE;
  }

  try {
    return normalizeLocale(localStorage.getItem(LOCALE_STORAGE_KEY));
  } catch {
    return DEFAULT_LOCALE;
  }
}

export const useLocaleStore = defineStore('locale', () => {
  const locale = ref<AppLocale>(readStoredLocale());

  function applyLocale(nextLocale: AppLocale): void {
    locale.value = nextLocale;
    setI18nLocale(nextLocale);
  }

  function setLocale(nextLocale: string): void {
    applyLocale(normalizeLocale(nextLocale));
  }

  const currentLocale = computed(() => locale.value);

  // 初始化时强制同步一次，确保 i18n / html lang / localStorage 一致。
  applyLocale(normalizeLocale(i18n.global.locale.value));

  return {
    locale: currentLocale,
    setLocale,
  };
});
