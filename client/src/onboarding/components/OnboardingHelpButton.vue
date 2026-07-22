<template>
  <n-tooltip trigger="hover">
    <template #trigger>
      <n-button
        class="onboarding-help-button"
        quaternary
        circle
        size="small"
        :aria-label="t('onboarding.common.restartGuide')"
        @click.stop="replayGuide"
      >
        <template #icon><n-icon :component="CircleHelp" /></template>
      </n-button>
    </template>
    {{ t('onboarding.common.restartGuide') }}
  </n-tooltip>
</template>

<script setup lang="ts">
import { CircleHelp } from '@lucide/vue';
import { NButton, NIcon, NTooltip } from 'naive-ui';
import { useI18n } from 'vue-i18n';
import { useOnboarding } from '../engine/useOnboarding';

const props = defineProps<{
  sceneId: string;
}>();

const { t } = useI18n();
const { engine, trigger } = useOnboarding();

function replayGuide(): void {
  if (engine.isActive.value) engine.destroy();
  void trigger(props.sceneId);
}
</script>

<style scoped>
.onboarding-help-button {
  flex: 0 0 auto;
  color: var(--spark-text-muted);
}

.onboarding-help-button:hover {
  color: var(--spark-primary);
}
</style>
