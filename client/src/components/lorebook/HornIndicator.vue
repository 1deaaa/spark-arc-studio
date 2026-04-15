<template>
  <n-tooltip trigger="hover">
    <template #trigger>
      <div class="horn-indicator" :class="{ active: hasHorn, locked: hornLocked }" @click.stop="handleToggle">
        <svg viewBox="0 0 24 24" class="comm-svg">
          <path d="M5 14c4-1 8-4 12-9v14c-4-5-8-8-12-9z" stroke="currentColor" stroke-width="2" fill="none" stroke-linejoin="round" />
          <path d="M5 14v3" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
          <circle v-if="hasHorn" cx="12" cy="12" r="9" stroke="currentColor" stroke-width="1" fill="none" class="pulse-ring" />
        </svg>
        <div v-if="hasHorn" class="status-glow"></div>
      </div>
    </template>
    <div class="tooltip-content">
      <div class="status-line">
        <span class="dot" :class="{ active: hasHorn }"></span>
        <strong>{{ hasHorn ? '号角已吹响' : '号角已放下' }}</strong>
      </div>
      <div class="desc">
        {{ hasHorn ? '该 Agent 持有号角，拥有主动向其他 Agent 发话与发起协作的资格。' : '该 Agent 没有号角，只能被动接收，不具备主动发起跨 Agent 通信的资格。' }}
      </div>
      <div class="action-hint">{{ hornLocked ? '该状态由系统强制保持开启' : '点击切换状态' }}</div>
    </div>
  </n-tooltip>
</template>

<script setup lang="ts">
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
const state = computed(() => store.signalStates[props.agentId] || { hasHorn: false, hornLocked: false });
const hasHorn = computed(() => !!state.value.hasHorn);
const hornLocked = computed(() => !!state.value.hornLocked);

const handleToggle = () => {
  if (hornLocked.value) return;
  store.toggleHorn(props.agentId, !hasHorn.value);
};
</script>

<style scoped>
.horn-indicator {
  width: 24px;
  height: 24px;
  position: relative;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  color: var(--spark-text-muted);
  border-radius: 6px;
}

.horn-indicator:hover {
  background: var(--spark-bg-hover);
  color: var(--spark-text);
}

.horn-indicator.locked {
  cursor: default;
}

.comm-svg {
  width: 18px;
  height: 18px;
  z-index: 2;
}

.horn-indicator.active {
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

.desc,
.action-hint {
  font-size: var(--spark-fs-2xs);
  color: var(--spark-text-muted);
  line-height: 1.4;
}

.action-hint {
  margin-top: 8px;
}
</style>
