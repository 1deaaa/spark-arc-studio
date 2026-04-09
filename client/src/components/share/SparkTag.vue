<template>
    <span
        class="spark-tag"
        :class="[`spark-tag--${normalizedType}`, `spark-tag--sz-${size}`, { 'spark-tag--ghost': ghost }]"
    ><slot /></span>
</template>

<script setup lang="ts">
import { computed } from 'vue';

const props = withDefaults(defineProps<{
    type?: 'primary' | 'info' | 'success' | 'warning' | 'danger' | 'error' | 'default';
    size?: 'tiny' | 'small' | 'default';
    ghost?: boolean;
}>(), {
    type: 'default',
    size: 'small',
    ghost: false,
});

const normalizedType = computed(() => {
    if (props.type === 'error') return 'danger';
    if (props.type === 'info') return 'primary';
    return props.type;
});
</script>

<style scoped>
.spark-tag {
    display: inline-flex;
    align-items: center;
    border-radius: 999px;
    font-weight: 500;
    white-space: nowrap;
    line-height: 1;
    border: 1px solid var(--_tag-border);
    background: var(--_tag-bg);
    color: var(--_tag-text);
    vertical-align: middle;
    transition: opacity 0.15s;
}

/* ---- 尺寸 ---- */
.spark-tag--sz-tiny  { padding: 1px 6px;  font-size: 10px; }
.spark-tag--sz-small { padding: 2px 8px;  font-size: 11px; }
.spark-tag--sz-default { padding: 3px 10px; font-size: 12px; }

/* ---- 类型颜色 ---- */
.spark-tag--primary {
    --_tag-color: var(--spark-primary);
    --_tag-bg: color-mix(in srgb, var(--spark-primary), transparent 85%);
    --_tag-border: color-mix(in srgb, var(--spark-primary), transparent 72%);
    --_tag-text: var(--spark-primary);
}
.spark-tag--success {
    --_tag-color: var(--spark-success);
    --_tag-bg: color-mix(in srgb, var(--spark-success), transparent 85%);
    --_tag-border: color-mix(in srgb, var(--spark-success), transparent 72%);
    --_tag-text: var(--spark-success);
}
.spark-tag--warning {
    --_tag-color: var(--spark-warning);
    --_tag-bg: color-mix(in srgb, var(--spark-warning), transparent 85%);
    --_tag-border: color-mix(in srgb, var(--spark-warning), transparent 72%);
    --_tag-text: color-mix(in srgb, var(--spark-warning), black 20%);
}
.spark-tag--danger {
    --_tag-color: var(--spark-danger);
    --_tag-bg: color-mix(in srgb, var(--spark-danger), transparent 85%);
    --_tag-border: color-mix(in srgb, var(--spark-danger), transparent 72%);
    --_tag-text: var(--spark-danger);
}
.spark-tag--default {
    --_tag-color: var(--spark-text-muted);
    --_tag-bg: color-mix(in srgb, var(--spark-text-muted), transparent 88%);
    --_tag-border: color-mix(in srgb, var(--spark-text-muted), transparent 75%);
    --_tag-text: var(--spark-text-muted);
}

/* ---- ghost 变体（仅描边，无背景） ---- */
.spark-tag--ghost {
    background: transparent;
}
</style>
