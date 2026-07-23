<template>
  <n-card class="search-provider-settings" size="small">
    <template #header>
      <div class="search-provider-title-row">
        <div class="search-provider-title">
          <n-icon :size="18"><Search /></n-icon>
          <span>{{ t('components.aiManager.searchProviders.title') }}</span>
        </div>
        <n-tag size="small" :type="systemServiceEnabledState ? 'success' : 'warning'">
          {{ systemServiceEnabledState
            ? t('components.aiManager.searchProviders.systemEnabled')
            : t('components.aiManager.searchProviders.systemDisabled') }}
        </n-tag>
      </div>
    </template>

    <n-tabs v-model:value="activeTab" type="line" animated>
      <n-tab-pane name="personal" :tab="t('components.aiManager.searchProviders.personalTab')">
        <div class="search-provider-list">
          <section v-for="provider in providers" :key="`personal-${provider.provider}`" class="search-provider-section">
            <div class="provider-header">
              <strong>{{ providerLabel(provider.provider) }}</strong>
              <n-tag size="small" :type="effectiveTagType(provider)">
                {{ effectiveLabel(provider) }}
              </n-tag>
            </div>

            <n-radio-group v-model:value="provider.personalMode" size="small">
              <n-radio-button value="inherit">
                {{ t('components.aiManager.searchProviders.inheritSystem') }}
              </n-radio-button>
              <n-radio-button value="custom">
                {{ t('components.aiManager.searchProviders.personalOverride') }}
              </n-radio-button>
            </n-radio-group>

            <n-form v-if="provider.personalMode === 'custom'" class="provider-form" label-placement="top" :show-feedback="false">
              <n-form-item :label="t('components.aiManager.searchProviders.urlLabel')">
                <n-input v-model:value="provider.personalUrl" :placeholder="provider.defaultUrl">
                  <template #prefix><n-icon><Link2 /></n-icon></template>
                </n-input>
              </n-form-item>
              <div class="provider-key-row">
                <n-form-item class="provider-key-input" :label="t('components.aiManager.searchProviders.apiKeyLabel')">
                  <n-input
                    v-model:value="provider.personalApiKey"
                    type="password"
                    show-password-on="click"
                    :disabled="provider.personalKeyless"
                    :placeholder="provider.personalApiKeySet
                      ? t('components.aiManager.searchProviders.keepKeyPlaceholder')
                      : t('components.aiManager.searchProviders.apiKeyPlaceholder')"
                    @update:value="() => { if (provider.personalApiKey) provider.personalKeyless = false; }"
                  >
                    <template #prefix><n-icon><KeyRound /></n-icon></template>
                  </n-input>
                </n-form-item>
                <n-checkbox v-model:checked="provider.personalKeyless" class="keyless-checkbox">
                  {{ t('components.aiManager.searchProviders.keylessMode') }}
                </n-checkbox>
              </div>
            </n-form>
          </section>
        </div>

        <div class="search-provider-actions">
          <n-button type="primary" :loading="savingPersonal" :disabled="loading || !personalCanSave" @click="savePersonalSettings">
            <template #icon><n-icon><Save /></n-icon></template>
            {{ t('components.aiManager.searchProviders.savePersonal') }}
          </n-button>
        </div>
      </n-tab-pane>

      <n-tab-pane v-if="isAdmin" name="system" :tab="t('components.aiManager.searchProviders.systemTab')">
        <div class="search-provider-list">
          <section v-for="provider in providers" :key="`system-${provider.provider}`" class="search-provider-section">
            <div class="provider-header">
              <strong>{{ providerLabel(provider.provider) }}</strong>
              <n-tag size="small" :type="provider.systemKeyless ? 'default' : 'success'">
                {{ provider.systemKeyless
                  ? t('components.aiManager.searchProviders.keylessStatus')
                  : t('components.aiManager.searchProviders.keyConfiguredStatus') }}
              </n-tag>
            </div>
            <n-form label-placement="top" :show-feedback="false">
              <n-form-item :label="t('components.aiManager.searchProviders.urlLabel')">
                <n-input v-model:value="provider.systemUrl" :placeholder="provider.defaultUrl">
                  <template #prefix><n-icon><Link2 /></n-icon></template>
                </n-input>
              </n-form-item>
              <div class="provider-key-row">
                <n-form-item class="provider-key-input" :label="t('components.aiManager.searchProviders.apiKeyLabel')">
                  <n-input
                    v-model:value="provider.systemApiKey"
                    type="password"
                    show-password-on="click"
                    :disabled="provider.systemKeyless"
                    :placeholder="provider.systemApiKeySet
                      ? t('components.aiManager.searchProviders.keepKeyPlaceholder')
                      : t('components.aiManager.searchProviders.apiKeyPlaceholder')"
                    @update:value="() => { if (provider.systemApiKey) provider.systemKeyless = false; }"
                  >
                    <template #prefix><n-icon><KeyRound /></n-icon></template>
                  </n-input>
                </n-form-item>
                <n-checkbox v-model:checked="provider.systemKeyless" class="keyless-checkbox">
                  {{ t('components.aiManager.searchProviders.keylessMode') }}
                </n-checkbox>
              </div>
            </n-form>
          </section>
        </div>

        <div class="search-provider-actions">
          <n-button type="primary" :loading="savingSystem" :disabled="loading || !systemCanSave" @click="saveSystemSettings">
            <template #icon><n-icon><Save /></n-icon></template>
            {{ t('components.aiManager.searchProviders.saveSystem') }}
          </n-button>
        </div>
      </n-tab-pane>
    </n-tabs>
  </n-card>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import {
  NButton,
  NCard,
  NCheckbox,
  NForm,
  NFormItem,
  NIcon,
  NInput,
  NRadioButton,
  NRadioGroup,
  NTabPane,
  NTabs,
  NTag,
  useMessage,
} from 'naive-ui';
import { KeyRound, Link2, Save, Search } from '@lucide/vue';

import { fetchWithAuth } from '@/services/api';

type SearchProviderName = 'exa' | 'tavily';
type PersonalMode = 'inherit' | 'custom';
type EffectiveSource = 'system' | 'user' | 'unavailable';

type SearchProviderState = {
  provider: SearchProviderName;
  defaultUrl: string;
  personalMode: PersonalMode;
  personalUrl: string;
  personalApiKey: string;
  personalApiKeySet: boolean;
  personalKeyless: boolean;
  systemUrl: string;
  systemApiKey: string;
  systemApiKeySet: boolean;
  systemKeyless: boolean;
  effectiveAvailable: boolean;
  effectiveSource: EffectiveSource;
};

const props = defineProps<{
  isAdmin?: boolean;
  systemServiceEnabled?: boolean;
}>();

const DEFAULT_URLS: Record<SearchProviderName, string> = {
  exa: 'https://mcp.exa.ai/mcp',
  tavily: 'https://mcp.tavily.com/mcp',
};

const { t } = useI18n();
const message = useMessage();
const activeTab = ref<'personal' | 'system'>('personal');
const loading = ref(false);
const savingPersonal = ref(false);
const savingSystem = ref(false);
const loadedSystemServiceEnabled = ref<boolean | null>(null);
const providers = ref<SearchProviderState[]>([
  createProviderState('exa'),
  createProviderState('tavily'),
]);

const isAdmin = computed(() => Boolean(props.isAdmin));
const systemServiceEnabledState = computed(() => (
  loadedSystemServiceEnabled.value ?? Boolean(props.systemServiceEnabled)
));
const personalCanSave = computed(() => providers.value.every((provider) => {
  if (provider.personalMode === 'inherit') return true;
  if (!provider.personalUrl.trim()) return false;
  return provider.personalKeyless || provider.personalApiKeySet || Boolean(provider.personalApiKey.trim());
}));
const systemCanSave = computed(() => providers.value.every((provider) => {
  if (!provider.systemUrl.trim()) return false;
  return provider.systemKeyless || provider.systemApiKeySet || Boolean(provider.systemApiKey.trim());
}));

function createProviderState(provider: SearchProviderName): SearchProviderState {
  return {
    provider,
    defaultUrl: DEFAULT_URLS[provider],
    personalMode: 'inherit',
    personalUrl: DEFAULT_URLS[provider],
    personalApiKey: '',
    personalApiKeySet: false,
    personalKeyless: true,
    systemUrl: DEFAULT_URLS[provider],
    systemApiKey: '',
    systemApiKeySet: false,
    systemKeyless: true,
    effectiveAvailable: false,
    effectiveSource: 'unavailable',
  };
}

function providerLabel(provider: SearchProviderName) {
  return t(`components.aiManager.searchProviders.providers.${provider}`);
}

function effectiveTagType(provider: SearchProviderState) {
  if (!provider.effectiveAvailable) return 'warning';
  return provider.effectiveSource === 'user' ? 'info' : 'success';
}

function effectiveLabel(provider: SearchProviderState) {
  if (!provider.effectiveAvailable) return t('components.aiManager.searchProviders.unavailableStatus');
  if (provider.effectiveSource === 'user') return t('components.aiManager.searchProviders.personalStatus');
  return t('components.aiManager.searchProviders.systemStatus');
}

function applyUserView(body: Record<string, unknown>) {
  loadedSystemServiceEnabled.value = Boolean(body.system_service_enabled);
  const rawProviders = Array.isArray(body.providers) ? body.providers : [];
  rawProviders.forEach((raw) => {
    if (!raw || typeof raw !== 'object') return;
    const view = raw as Record<string, any>;
    const provider = String(view.provider || '').toLowerCase() as SearchProviderName;
    const target = providers.value.find((item) => item.provider === provider);
    if (!target) return;

    const system = view.system && typeof view.system === 'object' ? view.system : {};
    const user = view.user && typeof view.user === 'object' ? view.user : {};
    const effective = view.effective && typeof view.effective === 'object' ? view.effective : {};
    target.systemUrl = String(system.url || target.defaultUrl);
    target.systemApiKey = '';
    target.systemApiKeySet = Boolean(system.api_key_set);
    target.systemKeyless = !target.systemApiKeySet;
    target.personalMode = user.configured ? 'custom' : 'inherit';
    target.personalUrl = String(user.url || effective.url || system.url || target.defaultUrl);
    target.personalApiKey = '';
    target.personalApiKeySet = Boolean(user.api_key_set);
    target.personalKeyless = user.configured ? !target.personalApiKeySet : true;
    target.effectiveAvailable = Boolean(effective.available);
    target.effectiveSource = ['system', 'user'].includes(String(effective.source))
      ? effective.source as EffectiveSource
      : 'unavailable';
  });
}

async function readJson(response: Response) {
  const body = await response.json().catch(() => ({}));
  if (!response.ok || body.success === false) {
    const detail = typeof body.detail === 'string' ? body.detail : body.message;
    throw new Error(detail || t('components.aiManager.searchProviders.messages.requestFailed'));
  }
  return body;
}

async function loadSettings() {
  loading.value = true;
  try {
    const response = await fetchWithAuth('/api/ai/search-providers');
    applyUserView(await readJson(response));
  } catch (error: unknown) {
    message.error(error instanceof Error ? error.message : t('components.aiManager.searchProviders.messages.loadFailed'));
  } finally {
    loading.value = false;
  }
}

async function savePersonalSettings() {
  if (!personalCanSave.value) return;
  savingPersonal.value = true;
  try {
    for (const provider of providers.value) {
      if (provider.personalMode === 'inherit') {
        const response = await fetchWithAuth(`/api/ai/search-providers/${provider.provider}`, { method: 'DELETE' });
        await readJson(response);
        continue;
      }
      const payload: Record<string, unknown> = {
        provider: provider.provider,
        url: provider.personalUrl.trim() || provider.defaultUrl,
      };
      if (provider.personalKeyless) payload.api_key = '';
      else if (provider.personalApiKey.trim()) payload.api_key = provider.personalApiKey.trim();
      const response = await fetchWithAuth('/api/ai/search-providers', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      await readJson(response);
    }
    await loadSettings();
    message.success(t('components.aiManager.searchProviders.messages.personalSaved'));
  } catch (error: unknown) {
    message.error(error instanceof Error ? error.message : t('components.aiManager.searchProviders.messages.saveFailed'));
  } finally {
    savingPersonal.value = false;
  }
}

async function saveSystemSettings() {
  if (!isAdmin.value || !systemCanSave.value) return;
  savingSystem.value = true;
  try {
    for (const provider of providers.value) {
      const payload: Record<string, unknown> = {
        provider: provider.provider,
        url: provider.systemUrl.trim() || provider.defaultUrl,
      };
      if (provider.systemKeyless) payload.api_key = '';
      else if (provider.systemApiKey.trim()) payload.api_key = provider.systemApiKey.trim();
      const response = await fetchWithAuth('/api/admin/config/search-providers', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      await readJson(response);
    }
    await loadSettings();
    message.success(t('components.aiManager.searchProviders.messages.systemSaved'));
  } catch (error: unknown) {
    message.error(error instanceof Error ? error.message : t('components.aiManager.searchProviders.messages.saveFailed'));
  } finally {
    savingSystem.value = false;
  }
}

watch(() => props.systemServiceEnabled, (value) => {
  if (typeof value === 'boolean') loadedSystemServiceEnabled.value = value;
});

onMounted(() => {
  void loadSettings();
});
</script>

<style scoped>
.search-provider-settings {
  margin-top: 20px;
}

.search-provider-title-row,
.search-provider-title,
.provider-header,
.search-provider-actions {
  display: flex;
  align-items: center;
}

.search-provider-title-row,
.provider-header {
  justify-content: space-between;
  gap: 12px;
}

.search-provider-title {
  gap: 8px;
  color: var(--spark-text-primary);
  font-weight: 600;
}

.search-provider-list {
  display: flex;
  flex-direction: column;
}

.search-provider-section {
  padding: 8px 0 18px;
}

.search-provider-section + .search-provider-section {
  padding-top: 20px;
  border-top: 1px solid var(--spark-border);
}

.provider-header {
  margin-bottom: 12px;
}

.provider-form {
  margin-top: 14px;
}

.provider-key-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: end;
  gap: 14px;
}

.provider-key-input {
  min-width: 0;
}

.keyless-checkbox {
  min-height: 34px;
  padding-bottom: 2px;
  white-space: nowrap;
}

.search-provider-actions {
  justify-content: flex-end;
  padding-top: 4px;
}

@media (max-width: 640px) {
  .search-provider-title-row {
    align-items: flex-start;
  }

  .provider-key-row {
    grid-template-columns: minmax(0, 1fr);
    gap: 0;
  }

  .keyless-checkbox {
    margin: 0 0 14px;
  }
}
</style>
