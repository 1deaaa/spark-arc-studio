<template>
  <n-tooltip trigger="hover">
    <template #trigger>
      <div 
        class="beacon-indicator" 
        :class="{ active: isOpen }"
        @click.stop="handleClick"
      >
        <div class="beacon-core"></div>
        <div v-if="isOpen" class="beacon-ring"></div>
      </div>
    </template>
    <div class="beacon-tooltip">
      <div class="status-line">
        <span class="dot" :class="{ active: isOpen }"></span>
        <strong>{{ isOpen ? '信标已开启 (Listening)' : '信标已关闭' }}</strong>
      </div>
      <div v-if="isOpen && allowedIntents.length > 0" class="intents-list">
        <div class="label">允许的意图:</div>
        <div class="tags">
          <n-tag v-for="intent in allowedIntents" :key="intent" size="small" :bordered="false" type="primary">
            {{ intent }}
          </n-tag>
        </div>
      </div>
      <div class="action-hint">点击查看消息记录</div>
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

const beaconState = computed(() => store.beaconStates[props.agentId] || { isOpen: false, allowedIntents: [] });
const isOpen = computed(() => beaconState.value.isOpen);
const allowedIntents = computed(() => beaconState.value.allowedIntents || []);

const handleClick = () => {
  store.setSelectedAgent(props.agentId);
};
</script>

<style scoped>
.beacon-indicator {
  width: 14px;
  height: 14px;
  position: relative;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: transform 0.2s ease;
}

.beacon-indicator:hover {
  transform: scale(1.2);
}

.beacon-core {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background-color: var(--spark-text-muted);
  border: 1px solid var(--spark-border);
  transition: all 0.3s ease;
}

.beacon-indicator.active .beacon-core {
  background-color: var(--spark-success);
  border-color: var(--spark-success);
  box-shadow: 0 0 4px var(--spark-success);
}

.beacon-ring {
  position: absolute;
  width: 100%;
  height: 100%;
  border: 2px solid var(--spark-success);
  border-radius: 50%;
  animation: pulse 2s infinite;
  opacity: 0;
}

@keyframes pulse {
  0% {
    transform: scale(0.5);
    opacity: 0.8;
  }
  100% {
    transform: scale(2.5);
    opacity: 0;
  }
}

.beacon-tooltip {
  padding: 4px;
  max-width: 200px;
}

.status-line {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background-color: var(--spark-text-muted);
}

.dot.active {
  background-color: var(--spark-success);
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
