<template>
  <section class="scene-length-control" :aria-label="t('components.storyTagsPanel.sceneLength.title')">
    <div class="scene-length-header">
      <div class="scene-length-heading">
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
    </div>

    <div class="scene-length-main">
      <SparkSegment
        :model-value="modelValue"
        :options="options"
        size="small"
        :block="true"
        @update:model-value="emit('update:modelValue', $event)"
      />
      <div class="scene-target-chars">
        <span class="scene-target-label">{{ t('components.storyTagsPanel.sceneLength.targetLabel') }}</span>
        <n-input-number
          :value="targetChars"
          :min="100"
          :max="100000"
          :step="100"
          :placeholder="t('components.storyTagsPanel.sceneLength.targetPlaceholder')"
          :aria-label="t('components.storyTagsPanel.sceneLength.targetLabel')"
          clearable
          size="small"
          @update:value="emit('update:targetChars', $event)"
        />
        <span class="scene-target-unit">{{ t('components.storyTagsPanel.sceneLength.targetUnit') }}</span>
      </div>
    </div>

    <div class="scene-length-hint" aria-live="polite">
      <span>{{ rangeHint }}</span>
      <span>{{ targetChars ? t('components.storyTagsPanel.sceneLength.targetNote') : t('components.storyTagsPanel.sceneLength.rhythmNote') }}</span>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';
import { NIcon, NTooltip, NInputNumber } from 'naive-ui';
import { Info } from '@lucide/vue';
import SparkSegment from './SparkSegment.vue';

type SceneLengthHint = 'concise' | 'standard' | 'expanded';

const props = withDefaults(defineProps<{
  modelValue?: SceneLengthHint;
  workspaceMode?: 'script' | 'novel';
  targetChars?: number | null;
}>(), {
  modelValue: 'standard',
  workspaceMode: 'script',
  targetChars: null,
});

const emit = defineEmits<{
  (event: 'update:modelValue', value: SceneLengthHint): void;
  (event: 'update:targetChars', value: number | null): void;
}>();

const { t } = useI18n();
const targetChars = computed(() => props.targetChars ?? null);

const options = computed(() => [
  { value: 'concise' as const, label: t('components.storyTagsPanel.sceneLength.concise') },
  { value: 'standard' as const, label: t('components.storyTagsPanel.sceneLength.standard') },
  { value: 'expanded' as const, label: t('components.storyTagsPanel.sceneLength.expanded') },
]);

const rangeHint = computed(() => {
  if (targetChars.value) {
    return t('components.storyTagsPanel.sceneLength.targetHint', { count: targetChars.value });
  }
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

.scene-length-heading {
  display: flex;
  align-items: center;
  gap: 6px;
}

.scene-length-main {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: 8px;
}

.scene-target-chars {
  display: flex;
  align-items: center;
  gap: 4px;
  color: var(--spark-text-muted);
  font-size: var(--spark-fs-xs);
}

.scene-target-chars :deep(.n-input-number) {
  width: 92px;
}

.scene-target-label,
.scene-target-unit {
  white-space: nowrap;
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
