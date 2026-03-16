<template>
  <n-tooltip trigger="hover">
    <template #trigger>
      <div 
        class="beacon-indicator" 
        :class="{ active: isBeaconOpen, locked: beaconLocked }"
        @click.stop="handleClick"
      >
        <svg viewBox="0 0 24 24" class="beacon-svg">
          <!-- 底部支架/中心点 -->
          <circle cx="12" cy="18" r="2" fill="currentColor" />
          <path d="M12 16v-4" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
          
          <!-- 信号波纹 -->
          <path 
            class="wave wave-1"
            d="M8.5 11.5c2-1.5 5-1.5 7 0" 
            stroke="currentColor" stroke-width="2" stroke-linecap="round" fill="none" 
          />
          <path 
            class="wave wave-2"
            d="M5 8c4-3.5 10-3.5 14 0" 
            stroke="currentColor" stroke-width="2" stroke-linecap="round" fill="none" 
          />
        </svg>
        <div v-if="isBeaconOpen" class="beacon-status-glow"></div>
      </div>
    </template>
    <div class="tooltip-content">
      <div class="status-line">
        <span class="dot" :class="{ active: isBeaconOpen }"></span>
        <strong>{{ isBeaconOpen ? '信标已开启' : '信标已关闭' }}</strong>
      </div>
      <div class="desc">
        {{ isBeaconOpen ? '信标已开启，该 Agent 会出现在其他 Agent 的协作视野中，并能接收外部消息。' : '信标已关闭，该 Agent 对其他 Agent 不可见，也不会收到外部消息。' }}
      </div>
      <div v-if="isBeaconOpen && allowedIntents.length > 0" class="intents-list">
        <div class="label">允许的意图:</div>
        <div class="tags">
          <n-tag v-for="intent in allowedIntents" :key="intent" size="small" :bordered="false" type="primary">
            {{ intent }}
          </n-tag>
        </div>
      </div>
      <div class="action-hint">{{ beaconLocked ? '该状态由系统强制保持开启' : '点击切换状态' }}</div>
    </div>
  </n-tooltip>
</template>

<script setup>
import { computed } from 'vue';
import { useAgentRuntimeStore } from '../stores/agentRuntimeStore';
import { NTooltip, NTag } from 'naive-ui';

const props = defineProps({
  agentId: {
    type: String,
    required: true
  }
});

const store = useAgentRuntimeStore();

const signalState = computed(() => store.signalStates[props.agentId] || { isBeaconOpen: false, beaconLocked: false, allowedIntents: [] });
const isBeaconOpen = computed(() => signalState.value.isBeaconOpen);
const beaconLocked = computed(() => !!signalState.value.beaconLocked);
const allowedIntents = computed(() => signalState.value.allowedIntents || []);

const handleClick = () => {
  if (beaconLocked.value) return;
  store.toggleBeacon(props.agentId, !isBeaconOpen.value);
};
</script>

<style scoped>
.beacon-indicator {
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

.beacon-indicator:hover {
  background: var(--spark-bg-hover);
  color: var(--spark-text);
}

.beacon-indicator.locked {
  cursor: default;
}

.beacon-svg {
  width: 20px;
  height: 20px;
  z-index: 2;
}

.beacon-indicator.active {
  color: var(--spark-primary);
}

.wave {
  opacity: 0.3;
  transition: opacity 0.3s ease;
}

.beacon-indicator.active .wave {
  opacity: 1;
}

.beacon-indicator.active .wave-1 {
  animation: wave-pulse 1.5s infinite 0s;
}

.beacon-indicator.active .wave-2 {
  animation: wave-pulse 1.5s infinite 0.4s;
}

@keyframes wave-pulse {
  0% { opacity: 0.3; transform: translateY(0); }
  50% { opacity: 1; transform: translateY(-1px); }
  100% { opacity: 0.3; transform: translateY(0); }
}

.beacon-status-glow {
  position: absolute;
  inset: 0;
  background: var(--spark-primary-glow);
  border-radius: 50%;
  filter: blur(8px);
  z-index: 1;
  opacity: 0.4;
  animation: glow-pulse 2s infinite ease-in-out;
}

@keyframes glow-pulse {
  0%, 100% { transform: scale(0.8); opacity: 0.2; }
  50% { transform: scale(1.2); opacity: 0.5; }
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
  background-color: var(--spark-primary);
}

.intents-list {
  font-size: 12px;
}

.intents-list .label {
  color: var(--spark-text-muted);
  margin-bottom: 4px;
}

.tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
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
