<template>
  <div
    :class="rootClass"
    @dragover.prevent="isDragOver = true"
    @dragleave.prevent="isDragOver = false"
    @drop.prevent="handleDrop"
    @click="triggerFileInput"
  >
    <input
      type="file"
      ref="fileInput"
      style="display: none"
      :accept="accept"
      @change="handleFileChange"
    />
    <slot name="icon">
      <div class="document-import-picker__icon">
        <n-icon :size="iconSize"><CloudUploadOutline /></n-icon>
      </div>
    </slot>
    <slot name="title">
      <p class="document-import-picker__title">{{ title }}</p>
    </slot>
    <slot name="subtitle">
      <p class="document-import-picker__subtitle">{{ subtitle }}</p>
    </slot>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue';
import { NIcon } from 'naive-ui';
import { CloudUploadOutline } from '@vicons/ionicons5';
import { useDocumentImport } from '@/composables/useDocumentImport';
import type { ImportUsage } from '@/services/fileImportService';

const props = withDefaults(defineProps<{
  usage?: ImportUsage;
  title: string;
  subtitle: string;
  variant?: 'desktop' | 'mobile';
  iconSize?: number;
}>(), {
  usage: 'style_analysis',
  variant: 'desktop',
  iconSize: 48,
});

const emit = defineEmits<{
  select: [file: File];
  invalid: [message: string];
}>();

const {
  fileInput,
  isDragOver,
  accept,
  handleFileChange,
  handleDrop,
  triggerFileInput,
  loadCapabilities,
} = useDocumentImport({
  usage: props.usage,
  onSelectFile: async (file) => emit('select', file),
  onInvalidFile: (message) => emit('invalid', message),
});

const rootClass = computed(() => [
  'document-import-picker',
  `document-import-picker--${props.variant}`,
  { 'is-dragover': isDragOver.value },
]);

onMounted(() => {
  loadCapabilities();
});
</script>

<style scoped>
.document-import-picker {
  border: 2px dashed var(--border-color);
  border-radius: 12px;
  text-align: center;
  cursor: pointer;
  transition: all 0.3s;
  background: var(--bg-color-secondary);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}

.document-import-picker.is-dragover,
.document-import-picker:hover {
  border-color: var(--primary-color);
  background: var(--primary-color-alpha-10);
}

.document-import-picker--desktop {
  min-height: 200px;
  padding: 40px;
}

.document-import-picker--mobile {
  padding: 24px;
  gap: 8px;
}

.document-import-picker__icon {
  margin-bottom: 16px;
  color: var(--text-color-secondary);
}

.document-import-picker__title {
  font-size: var(--spark-fs-md);
  color: var(--text-color);
  margin-bottom: 8px;
}

.document-import-picker__subtitle {
  font-size: var(--spark-fs-sm);
  color: var(--text-color-secondary);
}
</style>
