import { computed } from 'vue';
import { useI18n } from 'vue-i18n';

import { normalizeLocale } from './types';

export function isMainlandComplianceLocale(locale: string | null | undefined): boolean {
  return normalizeLocale(locale) === 'zh-CN';
}

export function useMainlandComplianceLocale() {
  const { locale } = useI18n();
  return computed(() => isMainlandComplianceLocale(locale.value));
}
