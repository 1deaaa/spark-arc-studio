<template>
  <n-modal
    :show="show"
    @update:show="$emit('update:show', $event)"
    preset="card"
    :title="isAdmin ? t('components.feedbackCard.modalTitleAdmin') : t('components.feedbackCard.modalTitle')"
    :style="{ maxWidth: '760px', width: '90vw' }"
    :mask-closable="true"
    size="small"
    class="feedback-modal"
  >
    <!-- ========== 普通用户视图 ========== -->
    <template v-if="!isAdmin">
      <n-tabs v-model:value="activeTab" type="segment" size="small" class="feedback-tabs spark-segment-tabs">
        <n-tab-pane name="submit" :tab="t('components.feedbackCard.submitFeedback')">
          <n-form :model="form" label-placement="top" size="small">
            <n-form-item :label="t('components.feedbackCard.categoryLabel')">
              <n-select v-model:value="form.category" :options="categoryOptions" />
            </n-form-item>
            <n-form-item :label="t('components.feedbackCard.contentLabel')">
              <n-input
                v-model:value="form.content"
                type="textarea"
                :autosize="{ minRows: 3, maxRows: 8 }"
                :placeholder="form.category === 'bug' ? t('components.feedbackCard.bugContentPlaceholder') : t('components.feedbackCard.contentPlaceholder')"
              />
            </n-form-item>
            <n-form-item :label="t('components.feedbackCard.anonymousLabel')">
              <div style="display: flex; align-items: center; justify-content: space-between; width: 100%;">
                <n-switch v-model:value="form.is_anonymous" />
                <n-button
                  type="primary"
                  size="small"
                  :loading="submitting"
                  :disabled="!form.content.trim()"
                  @click="submitFeedback"
                >
                  {{ t('components.feedbackCard.submitButton') }}
                </n-button>
              </div>
            </n-form-item>
          </n-form>
        </n-tab-pane>

        <n-tab-pane name="view" :tab="t('components.feedbackCard.myFeedback')">
          <div class="list-section">
            <n-spin :show="loadingList">
              <div v-if="!myFeedbacks || myFeedbacks.length === 0" class="empty-hint">
                {{ t('components.feedbackCard.noMyFeedback') }}
              </div>
              <div v-else class="feedback-list">
                <div
                  v-for="fb in myFeedbacks"
                  :key="fb.id"
                  class="feedback-item"
                  :class="{ unread: !fb.is_read_by_user && fb.admin_reply }"
                  @click="toggleExpand(fb.id)"
                >
                  <div class="item-header">
                    <span class="unread-dot" v-if="!fb.is_read_by_user && fb.admin_reply"></span>
                    <SparkTag :type="categoryTagType(fb.category)" size="tiny">
                      {{ categoryLabel(fb.category) }}
                    </SparkTag>
                    <SparkTag :type="priorityTagType(fb.priority)" size="tiny">
                      {{ priorityLabel(fb.priority) }}
                    </SparkTag>
                    <SparkTag :type="statusTagType(fb.status)" size="tiny">
                      {{ statusLabel(fb.status) }}
                    </SparkTag>
                    <span class="item-time">{{ formatDate(fb.created_at) }}</span>
                  </div>
                  <div class="item-content">{{ fb.content }}</div>

                  <!-- 展开详情 -->
                  <SparkCollapseTransition :show="expandedId === fb.id">
                    <div class="item-detail">
                      <div v-if="fb.admin_reply" class="reply-block">
                        <div class="reply-label">{{ t('components.feedbackCard.adminReply') }}</div>
                        <div class="reply-content">{{ fb.admin_reply }}</div>
                        <div v-if="fb.replier_name" class="reply-meta">
                          — {{ fb.replier_name }} · {{ formatDate(fb.replied_at!) }}
                        </div>
                      </div>
                      <div v-else class="no-reply">{{ t('components.feedbackCard.noReplyYet') }}</div>
                      <n-button
                        v-if="!fb.is_read_by_user && fb.admin_reply"
                        size="tiny"
                        secondary
                        type="primary"
                        @click.stop="markRead(fb.id)"
                        style="margin-top: 6px;"
                      >
                        {{ t('components.feedbackCard.markAsRead') }}
                      </n-button>
                    </div>
                  </SparkCollapseTransition>
                </div>
              </div>
            </n-spin>
          </div>
        </n-tab-pane>
      </n-tabs>
    </template>

    <!-- ========== 管理员视图 ========== -->
    <template v-else>
      <div class="admin-content">
      <!-- 筛选栏 -->
      <div class="filter-bar">
        <n-select
          v-model:value="filterStatus"
          :options="statusFilterOptions"
          :placeholder="t('components.feedbackCard.filterStatus')"
          clearable
          size="small"
          style="width: 120px;"
        />
        <n-select
          v-model:value="filterCategory"
          :options="categoryFilterOptions"
          :placeholder="t('components.feedbackCard.filterCategory')"
          clearable
          size="small"
          style="width: 120px;"
        />
        <n-select
          v-model:value="filterPriority"
          :options="priorityFilterOptions"
          :placeholder="t('components.feedbackCard.filterPriority')"
          clearable
          size="small"
          style="width: 120px;"
        />
        <n-button size="small" secondary @click="loadAdminList">
          <template #icon><n-icon :component="RefreshCw" /></template>
        </n-button>
      </div>

      <!-- 反馈列表 -->
      <div class="admin-list-wrapper">
        <n-spin :show="loadingList">
          <div v-if="!adminFeedbacks || adminFeedbacks.length === 0" class="empty-hint">
            {{ t('components.feedbackCard.noFeedbackYet') }}
          </div>
          <div v-else class="feedback-list admin-list">
            <div
              v-for="fb in adminFeedbacks"
              :key="fb.id"
              class="feedback-item admin-item"
              @click="toggleExpand(fb.id)"
            >
              <div class="item-header">
                <SparkTag :type="categoryTagType(fb.category)" size="tiny">
                  {{ categoryLabel(fb.category) }}
                </SparkTag>
                <SparkTag :type="priorityTagType(fb.priority)" size="tiny">
                  {{ priorityLabel(fb.priority) }}
                </SparkTag>
                <SparkTag :type="statusTagType(fb.status)" size="tiny">
                  {{ statusLabel(fb.status) }}
                </SparkTag>
                <span class="item-user">{{ fb.is_anonymous ? t('components.feedbackCard.anonymousUser') : (fb.username || '—') }}</span>
                <span class="item-time">{{ formatDate(fb.created_at) }}</span>
              </div>
              <div class="item-content">{{ truncate(fb.content, 120) }}</div>

              <!-- 展开详情 -->
              <SparkCollapseTransition :show="expandedId === fb.id">
                <div class="item-detail">
                  <div class="detail-full-content">{{ fb.content }}</div>
                  <div v-if="fb.admin_reply" class="reply-block">
                    <div class="reply-label">{{ t('components.feedbackCard.adminReply') }}</div>
                    <div class="reply-content">{{ fb.admin_reply }}</div>
                  </div>
                  <div class="admin-actions">
                    <n-button size="tiny" type="primary" secondary @click.stop="openReplyModal(fb)">
                      {{ fb.admin_reply ? t('components.feedbackCard.editReply') : t('components.feedbackCard.reply') }}
                    </n-button>
                    <n-button size="tiny" secondary @click.stop="openStatusModal(fb)">
                      {{ t('components.feedbackCard.updateStatus') }}
                    </n-button>
                  </div>
                </div>
              </SparkCollapseTransition>
            </div>
          </div>
        </n-spin>
      </div>
      </div>
    </template>
  </n-modal>

  <!-- 管理员回复/编辑弹窗 -->
  <n-modal
    v-model:show="replyModalShow"
    preset="card"
    :title="replyTarget ? (replyTarget.admin_reply ? t('components.feedbackCard.editReply') : t('components.feedbackCard.reply')) : ''"
    :style="{ maxWidth: '500px', width: '80vw' }"
    size="small"
  >
    <template v-if="replyTarget">
      <div class="reply-target-content">
        <SparkTag :type="categoryTagType(replyTarget.category)" size="tiny">{{ categoryLabel(replyTarget.category) }}</SparkTag>
        <span style="margin-left: 8px; color: var(--spark-text-secondary);">{{ truncate(replyTarget.content, 80) }}</span>
      </div>
      <n-input
        v-model:value="replyText"
        type="textarea"
        :autosize="{ minRows: 3, maxRows: 8 }"
        :placeholder="t('components.feedbackCard.replyPlaceholder')"
        style="margin-top: 12px;"
      />
      <div style="margin-top: 12px; display: flex; justify-content: flex-end; gap: 8px;">
        <n-button size="small" @click="replyModalShow = false">{{ t('views.common.cancel') }}</n-button>
        <n-button size="small" type="primary" :loading="replying" :disabled="!replyText.trim()" @click="submitReply">
          {{ t('components.feedbackCard.saveReply') }}
        </n-button>
      </div>
    </template>
  </n-modal>

  <!-- 管理员状态修改弹窗 -->
  <n-modal
    v-model:show="statusModalShow"
    preset="card"
    :title="t('components.feedbackCard.updateStatus')"
    :style="{ maxWidth: '400px', width: '70vw' }"
    size="small"
  >
    <template v-if="statusTarget">
      <n-form label-placement="left" label-width="auto" size="small">
        <n-form-item :label="t('components.feedbackCard.statusLabel')">
          <n-select v-model:value="newStatus" :options="statusOptions" />
        </n-form-item>
        <n-form-item :label="t('components.feedbackCard.priorityLabel')">
          <n-select v-model:value="newPriority" :options="priorityOptions" />
        </n-form-item>
      </n-form>
      <div style="margin-top: 12px; display: flex; justify-content: flex-end; gap: 8px;">
        <n-button size="small" @click="statusModalShow = false">{{ t('views.common.cancel') }}</n-button>
        <n-button size="small" type="primary" :loading="updatingStatus" @click="submitStatusUpdate">
          {{ t('components.feedbackCard.saveStatus') }}
        </n-button>
      </div>
    </template>
  </n-modal>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import {
  NModal, NCard, NForm, NFormItem, NInput, NSelect, NButton, NIcon,
  NSwitch, NSpin, NTabs, NTabPane, useMessage,
} from 'naive-ui';
import SparkTag from '../share/SparkTag.vue';
import SparkCollapseTransition from '../share/SparkCollapseTransition.vue';
import SparkAlert from '../share/SparkAlert.vue';
import { RefreshCw } from 'lucide-vue-next';
import {
  createFeedback, getMyFeedbacks, markFeedbackRead, getMyUnreadCount,
  getAllFeedbacks, updateFeedbackStatus, replyFeedback, getAdminUnreadCount,
  adminMarkFeedbackRead,
} from '../../services/feedbackService';
import type { FeedbackItem } from '../../services/feedbackService';

const props = withDefaults(defineProps<{
  show: boolean;
  isAdmin: boolean;
  initialTab?: 'submit' | 'view';
}>(), {
  initialTab: 'view',
});

const emit = defineEmits<{
  (e: 'update:show', val: boolean): void;
  (e: 'refresh'): void;
}>();

const { t } = useI18n();
const msg = useMessage();

// ---- 通用 ----
const loadingList = ref(false);
const expandedId = ref<number | null>(null);
const activeTab = ref<'submit' | 'view'>('view');

function toggleExpand(id: number) {
  expandedId.value = expandedId.value === id ? null : id;
  // 管理员展开未读反馈时自动标记为已读
  if (props.isAdmin && expandedId.value === id) {
    const fb = adminFeedbacks.value.find(f => f.id === id);
    if (fb && fb.status === 'unread') {
      adminMarkFeedbackRead(id).then(updated => {
        if (updated?.status) {
          fb.status = updated.status;
        }
        emit('refresh');
      }).catch(() => {
        // 静默处理，不阻塞交互
      });
    }
  }
}

function truncate(text: string, max: number): string {
  if (!text) return '';
  return text.length > max ? text.slice(0, max) + '…' : text;
}

function formatDate(iso: string | null): string {
  if (!iso) return '';
  const d = new Date(iso);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
}

function categoryTagType(category: string): 'primary' | 'danger' | 'success' | 'default' {
  switch (category) {
    case 'bug': return 'danger';
    case 'feature': return 'primary';
    case 'experience': return 'success';
    default: return 'default';
  }
}

function priorityTagType(priority: string): 'danger' | 'warning' | 'primary' | 'default' {
  switch (priority) {
    case 'critical': return 'danger';
    case 'high': return 'warning';
    case 'medium': return 'primary';
    default: return 'default';
  }
}

function statusTagType(status: string): 'danger' | 'primary' | 'success' | 'default' {
  switch (status) {
    case 'unread': return 'danger';
    case 'read': return 'primary';
    case 'processed': return 'success';
    default: return 'default';
  }
}

function categoryLabel(category: string): string {
  return t(`components.feedbackCard.category${category.charAt(0).toUpperCase() + category.slice(1)}`);
}

function priorityLabel(priority: string): string {
  return t(`components.feedbackCard.priority${priority.charAt(0).toUpperCase() + priority.slice(1)}`);
}

function statusLabel(status: string): string {
  return t(`components.feedbackCard.status${status.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join('')}`);
}

// ---- 选项 ----
const categoryOptions = computed(() => [
  { label: t('components.feedbackCard.categoryBug'), value: 'bug' },
  { label: t('components.feedbackCard.categoryFeature'), value: 'feature' },
  { label: t('components.feedbackCard.categoryExperience'), value: 'experience' },
  { label: t('components.feedbackCard.categoryOther'), value: 'other' },
]);

const priorityOptions = computed(() => [
  { label: t('components.feedbackCard.priorityLow'), value: 'low' },
  { label: t('components.feedbackCard.priorityMedium'), value: 'medium' },
  { label: t('components.feedbackCard.priorityHigh'), value: 'high' },
  { label: t('components.feedbackCard.priorityCritical'), value: 'critical' },
]);

const statusOptions = computed(() => [
  { label: t('components.feedbackCard.statusUnread'), value: 'unread' },
  { label: t('components.feedbackCard.statusRead'), value: 'read' },
  { label: t('components.feedbackCard.statusProcessed'), value: 'processed' },
]);

const categoryFilterOptions = computed(() => [
  { label: t('components.feedbackCard.categoryBug'), value: 'bug' },
  { label: t('components.feedbackCard.categoryFeature'), value: 'feature' },
  { label: t('components.feedbackCard.categoryExperience'), value: 'experience' },
  { label: t('components.feedbackCard.categoryOther'), value: 'other' },
]);

const priorityFilterOptions = computed(() => [
  { label: t('components.feedbackCard.priorityLow'), value: 'low' },
  { label: t('components.feedbackCard.priorityMedium'), value: 'medium' },
  { label: t('components.feedbackCard.priorityHigh'), value: 'high' },
  { label: t('components.feedbackCard.priorityCritical'), value: 'critical' },
]);

const statusFilterOptions = computed(() => [
  { label: t('components.feedbackCard.statusUnread'), value: 'unread' },
  { label: t('components.feedbackCard.statusRead'), value: 'read' },
  { label: t('components.feedbackCard.statusProcessed'), value: 'processed' },
]);

// ======== 普通用户 ========
const form = ref({ category: 'feature', content: '', is_anonymous: false });
const submitting = ref(false);
const myFeedbacks = ref<FeedbackItem[]>([]);

async function submitFeedback() {
  if (!form.value.content.trim()) return;
  submitting.value = true;
  try {
    await createFeedback({
      category: form.value.category,
      content: form.value.content,
      is_anonymous: form.value.is_anonymous,
    });
    msg.success(t('components.feedbackCard.submitSuccess'));
    form.value.content = '';
    form.value.is_anonymous = false;
    emit('refresh');
    emit('update:show', false);
  } catch (e: unknown) {
    msg.error((e as Error).message || t('components.feedbackCard.submitFailed'));
  } finally {
    submitting.value = false;
  }
}

async function loadMyList() {
  loadingList.value = true;
  try {
    const result = await getMyFeedbacks({ limit: 12, offset: 0 });
    myFeedbacks.value = result.data || [];
  } catch (e) {
    console.error('Failed to load my feedbacks', e);
  } finally {
    loadingList.value = false;
  }
}

async function markRead(id: number) {
  try {
    await markFeedbackRead(id);
    const fb = myFeedbacks.value.find(f => f.id === id);
    if (fb) fb.is_read_by_user = true;
    emit('refresh');
  } catch (e) {
    msg.error((e as Error).message);
  }
}

// ======== 管理员 ========
const adminFeedbacks = ref<FeedbackItem[]>([]);
const filterStatus = ref<string | null>(null);
const filterCategory = ref<string | null>(null);
const filterPriority = ref<string | null>(null);

async function loadAdminList() {
  loadingList.value = true;
  try {
    const result = await getAllFeedbacks({
      status: filterStatus.value || undefined,
      category: filterCategory.value || undefined,
      priority: filterPriority.value || undefined,
      limit: 100,
      offset: 0,
    });
    adminFeedbacks.value = result.data || [];
  } catch (e) {
    console.error('Failed to load admin feedbacks', e);
  } finally {
    loadingList.value = false;
  }
}

// ---- 回复弹窗 ----
const replyModalShow = ref(false);
const replyTarget = ref<FeedbackItem | null>(null);
const replyText = ref('');
const replying = ref(false);

function openReplyModal(fb: FeedbackItem) {
  replyTarget.value = fb;
  replyText.value = fb.admin_reply || '';
  replyModalShow.value = true;
}

async function submitReply() {
  if (!replyTarget.value || !replyText.value.trim()) return;
  replying.value = true;
  try {
    await replyFeedback(replyTarget.value.id, replyText.value);
    msg.success(t('components.feedbackCard.replySuccess'));
    replyModalShow.value = false;
    await loadAdminList();
    emit('refresh');
  } catch (e) {
    msg.error((e as Error).message);
  } finally {
    replying.value = false;
  }
}

// ---- 状态弹窗 ----
const statusModalShow = ref(false);
const statusTarget = ref<FeedbackItem | null>(null);
const newStatus = ref('open');
const newPriority = ref('medium');
const updatingStatus = ref(false);

function openStatusModal(fb: FeedbackItem) {
  statusTarget.value = fb;
  newStatus.value = fb.status;
  newPriority.value = fb.priority || 'medium';
  statusModalShow.value = true;
}

async function submitStatusUpdate() {
  if (!statusTarget.value) return;
  updatingStatus.value = true;
  try {
    await updateFeedbackStatus(statusTarget.value.id, {
      status: newStatus.value,
      priority: newPriority.value,
    });
    msg.success(t('components.feedbackCard.statusUpdateSuccess'));
    statusModalShow.value = false;
    await loadAdminList();
    emit('refresh');
  } catch (e) {
    msg.error((e as Error).message);
  } finally {
    updatingStatus.value = false;
  }
}

// ---- 弹窗打开时加载数据 ----
watch(() => props.show, (val) => {
  if (val) {
    expandedId.value = null;
    activeTab.value = props.initialTab;
    if (props.isAdmin) {
      loadAdminList();
    } else {
      loadMyList();
    }
  }
});
</script>

<style scoped>
.feedback-modal :deep(.n-card-header) {
  font-size: var(--spark-fs-sm);
}

.form-section {
  margin-bottom: 20px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--spark-border);
}

.section-title {
  font-size: var(--spark-fs-sm);
  font-weight: 600;
  color: var(--spark-text-highlight);
  margin: 0 0 12px 0;
}

.admin-content {
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.admin-list-wrapper {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
}

.admin-list-wrapper :deep(.n-spin-container) {
  height: 100%;
}

.admin-list-wrapper :deep(.n-spin-content) {
  height: 100%;
}

.list-section {
  max-height: 100%;
  overflow-y: auto;
}

.empty-hint {
  text-align: center;
  color: var(--spark-text-muted);
  font-size: var(--spark-fs-xs);
  padding: 16px 0;
  font-style: italic;
}

.feedback-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.feedback-item {
  padding: 8px 12px;
  border: 1px solid var(--spark-border);
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.15s;
  position: relative;
}

.feedback-item:hover {
  background: rgba(var(--spark-primary-rgb), 0.04);
}

.feedback-item.unread {
  border-left: 3px solid var(--spark-primary);
}

.unread-dot {
  display: inline-block;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--spark-primary);
  margin-right: 4px;
  flex-shrink: 0;
}

.item-header {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.item-user {
  font-size: var(--spark-fs-2xs);
  color: var(--spark-text-muted);
  margin-left: auto;
}

.item-time {
  font-size: var(--spark-fs-3xs);
  color: var(--spark-text-muted);
}

.item-content {
  font-size: var(--spark-fs-xs);
  color: var(--spark-text-secondary);
  margin-top: 4px;
  line-height: 1.4;
}

.item-detail {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px dashed var(--spark-border);
}

.detail-full-content {
  font-size: var(--spark-fs-xs);
  color: var(--spark-text-primary);
  white-space: pre-wrap;
  line-height: 1.6;
}

.reply-block {
  background: rgba(var(--spark-primary-rgb), 0.06);
  border-radius: 6px;
  padding: 8px 12px;
  margin-top: 8px;
}

.reply-label {
  font-size: var(--spark-fs-2xs);
  font-weight: 600;
  color: var(--spark-primary);
  margin-bottom: 4px;
}

.reply-content {
  font-size: var(--spark-fs-xs);
  color: var(--spark-text-secondary);
  white-space: pre-wrap;
  line-height: 1.5;
}

.reply-meta {
  font-size: var(--spark-fs-3xs);
  color: var(--spark-text-muted);
  margin-top: 4px;
}

.no-reply {
  font-size: var(--spark-fs-2xs);
  color: var(--spark-text-muted);
  font-style: italic;
}

.admin-actions {
  display: flex;
  gap: 8px;
  margin-top: 8px;
}

.filter-bar {
  display: flex;
  gap: 8px;
  margin-bottom: 8px;
  flex-wrap: wrap;
  align-items: center;
}

.reply-target-content {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 8px;
  background: var(--spark-bg);
  border-radius: 4px;
  font-size: var(--spark-fs-xs);
}
</style>

<style>
/* 非 scoped：modal 被 teleport 到 body，scoped 选择器无法穿透 */
.feedback-modal .n-card {
  display: flex;
  flex-direction: column;
  max-height: min(86vh, 760px);
}
.feedback-modal .n-card__content {
  flex: 1;
  min-height: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
</style>
