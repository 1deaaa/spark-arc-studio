<template>
  <n-modal
    :show="show"
    preset="card"
    class="agent-prompt-modal-card"
    :style="{ width: 'min(640px, calc(100vw - 32px))' }"
    :bordered="false"
    :mask-closable="!saving"
    @update:show="emit('update:show', $event)"
  >
    <template #header>
      <div class="prompt-modal-header">
        <span>{{ modalTitle }}</span>
        <n-tooltip trigger="hover">
          <template #trigger>
            <n-button text circle size="tiny" class="prompt-info-trigger">
              <template #icon><n-icon :component="CircleHelp" /></template>
            </n-button>
          </template>
          <div class="prompt-info-tooltip">
            <div class="prompt-info-tooltip-title">{{ t('components.agentModelCard.promptPreferencesInfoTitle') }}</div>
            <div>{{ t('components.agentModelCard.promptPreferencesInfoBody') }}</div>
          </div>
        </n-tooltip>
      </div>
    </template>
    <n-spin :show="loading">
      <div class="prompt-modal-body">
        <template v-if="preferences">
          <n-collapse v-if="preferences.default_content" class="system-recommendation" :default-expanded-names="[]">
            <n-collapse-item :title="t('components.agentModelCard.viewSystemRecommended')" name="system-recommended">
              <n-input
                :value="preferences.default_content"
                type="textarea"
                :autosize="{ minRows: 3, maxRows: 7 }"
                readonly
              />
            </n-collapse-item>
          </n-collapse>

          <n-form-item :label="t('components.agentModelCard.promptOverride')" label-placement="top" size="small">
            <n-input
              v-model:value="draftContent"
              type="textarea"
              :autosize="{ minRows: 6, maxRows: 10 }"
              :placeholder="t('components.agentModelCard.promptOverridePlaceholder')"
              :disabled="saving"
            />
          </n-form-item>

          <div class="prompt-actions">
            <div class="prompt-action-buttons">
              <n-button secondary :loading="loading" :disabled="saving" @click="reload">
                <template #icon><n-icon :component="RefreshCw" /></template>
                {{ t('components.agentModelCard.reloadPromptPreferences') }}
              </n-button>
              <n-button secondary :disabled="saving || !preferences.customized" @click="resetPreference">
                <template #icon><n-icon :component="RotateCcw" /></template>
                {{ t('components.agentModelCard.resetPromptPreference') }}
              </n-button>
              <n-button type="primary" :loading="saving" @click="savePreference">
                <template #icon><n-icon :component="Save" /></template>
                {{ t('components.agentModelCard.savePromptPreference') }}
              </n-button>
            </div>
          </div>
        </template>

        <div v-else class="empty-state">
          {{ t('components.agentModelCard.noPromptPreferences') }}
        </div>
      </div>
    </n-spin>
  </n-modal>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import {
  NButton,
  NCollapse,
  NCollapseItem,
  NFormItem,
  NIcon,
  NInput,
  NModal,
  NSpin,
  NTooltip,
  useMessage,
} from 'naive-ui';
import { CircleHelp, RefreshCw, RotateCcw, Save } from '@lucide/vue';
import {
  fetchAgentPromptPreferences,
  resetAgentPromptPreference,
  saveAgentPromptPreference,
  type PromptPreferenceState,
} from '@/services/agentPromptPreferences';

const props = defineProps<{
  show: boolean;
  agentId?: string | null;
  agentName?: string | null;
}>();

const emit = defineEmits<{
  (event: 'update:show', value: boolean): void;
  (event: 'changed', value: PromptPreferenceState): void;
}>();

const { t } = useI18n();
const message = useMessage();

const loading = ref(false);
const saving = ref(false);
const preferences = ref<PromptPreferenceState | null>(null);
const draftContent = ref('');

const modalTitle = computed(() => {
  const name = props.agentName || props.agentId || '';
  return name ? `${name} · ${t('components.agentModelCard.promptPreferences')}` : t('components.agentModelCard.promptPreferences');
});

function syncDraft(state: PromptPreferenceState | null) {
  if (!state) {
    draftContent.value = '';
    return;
  }
  draftContent.value = state.override_content || '';
}

async function loadPreferences(agentId: string | null | undefined) {
  if (!agentId) {
    preferences.value = null;
    syncDraft(null);
    return;
  }

  loading.value = true;
  try {
    const state = await fetchAgentPromptPreferences(agentId);
    preferences.value = state;
    syncDraft(state);
  } catch (err) {
    console.warn('Failed to load prompt preferences', err);
    message.error(t('components.agentModelCard.promptLoadFailed'));
    preferences.value = null;
    syncDraft(null);
  } finally {
    loading.value = false;
  }
}

async function reload() {
  await loadPreferences(props.agentId);
}

async function savePreference() {
  const agentId = props.agentId;
  if (!agentId || !preferences.value) return;

  saving.value = true;
  try {
    const nextState = await saveAgentPromptPreference(agentId, draftContent.value);
    preferences.value = nextState;
    syncDraft(nextState);
    emit('changed', nextState);
    message.success(t('components.agentModelCard.promptSaveSuccess'));
  } catch (err) {
    console.warn('Failed to save prompt preference', err);
    message.error(t('components.agentModelCard.promptSaveFailed'));
  } finally {
    saving.value = false;
  }
}

async function resetPreference() {
  const agentId = props.agentId;
  if (!agentId || !preferences.value) return;

  saving.value = true;
  try {
    const nextState = await resetAgentPromptPreference(agentId);
    preferences.value = nextState;
    syncDraft(nextState);
    emit('changed', nextState);
    message.success(t('components.agentModelCard.promptResetSuccess'));
  } catch (err) {
    console.warn('Failed to reset prompt preference', err);
    message.error(t('components.agentModelCard.promptResetFailed'));
  } finally {
    saving.value = false;
  }
}

watch(() => props.show, (visible) => {
  if (visible) {
    loadPreferences(props.agentId);
  }
});

watch(() => props.agentId, (agentId) => {
  if (props.show) {
    loadPreferences(agentId);
  }
});
</script>

<style scoped>
.prompt-modal-body {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.prompt-modal-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.prompt-info-trigger {
  color: var(--spark-text-muted);
}

.prompt-info-tooltip {
  max-width: 360px;
  font-size: var(--spark-fs-xs);
  line-height: 1.6;
  color: var(--n-text-color);
}

.prompt-info-tooltip-title {
  margin-bottom: 4px;
  font-weight: 600;
  color: var(--n-text-color);
}

.system-recommendation {
  padding: 0 8px;
  border: 1px solid var(--spark-border);
  border-radius: 8px;
}

.prompt-actions {
  padding-top: 2px;
}

.prompt-action-buttons {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: flex-end;
}

.empty-state {
  text-align: center;
  padding: 24px;
  color: var(--spark-text-muted);
  font-size: var(--spark-fs-sm);
}
</style>
