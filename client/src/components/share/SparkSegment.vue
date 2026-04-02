<template>
  <div
    class="spark-seg"
    :class="[`spark-seg--${size ?? 'medium'}`, { 'spark-seg--block': block }]"
    role="group"
  >
    <button
      v-for="(opt, i) in options"
      :key="opt.value"
      class="spark-seg__item"
      :class="{
        'is-active': modelValue === opt.value,
        'is-first': i === 0,
        'is-last': i === options.length - 1,
      }"
      type="button"
      @click="select(opt.value)"
    >
      <span class="spark-seg__label">{{ opt.label }}</span>
    </button>
  </div>
</template>

<script setup lang="ts" generic="T extends string">
interface SegmentOption {
  value: T
  label: string
}

const props = defineProps<{
  modelValue: T
  options: SegmentOption[]
  size?: 'tiny' | 'small' | 'medium'
  block?: boolean
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: T): void
}>()

function select(value: T) {
  emit('update:modelValue', value)
}
</script>

<style scoped>
.spark-seg {
  display: inline-flex;
  align-items: stretch;
  gap: 0;
  padding: 3px;
  border-radius: 999px;
  border: none;
  background: color-mix(in srgb, var(--spark-panel-bg), var(--spark-primary) 8%);
  flex-shrink: 0;
  overflow: visible;
}

.spark-seg--block {
  display: flex;
  width: 100%;
}

.spark-seg--block .spark-seg__item {
  flex: 1;
}

/* 各项默认：矩形，透明背景 */
.spark-seg__item {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  background: transparent;
  cursor: pointer;
  color: var(--spark-text-muted);
  font-family: inherit;
  font-weight: 700;
  outline: none;
  border-radius: 2px;
  z-index: 0;
  -webkit-tap-highlight-color: transparent;
  transition:
    color 0.18s ease,
    background 0.2s ease,
    transform 0.28s cubic-bezier(0.34, 1.56, 0.64, 1),
    box-shadow 0.2s ease;
}

/* 首尾项跟随胶囊弯角，内侧保持 2px 小圆角 */
.spark-seg__item.is-first {
  border-radius: 999px 2px 2px 999px;
}
.spark-seg__item.is-last {
  border-radius: 2px 999px 999px 2px;
}
.spark-seg__item.is-first.is-last {
  border-radius: 999px;
}

/* 竖线分隔符（非末项右侧） */
.spark-seg__item:not(.is-last)::after {
  content: '';
  position: absolute;
  right: 0;
  top: 18%;
  height: 64%;
  width: 1px;
  background: color-mix(in srgb, var(--spark-border), transparent 20%);
  pointer-events: none;
  transition: opacity 0.16s ease;
}

/* 激活项自身及其前一项的分隔符隐藏 */
.spark-seg__item.is-active::after {
  opacity: 0;
}
.spark-seg__item:has(+ .is-active)::after {
  opacity: 0;
}

/* 悬停 */
.spark-seg__item:hover:not(.is-active) {
  color: var(--spark-text);
  background: color-mix(in srgb, var(--spark-primary), transparent 91%);
}

/* 激活：向上弹出，平面填色 + 微发光 */
.spark-seg__item.is-active {
  background: var(--spark-primary);
  color: var(--spark-text-inverse);
  transform: translateY(-3px);
  box-shadow: 0 0 10px 1px color-mix(in srgb, var(--spark-primary), transparent 48%);
  z-index: 1;
}

/* 键盘焦点 */
.spark-seg__item:focus-visible {
  outline: 2px solid color-mix(in srgb, var(--spark-primary), transparent 36%);
  outline-offset: 2px;
}

.spark-seg__label {
  display: block;
  white-space: nowrap;
}

/* --- 尺寸规格 --- */
.spark-seg--tiny .spark-seg__item {
  height: 22px;
  min-width: 42px;
  padding: 0 12px;
  font-size: 12px;
}

.spark-seg--small .spark-seg__item {
  height: 26px;
  min-width: 50px;
  padding: 0 13px;
  font-size: 13px;
}

.spark-seg--medium .spark-seg__item {
  height: 30px;
  min-width: 56px;
  padding: 0 14px;
  font-size: 14px;
}
</style>
