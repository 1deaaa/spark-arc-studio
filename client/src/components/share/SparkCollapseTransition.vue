<template>
  <div
    class="spark-collapse-grid"
    :class="[{ 'spark-collapse-grid--expanded': show }, $attrs.class]"
    :style="[cssVars, $attrs.style as any]"
  >
    <div class="spark-collapse-grid__inner" :class="{ 'spark-collapse-grid__inner--no-opacity': noOpacity }">
      <slot />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';

defineOptions({ inheritAttrs: false });

const props = withDefaults(defineProps<{
  show?: boolean;
  duration?: string;
  noOpacity?: boolean;
}>(), {
  show: true,
  duration: '0.3s',
  noOpacity: false,
});

const cssVars = computed(() => ({
  '--spark-collapse-duration': props.duration,
}));
</script>

<style scoped>
.spark-collapse-grid {
  display: grid;
  grid-template-rows: 0fr;
  /* 收起：ease-in，快速利落 */
  transition: grid-template-rows var(--spark-collapse-duration) cubic-bezier(0.4, 0, 1, 1);
}

.spark-collapse-grid--expanded {
  grid-template-rows: 1fr;
  /* 展开：ease-out，有弹性感 */
  transition: grid-template-rows var(--spark-collapse-duration) cubic-bezier(0, 0, 0.2, 1);
}

.spark-collapse-grid__inner {
  overflow: hidden;
  min-height: 0;
  opacity: 0;
  transition: opacity var(--spark-collapse-duration) cubic-bezier(0.4, 0, 1, 1);
}

.spark-collapse-grid--expanded .spark-collapse-grid__inner {
  opacity: 1;
  transition: opacity var(--spark-collapse-duration) cubic-bezier(0, 0, 0.2, 1);
}

/* noOpacity 模式：仅高度过渡，不淡入淡出（适用于 tool-trace 等无需 opacity 的场景） */
.spark-collapse-grid__inner--no-opacity {
  opacity: 1;
  transition: none;
}
.spark-collapse-grid--expanded .spark-collapse-grid__inner--no-opacity {
  opacity: 1;
  transition: none;
}
</style>
