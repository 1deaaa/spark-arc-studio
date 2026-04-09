<template>
    <div
        v-if="show && !_dismissed"
        class="spark-alert"
        :class="[`spark-alert--${type}`, { 'spark-alert--no-icon': !showIcon }]"
    >
        <div v-if="showIcon" class="spark-alert__badge">
            <!-- warning：实心三角感叹号 -->
            <svg v-if="type === 'warning'" viewBox="0 0 24 24" fill="currentColor">
                <path fill-rule="evenodd" clip-rule="evenodd" d="M9.401 3.003c1.155-2 4.043-2 5.198 0l7.355 12.748c1.154 2-.29 4.5-2.599 4.5H4.645c-2.309 0-3.752-2.5-2.598-4.5L9.4 3.003zM12 8.25a.75.75 0 0 1 .75.75v3.75a.75.75 0 0 1-1.5 0V9a.75.75 0 0 1 .75-.75zm0 8.25a.75.75 0 1 0 0-1.5.75.75 0 0 0 0 1.5z"/>
            </svg>
            <!-- error：实心圆叉 -->
            <svg v-else-if="type === 'error'" viewBox="0 0 24 24" fill="currentColor">
                <path fill-rule="evenodd" clip-rule="evenodd" d="M12 2.25c-5.385 0-9.75 4.365-9.75 9.75s4.365 9.75 9.75 9.75 9.75-4.365 9.75-9.75S17.385 2.25 12 2.25zm-1.72 6.97a.75.75 0 1 0-1.06 1.06L10.94 12l-1.72 1.72a.75.75 0 1 0 1.06 1.06L12 13.06l1.72 1.72a.75.75 0 1 0 1.06-1.06L13.06 12l1.72-1.72a.75.75 0 1 0-1.06-1.06L12 10.94l-1.72-1.72z"/>
            </svg>
            <!-- success：实心圆勾 -->
            <svg v-else-if="type === 'success'" viewBox="0 0 24 24" fill="currentColor">
                <path fill-rule="evenodd" clip-rule="evenodd" d="M2.25 12c0-5.385 4.365-9.75 9.75-9.75s9.75 4.365 9.75 9.75-4.365 9.75-9.75 9.75S2.25 17.385 2.25 12zm13.36-1.814a.75.75 0 1 0-1.22-.872l-3.236 4.53L9.53 12.22a.75.75 0 0 0-1.06 1.06l2.25 2.25a.75.75 0 0 0 1.14-.094l3.75-5.25z"/>
            </svg>
            <!-- info：实心圆 i -->
            <svg v-else viewBox="0 0 24 24" fill="currentColor">
                <path fill-rule="evenodd" clip-rule="evenodd" d="M2.25 12c0-5.385 4.365-9.75 9.75-9.75s9.75 4.365 9.75 9.75-4.365 9.75-9.75 9.75S2.25 17.385 2.25 12zm8.706-1.442c1.146-.573 2.437.463 2.126 1.706l-.709 2.836.042-.02a.75.75 0 0 1 .67 1.34l-.04.022c-1.147.573-2.438-.463-2.127-1.706l.71-2.836-.042.02a.75.75 0 1 1-.671-1.34l.041-.022zM12 9a.75.75 0 1 0 0-1.5.75.75 0 0 0 0 1.5z"/>
            </svg>
        </div>

        <div class="spark-alert__body">
            <div v-if="title" class="spark-alert__title">{{ title }}</div>
            <div class="spark-alert__content">
                <slot />
                <button v-if="actionText" class="spark-alert__action" @click="$emit('action')">
                    {{ actionText }}
                </button>
            </div>
        </div>

        <button v-if="closable" class="spark-alert__close" @click="_dismissed = true" aria-label="关闭">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round">
                <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
        </button>
    </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';

withDefaults(defineProps<{
    type?: 'info' | 'success' | 'warning' | 'error';
    title?: string;
    showIcon?: boolean;
    show?: boolean;
    actionText?: string;
    closable?: boolean;
}>(), {
    type: 'info',
    showIcon: true,
    show: true,
    closable: false,
});

defineEmits<{ (e: 'action'): void }>();

const _dismissed = ref(false);
</script>

<style scoped>
/* ================================================================
   SparkAlert — 背景统一 panel-bg，类型色只做强调（边框/徽章/标题）
   ================================================================ */
.spark-alert {
    position: relative;
    display: flex;
    align-items: flex-start;
    gap: 12px;
    padding: 12px 16px 12px 14px;
    border-radius: var(--spark-radius-sm);
    border: 1px solid color-mix(in srgb, var(--_alert-color), transparent 70%);
    border-left: 3px solid var(--_alert-color);
    background: var(--spark-panel-bg);
    font-size: 13px;
    line-height: 1.6;
    color: var(--spark-text);
}

.spark-alert--no-icon { padding-left: 14px; }

/* ---- 各类型：只设色彩变量，背景由上层统一处理 ---- */

.spark-alert--info {
    --_alert-color:  var(--spark-primary);
    --_alert-badge:  color-mix(in srgb, var(--spark-primary), transparent 75%);
    --_alert-title:  var(--spark-primary);
    --_alert-action: var(--spark-primary);
}

.spark-alert--success {
    --_alert-color:  var(--spark-success);
    --_alert-badge:  color-mix(in srgb, var(--spark-success), transparent 72%);
    --_alert-title:  var(--spark-success);
    --_alert-action: var(--spark-success);
}

.spark-alert--warning {
    --_alert-color:  var(--spark-warning);
    --_alert-badge:  color-mix(in srgb, var(--spark-warning), transparent 68%);
    --_alert-title:  var(--spark-warning);
    --_alert-action: var(--spark-warning);
}

.spark-alert--error {
    --_alert-color:  var(--spark-danger);
    --_alert-badge:  color-mix(in srgb, var(--spark-danger), transparent 70%);
    --_alert-title:  var(--spark-danger);
    --_alert-action: var(--spark-danger);
}

/* ---- 图标徽章 ---- */
.spark-alert__badge {
    flex-shrink: 0;
    width: 34px;
    height: 34px;
    border-radius: 8px;
    background: var(--_alert-badge);
    color: var(--_alert-color);
    display: flex;
    align-items: center;
    justify-content: center;
    margin-top: 1px;
}
.spark-alert__badge svg {
    width: 20px;
    height: 20px;
}

/* ---- 正文 ---- */
.spark-alert__body {
    flex: 1;
    min-width: 0;
    padding-top: 1px;
}
.spark-alert__title {
    font-weight: 700;
    font-size: 13.5px;
    color: var(--_alert-title);
    margin-bottom: 3px;
    line-height: 1.4;
}
.spark-alert__content {
    color: var(--spark-text-muted);
    font-size: 12.5px;
    line-height: 1.65;
}

/* ---- 行内操作按钮（主题色链接样式） ---- */
.spark-alert__action {
    display: inline;
    margin-left: 6px;
    padding: 0;
    background: none;
    border: none;
    cursor: pointer;
    font-size: 12.5px;
    font-weight: 600;
    color: var(--_alert-action);
    text-decoration: underline;
    text-decoration-color: color-mix(in srgb, var(--_alert-action), transparent 55%);
    text-underline-offset: 2px;
    transition: text-decoration-color 0.15s, opacity 0.15s;
}
.spark-alert__action:hover {
    opacity: 0.8;
    text-decoration-color: var(--_alert-action);
}

/* ---- 关闭按钮 ---- */
.spark-alert__close {
    flex-shrink: 0;
    align-self: flex-start;
    width: 20px;
    height: 20px;
    padding: 0;
    background: none;
    border: none;
    cursor: pointer;
    color: var(--spark-text-muted);
    opacity: 0.5;
    transition: opacity 0.15s;
    display: flex;
    align-items: center;
    justify-content: center;
    margin-top: 2px;
}
.spark-alert__close:hover { opacity: 1; }
.spark-alert__close svg { width: 11px; height: 11px; }
</style>
