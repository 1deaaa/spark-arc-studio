<template>
  <span v-if="locale === 'zh-CN'" class="zh-only-tag" :class="type">
    <slot />
  </span>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n';

/**
 * 仅在当前界面语言为简体中文时渲染内容的合规标签组件。
 * 用于展示仅中国大陆合规场景需要的声明，其他语言不显示。
 */

type ZhOnlyTagType = 'disclaimer' | 'info' | 'warning';

withDefaults(defineProps<{ type?: ZhOnlyTagType }>(), {
  type: 'disclaimer',
});

const { locale } = useI18n();
</script>

<style scoped>
.zh-only-tag {
  display: inline-block;
  font-size: 10px;
  line-height: 1.35;
  letter-spacing: 0.01em;
  padding: 1px 4px;
  border-radius: 2px;
  vertical-align: middle;
}

.zh-only-tag.disclaimer {
  color: rgba(255, 255, 255, 0.38);
  background: rgba(255, 255, 255, 0.04);
}

.zh-only-tag.info {
  color: rgba(255, 255, 255, 0.62);
  background: rgba(100, 160, 255, 0.1);
}

.zh-only-tag.warning {
  color: rgba(255, 200, 80, 0.72);
  background: rgba(255, 200, 80, 0.08);
}
</style>
