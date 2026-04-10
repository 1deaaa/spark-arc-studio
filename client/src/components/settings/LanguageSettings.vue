<template>
  <div class="settings-section">
    <h3>{{ t('settings.language.title') }}</h3>
    <p class="section-desc">{{ t('settings.language.description') }}</p>

    <n-form label-placement="left" label-width="90">
      <n-form-item :label="t('settings.language.label')">
        <n-select
          v-model:value="selectedLocale"
          :options="localeOptions"
          :consistent-menu-width="false"
        />
      </n-form-item>
    </n-form>

    <n-text depth="3" class="helper-text">{{ t('settings.language.helper') }}</n-text>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { NForm, NFormItem, NSelect, NText } from 'naive-ui';
import { useI18n } from 'vue-i18n';
import { useLocaleStore } from '../stores/localeStore';
import type { AppLocale } from '@/i18n/types';

const { t } = useI18n();
const localeStore = useLocaleStore();

const selectedLocale = computed({
  get: () => localeStore.locale,
  set: (value: AppLocale) => {
    localeStore.setLocale(value);
  },
});

const localeOptions = computed(() => [
  { label: t('locale.zh-CN'), value: 'zh-CN' },
  { label: t('locale.en-US'), value: 'en-US' },
  { label: t('locale.ja-JP'), value: 'ja-JP' },
]);
</script>

<style scoped>
.settings-section {
  background: var(--spark-panel-bg);
  border: 1px solid var(--spark-border);
  border-radius: var(--spark-radius);
  padding: var(--spark-panel-padding);
  margin-bottom: 20px;
}

.settings-section h3 {
  margin: 0 0 8px 0;
  font-size: 18px;
  color: var(--spark-primary);
}

.section-desc {
  color: var(--spark-text-muted);
  margin-bottom: 16px;
  font-size: 14px;
  line-height: 1.5;
}

.helper-text {
  display: block;
  margin-top: 8px;
}
</style>
