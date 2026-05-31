<template>
  <div
    class="agent-avatar"
    :class="{ 'is-active': active, 'is-disabled': disabled }"
    :style="avatarStyle"
    :aria-label="resolvedAriaLabel"
    :role="role"
  >
    <component
      :is="iconComponent"
      class="agent-avatar-icon"
      :stroke-width="strokeWidth"
    />
  </div>
</template>

<script setup lang="ts">
/**
 * AgentAvatar.vue —— 全局统一 Agent 头像组件
 *
 * 设计目标：
 * 1. 唯一真相源：所有 Agent 头像渲染（聊天气泡、轮盘、欢迎页、Agent 列表等）必须经由本组件。
 * 2. 数据驱动：图标 (Lucide 名) 与主题色 (hex) 从后端 registry.py 取，前端不再硬编码。
 * 3. 风格统一：所有 Agent 头像具备一致的圆形容器 / 描边 / 光晕 / 脉冲动画。
 *
 * 使用方式：
 *   <AgentAvatar :agent-id="seg.source_agent" :size="32" :active="isStreaming" />
 */
import { computed, markRaw, type Component } from 'vue';
import {
  Compass, Wand2, ScrollText, Waypoints, Feather, ScanEye, Palette, Sparkles,
} from '@lucide/vue';
import { useAgentRegistry } from '@/composables/useAgentRegistry';

/**
 * Lucide 图标名 → 组件映射表
 * 后端 registry.icon 返回的字符串通过这里转为实际组件。
 * 新增 Agent 时，把对应 Lucide PascalCase 名加到这里即可。
 */
const LUCIDE_ICON_MAP: Record<string, Component> = {
  Compass: markRaw(Compass),
  Wand2: markRaw(Wand2),
  ScrollText: markRaw(ScrollText),
  Waypoints: markRaw(Waypoints),
  Feather: markRaw(Feather),
  ScanEye: markRaw(ScanEye),
  Palette: markRaw(Palette),
  Sparkles: markRaw(Sparkles),
};

const props = defineProps({
  /** Agent ID，对应 registry.py 的 key */
  agentId: { type: String, default: '' },
  /** 头像直径（px），默认 32 */
  size: { type: Number, default: 32 },
  /** 是否处于活动状态（脉冲动画，常用于流式输出中的 agent 头像） */
  active: { type: Boolean, default: false },
  /** 是否禁用（灰化半透明，常用于轮盘中已被其他窗口占用的 agent） */
  disabled: { type: Boolean, default: false },
  /** 图标 stroke 宽度，默认 2 */
  strokeWidth: { type: Number, default: 2 },
  /** ARIA 标签覆盖，默认使用 Agent name */
  ariaLabel: { type: String, default: '' },
  /** ARIA role，默认 img */
  role: { type: String, default: 'img' },
});

const { getAgentIcon, getAgentColor, getAgentName } = useAgentRegistry();

const iconComponent = computed<Component>(() => {
  const iconName = getAgentIcon(props.agentId);
  if (iconName && LUCIDE_ICON_MAP[iconName]) {
    return LUCIDE_ICON_MAP[iconName];
  }
  // 最终兜底：罗盘（Director 同款），永远不会渲染空白
  return LUCIDE_ICON_MAP.Compass;
});

const color = computed(() => getAgentColor(props.agentId));

const avatarStyle = computed(() => ({
  '--agent-avatar-color': color.value,
  width: `${props.size}px`,
  height: `${props.size}px`,
}));

const resolvedAriaLabel = computed(() => props.ariaLabel || getAgentName(props.agentId));
</script>

<style scoped>
.agent-avatar {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: color-mix(
    in srgb,
    var(--agent-avatar-color, var(--spark-primary)) 8%,
    var(--spark-panel-bg, transparent)
  );
  border: 1.5px solid color-mix(
    in srgb,
    var(--agent-avatar-color, var(--spark-primary)) 38%,
    var(--spark-border)
  );
  color: var(--agent-avatar-color, var(--spark-primary));
  box-shadow: 0 4px 10px rgba(0, 0, 0, 0.08);
  position: relative;
  /* 仅保留颜色/光感过渡，禁止 transform 过渡——避免外部触发的 transform 变化产生"幽灵帧" */
  transition: box-shadow 0.2s ease, opacity 0.15s ease;
  flex-shrink: 0;
}

.agent-avatar-icon {
  width: 60%;
  height: 60%;
  display: block;
}

.agent-avatar.is-active {
  animation: agentAvatarPulse 1.4s ease-in-out infinite;
}

.agent-avatar.is-disabled {
  opacity: 0.35;
  filter: grayscale(0.6);
  cursor: not-allowed;
}

@keyframes agentAvatarPulse {
  0% {
    transform: scale(1);
    box-shadow:
      0 0 0 0 color-mix(in srgb, var(--agent-avatar-color, var(--spark-primary)) 26%, transparent),
      0 4px 10px rgba(0, 0, 0, 0.1);
  }
  60% {
    transform: scale(1.05);
    box-shadow:
      0 0 0 8px color-mix(in srgb, var(--agent-avatar-color, var(--spark-primary)) 0%, transparent),
      0 6px 14px rgba(0, 0, 0, 0.12);
  }
  100% {
    transform: scale(1);
    box-shadow:
      0 0 0 0 color-mix(in srgb, var(--agent-avatar-color, var(--spark-primary)) 0%, transparent),
      0 4px 10px rgba(0, 0, 0, 0.1);
  }
}

/* 尊重用户的"减少动效"偏好 */
@media (prefers-reduced-motion: reduce) {
  .agent-avatar.is-active {
    animation: none;
  }
  .agent-avatar {
    transition: none;
  }
}
</style>
