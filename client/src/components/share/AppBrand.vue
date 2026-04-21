<template>
  <span class="app-brand" :class="{ 'is-icon-only': !showText }">
    <img class="app-brand__icon" :src="brandLogo" :alt="altText" :style="iconStyle" />
    <span v-if="showText" class="app-brand__text">{{ text }}</span>
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import brandLogo from '@/assets/sparkarc-logo-rounded.png';

const props = withDefaults(defineProps<{
  size?: number | string;
  text?: string;
  showText?: boolean;
  alt?: string;
}>(), {
  size: 24,
  text: 'SparkArc',
  showText: true,
  alt: 'SparkArc',
});

const normalizedSize = computed(() => {
  return typeof props.size === 'number' ? `${props.size}px` : props.size;
});

const iconStyle = computed(() => ({
  width: normalizedSize.value,
  height: normalizedSize.value,
}));

const altText = computed(() => props.alt || props.text || 'SparkArc');
</script>

<style scoped>
.app-brand {
  display: inline-flex;
  align-items: center;
  gap: 0.55rem;
  min-width: 0;
  vertical-align: middle;
  color: inherit;
}

.app-brand.is-icon-only {
  gap: 0;
}

.app-brand__icon {
  display: block;
  flex-shrink: 0;
  object-fit: cover;
}

.app-brand__text {
  min-width: 0;
  color: inherit;
  font: inherit;
  font-weight: inherit;
  letter-spacing: inherit;
  line-height: inherit;
  white-space: nowrap;
}
</style>
