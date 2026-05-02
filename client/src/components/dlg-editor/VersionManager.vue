<template>
  <div class="version-manager">
    <div class="header">
      <div class="left">
        <div class="title-row">
          <h3>{{ t('components.versionManager.title') }}</h3>
          <n-tag size="small" :type="contentFormat === 'novel' ? 'warning' : 'info'">
            {{ t('components.versionManager.currentMode') }}：{{ contentFormat === 'novel' ? t('components.versionManager.modeNovel') : t('components.versionManager.modeScript') }}
          </n-tag>
        </div>
        <n-text depth="3" class="subtitle">{{ t('components.versionManager.subtitle') }}</n-text>
      </div>
      <n-space align="center">
        <n-button type="primary" @click="openCreateModal">
          <template #icon><n-icon :component="Save" /></template>
          {{ t('components.versionManager.createVersion') }}
        </n-button>
      </n-space>
    </div>

    <n-alert v-if="globalShareDisabled" type="warning" class="share-disabled-banner" :show-icon="true">
      {{ t('components.versionManager.publicShareDisabledBanner') }}
    </n-alert>

    <div class="filter-bar" v-if="!projectId">
      <n-select 
        v-model:value="filterProject" 
        :options="projectOptions" 
        :placeholder="t('components.versionManager.filterProject')" 
        clearable 
        @update:value="loadVersions"
        style="width: 200px"
      />
    </div>

    <n-spin :show="loading">
      <div class="version-list">
        <n-empty v-if="versions.length === 0" :description="t('components.versionManager.empty')" />
        
        <n-card v-for="ver in versions" :key="ver.id" class="version-item" size="small">
          <template #header>
            <div class="version-header">
              <span class="version-title">{{ ver.version_name }}</span>
              <n-tag size="small" :type="ver.content_format === 'novel' ? 'warning' : 'info'">
                {{ ver.content_format === 'novel' ? t('components.versionManager.modeNovel') : t('components.versionManager.modeScript') }}
              </n-tag>
            </div>
          </template>
          <template #header-extra>
            <n-text depth="3" size="small">{{ formatDate(ver.created_at) }}</n-text>
          </template>
          
          <div class="version-content">
            <div class="version-desc">{{ ver.description || t('components.versionManager.noDescription') }}</div>
            <n-alert
              v-if="globalShareDisabled && ver.is_shared"
              type="warning"
              class="version-warning"
              :show-icon="false"
            >
              {{ t('components.versionManager.publicShareDisabledOnItem') }}
            </n-alert>
            <n-space class="version-top-actions" justify="end" align="center" wrap>
              <n-button size="small" secondary @click="downloadVersionSnapshot(ver)">
                <template #icon><n-icon :component="CloudDownload" /></template>
                {{ ver.content_format === 'novel' ? t('components.versionManager.exportNovel') : t('components.versionManager.exportScript') }}
              </n-button>

              <n-popconfirm v-if="ver.content_format !== 'novel'" @positive-click="restoreVersion(ver)">
                <template #trigger>
                  <n-button size="small" secondary>
                    <template #icon><n-icon :component="RefreshCw" /></template>
                    {{ t('components.versionManager.restoreToThisVersion') }}
                  </n-button>
                </template>
                {{ t('components.versionManager.confirmRestore') }}
              </n-popconfirm>

              <n-popconfirm @positive-click="deleteVersion(ver.id)">
                <template #trigger>
                  <n-button size="small" type="error" ghost>
                    <template #icon><n-icon :component="Trash" /></template>
                  </n-button>
                </template>
                {{ t('components.versionManager.confirmDelete') }}
              </n-popconfirm>
            </n-space>
          </div>
          
          <template #action>
            <div class="action-row">
              <div class="action-right-group">
                <n-space class="action-buttons" align="center" wrap>
                  <n-button size="small" :disabled="!ver.is_shared || globalShareDisabled" @click="copyLink(ver.share_id)">
                    <template #icon><n-icon :component="Copy" /></template>
                    {{ t('components.versionManager.copyLink') }}
                  </n-button>

                  <n-button size="small" @click="editVersion(ver)">
                    <template #icon><n-icon :component="SquarePen" /></template>
                    {{ t('components.versionManager.edit') }}
                  </n-button>
                  
                  <n-button size="small" type="info" @click="openLink(ver.share_id || ver.id)">
                    <template #icon><n-icon :component="Play" /></template>
                    {{ ver.content_format === 'novel' ? t('components.versionManager.previewRead') : t('components.versionManager.previewPlay') }}
                  </n-button>
                </n-space>

                <div
                  class="share-toggle"
                  :title="globalShareDisabled
                    ? t('components.versionManager.publicShareDisabledTooltip')
                    : ver.is_shared
                      ? t('components.versionManager.shareEnabledTooltip')
                      : t('components.versionManager.shareDisabledTooltip')"
                >
                  <n-text depth="3" class="share-state-label">{{ ver.is_shared ? t('components.versionManager.public') : t('components.versionManager.private') }}</n-text>
                  <n-switch
                    size="small"
                    :value="ver.is_shared"
                    :disabled="globalShareDisabled"
                    @update:value="toggleShare(ver, $event)"
                  />
                </div>
              </div>
            </div>
          </template>
        </n-card>
      </div>
    </n-spin>

    <!-- Create/Edit Modal -->
    <n-modal v-model:show="showModal" preset="card" :title="isEditing ? t('components.versionManager.editVersionInfo') : t('components.versionManager.createVersion')" style="width: 500px">
      <n-form label-placement="top">
        <n-form-item :label="t('components.versionManager.project')" v-if="!projectId && !isEditing">
          <n-select v-model:value="formModel.projectName" :options="projectOptions" />
        </n-form-item>
        <n-form-item :label="t('components.versionManager.versionName')">
          <n-input v-model:value="formModel.versionName" :placeholder="t('components.versionManager.versionNamePlaceholder')" />
        </n-form-item>
        <n-form-item v-if="!isEditing" :label="t('components.versionManager.versionType')">
          <n-select v-model:value="formModel.contentFormat" :options="formatOptions" />
        </n-form-item>
        <n-form-item :label="t('components.versionManager.descriptionOptional')">
          <n-input v-model:value="formModel.description" type="textarea" :placeholder="t('components.versionManager.descriptionPlaceholder')" />
        </n-form-item>
      </n-form>
      <template #footer>
        <n-space justify="end">
          <n-button @click="showModal = false">{{ t('views.common.cancel') }}</n-button>
          <n-button type="primary" :loading="submitting" @click="submitForm" :disabled="!canSubmit">
            {{ isEditing ? t('views.common.save') : t('views.common.create') }}
          </n-button>
        </n-space>
      </template>
    </n-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, computed, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { 
  NButton, NIcon, NCard, NEmpty, NTag, NSpace, NPopconfirm, NModal, NAlert,
  NForm, NFormItem, NSelect, NInput, NSwitch, NSpin, 
  NText, useMessage, useDialog
} from 'naive-ui';
import { CloudDownload, Copy, Play, RefreshCw, Save, SquarePen, Trash } from 'lucide-vue-next';
import { fetchWithAuth } from '@/services/api';
import { useProjectStore } from '@/components/stores/projectStore';
import bus from '@/eventBus';

type ContentFormat = 'script' | 'novel';

type VersionListItem = {
  id: string;
  project_name: string;
  version_name: string;
  description?: string;
  created_at?: string | null;
  content_format?: ContentFormat | null;
  is_shared?: boolean;
  share_id?: string | null;
  share_url?: string | null;
  share_url_public?: string | null;
};

type VersionFormModel = {
  id: string | null;
  projectName: string | null;
  versionName: string;
  description: string;
  contentFormat: ContentFormat;
};

const props = defineProps({
  projectId: { type: String, default: null },
  contentFormat: { type: String, default: 'script' }
});

const message = useMessage();
const dialog = useDialog();
const { t, locale } = useI18n();
const projectStore = useProjectStore();

const versions = ref<VersionListItem[]>([]);
const loading = ref(false);
const showModal = ref(false);
const submitting = ref(false);
const isEditing = ref(false);
const filterProject = ref<string | null>(null);
const globalShareDisabled = ref(true);

const formModel = ref<VersionFormModel>({
  id: null,
  projectName: null,
  versionName: '',
  description: '',
  contentFormat: props.contentFormat === 'novel' ? 'novel' : 'script'
});

const contentFormat = computed(() => props.contentFormat === 'novel' ? 'novel' : 'script');

const formatOptions = computed(() => [
  { label: t('components.versionManager.modeScript'), value: 'script' },
  { label: t('components.versionManager.modeNovel'), value: 'novel' },
]);

const projectOptions = computed(() => {
  return projectStore.projects.map(p => ({ label: p, value: p }));
});

const canSubmit = computed(() => {
  if (isEditing.value) return !!formModel.value.versionName;
  return (props.projectId || formModel.value.projectName) && formModel.value.versionName;
});

async function parseApiError(response: Response, fallback: string): Promise<string> {
  try {
    const payload = await response.json() as Record<string, unknown>;
    const detail = payload.detail;
    if (typeof payload.error === 'string' && payload.error) return payload.error;
    if (typeof payload.message === 'string' && payload.message) return payload.message;
    if (typeof detail === 'string' && detail) return detail;
    if (detail && typeof detail === 'object' && typeof (detail as { message?: unknown }).message === 'string') {
      return (detail as { message: string }).message;
    }
  } catch {
    // ignore invalid response body
  }
  return fallback;
}

async function loadPublicShareState() {
  try {
    const res = await fetchWithAuth('/api/admin/config/public-share-state');
    if (!res.ok) {
      globalShareDisabled.value = true;
      return;
    }
    const data = await res.json() as { success?: boolean; data?: { disable_public_share?: boolean } };
    globalShareDisabled.value = !!data.data?.disable_public_share;
  } catch {
    globalShareDisabled.value = true;
  }
}

async function loadVersions() {
  const targetProject = props.projectId || filterProject.value;
  if (!targetProject) {
    versions.value = [];
    return;
  }

  loading.value = true;
  try {
    const res = await fetchWithAuth(`/api/versions/${targetProject}`);
    if (res.ok) {
      versions.value = await res.json();
    } else {
      const errorMessage = await parseApiError(res, t('components.versionManager.loadFailed'));
      message.error(errorMessage);
    }
  } catch {
    message.error(t('components.versionManager.loadFailed'));
  } finally {
    loading.value = false;
  }
}

function openCreateModal() {
  isEditing.value = false;
  formModel.value = {
    id: null,
    projectName: props.projectId || filterProject.value || null,
    versionName: generateDefaultTitle(),
    description: '',
    contentFormat: contentFormat.value
  };
  showModal.value = true;
}

function generateDefaultTitle() {
  const date = new Date();
  const pad = (n) => n.toString().padStart(2, '0');
  return `v${date.getFullYear()}${pad(date.getMonth()+1)}${pad(date.getDate())}_${pad(date.getHours())}${pad(date.getMinutes())}`;
}

function editVersion(ver: VersionListItem) {
  isEditing.value = true;
  formModel.value = {
    id: ver.id,
    projectName: ver.project_name,
    versionName: ver.version_name,
    description: ver.description || '',
    contentFormat: ver.content_format || 'script'
  };
  showModal.value = true;
}

async function submitForm() {
  submitting.value = true;
  try {
    const targetProject = props.projectId || formModel.value.projectName;
    if (isEditing.value) {
      // Update
      const res = await fetchWithAuth(`/api/versions/${formModel.value.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          versionName: formModel.value.versionName,
          description: formModel.value.description
        })
      });
      if (res.ok) {
        message.success(t('components.versionManager.updateSuccess'));
        showModal.value = false;
        await loadVersions();
      } else {
        const errorMessage = await parseApiError(res, t('components.versionManager.updateFailed'));
        message.error(errorMessage);
      }
    } else {
      // Create
        const res = await fetchWithAuth(`/api/versions/${targetProject}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          versionName: formModel.value.versionName,
          description: formModel.value.description,
          contentFormat: formModel.value.contentFormat || contentFormat.value
        })
      });
      if (res.ok) {
        message.success(t('components.versionManager.created'));
        showModal.value = false;
        await loadVersions();
      } else {
        const errorMessage = await parseApiError(res, t('components.versionManager.createFailed'));
        message.error(errorMessage);
      }
    }
  } catch (e: unknown) {
    const errorMessage = e instanceof Error ? e.message : String(e || 'Unknown error');
    message.error(`${t('components.versionManager.operationFailed')}: ${errorMessage}`);
  } finally {
    submitting.value = false;
  }
}

async function toggleShare(ver: VersionListItem, value: boolean) {
  if (globalShareDisabled.value && value) {
    message.warning(t('components.versionManager.publicShareDisabledTooltip'));
    return;
  }

  if (value) {
    const confirmed = await confirmPublicShareEnable();
    if (!confirmed) return;
  }

  const oldVal = ver.is_shared;
  ver.is_shared = value;
  try {
    const res = await fetchWithAuth(`/api/versions/${ver.id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ is_shared: value })
    });
    if (!res.ok) {
      throw new Error(await parseApiError(res, t('components.versionManager.shareUpdateFailed')));
    }

    const data = await res.json().catch(() => ({} as { share_id?: string }));
    if (value && data.share_id) {
      ver.share_id = data.share_id;
    }
    
    message.success(value ? t('components.versionManager.switchedPublic') : t('components.versionManager.switchedPrivate'));
  } catch (e: unknown) {
    ver.is_shared = oldVal;
    const errorMessage = e instanceof Error ? e.message : t('components.versionManager.shareUpdateFailed');
    message.error(errorMessage);
  }
}

function confirmPublicShareEnable(): Promise<boolean> {
  return new Promise((resolve) => {
    dialog.warning({
      title: t('components.versionManager.publicShareEnableWarning.title'),
      content: t('components.versionManager.publicShareEnableWarning.content'),
      positiveText: t('components.versionManager.publicShareEnableWarning.positive'),
      negativeText: t('components.versionManager.publicShareEnableWarning.negative'),
      onPositiveClick: () => resolve(true),
      onNegativeClick: () => resolve(false),
      onClose: () => resolve(false),
      onEsc: () => resolve(false),
      onMaskClick: () => resolve(false),
    });
  });
}

async function deleteVersion(id: string) {
  try {
    const res = await fetchWithAuth(`/api/versions/${id}`, { method: 'DELETE' });
    if (res.ok) {
      message.success(t('views.common.deleted'));
      await loadVersions();
    } else {
      const errorMessage = await parseApiError(res, t('views.common.deleteFailed'));
      message.error(errorMessage);
    }
  } catch {
    message.error(t('views.common.deleteFailed'));
  }
}

async function restoreVersion(ver: VersionListItem) {
  try {
    const res = await fetchWithAuth(`/api/versions/${ver.id}/restore`, { method: 'POST' });
    if (res.ok) {
      message.success(t('components.versionManager.restoreSuccess'));
      // 触发全局事件或刷新
      window.location.reload(); 
    } else {
      const errorMessage = await parseApiError(res, t('components.versionManager.restoreFailed'));
      message.error(errorMessage);
    }
  } catch {
    message.error(t('components.versionManager.restoreFailed'));
  }
}

async function downloadVersionSnapshot(ver: VersionListItem) {
  try {
    const response = await fetchWithAuth(`/api/versions/${ver.id}/download`);
    if (!response.ok) {
      throw new Error(await parseApiError(response, t('components.versionManager.downloadFailed')));
    }

    const blob = await response.blob();
    const disposition = response.headers.get('Content-Disposition') || '';
    const nameMatch = disposition.match(/filename\*=UTF-8''([^;]+)|filename="?([^";]+)"?/i);
    const filename = decodeURIComponent(nameMatch?.[1] || nameMatch?.[2] || `${ver.version_name}.${ver.content_format === 'novel' ? 'md' : 'db'}`);
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    message.success(ver.content_format === 'novel' ? t('components.versionManager.exportNovelDone') : t('components.versionManager.exportScriptDone'));
  } catch (e: unknown) {
    const errorMessage = e instanceof Error ? e.message : String(e || 'Unknown error');
    message.error(`${t('components.versionManager.downloadFailed')}: ${errorMessage}`);
  }
}

function copyLink(shareId: string | null | undefined) {
  if (!shareId) return;
  if (globalShareDisabled.value) {
    message.warning(t('components.versionManager.publicShareDisabledTooltip'));
    return;
  }
  // 使用当前页面的基础路径（包含子路径和端口），确保链接在任何部署环境下都有效
  const baseUrl = window.location.href.split('#')[0];
  const url = `${baseUrl}#/play/v/${shareId}`;
  navigator.clipboard.writeText(url).then(() => {
    message.success(t('components.versionManager.linkCopied'));
  });
}

function openLink(shareId: string | null | undefined) {
  if (!shareId) return;
  // 使用相对路径（不带开头的 /），确保在子路径部署时不会跳到根域名
  const url = `#/play/v/${shareId}`;
  window.open(url, '_blank');
}

function formatDate(isoStr?: string | null) {
  if (!isoStr) return '';
  const localeCode = ['zh-CN', 'en-US', 'ja-JP'].includes(locale.value) ? locale.value : 'zh-CN';
  return new Date(isoStr).toLocaleString(localeCode);
}

function handleSystemConfigUpdated(payload: unknown) {
  if (
    payload &&
    typeof payload === 'object' &&
    typeof (payload as { disable_public_share?: unknown }).disable_public_share === 'boolean'
  ) {
    globalShareDisabled.value = (payload as { disable_public_share: boolean }).disable_public_share;
  }
}

watch(() => props.projectId, () => {
  void loadVersions();
});

onMounted(() => {
  void loadVersions();
  void loadPublicShareState();
  bus.on('system-config-updated', handleSystemConfigUpdated);
  if (projectStore.projects.length === 0) {
    void projectStore.loadProjects();
  }
});

onBeforeUnmount(() => {
  bus.off('system-config-updated', handleSystemConfigUpdated);
});
</script>

<style scoped>
.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.subtitle {
  font-size: 0.9em;
}

.filter-bar {
  margin-bottom: 16px;
}

.share-disabled-banner {
  margin-bottom: 12px;
}

.version-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.version-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.version-content {
  margin: 8px 0;
  display: flex;
  gap: 12px;
  align-items: flex-start;
  justify-content: space-between;
}

.version-desc {
  color: var(--n-text-color-3);
  font-size: 0.9em;
  flex: 1 1 auto;
  min-width: 0;
}

.version-top-actions {
  flex: 0 0 auto;
  align-self: center;
}

.version-warning {
  margin-top: 8px;
}

.title-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.action-row {
  display: flex;
  align-items: center;
  gap: 16px;
  width: 100%;
}

.action-right-group {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-left: auto;
}

.action-buttons {
  flex: 0 0 auto;
  min-width: 0;
  justify-content: flex-end;
}

.share-toggle {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 0 4px;
  flex: 0 0 auto;
}

.share-state-label {
  min-width: 2.5em;
  text-align: right;
  color: var(--n-primary-color);
  font-weight: 600;
}

.version-title {
  font-weight: bold;
}

.version-desc {
  color: var(--n-text-color-3);
  font-size: 0.9em;
}

@media (max-width: 720px) {
  .version-content,
  .action-row {
    flex-direction: column;
    align-items: stretch;
  }

  .version-top-actions,
  .action-buttons,
  .share-toggle {
    width: 100%;
    justify-content: flex-start;
    min-width: 0;
    margin-left: 0;
  }

  .action-right-group {
    width: 100%;
    margin-left: 0;
    flex-direction: column;
    align-items: stretch;
  }

  .title-row {
    align-items: flex-start;
  }
}
</style>
