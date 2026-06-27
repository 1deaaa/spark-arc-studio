<template>
  <n-card class="agent-skill-manager" size="small">
    <template #header>
      <div class="skill-header">
        <n-icon :component="BrainCircuit" size="18" />
        <span>{{ t('components.agentSkillManager.title') }}</span>
      </div>
    </template>
    <template #header-extra>
      <n-button text size="tiny" :loading="loading" @click="loadSkills">
        <template #icon><n-icon :component="RefreshCw" /></template>
      </n-button>
    </template>

    <div class="skill-intro">{{ t('components.agentSkillManager.description') }}</div>

    <div class="skill-actions">
      <n-input
        v-model:value="urlInput"
        size="small"
        :placeholder="t('components.agentSkillManager.urlPlaceholder')"
        clearable
      />
      <div class="skill-action-row">
        <n-button size="small" secondary :loading="importing" @click="importFromUrl">
          <template #icon><n-icon :component="CloudDownload" /></template>
          {{ t('components.agentSkillManager.importUrl') }}
        </n-button>
        <n-upload
          class="skill-upload-action"
          :show-file-list="false"
          :custom-request="handleUpload"
          accept=".md,.txt,.zip"
        >
          <n-button size="small" secondary :loading="uploading">
            <template #icon><n-icon :component="CloudUpload" /></template>
            {{ t('components.agentSkillManager.upload') }}
          </n-button>
        </n-upload>
      </div>
      <n-checkbox v-if="isAdmin" v-model:checked="publishGlobal" size="small">
        {{ t('components.agentSkillManager.publishGlobal') }}
      </n-checkbox>
    </div>

    <n-spin :show="loading">
      <div v-if="error" class="skill-error">{{ error }}</div>
      <div v-else-if="!skills.length" class="skill-empty">
        {{ t('components.agentSkillManager.empty') }}
      </div>
      <div v-else class="skill-list">
        <div v-for="skill in skills" :key="skill.skill_id" class="skill-item">
          <div class="skill-item-main">
            <div class="skill-name-row">
              <span class="skill-name">{{ skill.name }}</span>
              <SparkTag :type="skill.domain === 'global' ? 'primary' : 'default'" size="tiny">
                {{ skill.domain === 'global' ? t('components.agentSkillManager.global') : t('components.agentSkillManager.personal') }}
              </SparkTag>
              <SparkTag
                v-if="skill.compatibility_status === 'compatible_scripts_ignored'"
                type="warning"
                size="tiny"
              >
                {{ t('components.agentSkillManager.scriptsIgnored') }}
              </SparkTag>
            </div>
            <div class="skill-desc">{{ skill.description || t('components.agentSkillManager.noDescription') }}</div>
            <div class="skill-id">{{ skill.normalized_name }}</div>
          </div>
          <n-popconfirm
            v-if="canDelete(skill)"
            :positive-text="t('common.confirm')"
            :negative-text="t('common.cancel')"
            @positive-click="removeSkill(skill.skill_id)"
          >
            <template #trigger>
              <n-button text size="tiny" class="delete-btn">
                <template #icon><n-icon :component="Trash2" /></template>
              </n-button>
            </template>
            {{ t('components.agentSkillManager.deleteConfirm') }}
          </n-popconfirm>
        </div>
      </div>
    </n-spin>
  </n-card>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { useI18n } from 'vue-i18n';
import { NButton, NCard, NCheckbox, NIcon, NInput, NPopconfirm, NSpin, NUpload, useMessage } from 'naive-ui';
import type { UploadCustomRequestOptions } from 'naive-ui';
import { BrainCircuit, CloudDownload, CloudUpload, RefreshCw, Trash2 } from '@lucide/vue';
import SparkTag from '@/components/share/SparkTag.vue';
import {
  deleteAgentSkill,
  fetchAgentSkills,
  importAgentSkillFromUrl,
  type AgentSkillRecord,
  uploadAgentSkill,
} from '@/services/agentSkills';

const { t } = useI18n();
const message = useMessage();

const loading = ref(false);
const importing = ref(false);
const uploading = ref(false);
const error = ref('');
const urlInput = ref('');
const publishGlobal = ref(false);
const isAdmin = ref(false);
const skills = ref<AgentSkillRecord[]>([]);

async function loadSkills() {
  loading.value = true;
  error.value = '';
  try {
    const data = await fetchAgentSkills();
    isAdmin.value = Boolean(data.is_admin);
    skills.value = data.skills || [];
  } catch (err: unknown) {
    error.value = err instanceof Error ? err.message : t('components.agentSkillManager.loadFailed');
  } finally {
    loading.value = false;
  }
}

async function importFromUrl() {
  const url = urlInput.value.trim();
  if (!url) {
    message.warning(t('components.agentSkillManager.urlRequired'));
    return;
  }
  importing.value = true;
  try {
    const results = await importAgentSkillFromUrl(url, publishGlobal.value);
    await loadSkills();
    message.success(t('components.agentSkillManager.importSuccess', { count: results.length }));
    urlInput.value = '';
  } catch {
    message.error(t('components.agentSkillManager.importFailed'));
  } finally {
    importing.value = false;
  }
}

async function handleUpload(options: UploadCustomRequestOptions) {
  const rawFile = options.file.file;
  if (!rawFile) {
    options.onError();
    return;
  }
  uploading.value = true;
  try {
    const results = await uploadAgentSkill(rawFile, publishGlobal.value);
    await loadSkills();
    message.success(t('components.agentSkillManager.uploadSuccess', { count: results.length }));
    options.onFinish();
  } catch {
    message.error(t('components.agentSkillManager.uploadFailed'));
    options.onError();
  } finally {
    uploading.value = false;
  }
}

function canDelete(skill: AgentSkillRecord) {
  return skill.domain !== 'global' || isAdmin.value;
}

async function removeSkill(skillId: string) {
  try {
    await deleteAgentSkill(skillId);
    await loadSkills();
    message.success(t('components.agentSkillManager.deleteSuccess'));
  } catch {
    message.error(t('components.agentSkillManager.deleteFailed'));
  }
}

onMounted(loadSkills);
</script>

<style scoped>
.agent-skill-manager {
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.agent-skill-manager :deep(.n-card__content) {
  flex: 1 1 auto;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.skill-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.skill-intro {
  margin-bottom: 12px;
  color: var(--spark-text-muted);
  font-size: var(--spark-fs-xs);
  line-height: 1.5;
}

.skill-actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 12px;
}

.skill-action-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.skill-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  flex: 1 1 auto;
  min-height: 0;
  overflow: auto;
}

.skill-item {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
  padding: 10px;
  border: 1px solid var(--spark-border);
  border-radius: 8px;
  background: color-mix(in srgb, var(--spark-panel-bg), var(--spark-bg) 18%);
}

.skill-item-main {
  min-width: 0;
}

.skill-name-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 4px;
}

.skill-name {
  color: var(--spark-text);
  font-size: var(--spark-fs-sm);
  font-weight: 600;
}

.skill-desc {
  color: var(--spark-text-muted);
  font-size: var(--spark-fs-xs);
  line-height: 1.45;
}

.skill-id {
  margin-top: 4px;
  color: var(--spark-text-subtle);
  font-size: var(--spark-fs-2xs);
  word-break: break-all;
}

.skill-empty,
.skill-error {
  padding: 14px 10px;
  color: var(--spark-text-muted);
  font-size: var(--spark-fs-sm);
  text-align: center;
}

.skill-error {
  color: var(--spark-danger);
}

.delete-btn {
  color: var(--spark-text-muted);
}

@media (max-width: 720px) {
  .agent-skill-manager {
    height: auto;
  }

  .agent-skill-manager :deep(.n-card__content) {
    display: block;
  }

  .skill-intro {
    margin-bottom: 10px;
    line-height: 1.55;
  }

  .skill-actions {
    gap: 8px;
    margin-bottom: 10px;
  }

  .skill-action-row {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 8px;
  }

  .skill-upload-action,
  .skill-action-row :deep(.n-button) {
    width: 100%;
    min-width: 0;
  }

  .skill-action-row :deep(.n-upload-trigger) {
    width: 100%;
  }

  .skill-action-row :deep(.n-button__content) {
    min-width: 0;
    max-width: 100%;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .skill-list {
    max-height: none;
  }

  .skill-empty,
  .skill-error {
    padding: 12px 8px 6px;
  }
}
</style>
