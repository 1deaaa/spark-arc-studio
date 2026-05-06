<template>
  <div class="chat-file-import-button">
    <input
      type="file"
      ref="fileInput"
      style="display: none"
      :accept="accept"
      @change="handleFileChange"
    />
    <!-- 已附加文件：点击按钮弹出附件管理面板 -->
    <n-popover
      v-if="hasAttachment && !importing"
      v-model:show="popoverShow"
      trigger="click"
      placement="top-start"
      :width="280"
      :show-arrow="false"
    >
      <template #trigger>
        <n-button
          quaternary
          circle
          size="small"
          class="chat-file-import-button__trigger chat-file-import-button__trigger--active"
        >
          <template #icon>
            <n-icon :size="16"><Paperclip /></n-icon>
          </template>
        </n-button>
      </template>
      <div class="chat-attachment-popover">
        <div class="chat-attachment-popover__title">{{ t('components.chatPanel.attachmentPanelTitle') }}</div>
        <div class="chat-attachment-popover__name" :title="importedContext?.filename">
          {{ importedContext?.filename }}
        </div>
        <div class="chat-attachment-popover__desc">{{ importedContextDescription }}</div>
        <div class="chat-attachment-popover__actions">
          <n-button size="small" @click="onReplaceClick">
            {{ t('components.chatPanel.replaceImportedFile') }}
          </n-button>
          <n-button size="small" type="error" ghost @click="onRemoveClick">
            {{ t('components.chatPanel.removeImportedFile') }}
          </n-button>
        </div>
      </div>
    </n-popover>

    <!-- 无附件 / 正在导入：保持原 paperclip 按钮 + tooltip -->
    <n-tooltip v-else trigger="hover">
      <template #trigger>
        <n-button
          quaternary
          circle
          size="small"
          class="chat-file-import-button__trigger"
          :loading="importing"
          @click="onClickButton"
        >
          <template #icon>
            <n-icon :size="16"><Paperclip /></n-icon>
          </template>
        </n-button>
      </template>
      {{ importing ? t('components.chatPanel.cancelImport') : t('components.chatPanel.attachFile') }}
    </n-tooltip>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';
import { useI18n } from 'vue-i18n';
import { NButton, NIcon, NPopover, NTooltip } from 'naive-ui';
import { Paperclip } from 'lucide-vue-next';
import { useChatFileImport } from '@/composables/useChatFileImport';

const props = defineProps<{
  sessionId: number | null | undefined;
}>();

const { t } = useI18n();
const {
  fileInput,
  accept,
  importing,
  importedContext,
  importedContextDescription,
  handleFileChange,
  openImportPicker,
  cancelImport,
  removeImportedContext,
} = useChatFileImport(() => props.sessionId);

const popoverShow = ref(false);
const hasAttachment = computed(() => !!importedContext.value?.attachmentId);

function onClickButton() {
  if (importing.value) {
    cancelImport();
    return;
  }
  openImportPicker();
}

function onReplaceClick() {
  popoverShow.value = false;
  openImportPicker();
}

async function onRemoveClick() {
  popoverShow.value = false;
  await removeImportedContext();
}
</script>

<style scoped>
.chat-file-import-button {
  display: flex;
  align-items: center;
}

.chat-file-import-button__trigger {
  flex-shrink: 0;
}

/* 已附加文件时：按钮高亮以提示状态 */
.chat-file-import-button__trigger--active {
  background: color-mix(in srgb, var(--spark-primary) 14%, transparent);
  color: var(--spark-primary);
}

.chat-attachment-popover {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 2px 0;
}

.chat-attachment-popover__title {
  font-size: 11px;
  color: var(--spark-text-3, var(--n-text-color-disabled));
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.chat-attachment-popover__name {
  font-size: 13px;
  font-weight: 600;
  color: var(--spark-text-1, var(--n-text-color));
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.chat-attachment-popover__desc {
  font-size: 11px;
  color: var(--spark-text-3, var(--n-text-color-disabled));
}

.chat-attachment-popover__actions {
  display: flex;
  gap: 8px;
  margin-top: 4px;
  justify-content: flex-end;
}
</style>
