<template>
  <section class="scene-length-control" :aria-label="t('components.storyTagsPanel.sceneLength.title')">
    <div class="scene-length-header">
      <span class="scene-length-title">{{ t('components.storyTagsPanel.sceneLength.title') }}</span>
      <n-tooltip trigger="hover">
        <template #trigger>
          <n-icon
            class="scene-length-info"
            :component="Info"
            :aria-label="t('components.storyTagsPanel.sceneLength.tooltip')"
          />
        </template>
        {{ t('components.storyTagsPanel.sceneLength.tooltip') }}
      </n-tooltip>
    </div>

    <SparkSegment
      :model-value="modelValue"
      :options="options"
      size="small"
      :block="true"
      @update:model-value="emit('update:modelValue', $event)"
    />

    <div class="scene-length-hint" aria-live="polite">
      <span>{{ rangeHint }}</span>
      <span>{{ t('components.storyTagsPanel.sceneLength.rhythmNote') }}</span>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';
import { NIcon, NTooltip } from 'naive-ui';
import { Info } from '@lucide/vue';
import SparkSegment from './SparkSegment.vue';

type SceneLengthHint = 'concise' | 'standard' | 'expanded';

const props = withDefaults(defineProps<{
  modelValue?: SceneLengthHint;
  workspaceMode?: 'script' | 'novel';
}>(), {
  modelValue: 'standard',
  workspaceMode: 'script',
});

const emit = defineEmits<{
  (event: 'update:modelValue', value: SceneLengthHint): void;
}>();

const { t } = useI18n();

const options = computed(() => [
  { value: 'concise' as const, label: t('components.storyTagsPanel.sceneLength.concise') },
  { value: 'standard' as const, label: t('components.storyTagsPanel.sceneLength.standard') },
  { value: 'expanded' as const, label: t('components.storyTagsPanel.sceneLength.expanded') },
]);

const rangeHint = computed(() => {
  const mode = props.workspaceMode === 'novel' ? 'novel' : 'script';
  return t(`components.storyTagsPanel.sceneLength.ranges.${mode}.${props.modelValue}`);
});
</script>

<style scoped>
.scene-length-control {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--spark-border);
}

.scene-length-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 20px;
}

.scene-length-title {
  color: var(--spark-text);
  font-size: var(--spark-fs-sm);
  font-weight: 600;
}

.scene-length-info {
  color: var(--spark-text-muted);
  cursor: help;
  font-size: 15px;
}

.scene-length-hint {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-height: 34px;
  color: var(--spark-text-muted);
  font-size: var(--spark-fs-xs);
  line-height: 1.4;
}
</style>
