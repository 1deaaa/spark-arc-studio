<template>
  <div class="chat-file-import-button">
    <input
      type="file"
      ref="fileInput"
      style="display: none"
      :accept="accept"
      @change="handleFileChange"
    />
    <n-tooltip trigger="hover">
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
import { useI18n } from 'vue-i18n';
import { NButton, NIcon, NTooltip } from 'naive-ui';
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
  handleFileChange,
  triggerFileInput,
  cancelImport,
} = useChatFileImport(() => props.sessionId);

function onClickButton() {
  if (importing.value) {
    cancelImport();
    return;
  }
  triggerFileInput();
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
</style>
