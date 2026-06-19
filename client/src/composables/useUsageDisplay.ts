import { computed } from 'vue';
import { useI18n } from 'vue-i18n';

type UsageLike = {
  usage_key?: string | null;
  usage_label?: string | null;
} | null | undefined;

const BUILTIN_USAGE_NAME_KEYS: Record<string, string> = {
  main: 'components.modelUsageManager.usageNameMain',
  fast: 'components.modelUsageManager.usageNameFast',
  reason: 'components.modelUsageManager.usageNameReason',
};

const BUILTIN_USAGE_DESCRIPTION_KEYS: Record<string, string> = {
  main: 'components.modelUsageManager.usageDescMain',
  fast: 'components.modelUsageManager.usageDescFast',
  reason: 'components.modelUsageManager.usageDescReason',
};

function normalizeUsageKey(key: unknown): string {
  return String(key ?? '').trim().toLowerCase();
}

export function useUsageDisplay() {
  const { t } = useI18n();

  const builtinUsageKeys = computed(() => Object.keys(BUILTIN_USAGE_NAME_KEYS));

  function isBuiltinUsage(key: unknown): boolean {
    return normalizeUsageKey(key) in BUILTIN_USAGE_NAME_KEYS;
  }

  function getBuiltinUsageName(key: unknown): string {
    const nameKey = BUILTIN_USAGE_NAME_KEYS[normalizeUsageKey(key)];
    return nameKey ? t(nameKey) : '';
  }

  function getBuiltinUsageDescription(key: unknown): string {
    const descriptionKey = BUILTIN_USAGE_DESCRIPTION_KEYS[normalizeUsageKey(key)];
    return descriptionKey ? t(descriptionKey) : '';
  }

  function getUsageDisplayLabel(usage: UsageLike): string {
    const key = usage?.usage_key || '';
    return getBuiltinUsageName(key) || usage?.usage_label || key;
  }

  function getUsageKeyDisplayName(usageKey: unknown, usageList: UsageLike[] = []): string {
    const key = String(usageKey ?? '');
    const usage = usageList.find(item => item?.usage_key === key);
    return getUsageDisplayLabel(usage || { usage_key: key });
  }

  function formatUsageOptionLabel(usage: UsageLike): string {
    const key = usage?.usage_key || '';
    const label = getUsageDisplayLabel(usage);
    return key ? `${label} (${key})` : label;
  }

  return {
    builtinUsageKeys,
    isBuiltinUsage,
    getBuiltinUsageName,
    getBuiltinUsageDescription,
    getUsageDisplayLabel,
    getUsageKeyDisplayName,
    formatUsageOptionLabel,
  };
}
