<template>
  <!-- 移动端刷卡式流程引导：6步垂直滑动 -->
  <OnboardingOverlay />
</template>

<script setup lang="ts">
/**
 * 移动端 Flow 引导场景
 *
 * 复用 OnboardingOverlay，步骤由 stepDefinitions + OnboardingEngine 驱动。
 * 每步 beforeEnter 钩子自动滚动到对应 FlowCard。
 * 引导逻辑与 UI 逻辑完全分离。
 */
import OnboardingOverlay from '../../engine/OnboardingOverlay.vue';
</script>
