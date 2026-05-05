<template>
  <n-card class="feedback-card" size="small">
    <template #header>
      <div class="card-header" @click="toggleFold">
        <n-icon size="18" :component="MessagesSquare" color="#63e2b7" />
        <span class="title">{{ isAdmin ? t('components.feedbackCard.titleAdmin') : t('components.feedbackCard.title') }}</span>
        <div class="header-controls" @click.stop>
          <!-- 未读角标 -->
          <span v-if="unreadCount > 0" class="unread-badge">{{ unreadCount }}</span>
          <!-- 普通用户：提交反馈 -->
          <n-tooltip v-if="!isAdmin" trigger="hover">
            <template #trigger>
              <n-button quaternary circle size="tiny" @click="openModal('submit')">
                <template #icon><n-icon size="16" :component="Plus" /></template>
              </n-button>
            </template>
            {{ t('components.feedbackCard.submitFeedback') }}
          </n-tooltip>
          <!-- 查看详情 -->
          <n-tooltip trigger="hover">
            <template #trigger>
              <n-button quaternary circle size="tiny" @click="openModal('view')">
                <template #icon><n-icon size="16" :component="ExternalLink" /></template>
              </n-button>
            </template>
            {{ isAdmin ? t('components.feedbackCard.viewAll') : t('components.feedbackCard.viewDetails') }}
          </n-tooltip>
          <!-- 折叠箭头 -->
          <n-icon size="20" :component="ChevronDown" class="fold-icon" :class="{ folded: isFolded }" />
        </div>
      </div>
    </template>

    <SparkCollapseTransition :show="!isFolded">
      <div class="card-content">
        <!-- 最近一条反馈摘要 -->
        <div v-if="latestFeedback" class="latest-hint" @click="openModal('view')">
          <SparkTag :type="statusTagType(latestFeedback.status)" size="tiny">
            {{ statusLabel(latestFeedback.status) }}
          </SparkTag>
          <SparkTag :type="categoryTagType(latestFeedback.category)" size="tiny">
            {{ categoryLabel(latestFeedback.category) }}
          </SparkTag>
          <span class="latest-text">{{ truncate(latestFeedback.content, 60) }}</span>
        </div>
        <div v-else class="latest-hint empty" @click="isAdmin ? openModal('view') : openModal('submit')">
          {{ isAdmin ? t('components.feedbackCard.noFeedbackYet') : t('components.feedbackCard.noMyFeedback') }}
        </div>
      </div>
    </SparkCollapseTransition>

    <!-- 反馈弹窗 -->
    <FeedbackModal
      v-model:show="showModal"
      :is-admin="isAdmin"
      :initial-tab="modalInitialTab"
      @refresh="refreshData"
    />
  </n-card>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import { useI18n } from 'vue-i18n';
import { NCard, NIcon, NButton, NTooltip, useMessage } from 'naive-ui';
import SparkCollapseTransition from '../share/SparkCollapseTransition.vue';
import SparkTag from '../share/SparkTag.vue';
import { ChevronDown, ExternalLink, MessagesSquare, Plus } from 'lucide-vue-next';
import FeedbackModal from './FeedbackModal.vue';
import { getMyFeedbacks, getMyUnreadCount, getAllFeedbacks, getAdminUnreadCount } from '../../services/feedbackService';
import type { FeedbackItem } from '../../services/feedbackService';

const props = defineProps<{
  isAdmin?: boolean;
}>();

const { t } = useI18n();
const message = useMessage();
const isAdmin = computed(() => props.isAdmin ?? false);

const isFolded = ref(false);
const showModal = ref(false);
const modalInitialTab = ref<'submit' | 'view'>('view');
const unreadCount = ref(0);
const latestFeedback = ref<FeedbackItem | null>(null);

function toggleFold() {
  isFolded.value = !isFolded.value;
}

function openModal(tab: 'submit' | 'view') {
  modalInitialTab.value = tab;
  showModal.value = true;
}

function truncate(text: string, max: number): string {
  if (!text) return '';
  return text.length > max ? text.slice(0, max) + '…' : text;
}

function categoryTagType(category: string): 'primary' | 'danger' | 'success' | 'default' {
  switch (category) {
    case 'bug': return 'danger';
    case 'feature': return 'primary';
    case 'experience': return 'success';
    default: return 'default';
  }
}

function categoryLabel(category: string): string {
  return t(`components.feedbackCard.category${category.charAt(0).toUpperCase() + category.slice(1)}`);
}

function statusTagType(status: string): 'danger' | 'primary' | 'success' | 'default' {
  switch (status) {
    case 'unread': return 'danger';
    case 'read': return 'primary';
    case 'processed': return 'success';
    default: return 'default';
  }
}

function statusLabel(status: string): string {
  return t(`components.feedbackCard.status${status.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join('')}`);
}

async function refreshData() {
  try {
    if (isAdmin.value) {
      unreadCount.value = await getAdminUnreadCount();
      const result = await getAllFeedbacks({ limit: 1, offset: 0 });
      latestFeedback.value = result.data?.[0] || null;
    } else {
      unreadCount.value = await getMyUnreadCount();
      const result = await getMyFeedbacks({ limit: 1, offset: 0 });
      latestFeedback.value = result.data?.[0] || null;
    }
  } catch (e) {
    // 静默处理，不阻塞 UI
    console.warn('FeedbackCard: refresh failed', e);
  }
}

onMounted(() => {
  refreshData();
});
</script>

<style scoped>
.feedback-card {
  margin-bottom: 20px;
  border-color: var(--spark-border);
  background-color: var(--spark-panel-bg);
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  cursor: pointer;
  width: 100%;
}

.card-header .title {
  margin-left: 8px;
  font-weight: 600;
  color: var(--spark-text-highlight);
  flex: 1;
}

.header-controls {
  display: flex;
  align-items: center;
  gap: 4px;
}

.unread-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 16px;
  height: 16px;
  padding: 0 4px;
  border-radius: 8px;
  background: var(--spark-warning);
  color: #fff;
  font-size: 10px;
  font-weight: 600;
  line-height: 1;
}

.fold-icon {
  transition: transform 0.3s;
  color: var(--spark-text-muted);
}
.fold-icon.folded {
  transform: rotate(-90deg);
}

.card-content {
  padding-top: 8px;
}

.latest-hint {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: var(--spark-fs-xs);
  color: var(--spark-text-secondary);
  cursor: pointer;
  padding: 4px 0;
  border-radius: 4px;
  transition: background 0.15s;
}
.latest-hint:hover {
  background: rgba(var(--spark-primary-rgb), 0.06);
}

.latest-hint.empty {
  color: var(--spark-text-muted);
  font-style: italic;
}

.latest-text {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
