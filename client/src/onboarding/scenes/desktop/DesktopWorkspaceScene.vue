<template>
  <!-- 桌面端工作台引导：8步聚光灯逐步揭示 -->
  <OnboardingOverlay />
</template>

<script setup lang="ts">
/**
 * 桌面端工作台引导场景
 *
 * 此组件仅挂载 OnboardingOverlay，实际步骤由 stepDefinitions + OnboardingEngine 驱动。
 * 引导逻辑与 UI 逻辑完全分离。
 */
import OnboardingOverlay from '../../engine/OnboardingOverlay.vue';
</script>
