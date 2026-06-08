<template>
  <n-modal
    v-model:show="visible"
    :mask-closable="false"
    :close-on-esc="false"
    preset="card"
    :title="titleText"
    style="width: 520px; max-width: calc(100vw - 40px);"
    :bordered="false"
    :segmented="{ content: true, footer: true }"
  >
    <div v-if="notice" class="announcement-body">
      <div class="announcement-time">{{ formattedTime }}</div>
      <MarkdownRenderer :content="notice.content" />
    </div>
    <template #footer>
      <div class="announcement-footer">
        <n-button type="primary" @click="handleMarkRead" :loading="loading">
          {{ t('components.announcement.markRead') }}
        </n-button>
      </div>
    </template>
  </n-modal>
</template>

<script setup lang="ts">
import { defineAsyncComponent, ref, computed } from 'vue';
import { NModal, NButton, useMessage } from 'naive-ui';
import { useI18n } from 'vue-i18n';
import { fetchWithAuth } from '../../services/apiClient';

export type NoticeItem = {
  id: string;
  title: string;
  content: string;
  timestamp: string;
};

const props = defineProps<{
  locale?: string;
}>();

const emit = defineEmits<{
  (e: 'read'): void;
}>();

const { t, locale: i18nLocale } = useI18n();
const message = useMessage();
const MarkdownRenderer = defineAsyncComponent(() => import('./MarkdownRenderer.vue'));

const visible = ref(false);
const loading = ref(false);
const notice = ref<NoticeItem | null>(null);

const titleText = computed(() => {
  if (!notice.value) return t('components.announcement.title');
  return notice.value.title || t('components.announcement.title');
});

const formattedTime = computed(() => {
  if (!notice.value?.timestamp) return '';
  try {
    const date = new Date(notice.value.timestamp);
    const localeCode = ['zh-CN', 'en-US', 'ja-JP', 'ko-KR'].includes(i18nLocale.value) ? i18nLocale.value : 'zh-CN';
    return date.toLocaleString(localeCode, {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return notice.value.timestamp;
  }
});

function show(item: NoticeItem) {
  notice.value = item;
  visible.value = true;
}

async function handleMarkRead() {
  if (!notice.value) return;
  loading.value = true;
  try {
    const res = await fetchWithAuth('/api/user/notice-read', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ notice_id: notice.value.id }),
    });
    const data = await res.json();
    if (!res.ok || data.success === false) {
      throw new Error(data.message || data.detail || t('components.announcement.markReadFailed'));
    }
    visible.value = false;
    emit('read');
  } catch (e: unknown) {
    const errorMessage = e instanceof Error ? e.message : String(e || '');
    message.error(`${t('components.announcement.markReadFailed')}: ${errorMessage}`);
  } finally {
    loading.value = false;
  }
}

defineExpose({ show });
</script>

<style scoped>
.announcement-body {
  max-height: 60vh;
  overflow-y: auto;
  padding: 4px 0;
}
.announcement-time {
  color: var(--n-text-color-3, #999);
  font-size: 12px;
  margin-bottom: 12px;
}
.announcement-footer {
  display: flex;
  justify-content: flex-end;
}
</style>
