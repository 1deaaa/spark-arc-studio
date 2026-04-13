<template>
  <!-- 移动端聊天浮窗引导：3步聚光灯 -->
  <OnboardingOverlay />
</template>

<script setup lang="ts">
/**
 * 移动端聊天浮窗引导场景
 *
 * 复用 OnboardingOverlay，步骤由 stepDefinitions + OnboardingEngine 驱动。
 */
import OnboardingOverlay from '../../engine/OnboardingOverlay.vue';
</script>
