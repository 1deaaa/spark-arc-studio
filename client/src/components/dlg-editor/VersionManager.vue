<template>
  <div class="version-manager">
    <div class="vm-toolbar">
      <div class="vm-toolbar__info">
        <div class="title-row">
          <h3 class="vm-title">{{ t('components.versionManager.title') }}</h3>
          <n-tag size="small" :type="contentFormat === 'novel' ? 'warning' : 'info'">
            {{ t('components.versionManager.currentMode') }}：{{ contentFormat === 'novel' ? t('components.versionManager.modeNovel') : t('components.versionManager.modeScript') }}
          </n-tag>
        </div>
        <n-text depth="3" class="subtitle">{{ t('components.versionManager.subtitle') }}</n-text>
      </div>
      <n-button class="vm-create-btn" type="primary" @click="openCreateModal">
        <template #icon><n-icon :component="Save" /></template>
        {{ t('components.versionManager.createVersion') }}
      </n-button>
    </div>

    <n-alert v-if="globalShareDisabled" type="warning" class="share-disabled-banner" :show-icon="true">
      {{ t('components.versionManager.publicShareDisabledBanner') }}
    </n-alert>

    <div class="filter-bar" v-if="!projectId">
      <n-select 
        class="filter-bar__select"
        v-model:value="filterProject" 
        :options="projectOptions" 
        :placeholder="t('components.versionManager.filterProject')" 
        clearable 
        @update:value="loadVersions"
      />
    </div>

    <n-spin :show="loading || !!shareToggleVersionId" :description="spinDescription">
      <div class="version-list">
        <n-empty v-if="versions.length === 0" :description="t('components.versionManager.empty')" />
        
        <n-card v-for="ver in versions" :key="ver.id" class="version-item" size="small">
          <template #header>
            <div class="version-card-header">
              <div class="version-card-header__main">
                <span class="version-title">{{ ver.version_name }}</span>
                <n-tag size="small" :type="ver.content_format === 'novel' ? 'warning' : 'info'">
                  {{ ver.content_format === 'novel' ? t('components.versionManager.modeNovel') : t('components.versionManager.modeScript') }}
                </n-tag>
              </div>
              <div class="version-card-header__meta">
                <n-text depth="3" size="small" class="version-date">{{ formatDate(ver.created_at) }}</n-text>
                <n-tooltip trigger="hover">
                  <template #trigger>
                    <div class="share-toggle">
                      <n-text depth="3" size="small" class="share-state-label">{{ ver.is_shared ? t('components.versionManager.public') : t('components.versionManager.private') }}</n-text>
                      <n-switch
                        size="small"
                        :value="ver.is_shared"
                        :loading="shareToggleVersionId === ver.id"
                        :disabled="globalShareDisabled || !!shareToggleVersionId"
                        @update:value="toggleShare(ver, $event)"
                      />
                    </div>
                  </template>
                  {{
                    globalShareDisabled
                      ? t('components.versionManager.publicShareDisabledTooltip')
                      : ver.is_shared
                        ? t('components.versionManager.shareEnabledTooltip')
                        : t('components.versionManager.shareDisabledTooltip')
                  }}
                </n-tooltip>
              </div>
            </div>
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

            <div class="version-actions">
              <div class="version-actions__primary">
                <n-button
                  size="small"
                  type="info"
                  strong
                  class="vm-action-btn vm-action-btn--play"
                  @click="openLink(ver.share_id || ver.id)"
                >
                  <template #icon><n-icon :component="Play" /></template>
                  {{ ver.content_format === 'novel' ? t('components.versionManager.previewRead') : t('components.versionManager.previewPlay') }}
                </n-button>
                <n-button
                  size="small"
                  class="vm-action-btn"
                  :disabled="!ver.is_shared || globalShareDisabled"
                  @click="copyLink(ver.share_id)"
                >
                  <template #icon><n-icon :component="Copy" /></template>
                  {{ t('components.versionManager.copyLink') }}
                </n-button>
                <n-button
                  size="small"
                  secondary
                  class="vm-action-btn"
                  @click="editVersion(ver)"
                >
                  <template #icon><n-icon :component="SquarePen" /></template>
                  {{ t('components.versionManager.edit') }}
                </n-button>
              </div>

              <div class="version-actions__secondary">
                <n-button size="tiny" quaternary @click="downloadVersionSnapshot(ver)">
                  <template #icon><n-icon :component="CloudDownload" /></template>
                  {{ ver.content_format === 'novel' ? t('components.versionManager.exportNovel') : t('components.versionManager.exportScript') }}
                </n-button>

                <n-popconfirm v-if="ver.content_format !== 'novel'" @positive-click="restoreVersion(ver)">
                  <template #trigger>
                    <n-button size="tiny" quaternary>
                      <template #icon><n-icon :component="RefreshCw" /></template>
                      {{ t('components.versionManager.restoreToThisVersion') }}
                    </n-button>
                  </template>
                  {{ t('components.versionManager.confirmRestore') }}
                </n-popconfirm>

                <span class="version-actions__spacer" />

                <n-popconfirm @positive-click="deleteVersion(ver.id)">
                  <template #trigger>
                    <n-button size="tiny" type="error" quaternary class="vm-delete-btn">
                      <template #icon><n-icon :component="Trash" /></template>
                    </n-button>
                  </template>
                  {{ t('components.versionManager.confirmDelete') }}
                </n-popconfirm>
              </div>
            </div>
          </div>
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
import { ref, onMounted, onBeforeUnmount, computed, watch, h } from 'vue';
import { useI18n } from 'vue-i18n';
import { 
  NButton, NIcon, NCard, NEmpty, NTag, NSpace, NPopconfirm, NModal, NAlert,
  NForm, NFormItem, NSelect, NInput, NSwitch, NSpin,
  NText, NTooltip, useMessage, useDialog
} from 'naive-ui';
import { CloudDownload, Copy, Play, RefreshCw, Save, SquarePen, Trash } from 'lucide-vue-next';
import { fetchWithAuth } from '@/services/api';
import { useMainlandComplianceLocale } from '@/i18n/compliance';
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

type ShareReviewPayload = {
  decision?: string;
  reason?: string;
  risk_tags?: string[];
  evidence?: string[];
  rejected_chunk_index?: number | null;
  total_chunks?: number;
};

type ApiFailure = {
  message: string;
  review: ShareReviewPayload | null;
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
const showMainlandComplianceFeatures = useMainlandComplianceLocale();
const projectStore = useProjectStore();

const versions = ref<VersionListItem[]>([]);
const loading = ref(false);
const shareToggleVersionId = ref<string | null>(null);
const showModal = ref(false);
const submitting = ref(false);
const isEditing = ref(false);
const filterProject = ref<string | null>(null);
const globalShareDisabled = ref(true);
const publicShareReviewEffective = ref(false);

const SHARE_UPDATE_HANDLED_ERROR = '__SHARE_UPDATE_HANDLED__';

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

const spinDescription = computed(() => {
  if (shareToggleVersionId.value) {
    return publicShareReviewEffective.value
      ? t('components.versionManager.shareReviewLoading')
      : t('components.versionManager.shareToggleLoading');
  }
  return '';
});

const canSubmit = computed(() => {
  if (isEditing.value) return !!formModel.value.versionName;
  return (props.projectId || formModel.value.projectName) && formModel.value.versionName;
});

async function parseApiFailure(response: Response, fallback: string): Promise<ApiFailure> {
  let payload: Record<string, unknown> | null = null;
  try {
    payload = await response.json() as Record<string, unknown>;
  } catch {
    return { message: fallback, review: null };
  }

  let messageText = fallback;
  try {
    const detail = payload.detail;
    if (typeof payload.error === 'string' && payload.error) messageText = payload.error;
    else if (typeof payload.message === 'string' && payload.message) messageText = payload.message;
    else if (typeof detail === 'string' && detail) messageText = detail;
    if (detail && typeof detail === 'object' && typeof (detail as { message?: unknown }).message === 'string') {
      messageText = (detail as { message: string }).message;
    }
  } catch {
  }

  const rawReview = payload.review;
  if (!rawReview || typeof rawReview !== 'object' || Array.isArray(rawReview)) {
    return { message: messageText, review: null };
  }

  const reviewRecord = rawReview as Record<string, unknown>;
  return {
    message: messageText,
    review: {
      decision: typeof reviewRecord.decision === 'string' ? reviewRecord.decision : undefined,
      reason: typeof reviewRecord.reason === 'string' ? reviewRecord.reason : undefined,
      risk_tags: Array.isArray(reviewRecord.risk_tags)
        ? reviewRecord.risk_tags.filter((item): item is string => typeof item === 'string' && !!item.trim())
        : [],
      evidence: Array.isArray(reviewRecord.evidence)
        ? reviewRecord.evidence.filter((item): item is string => typeof item === 'string' && !!item.trim())
        : [],
      rejected_chunk_index: typeof reviewRecord.rejected_chunk_index === 'number' ? reviewRecord.rejected_chunk_index : null,
      total_chunks: typeof reviewRecord.total_chunks === 'number' ? reviewRecord.total_chunks : undefined,
    },
  };
}

async function parseApiError(response: Response, fallback: string): Promise<string> {
  return (await parseApiFailure(response, fallback)).message;
}

async function loadPublicShareState() {
  try {
    const res = await fetchWithAuth('/api/admin/config/public-share-state');
    if (!res.ok) {
      globalShareDisabled.value = true;
      publicShareReviewEffective.value = false;
      return;
    }
    const data = await res.json() as {
      success?: boolean;
      data?: {
        disable_public_share?: boolean;
        force_public_share_review?: boolean;
        force_public_share_review_effective?: boolean;
      };
    };
    globalShareDisabled.value = !!data.data?.disable_public_share;
    publicShareReviewEffective.value = typeof data.data?.force_public_share_review_effective === 'boolean'
      ? !!data.data?.force_public_share_review_effective
      : (showMainlandComplianceFeatures.value && !!data.data?.force_public_share_review);
  } catch {
    globalShareDisabled.value = true;
    publicShareReviewEffective.value = false;
  }
}

function showShareReviewRejectedDialog(review: ShareReviewPayload | null, fallbackMessage: string) {
  const reason = review?.reason || fallbackMessage;
  const riskTags = review?.risk_tags || [];
  const evidence = review?.evidence || [];

  dialog.warning({
    title: t('components.versionManager.shareReviewRejectedDialog.title'),
    positiveText: t('common.confirm'),
    content: () => h('div', { class: 'share-review-dialog' }, [
      h('p', { class: 'share-review-dialog-intro' }, t('components.versionManager.shareReviewRejectedDialog.intro')),
      h('div', { class: 'share-review-dialog-block' }, [
        h('div', { class: 'share-review-dialog-label' }, t('components.versionManager.shareReviewRejectedDialog.reasonLabel')),
        h('div', { class: 'share-review-dialog-text' }, reason),
      ]),
      ...(riskTags.length > 0
        ? [
            h('div', { class: 'share-review-dialog-block' }, [
              h('div', { class: 'share-review-dialog-label' }, t('components.versionManager.shareReviewRejectedDialog.riskTagsLabel')),
              h('ul', { class: 'share-review-dialog-list' }, riskTags.map((item) => h('li', { class: 'share-review-dialog-item' }, item))),
            ]),
          ]
        : []),
      ...(evidence.length > 0
        ? [
            h('div', { class: 'share-review-dialog-block' }, [
              h('div', { class: 'share-review-dialog-label' }, t('components.versionManager.shareReviewRejectedDialog.evidenceLabel')),
              h('ul', { class: 'share-review-dialog-list' }, evidence.map((item) => h('li', { class: 'share-review-dialog-item' }, item))),
            ]),
          ]
        : []),
      h('div', { class: 'share-review-dialog-footer' }, t('components.versionManager.shareReviewRejectedDialog.footer')),
    ]),
  });
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
  shareToggleVersionId.value = ver.id;
  try {
    const res = await fetchWithAuth(`/api/versions/${ver.id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ is_shared: value })
    });
    if (!res.ok) {
      const failure = await parseApiFailure(res, t('components.versionManager.shareUpdateFailed'));
      if (failure.review) {
        showShareReviewRejectedDialog(failure.review, failure.message);
        throw new Error(SHARE_UPDATE_HANDLED_ERROR);
      }
      throw new Error(failure.message);
    }

    const data = await res.json().catch(() => ({} as { share_id?: string }));
    if (value && data.share_id) {
      ver.share_id = data.share_id;
    }
    
    message.success(value ? t('components.versionManager.switchedPublic') : t('components.versionManager.switchedPrivate'));
  } catch (e: unknown) {
    ver.is_shared = oldVal;
    if (e instanceof Error && e.message === SHARE_UPDATE_HANDLED_ERROR) {
      return;
    }
    const errorMessage = e instanceof Error ? e.message : t('components.versionManager.shareUpdateFailed');
    message.error(errorMessage);
  } finally {
    shareToggleVersionId.value = null;
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

  if (
    payload &&
    typeof payload === 'object' &&
    typeof (payload as { force_public_share_review?: unknown }).force_public_share_review === 'boolean'
  ) {
    publicShareReviewEffective.value = showMainlandComplianceFeatures.value
      && !!(payload as { force_public_share_review: boolean }).force_public_share_review;
  }
}

watch(() => props.projectId, () => {
  void loadVersions();
});

watch(() => locale.value, () => {
  void loadPublicShareState();
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
.version-manager {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

/* === 顶部 toolbar === */
.vm-toolbar {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 4px;
}

.vm-toolbar__info {
  flex: 1 1 auto;
  min-width: 0;
}

.title-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.vm-title {
  margin: 0;
  font-size: 1.1rem;
  line-height: 1.3;
}

.subtitle {
  display: block;
  margin-top: 4px;
  font-size: 0.85em;
  line-height: 1.4;
}

.vm-create-btn {
  flex: 0 0 auto;
}

/* === 筛选 / 公告条 === */
.filter-bar {
  margin-bottom: 4px;
}

.filter-bar__select {
  width: 220px;
  max-width: 100%;
}

.share-disabled-banner {
  margin-bottom: 4px;
}

/* === 版本列表 === */
.version-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.version-item :deep(.n-card-header) {
  padding-bottom: 6px;
}

.version-card-header {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 8px 12px;
  width: 100%;
  min-width: 0;
}

.version-card-header__main {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  min-width: 0;
}

.version-card-header__meta {
  display: inline-flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.version-title {
  font-weight: 700;
  word-break: break-all;
}

.version-date {
  white-space: nowrap;
}

.share-toggle {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 0 2px;
}

.share-state-label {
  min-width: 2.2em;
  text-align: right;
  color: var(--n-primary-color);
  font-weight: 600;
}

/* === 卡片正文 === */
.version-content {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.version-desc {
  color: var(--n-text-color-3);
  font-size: 0.9em;
  line-height: 1.5;
  word-break: break-word;
}

.version-warning {
  margin-top: 0;
}

/* === 操作区 === */
.version-actions {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.version-actions__primary {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.version-actions__primary .vm-action-btn {
  flex: 1 1 0;
  min-width: 96px;
}

.version-actions__secondary {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 4px;
  padding-top: 2px;
}

.version-actions__spacer {
  flex: 1 1 auto;
}

.vm-delete-btn {
  margin-left: auto;
}

/* === 审核拒绝对话框（保留原样式） === */
.share-review-dialog {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.share-review-dialog-intro,
.share-review-dialog-footer,
.share-review-dialog-text {
  line-height: 1.6;
  color: var(--n-text-color-2);
}

.share-review-dialog-block {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.share-review-dialog-label {
  font-weight: 700;
  color: var(--n-text-color-1);
}

.share-review-dialog-list {
  margin: 0;
  padding-left: 18px;
  color: var(--n-text-color-2);
}

.share-review-dialog-item {
  line-height: 1.5;
}

/* === 移动端响应式：≤720px === */
@media (max-width: 720px) {
  .vm-toolbar {
    flex-direction: column;
    align-items: stretch;
    gap: 10px;
  }

  .vm-create-btn {
    width: 100%;
    justify-content: center;
  }

  .filter-bar__select {
    width: 100%;
  }

  .version-card-header {
    flex-direction: column;
    align-items: stretch;
    gap: 6px;
  }

  .version-card-header__main {
    width: 100%;
  }

  .version-card-header__meta {
    width: 100%;
    justify-content: space-between;
    gap: 8px;
  }

  .version-actions__primary {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 6px;
  }

  .version-actions__primary .vm-action-btn {
    width: 100%;
    min-width: 0;
  }

  .version-actions__secondary {
    gap: 6px;
  }
}

/* === 极窄屏：≤420px，主操作改 1+2 布局，让“试玩”独占首行 === */
@media (max-width: 420px) {
  .version-actions__primary {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .version-actions__primary .vm-action-btn--play {
    grid-column: 1 / -1;
  }
}
</style>
