<template>
  <n-tooltip trigger="hover">
    <template #trigger>
      <div class="baton-indicator" :class="{ active: hasBaton }">
        <svg viewBox="0 0 24 24" class="comm-svg">
          <line x1="5" y1="18" x2="19" y2="6" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
          <circle cx="6" cy="18" r="2" fill="currentColor" />
          <circle cx="18" cy="6" r="2" fill="currentColor" />
          <circle v-if="hasBaton" cx="12" cy="12" r="9" stroke="currentColor" stroke-width="1" fill="none" class="pulse-ring" />
        </svg>
        <div v-if="hasBaton" class="status-glow"></div>
      </div>
    </template>
    <div class="tooltip-content">
      <div class="status-line">
        <span class="dot" :class="{ active: hasBaton }"></span>
        <strong>{{ hasBaton ? '旗帜在手' : '旗帜不在手' }}</strong>
      </div>
      <div class="desc">
        {{ hasBaton ? '该 Agent 当前持有旗帜（接力棒），说明这条任务链当前由它继续推进。' : '该 Agent 当前没有持有旗帜，它不是这条任务链的当前推进者。' }}
      </div>
    </div>
  </n-tooltip>
</template>

<script setup>
import { computed } from 'vue';
import { NTooltip } from 'naive-ui';
import { useAgentRuntimeStore } from '../stores/agentRuntimeStore';

const props = defineProps({
  agentId: {
    type: String,
    required: true,
  },
});

const store = useAgentRuntimeStore();
const state = computed(() => store.signalStates[props.agentId] || { hasBaton: false });
const hasBaton = computed(() => !!state.value.hasBaton);
</script>

<style scoped>
.baton-indicator {
  width: 24px;
  height: 24px;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  color: var(--spark-text-muted);
  border-radius: 6px;
}

.comm-svg {
  width: 18px;
  height: 18px;
  z-index: 2;
}

.baton-indicator.active {
  color: var(--spark-contrast-output);
}

.status-glow {
  position: absolute;
  inset: 0;
  background: color-mix(in srgb, var(--spark-contrast-output), transparent 80%);
  border-radius: 50%;
  filter: blur(6px);
  z-index: 1;
  opacity: 0.6;
}

.pulse-ring {
  transform-origin: center;
  animation: ring-pulse 2s infinite ease-out;
}

@keyframes ring-pulse {
  0% { transform: scale(0.5); opacity: 0.8; }
  100% { transform: scale(1.5); opacity: 0; }
}

.tooltip-content {
  padding: 4px;
  max-width: 180px;
}

.status-line {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background-color: var(--spark-text-muted);
}

.dot.active {
  background-color: var(--spark-contrast-output);
}

.desc {
  font-size: 11px;
  color: var(--spark-text-muted);
  line-height: 1.4;
}
</style>
