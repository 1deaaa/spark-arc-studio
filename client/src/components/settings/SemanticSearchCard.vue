<template>
    <div class="settings-section">
        <div class="section-header">
            <h3>{{ t('components.semanticSearchCard.title') }}</h3>
        </div>
        <p class="section-desc">{{ t('components.semanticSearchCard.subtitle') }}</p>

        <div v-if="loading" class="loading-state">
            <n-spin size="large" />
        </div>

        <div v-else>
            <!-- 嵌入模型状态栏 -->
            <div class="embedding-bar" v-if="embeddingReady !== null">
                <div class="embedding-info">
                    <span class="dot" :class="embeddingReady ? 'dot-ok' : 'dot-warn'" />
                    <span class="embedding-label">{{ t('components.semanticSearchCard.embeddingModel') }}</span>
                    <span class="embedding-value">{{ embeddingReady ? (embeddingModelName || 'OK') : t('components.semanticSearchCard.notConfigured') }}</span>
                </div>
                <n-button
                    size="tiny"
                    quaternary
                    :loading="testingEmbedding"
                    @click="handleTestEmbedding"
                    type="primary"
                >
                    {{ t('components.semanticSearchCard.testEmbedding') }}
                </n-button>
            </div>

            <div class="project-summary" v-if="projects.length > 0">
                <div class="summary-pill summary-pill-enabled">
                    <span class="summary-number">{{ enabledCount }}</span>
                    <span class="summary-label">{{ t('components.semanticSearchCard.enabled') }}</span>
                </div>
                <div class="summary-pill summary-pill-disabled">
                    <span class="summary-number">{{ disabledCount }}</span>
                    <span class="summary-label">{{ t('components.semanticSearchCard.disabled') }}</span>
                </div>
                <div class="summary-pill summary-pill-total">
                    <span class="summary-number">{{ filteredProjects.length }}</span>
                    <span class="summary-label">{{ t('components.semanticSearchCard.visibleProjects') }}</span>
                </div>
            </div>

            <div class="project-toolbar" v-if="projects.length > 0">
                <input
                    type="search"
                    v-model.trim="searchKeyword"
                    class="project-search"
                    :placeholder="t('components.semanticSearchCard.searchPlaceholder')"
                    autocomplete="nope"
                    spellcheck="false"
                    data-1p-ignore
                    data-lpignore="true"
                />
            </div>

            <!-- 项目列表 -->
            <div v-if="projects.length > 0" class="project-list-shell">
                <div v-if="filteredProjects.length > 0" class="project-list">
                    <div v-for="proj in filteredProjects" :key="proj.projectName" class="project-card">
                        <div class="project-card-main">
                            <span class="project-name" :title="proj.projectName">{{ proj.projectName }}</span>
                        </div>
                        <div class="project-card-tags">
                            <span
                                v-for="tag in getProjectStatusTags(proj)"
                                :key="`${proj.projectName}-${tag.key}`"
                                class="semantic-status-pill"
                                :class="`semantic-status-pill-${tag.tone}`"
                                :title="tag.title || tag.label"
                            >
                                {{ tag.label }}
                            </span>
                        </div>
                        <n-switch
                            :value="proj.enabled"
                            :loading="proj._loading"
                            @update:value="(val: boolean) => handleToggle(proj, val)"
                            size="small"
                        />
                    </div>
                </div>
                <n-empty v-else :description="t('components.semanticSearchCard.noSearchResults')" size="small" />
            </div>
            <n-empty v-else :description="t('components.semanticSearchCard.noProjects')" size="small" />

            <!-- 底部：默认启用 + 自动更新提示 -->
            <div class="card-footer">
                <div class="default-toggle">
                    <n-switch
                        :value="defaultEnabled"
                        @update:value="handleDefaultToggle"
                        size="small"
                    />
                    <div class="default-toggle-text">
                        <span class="default-toggle-label">{{ t('components.semanticSearchCard.defaultEnabled') }}</span>
                    </div>
                </div>
                <p class="auto-update-hint">{{ t('components.semanticSearchCard.autoUpdateHint') }}</p>
            </div>
        </div>
    </div>
</template>

<script setup lang="ts">
import { computed, ref, onBeforeUnmount, onMounted } from 'vue';
import { useI18n } from 'vue-i18n';
import { NSpin, NButton, NSwitch, NEmpty, useMessage, useDialog } from 'naive-ui';
import {
    fetchSemanticSearchStatus,
    enableSemanticSearch,
    disableSemanticSearch,
    testSemanticEmbedding,
    setSemanticSearchDefaults,
    type SemanticSearchProjectStatus,
} from '../../services/api';

const { t } = useI18n();
const message = useMessage();
const dialog = useDialog();

type ProjectRow = SemanticSearchProjectStatus & { _loading?: boolean };
type ProjectStatusTag = { key: string; label: string; tone: 'info' | 'success' | 'warning' | 'error'; title?: string };

const BUILDING_STATUSES = new Set(['queued', 'building']);
const POLL_INTERVAL_MS = 2500;

const loading = ref(true);
const testingEmbedding = ref(false);
const embeddingReady = ref<boolean | null>(null);
const embeddingModelName = ref('');
const defaultEnabled = ref(false);
const searchKeyword = ref('');
const projects = ref<ProjectRow[]>([]);
let pollingTimer: number | null = null;

const enabledCount = computed(() => projects.value.filter((project) => project.enabled).length);
const disabledCount = computed(() => projects.value.length - enabledCount.value);
const filteredProjects = computed(() => {
    const keyword = searchKeyword.value.trim().toLowerCase();
    if (!keyword) {
        return projects.value;
    }
    return projects.value.filter((project) => project.projectName.toLowerCase().includes(keyword));
});

function clearStatusPolling() {
    if (pollingTimer !== null && typeof window !== 'undefined') {
        window.clearTimeout(pollingTimer);
    }
    pollingTimer = null;
}

function isProjectBuilding(project: SemanticSearchProjectStatus) {
    return BUILDING_STATUSES.has(project.buildState.status);
}

function truncateText(text: string, maxLength = 42) {
    if (text.length <= maxLength) {
        return text;
    }
    return `${text.slice(0, maxLength - 1)}…`;
}

function getProjectStatusTags(project: SemanticSearchProjectStatus): ProjectStatusTag[] {
    if (project.buildState.status === 'error') {
        const tags: ProjectStatusTag[] = [
            {
                key: 'status',
                label: t('components.semanticSearchCard.statusError'),
                tone: 'error',
            },
        ];
        if (project.buildState.error) {
            tags.push({
                key: 'error-detail',
                label: truncateText(project.buildState.error),
                tone: 'error',
                title: project.buildState.error,
            });
        }
        return tags;
    }

    if (BUILDING_STATUSES.has(project.buildState.status)) {
        return [
            {
                key: 'status',
                label: t('components.semanticSearchCard.statusBuilding'),
                tone: 'info',
            },
        ];
    }

    if (!project.indexExists || project.buildState.status === 'not_built') {
        return [
            {
                key: 'status',
                label: t('components.semanticSearchCard.statusPending'),
                tone: 'warning',
            },
        ];
    }

    if (project.needsRebuild || project.buildState.status === 'stale') {
        return [
            {
                key: 'status',
                label: t('components.semanticSearchCard.statusPendingUpdate'),
                tone: 'warning',
            },
        ];
    }

    return [
        {
            key: 'status',
            label: t('components.semanticSearchCard.statusReady'),
            tone: 'success',
        },
    ];
}

function syncStatusPolling() {
    clearStatusPolling();
    if (typeof window === 'undefined') {
        return;
    }
    if (!projects.value.some((project) => isProjectBuilding(project))) {
        return;
    }
    pollingTimer = window.setTimeout(() => {
        void loadData({ silent: true });
    }, POLL_INTERVAL_MS);
}

async function loadData(options: { silent?: boolean } = {}) {
    const silent = options.silent === true;
    if (!silent) {
        loading.value = true;
    }
    try {
        const status = await fetchSemanticSearchStatus();
        embeddingReady.value = status.embedding_ready;
        embeddingModelName.value = status.embedding_model_name || '';
        defaultEnabled.value = status.default_enabled ?? false;
        const loadingMap = new Map(projects.value.map(project => [project.projectName, Boolean(project._loading)]));
        projects.value = status.projects.map(project => ({
            ...project,
            _loading: loadingMap.get(project.projectName) ?? false,
        }));
    } catch (e: unknown) {
        const msg = e instanceof Error ? e.message : String(e);
        message.error(msg);
    } finally {
        if (!silent) {
            loading.value = false;
        }
        syncStatusPolling();
    }
}

async function handleToggle(proj: ProjectRow, enabled: boolean) {
    proj._loading = true;
    try {
        if (enabled) {
            const result = await enableSemanticSearch(proj.projectName);
            proj.enabled = true;
            proj.buildState = result.buildState;
            proj.indexExists = result.indexExists;
            proj.needsRebuild = result.needsRebuild;
            message.success(t('components.semanticSearchCard.enableSuccess', { name: proj.projectName }));
        } else {
            const result = await disableSemanticSearch(proj.projectName);
            proj.enabled = false;
            proj.buildState = result.buildState;
            proj.indexExists = result.indexExists;
            proj.needsRebuild = result.needsRebuild;
            message.success(t('components.semanticSearchCard.disableSuccess', { name: proj.projectName }));
        }
        await loadData({ silent: true });
    } catch (e: unknown) {
        const msg = e instanceof Error ? e.message : String(e);
        if (enabled) {
            dialog.error({
                title: t('components.semanticSearchCard.enableFailed'),
                content: msg,
                positiveText: t('common.confirm'),
            });
            proj.enabled = false;
        } else {
            message.error(msg);
        }
    } finally {
        const target = projects.value.find(project => project.projectName === proj.projectName);
        if (target) {
            target._loading = false;
        } else {
            proj._loading = false;
        }
        syncStatusPolling();
    }
}

async function handleTestEmbedding() {
    testingEmbedding.value = true;
    try {
        const result = await testSemanticEmbedding();
        if (result.success) {
            embeddingReady.value = true;
            embeddingModelName.value = result.model_name || '';
            dialog.success({
                title: t('components.semanticSearchCard.testSuccess'),
                content: t('components.semanticSearchCard.testSuccessDetail', {
                    model: result.model_name || '',
                    dims: result.dims || 0,
                }),
                positiveText: t('common.confirm'),
            });
        } else {
            embeddingReady.value = false;
            dialog.error({
                title: t('components.semanticSearchCard.testFailed'),
                content: result.error || t('components.semanticSearchCard.testFailedUnknown'),
                positiveText: t('common.confirm'),
            });
        }
    } catch (e: unknown) {
        const msg = e instanceof Error ? e.message : String(e);
        dialog.error({
            title: t('components.semanticSearchCard.testFailed'),
            content: msg,
            positiveText: t('common.confirm'),
        });
    } finally {
        testingEmbedding.value = false;
    }
}

async function handleDefaultToggle(val: boolean) {
    try {
        const result = await setSemanticSearchDefaults(val);
        defaultEnabled.value = result.default_enabled;
    } catch (e: unknown) {
        const msg = e instanceof Error ? e.message : String(e);
        message.error(msg);
    }
}

onMounted(() => {
    loadData();
});

onBeforeUnmount(() => {
    clearStatusPolling();
});
</script>

<style scoped>
.settings-section {
    background: var(--spark-panel-bg);
    border: 1px solid var(--spark-border);
    border-radius: var(--spark-radius);
    padding: var(--spark-panel-padding);
    margin-bottom: 20px;
}

.section-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    margin-bottom: 8px;
}

.settings-section h3 {
    margin: 0;
    font-size: var(--spark-fs-h3);
    color: var(--spark-primary);
    line-height: 28px;
    display: inline-flex;
    align-items: center;
    -webkit-user-select: none;
    user-select: none;
    cursor: default;
}

.section-desc {
    color: var(--spark-text-muted);
    margin-bottom: 14px;
    font-size: var(--spark-fs-base);
}

.loading-state {
    display: flex;
    justify-content: center;
    padding: 20px 0;
}

/* 嵌入模型状态栏 */
.embedding-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding: 8px 0 12px;
    border-bottom: 1px solid color-mix(in srgb, var(--spark-border), transparent 10%);
    margin-bottom: 6px;
}

.embedding-info {
    display: flex;
    align-items: center;
    gap: 6px;
}

.embedding-label {
    font-size: var(--spark-fs-sm);
    color: var(--spark-text-muted);
}

.embedding-value {
    font-size: var(--spark-fs-sm);
    color: var(--spark-text);
}

/* 状态圆点 */
.dot {
    display: inline-block;
    width: 8px;
    height: 8px;
    border-radius: 50%;
    flex-shrink: 0;
}

.dot-ok { background: #52c41a; }
.dot-warn { background: #faad14; }
.dot-off { background: #d9d9d9; }

.project-summary {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin: 12px 0 10px;
}

.summary-pill {
    display: inline-flex;
    align-items: baseline;
    gap: 6px;
    padding: 6px 10px;
    border-radius: 999px;
    font-size: var(--spark-fs-sm);
}

.summary-pill-enabled {
    background: color-mix(in srgb, #52c41a 14%, var(--spark-panel-bg));
    color: #2b8a3e;
}

.summary-pill-disabled {
    background: color-mix(in srgb, #8c8c8c 12%, var(--spark-panel-bg));
    color: var(--spark-text-muted);
}

.summary-pill-total {
    background: color-mix(in srgb, var(--spark-primary) 12%, var(--spark-panel-bg));
    color: var(--spark-primary);
}

.summary-number {
    font-size: var(--spark-fs-base);
    font-weight: 700;
}

.summary-label {
    font-size: var(--spark-fs-sm);
}

.project-toolbar {
    margin-bottom: 10px;
}

.project-search {
    width: 100%;
    height: 34px;
    padding: 0 12px;
    border-radius: 10px;
    border: 1px solid var(--spark-border);
    background: var(--spark-panel-bg);
    color: var(--spark-text);
    outline: none;
    box-sizing: border-box;
}

.project-search:focus {
    border-color: var(--spark-primary);
}

.project-list-shell {
    border: 1px solid color-mix(in srgb, var(--spark-border), transparent 10%);
    border-radius: 12px;
    padding: 10px;
    background: color-mix(in srgb, var(--spark-panel-bg), white 2%);
}

/* 项目列表 */
.project-list {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
    gap: 8px;
    max-height: 260px;
    overflow: auto;
    padding-right: 2px;
}

.project-card {
    display: flex;
    align-items: center;
    gap: 8px;
    min-height: 42px;
    padding: 8px 10px;
    border: 1px solid color-mix(in srgb, var(--spark-border), transparent 15%);
    border-radius: 10px;
    background: var(--spark-panel-bg);
}

.project-card-main {
    flex: 1;
    min-width: 0;
    display: flex;
    align-items: center;
    gap: 6px;
}

.project-card-tags {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: 6px;
    flex-wrap: wrap;
}

.project-name {
    font-size: var(--spark-fs-base);
    color: var(--spark-text);
    font-weight: 500;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.semantic-status-pill {
    flex-shrink: 0;
    max-width: 180px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-size: 12px;
    line-height: 18px;
    padding: 2px 8px;
    border-radius: 999px;
    border: 1px solid transparent;
}

.semantic-status-pill-info {
    color: var(--spark-primary);
    background: color-mix(in srgb, var(--spark-primary) 10%, var(--spark-panel-bg));
    border-color: color-mix(in srgb, var(--spark-primary) 22%, transparent);
}

.semantic-status-pill-success {
    color: #2b8a3e;
    background: color-mix(in srgb, #52c41a 14%, var(--spark-panel-bg));
    border-color: color-mix(in srgb, #52c41a 24%, transparent);
}

.semantic-status-pill-warning {
    color: #b26a00;
    background: color-mix(in srgb, #faad14 16%, var(--spark-panel-bg));
    border-color: color-mix(in srgb, #faad14 24%, transparent);
}

.semantic-status-pill-error {
    color: #cf1322;
    background: color-mix(in srgb, #ff4d4f 14%, var(--spark-panel-bg));
    border-color: color-mix(in srgb, #ff4d4f 24%, transparent);
}

.build-spinner {
    width: 14px;
    height: 14px;
    border-radius: 50%;
    border: 2px solid color-mix(in srgb, var(--spark-primary) 18%, transparent);
    border-top-color: var(--spark-primary);
    animation: semantic-build-spin 0.85s linear infinite;
    flex-shrink: 0;
}

@keyframes semantic-build-spin {
    from {
        transform: rotate(0deg);
    }
    to {
        transform: rotate(360deg);
    }
}

/* 移动端适配 */
@media (max-width: 640px) {
    .project-list {
        grid-template-columns: 1fr;
    }

    .project-summary {
        gap: 6px;
    }

    .summary-pill {
        padding: 4px 8px;
    }

    .project-card {
        align-items: flex-start;
    }

    .project-card-tags {
        justify-content: flex-start;
    }
}

/* 底部 */
.card-footer {
    margin-top: 12px;
    padding-top: 12px;
    border-top: 1px solid color-mix(in srgb, var(--spark-border), transparent 10%);
}

.default-toggle {
    display: flex;
    align-items: center;
    gap: 8px;
}

.default-toggle-text {
    display: flex;
    align-items: center;
}

.default-toggle-label {
    font-size: var(--spark-fs-base);
    color: var(--spark-text);
}

.auto-update-hint {
    font-size: var(--spark-fs-sm);
    color: var(--spark-text-muted);
    margin: 8px 0 0;
    padding-left: 0;
}
</style>
