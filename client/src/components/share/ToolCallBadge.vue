<template>
  <span class="tool-call-badge">
    <svg class="tool-spinner" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
      <circle cx="12" cy="12" r="10" class="orbit" />
      <circle cx="12" cy="2" r="2.5" class="satellite" />
    </svg>
    <span class="tool-name">{{ displayName }}</span>
  </span>
</template>

<script setup>
import { computed } from 'vue';

const props = defineProps({
  toolName: { type: String, default: '' }
});

const toolNameMap = {
  'rewrite_worldview': '重写世界观',
  'rewrite_all_characters': '重写角色',
  'update_character': '修改角色',
  'rewrite_synopsis': '重写梗概',
  'rewrite_beat_sheet': '重写节拍',
  'rewrite_outline': '重写大纲',
  'rewrite_script': '重写剧本',
};

const displayName = computed(() => toolNameMap[props.toolName] || props.toolName || '工具调用中');
</script>

<style scoped>
.tool-call-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  background: linear-gradient(135deg, 
    color-mix(in srgb, var(--spark-primary), transparent 85%),
    color-mix(in srgb, var(--spark-harmonious-a), transparent 85%)
  );
  border: 1px solid color-mix(in srgb, var(--spark-primary), transparent 60%);
  border-radius: 16px;
  font-size: 0.8rem;
  color: var(--spark-primary);
  font-weight: 500;
}

.tool-spinner {
  width: 16px;
  height: 16px;
  animation: spin 1.5s linear infinite;
}

.orbit {
  fill: none;
  stroke: currentColor;
  stroke-width: 1;
  opacity: 0.3;
}

.satellite {
  fill: currentColor;
  transform-origin: 12px 12px;
}

.tool-name {
  letter-spacing: 0.5px;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>
