<template>
  <span class="app-brand" :class="{ 'is-icon-only': !showText }">
    <img class="app-brand__icon" :src="brandLogo" :alt="altText" :style="iconStyle" />
    <span v-if="showText" class="app-brand__text">{{ displayText }}</span>
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';
import brandLogoLight from '@/assets/sparkarc-light.png';
import brandLogoDark from '@/assets/sparkarc-dark.png';
import { useThemeStore } from '@/components/stores/themeStore';

const { locale } = useI18n();

const props = withDefaults(defineProps<{
  size?: number | string;
  text?: string;
  showText?: boolean;
  alt?: string;
}>(), {
  size: 24,
  text: undefined, // 改为 undefined，由 computed 动态决定
  showText: true,
  alt: undefined,
});

const themeStore = useThemeStore();

const isDark = computed(() =>
  themeStore.themeMode === 'dark' || (themeStore.themeMode === 'system' && themeStore.prefersDark)
);

const brandLogo = computed(() => isDark.value ? brandLogoDark : brandLogoLight);

const normalizedSize = computed(() => {
  return typeof props.size === 'number' ? `${props.size}px` : props.size;
});

const iconStyle = computed(() => ({
  width: normalizedSize.value,
  height: normalizedSize.value,
}));

// 动态品牌文本：中文模式显示"引火AI"，其他语言显示"SparkArc"
const displayText = computed(() => {
  if (props.text !== undefined) return props.text;
  const lang = locale.value.toLowerCase();
  return lang.startsWith('zh') ? '引火AI' : 'SparkArc';
});

const altText = computed(() => props.alt || displayText.value);
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
  object-fit: contain;
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
