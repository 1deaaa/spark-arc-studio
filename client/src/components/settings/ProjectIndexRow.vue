<template>
    <div class="index-row" :class="`index-row--${kind}`">
        <span class="index-row-label">
            <n-icon class="index-row-label-icon" :size="14"><component :is="kindIcon" /></n-icon>
            {{ label }}
        </span>
        <div class="index-row-tags">
            <template v-for="tag in tags" :key="tag.key">
                <n-popover
                    v-if="tag.tone === 'error'"
                    trigger="manual"
                    placement="top"
                    :show="isErrorTagVisible(tag.key)"
                >
                    <template #trigger>
                        <button
                            type="button"
                            class="status-pill status-pill-error-dot"
                            :aria-label="tag.title || tag.label"
                            @mouseenter="showErrorTag(tag.key)"
                            @mouseleave="hideErrorTag(tag.key)"
                            @focus="showErrorTag(tag.key)"
                            @blur="hideErrorTag(tag.key)"
                            @click.stop.prevent="toggleErrorTag(tag.key)"
                        >
                            <span class="status-pill-error-dot-inner" />
                        </button>
                    </template>
                    <div
                        class="error-popover-content"
                        @mouseenter="showErrorTag(tag.key)"
                        @mouseleave="hideErrorTag(tag.key)"
                    >
                        {{ tag.title || tag.label }}
                    </div>
                </n-popover>
                <n-tooltip v-else trigger="hover">
                    <template #trigger>
                        <span class="status-pill" :class="`status-pill-${tag.tone}`">
                            {{ tag.label }}
                        </span>
                    </template>
                    {{ tag.title || tag.label }}
                </n-tooltip>
            </template>
        </div>
        <n-tooltip trigger="hover" placement="top">
            <template #trigger>
                <button
                    :disabled="!enabled || !refreshable || refreshing"
                    class="refresh-icon-btn"
                    :class="{ 'refresh-icon-btn--spinning': refreshing }"
                    @click="onRefreshClick"
                    :aria-label="refreshTooltip"
                >
                    <n-icon :size="15">
                        <RefreshCw />
                    </n-icon>
                </button>
            </template>
            {{ enabled
                ? (refreshable ? refreshTooltip : refreshBusyTooltip || refreshTooltip)
                : refreshDisabledTooltip }}
        </n-tooltip>
        <n-switch
            :value="enabled"
            :loading="loading"
            @update:value="onToggle"
            size="small"
        />
    </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';
import { NSwitch, NTooltip, NPopover, NIcon } from 'naive-ui';
import { RefreshCw, Search, Network } from '@lucide/vue';

export type IndexKind = 'semantic' | 'graphrag';

export type IndexRowTag = {
    key: string;
    label: string;
    tone: 'info' | 'success' | 'warning' | 'error' | 'muted';
    title?: string;
};

const props = defineProps<{
    kind: IndexKind;
    label: string;
    enabled: boolean;
    tags: IndexRowTag[];
    refreshable: boolean;        // 当前是否允许触发刷新（构建中应为 false）
    loading?: boolean;            // toggle 处理中
    refreshing?: boolean;         // refresh 处理中
    refreshTooltip: string;
    refreshDisabledTooltip: string;
    refreshBusyTooltip?: string;
}>();

const emit = defineEmits<{
    (e: 'toggle', value: boolean): void;
    (e: 'refresh'): void;
}>();

const hoveredErrorTagKey = ref<string | null>(null);
const pinnedErrorTagKey = ref<string | null>(null);
const kindIcon = computed(() => (props.kind === 'graphrag' ? Network : Search));

function onToggle(value: boolean) {
    emit('toggle', value);
}

function onRefreshClick() {
    emit('refresh');
}

function isErrorTagVisible(key: string): boolean {
    return hoveredErrorTagKey.value === key || pinnedErrorTagKey.value === key;
}

function showErrorTag(key: string): void {
    hoveredErrorTagKey.value = key;
}

function hideErrorTag(key: string): void {
    if (hoveredErrorTagKey.value === key) {
        hoveredErrorTagKey.value = null;
    }
}

function toggleErrorTag(key: string): void {
    if (pinnedErrorTagKey.value === key) {
        pinnedErrorTagKey.value = null;
        if (hoveredErrorTagKey.value === key) {
            hoveredErrorTagKey.value = null;
        }
        return;
    }

    pinnedErrorTagKey.value = key;
    hoveredErrorTagKey.value = key;
}
</script>

<style scoped>
.index-row {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 10px;
    border-radius: 8px;
    background: color-mix(in srgb, var(--spark-panel-bg), white 1%);
    border: 1px solid color-mix(in srgb, var(--spark-border), transparent 25%);
}

.index-row + .index-row {
    margin-top: 6px;
}

.index-row-label {
    flex-shrink: 0;
    display: inline-flex;
    align-items: center;
    gap: 4px;
    font-size: var(--spark-fs-sm);
    color: var(--spark-text-muted);
    min-width: 78px;
    -webkit-user-select: none;
    user-select: none;
}

.index-row-label-icon {
    color: var(--spark-text-muted);
}

.index-row--graphrag .index-row-label-icon {
    color: color-mix(in srgb, var(--spark-primary) 80%, transparent);
}

.index-row-tags {
    flex: 1;
    min-width: 0;
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: 6px;
    flex-wrap: wrap;
}

.status-pill {
    flex-shrink: 0;
    max-width: 240px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-size: 12px;
    line-height: 18px;
    padding: 2px 8px;
    border-radius: 999px;
    border: 1px solid transparent;
}

.status-pill-info {
    color: var(--spark-primary);
    background: color-mix(in srgb, var(--spark-primary) 10%, var(--spark-panel-bg));
    border-color: color-mix(in srgb, var(--spark-primary) 22%, transparent);
}

.status-pill-success {
    color: #2b8a3e;
    background: color-mix(in srgb, #52c41a 14%, var(--spark-panel-bg));
    border-color: color-mix(in srgb, #52c41a 24%, transparent);
}

.status-pill-warning {
    color: #b26a00;
    background: color-mix(in srgb, #faad14 16%, var(--spark-panel-bg));
    border-color: color-mix(in srgb, #faad14 24%, transparent);
}

.status-pill-error {
    color: #cf1322;
    background: color-mix(in srgb, #ff4d4f 14%, var(--spark-panel-bg));
    border-color: color-mix(in srgb, #ff4d4f 24%, transparent);
}

.status-pill-error-dot {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 14px;
    height: 14px;
    padding: 0;
    margin: 0;
    line-height: 0;
    border: 1px solid color-mix(in srgb, #ff4d4f 36%, transparent);
    background: color-mix(in srgb, #ff4d4f 80%, #ffffff 20%);
    color: #ffffff;
    cursor: pointer;
    flex-shrink: 0;
}

.status-pill-error-dot:hover {
    filter: brightness(1.04);
}

.status-pill-error-dot:focus-visible {
    outline: 2px solid color-mix(in srgb, #ff4d4f 52%, white);
    outline-offset: 2px;
}

.status-pill-error-dot-inner {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: currentColor;
    display: block;
}

.error-popover-content {
    max-width: 320px;
    white-space: pre-wrap;
    word-break: break-word;
    line-height: 1.45;
    font-size: 12px;
    color: var(--spark-text);
}

.status-pill-muted {
    color: var(--spark-text-muted);
    background: color-mix(in srgb, #8c8c8c 10%, var(--spark-panel-bg));
    border-color: color-mix(in srgb, #8c8c8c 18%, transparent);
}

.refresh-icon-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 24px;
    height: 24px;
    border: none;
    border-radius: 6px;
    background: transparent;
    color: var(--spark-text-muted);
    cursor: pointer;
    transition: color 0.15s ease, opacity 0.15s ease;
    padding: 0;
    flex-shrink: 0;
}

.refresh-icon-btn:hover:not(:disabled) {
    color: var(--spark-primary);
}

.refresh-icon-btn:disabled {
    opacity: 0.35;
    cursor: not-allowed;
}

.refresh-icon-btn--spinning {
    color: var(--spark-primary);
    opacity: 0.7;
}

.refresh-icon-btn--spinning :deep(svg) {
    animation: project-index-row-refresh-spin 0.9s linear infinite;
}

@keyframes project-index-row-refresh-spin {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
}

@media (max-width: 640px) {
    .index-row {
        flex-wrap: wrap;
    }

    .index-row-label {
        min-width: auto;
    }

    .index-row-tags {
        justify-content: flex-start;
        width: 100%;
        order: 3;
    }
}
</style>
