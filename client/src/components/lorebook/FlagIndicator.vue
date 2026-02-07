<template>
  <n-tooltip trigger="hover">
    <template #trigger>
      <div 
        class="flag-indicator" 
        :class="{ active: hasFlag }"
        @click.stop="handleToggle"
      >
        <svg viewBox="0 0 24 24" class="comm-svg">
          <!-- 旗帜图标 -->
          <path 
            d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z" 
            stroke="currentColor" stroke-width="2" stroke-linecap="round" fill="none"
          />
          <line x1="4" y1="22" x2="4" y2="15" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
          <circle v-if="hasFlag" cx="12" cy="12" r="9" stroke="currentColor" stroke-width="1" fill="none" class="pulse-ring" />
        </svg>
        <div v-if="hasFlag" class="status-glow"></div>
      </div>
    </template>
    <div class="tooltip-content">
      <div class="status-line">
        <span class="dot" :class="{ active: hasFlag }"></span>
        <strong>{{ hasFlag ? '旗帜已持有' : '旗帜未持有' }}</strong>
      </div>
      <div class="desc">
        {{ hasFlag ? '该 Agent 持有旗帜，具有主动发起通讯、调度他人的主动权。持有旗帜时将强制开启信标。' : '该 Agent 未持有旗帜，处于被动状态，无法主动发起通讯。' }}
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

const state = computed(() => store.beaconStates[props.agentId] || { hasFlag: false });
const hasFlag = computed(() => !!state.value.hasFlag);

const handleToggle = () => {
  const newVal = !hasFlag.value;
  store.toggleFlag(props.agentId, newVal);
  // 如果开启旗帜，同步前端 UI 状态（后端 take_flag 已经处理了 logic，但前端 store 刷新可能延迟或需要手动同步以保证即时反馈）
  if (newVal) {
    store.beaconStates[props.agentId].isOpen = true;
  }
};
</script>

<style scoped>
.flag-indicator {
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

.flag-indicator:hover {
  background: var(--spark-bg-hover);
  color: var(--spark-text);
}

.comm-svg {
  width: 18px;
  height: 18px;
  z-index: 2;
}

.flag-indicator.active {
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

.action-hint {
  margin-top: 8px;
  font-size: 10px;
  color: var(--spark-text-muted);
  border-top: 1px solid var(--spark-border);
  padding-top: 4px;
  text-align: center;
}
</style>
