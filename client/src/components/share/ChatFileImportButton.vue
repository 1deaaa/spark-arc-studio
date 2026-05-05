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
          @click="triggerFileInput"
        >
          <template #icon>
            <n-icon :size="16"><Paperclip /></n-icon>
          </template>
        </n-button>
      </template>
      {{ t('components.chatPanel.attachFile') }}
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
} = useChatFileImport(() => props.sessionId);
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
