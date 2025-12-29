<template>
  <n-tooltip trigger="hover">
    <template #trigger>
      <div 
        class="comm-right-indicator" 
        :class="{ active: hasRight }"
        @click.stop="handleToggle"
      >
        <svg viewBox="0 0 24 24" class="comm-svg">
          <!-- 喇叭/发射塔图标 -->
          <path 
            d="M12 3v10m0 0l-3-3m3 3l3-3" 
            stroke="currentColor" stroke-width="2" stroke-linecap="round" fill="none"
            v-if="false"
          />
          <path 
            d="M19 12c0 3.866-3.134 7-7 7s-7-3.134-7-7M12 5v14m0-14l-3 3m3-3l3 3" 
            stroke="currentColor" stroke-width="2" stroke-linecap="round" fill="none"
          />
          <circle v-if="hasRight" cx="12" cy="12" r="9" stroke="currentColor" stroke-width="1" fill="none" class="pulse-ring" />
        </svg>
        <div v-if="hasRight" class="comm-status-glow"></div>
      </div>
    </template>
    <div class="comm-tooltip">
      <div class="status-line">
        <span class="dot" :class="{ active: hasRight }"></span>
        <strong>{{ hasRight ? '通信权已开启 (Active)' : '通信权已关闭' }}</strong>
      </div>
      <div class="desc">
        {{ hasRight ? '该 Agent 具有主动发起通讯、调度他人的权限。' : '该 Agent 目前处于被动状态，无法主动发起通讯。' }}
      </div>
      <div class="action-hint">点击切换状态</div>
    </div>
  </n-tooltip>
</template>

<script setup>
import { computed } from 'vue';
import { useAgentRuntimeStore } from '../stores/agentRuntimeStore';
import { NTooltip } from 'naive-ui';

const props = defineProps({
  agentId: {
    type: String,
    required: true
  }
});

const store = useAgentRuntimeStore();

const state = computed(() => store.beaconStates[props.agentId] || { hasCommunicationRight: false });
const hasRight = computed(() => !!state.value.hasCommunicationRight);

const handleToggle = () => {
  store.toggleCommunicationRight(props.agentId, !hasRight.value);
};
</script>

<style scoped>
.comm-right-indicator {
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

.comm-right-indicator:hover {
  background: var(--spark-bg-hover);
  color: var(--spark-text);
}

.comm-svg {
  width: 18px;
  height: 18px;
  z-index: 2;
}

.comm-right-indicator.active {
  color: var(--spark-contrast-output);
}

.comm-status-glow {
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

.comm-tooltip {
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

.action-hint {
  margin-top: 8px;
  font-size: 10px;
  color: var(--spark-text-muted);
  border-top: 1px solid var(--spark-border);
  padding-top: 4px;
  text-align: center;
}
</style>
