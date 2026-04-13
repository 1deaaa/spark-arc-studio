<template>
  <!-- 聚光灯效果：SVG clip-path 挖洞高亮目标元素 -->
  <div v-if="engine.isActive.value && rect && !engine.isTransitioning.value" class="onboarding-spotlight">
    <svg class="spotlight-svg" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <mask id="spotlight-mask">
          <!-- 全白遮罩 -->
          <rect x="0" y="0" width="100%" height="100%" fill="white" />
          <!-- 挖洞区域（黑色 = 透明） -->
          <rect
            :x="rect.left"
            :y="rect.top"
            :width="rect.width"
            :height="rect.height"
            rx="8"
            fill="black"
          />
        </mask>
      </defs>
      <!-- 半透明遮罩层，挖洞处透明（亮色用白底，暗色用黑底） -->
      <rect
        x="0" y="0" width="100%" height="100%"
        :fill="isLightMode ? 'rgba(255, 255, 255, 0.6)' : 'rgba(0, 0, 0, 0.55)'"
        mask="url(#spotlight-mask)"
      />
    </svg>
    <!-- 高亮边框 -->
    <div
      v-if="showBorder"
      class="spotlight-border"
      :style="borderStyle"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, type StyleValue } from 'vue';
import { getOnboardingEngine } from './OnboardingEngine';

const engine = getOnboardingEngine();

const rect = computed(() => engine.targetRect.value);
const showBorder = computed(() => engine.allowInteraction.value);

// 检测亮色模式
const isLightMode = computed(() => document.body.classList.contains('light-mode'));

const borderStyle = computed<StyleValue>(() => {
  const r = rect.value;
  if (!r) return {};
  return {
    position: 'fixed',
    left: `${r.left}px`,
    top: `${r.top}px`,
    width: `${r.width}px`,
    height: `${r.height}px`,
    borderRadius: '8px',
    boxShadow: '0 0 0 2px var(--spark-primary, #ffaa40), 0 0 20px rgba(255, 170, 64, 0.3)',
    pointerEvents: 'none',
    zIndex: 10001,
  };
});
</script>

<style scoped>
.onboarding-spotlight {
  position: fixed;
  inset: 0;
  z-index: 10000;
  pointer-events: none;
}

.spotlight-svg {
  width: 100%;
  height: 100%;
}

/* 允许交互穿透时，遮罩层可点击穿透到下方元素 */
.onboarding-spotlight.interactive {
  pointer-events: auto;
}
</style>
