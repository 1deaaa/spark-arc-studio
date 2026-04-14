<template>
  <!-- 全屏遮罩层：半透明 + 聚光灯高亮 + 引导气泡 -->
  <Teleport to="body">
    <transition name="onboarding-overlay">
      <div v-if="engine.isActive.value" class="onboarding-overlay-root">
        <!-- 聚光灯 -->
        <OnboardingSpotlight />
        <!-- 引导气泡 -->
        <OnboardingTooltip />
        <!-- 全屏点击穿透遮罩（非高亮区域拦截点击，center 模式或交互穿透时隐藏） -->
        <div
          v-if="!isCenterMode && !engine.allowInteraction.value"
          class="overlay-backdrop"
          @click="onBackdropClick"
        />
      </div>
    </transition>
  </Teleport>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { getOnboardingEngine } from './OnboardingEngine';
import OnboardingSpotlight from './OnboardingSpotlight.vue';
import OnboardingTooltip from './OnboardingTooltip.vue';

const engine = getOnboardingEngine();

// center 模式步骤不需要遮罩阻挡交互
const isCenterMode = computed(() => engine.currentStep?.placement === 'center');

function onBackdropClick() {
  // 点击遮罩区域不做任何事（防止误操作关闭引导）
  // 用户必须通过气泡按钮操作
}
</script>

<style scoped>
.onboarding-overlay-root {
  position: fixed;
  inset: 0;
  z-index: 10000;
  pointer-events: none;
}

.overlay-backdrop {
  position: fixed;
  inset: 0;
  z-index: 9999;
  pointer-events: auto;
}

/* 过渡动画 */
.onboarding-overlay-enter-active {
  transition: opacity 0.4s ease;
}

.onboarding-overlay-leave-active {
  transition: opacity 0.3s ease;
}

.onboarding-overlay-enter-from,
.onboarding-overlay-leave-to {
  opacity: 0;
}
</style>
