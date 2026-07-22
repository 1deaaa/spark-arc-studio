<template>
  <!-- 聚光灯效果：SVG clip-path 挖洞高亮目标元素 -->
  <div
    v-if="engine.isActive.value && currentStep?.spotlight !== false && rect && !engine.isTransitioning.value"
    class="onboarding-spotlight"
  >
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
        :fill="isLightMode ? 'rgba(247, 248, 250, 0.82)' : 'rgba(3, 5, 9, 0.78)'"
        mask="url(#spotlight-mask)"
      />
    </svg>
    <!-- 高亮边框 -->
    <div
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
const currentStep = computed(() => engine.getCurrentStep());

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
    boxShadow: '0 0 0 3px var(--spark-primary, #ffaa40), 0 0 0 7px color-mix(in srgb, var(--spark-primary, #ffaa40), transparent 78%), 0 18px 48px rgba(0, 0, 0, 0.34)',
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

</style>
