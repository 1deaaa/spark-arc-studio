<template>
    <div v-if="show" class="spark-alert" :class="[`spark-alert--${type}`, { 'spark-alert--no-icon': !showIcon }]">
        <div v-if="showIcon" class="spark-alert__icon">
            <svg v-if="type === 'success'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
                <polyline points="22 4 12 14.01 9 11.01"/>
            </svg>
            <svg v-else-if="type === 'warning'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
                <line x1="12" y1="9" x2="12" y2="13"/>
                <line x1="12" y1="17" x2="12.01" y2="17"/>
            </svg>
            <svg v-else-if="type === 'error'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="12" r="10"/>
                <line x1="15" y1="9" x2="9" y2="15"/>
                <line x1="9" y1="9" x2="15" y2="15"/>
            </svg>
            <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="12" r="10"/>
                <line x1="12" y1="8" x2="12" y2="12"/>
                <line x1="12" y1="16" x2="12.01" y2="16"/>
            </svg>
        </div>
        <div class="spark-alert__body">
            <div v-if="title" class="spark-alert__title">{{ title }}</div>
            <div class="spark-alert__content">
                <slot />
            </div>
        </div>
    </div>
</template>

<script setup lang="ts">
withDefaults(defineProps<{
    type?: 'info' | 'success' | 'warning' | 'error';
    title?: string;
    showIcon?: boolean;
    show?: boolean;
}>(), {
    type: 'info',
    showIcon: true,
    show: true,
});
</script>

<style scoped>
.spark-alert {
    display: flex;
    align-items: flex-start;
    gap: 10px;
    padding: 10px 14px;
    border-radius: var(--spark-radius-sm);
    border: 1px solid;
    font-size: 13px;
    line-height: 1.6;
}

.spark-alert--no-icon {
    padding-left: 14px;
}

/* info */
.spark-alert--info {
    background: color-mix(in srgb, var(--spark-primary), transparent 88%);
    border-color: color-mix(in srgb, var(--spark-primary), transparent 60%);
    color: var(--spark-text);
}
.spark-alert--info .spark-alert__icon {
    color: var(--spark-primary);
}
.spark-alert--info .spark-alert__title {
    color: var(--spark-primary-light);
}

/* success */
.spark-alert--success {
    background: color-mix(in srgb, var(--spark-success), transparent 88%);
    border-color: color-mix(in srgb, var(--spark-success), transparent 60%);
    color: var(--spark-text);
}
.spark-alert--success .spark-alert__icon {
    color: var(--spark-success);
}
.spark-alert--success .spark-alert__title {
    color: var(--spark-success);
}

/* warning */
.spark-alert--warning {
    background: color-mix(in srgb, var(--spark-warning), transparent 88%);
    border-color: color-mix(in srgb, var(--spark-warning), transparent 60%);
    color: var(--spark-text);
}
.spark-alert--warning .spark-alert__icon {
    color: var(--spark-warning);
}
.spark-alert--warning .spark-alert__title {
    color: var(--spark-warning);
}

/* error */
.spark-alert--error {
    background: color-mix(in srgb, var(--spark-danger), transparent 88%);
    border-color: color-mix(in srgb, var(--spark-danger), transparent 60%);
    color: var(--spark-text);
}
.spark-alert--error .spark-alert__icon {
    color: var(--spark-danger);
}
.spark-alert--error .spark-alert__title {
    color: var(--spark-danger);
}

.spark-alert__icon {
    flex-shrink: 0;
    width: 18px;
    height: 18px;
    margin-top: 1px;
    display: flex;
    align-items: center;
    justify-content: center;
}

.spark-alert__icon svg {
    width: 100%;
    height: 100%;
}

.spark-alert__body {
    flex: 1;
    min-width: 0;
}

.spark-alert__title {
    font-weight: 600;
    margin-bottom: 3px;
    font-size: 13px;
}

.spark-alert__content {
    opacity: 0.9;
}
</style>
