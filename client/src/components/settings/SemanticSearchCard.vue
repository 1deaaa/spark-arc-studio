<template>
    <div class="settings-section">
        <div class="section-header">
            <h3>{{ t('components.semanticSearchCard.title') }}</h3>
        </div>
        <p class="section-desc">{{ t('components.semanticSearchCard.subtitle') }}</p>

        <div v-if="loading" class="loading-state">
            <SparkLoaderAnimation />
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

            <div v-if="isAdmin" class="local-embedding-bar">
                <div class="embedding-info">
                    <span class="dot" :class="localEmbeddingDotClass" />
                    <span class="embedding-label">{{ t('components.semanticSearchCard.localEmbedding') }}</span>
                    <span class="embedding-value">{{ localEmbeddingLabel }}</span>
                </div>
                <n-switch
                    :value="localEmbeddingSwitchOn"
                    :loading="togglingLocalEmbedding"
                    :disabled="!isAdmin || localEmbeddingEnabled === null"
                    size="small"
                    @update:value="handleLocalEmbeddingToggle"
                />
            </div>

            <div class="project-summary" v-if="projects.length > 0">
                <div class="summary-pill summary-pill-enabled">
                    <span class="summary-number">{{ semanticEnabledCount }}</span>
                    <span class="summary-label">{{ t('components.semanticSearchCard.summaryLabelSemantic') }}</span>
                </div>
                <div class="summary-pill summary-pill-graphrag">
                    <span class="summary-number">{{ graphragEnabledCount }}</span>
                    <span class="summary-label">{{ t('components.semanticSearchCard.summaryLabelGraphRAG') }}</span>
                </div>
                <div class="summary-pill summary-pill-total">
                    <span class="summary-number">{{ filteredProjects.length }}</span>
                    <span class="summary-label">{{ t('components.semanticSearchCard.visibleProjects') }}</span>
                </div>
            </div>

            <div class="project-toolbar" v-if="projects.length > 0">
                <!-- 隐藏诱饵输入框：吸收 Edge/Chromium 的自动填充行为（已知 Bug #468153, WontFix） -->
                <input
                    type="text"
                    name="prevent_autofill_username"
                    tabindex="-1"
                    autocomplete="off"
                    style="position:absolute;opacity:0;width:0;height:0;pointer-events:none;"
                />
                <input
                    type="password"
                    name="prevent_autofill_password"
                    tabindex="-1"
                    autocomplete="new-password"
                    style="position:absolute;opacity:0;width:0;height:0;pointer-events:none;"
                />
                <input
                    type="search"
                    v-model.trim="searchKeyword"
                    class="project-search"
                    :placeholder="t('components.semanticSearchCard.searchPlaceholder')"
                    autocomplete="off"
                    spellcheck="false"
                    data-1p-ignore
                    data-lpignore="true"
                />
            </div>

            <!-- 项目列表 -->
            <div v-if="projects.length > 0" class="project-list-shell">
                <div v-if="filteredProjects.length > 0" class="project-list">
                    <div v-for="proj in filteredProjects" :key="proj.projectName" class="project-card">
                        <div class="project-card-header">
                            <n-tooltip trigger="hover">
                                <template #trigger>
                                    <span class="project-name">{{ proj.projectName }}</span>
                                </template>
                                {{ proj.projectName }}
                            </n-tooltip>
                        </div>
                        <div class="project-card-rows">
                            <ProjectIndexRow
                                kind="semantic"
                                :label="t('components.semanticSearchCard.indexLabelSemantic')"
                                :enabled="proj.enabled"
                                :tags="getSemanticTags(proj)"
                                :refreshable="!isProjectBuilding(proj)"
                                :loading="proj._loading"
                                :refreshing="Boolean(proj._refreshing)"
                                :refresh-tooltip="t('components.semanticSearchCard.refreshTooltip')"
                                :refresh-disabled-tooltip="t('components.semanticSearchCard.refreshDisabledTooltip')"
                                :refresh-busy-tooltip="t('components.semanticSearchCard.refreshBusyTooltip')"
                                @toggle="(val) => handleToggleSemantic(proj, val)"
                                @refresh="() => handleRefreshSemantic(proj)"
                            />
                            <ProjectIndexRow
                                v-if="getGraphRAG(proj.projectName)"
                                kind="graphrag"
                                :label="t('components.semanticSearchCard.indexLabelGraphRAG')"
                                :enabled="getGraphRAG(proj.projectName)!.enabled"
                                :tags="getGraphRAGTags(getGraphRAG(proj.projectName)!)"
                                :refreshable="!isGraphRAGBuilding(getGraphRAG(proj.projectName)!)"
                                :loading="Boolean(getGraphRAG(proj.projectName)!._loading)"
                                :refreshing="Boolean(getGraphRAG(proj.projectName)!._refreshing)"
                                :refresh-tooltip="t('components.semanticSearchCard.graphragRefreshTooltip')"
                                :refresh-disabled-tooltip="t('components.semanticSearchCard.graphragRefreshDisabledTooltip')"
                                :refresh-busy-tooltip="t('components.semanticSearchCard.graphragRefreshBusyTooltip')"
                                @toggle="(val) => handleToggleGraphRAG(proj.projectName, val)"
                                @refresh="() => handleRefreshGraphRAG(proj.projectName)"
                            />
                        </div>
                    </div>
                </div>
                <n-empty v-else :description="t('components.semanticSearchCard.noSearchResults')" size="small" />
            </div>
            <n-empty v-else :description="t('components.semanticSearchCard.noProjects')" size="small" />

            <!-- 底部：默认启用 + 自动更新提示 -->
            <div class="card-footer">
                <div class="default-toggle-group">
                    <div class="default-toggle">
                        <n-switch
                            :value="defaultEnabledSemantic"
                            @update:value="handleDefaultSemanticToggle"
                            size="small"
                        />
                        <span class="default-toggle-label">{{ t('components.semanticSearchCard.defaultEnabledSemantic') }}</span>
                    </div>
                    <div class="default-toggle">
                        <n-switch
                            :value="defaultEnabledGraphRAG"
                            @update:value="handleDefaultGraphRAGToggle"
                            size="small"
                        />
                        <span class="default-toggle-label">{{ t('components.semanticSearchCard.defaultEnabledGraphRAG') }}</span>
                        <n-popover trigger="hover" placement="top" style="max-width: 320px;">
                            <template #trigger>
                                <n-icon :size="14" class="graphrag-fast-tip-icon" :aria-label="t('components.semanticSearchCard.graphragFastModelTipTitle')">
                                    <Info />
                                </n-icon>
                            </template>
                            <div class="graphrag-fast-tip">
                                <div class="graphrag-fast-tip-title">{{ t('components.semanticSearchCard.graphragFastModelTipTitle') }}</div>
                                <div class="graphrag-fast-tip-body">{{ t('components.semanticSearchCard.graphragFastModelTipBody') }}</div>
                            </div>
                        </n-popover>
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
import { NButton, NSwitch, NEmpty, NTooltip, NPopover, NIcon, useMessage, useDialog } from 'naive-ui';
import { Info } from '@lucide/vue';
import SparkLoaderAnimation from '../share/SparkLoaderAnimation.vue';
import ProjectIndexRow, { type IndexRowTag } from './ProjectIndexRow.vue';
import {
    getLocalEmbeddingErrorSummary,
    isLocalEmbeddingStartupActive,
    isLocalEmbeddingSwitchOn,
} from './localEmbeddingUi';
import {
    fetchSemanticSearchStatus,
    enableSemanticSearch,
    disableSemanticSearch,
    refreshSemanticSearchProject,
    testSemanticEmbedding,
    setSemanticSearchDefaults,
    fetchLocalEmbeddingStatus,
    setLocalEmbeddingEnabled,
    fetchGraphRAGStatus,
    enableGraphRAG,
    disableGraphRAG,
    refreshGraphRAGProject,
    setGraphRAGDefaults,
    type SemanticSearchProjectStatus,
    type GraphRAGProjectStatus,
    type LocalEmbeddingStatus,
} from '../../services/api';
import { getUserInfo } from '../../services/authService';

const { t } = useI18n();
const message = useMessage();
const dialog = useDialog();

type SemanticRow = SemanticSearchProjectStatus & { _loading?: boolean; _refreshing?: boolean };
type GraphRAGRow = GraphRAGProjectStatus & { _loading?: boolean; _refreshing?: boolean };

const BUILDING_STATUSES = new Set(['queued', 'building']);
const POLL_INTERVAL_MS = 2500;

const loading = ref(true);
const testingEmbedding = ref(false);
const togglingLocalEmbedding = ref(false);
const embeddingReady = ref<boolean | null>(null);
const embeddingModelName = ref('');
const isAdmin = ref(false);
const localEmbeddingStatus = ref<LocalEmbeddingStatus | null>(null);
const localEmbeddingEnabled = ref<boolean | null>(null);
const defaultEnabledSemantic = ref(false);
const defaultEnabledGraphRAG = ref(false);
const searchKeyword = ref('');
const projects = ref<SemanticRow[]>([]);
const graphragMap = ref<Map<string, GraphRAGRow>>(new Map());
let pollingTimer: number | null = null;

const semanticEnabledCount = computed(() => projects.value.filter((project) => project.enabled).length);
const graphragEnabledCount = computed(() => {
    let count = 0;
    graphragMap.value.forEach((row) => {
        if (row.enabled) count += 1;
    });
    return count;
});
const filteredProjects = computed(() => {
    const keyword = searchKeyword.value.trim().toLowerCase();
    if (!keyword) {
        return projects.value;
    }
    return projects.value.filter((project) => project.projectName.toLowerCase().includes(keyword));
});

const localEmbeddingLabel = computed(() => {
    const status = localEmbeddingStatus.value;
    if (!status) {
        return t('components.semanticSearchCard.localEmbeddingUnknown');
    }
    if (status.alive) {
        return t('components.semanticSearchCard.localEmbeddingAlive', { url: status.base_url || '' });
    }
    const startup = status.startup;
    if (isLocalEmbeddingStartupActive(status)) {
        const progress = typeof startup?.progress === 'number' ? `${startup.progress}%` : '';
        return [startup?.message || t('components.semanticSearchCard.localEmbeddingStarting'), progress].filter(Boolean).join(' ');
    }
    const errorSummary = getLocalEmbeddingErrorSummary(
        status,
        t('components.semanticSearchCard.localEmbeddingStartFailed'),
    );
    if (errorSummary) {
        return errorSummary;
    }
    if (status.running) {
        return t('components.semanticSearchCard.localEmbeddingStarting');
    }
    if (!status.configured) {
        return t('components.semanticSearchCard.localEmbeddingNotConfigured');
    }
    return t('components.semanticSearchCard.localEmbeddingStopped');
});

const localEmbeddingSwitchOn = computed(() => isLocalEmbeddingSwitchOn(localEmbeddingEnabled.value));
const localEmbeddingDotClass = computed(() => {
    if (localEmbeddingStatus.value?.alive) {
        return 'dot-ok';
    }
    if (localEmbeddingStatus.value?.running || isLocalEmbeddingStartupActive(localEmbeddingStatus.value)) {
        return 'dot-warn';
    }
    return 'dot-off';
});

function getGraphRAG(projectName: string): GraphRAGRow | undefined {
    return graphragMap.value.get(projectName);
}

function clearStatusPolling() {
    if (pollingTimer !== null && typeof window !== 'undefined') {
        window.clearTimeout(pollingTimer);
    }
    pollingTimer = null;
}

function isProjectBuilding(project: SemanticSearchProjectStatus) {
    return BUILDING_STATUSES.has(project.buildState.status);
}

function isGraphRAGBuilding(project: GraphRAGProjectStatus) {
    return BUILDING_STATUSES.has(project.buildState.status);
}

function hasAnyBuilding(): boolean {
    if (projects.value.some((p) => isProjectBuilding(p))) {
        return true;
    }
    let busy = false;
    graphragMap.value.forEach((row) => {
        if (isGraphRAGBuilding(row)) busy = true;
    });
    if (isAdmin.value && (localEmbeddingStatus.value?.running || isLocalEmbeddingStartupActive(localEmbeddingStatus.value))) {
        busy = true;
    }
    return busy;
}

function truncateText(text: string, maxLength = 42) {
    if (text.length <= maxLength) {
        return text;
    }
    return `${text.slice(0, maxLength - 1)}…`;
}

// 语义索引：把后端 build_state 翻译成可读的状态 pill
function getSemanticTags(project: SemanticSearchProjectStatus): IndexRowTag[] {
    const buildState = project.buildState;
    if (buildState.status === 'error') {
        const tags: IndexRowTag[] = [
            { key: 'status', label: t('components.semanticSearchCard.statusError'), tone: 'error' },
        ];
        if (buildState.error) {
            tags.push({
                key: 'error-detail',
                label: truncateText(buildState.error),
                tone: 'error',
                title: buildState.error,
            });
        }
        return tags;
    }

    if (BUILDING_STATUSES.has(buildState.status)) {
        const progress = buildState.progress;
        const totalChunks = progress.total_chunks || 0;
        const embedded = progress.embedded_chunks || 0;
        const totalFiles = progress.total_files || 0;
        const doneFiles = progress.done_files || 0;
        const detail = totalChunks > 0
            ? t('components.semanticSearchCard.statusBuildingDetailChunks', { done: embedded, total: totalChunks })
            : t('components.semanticSearchCard.statusBuildingDetailFiles', { done: doneFiles, total: totalFiles });
        return [
            { key: 'status', label: t('components.semanticSearchCard.statusBuilding'), tone: 'info' },
            { key: 'progress', label: detail, tone: 'info', title: detail },
        ];
    }

    if (!project.indexExists || buildState.status === 'not_built') {
        if (!project.enabled) {
            return [
                { key: 'status', label: t('components.semanticSearchCard.statusDisabled'), tone: 'muted' },
            ];
        }
        return [
            { key: 'status', label: t('components.semanticSearchCard.statusPending'), tone: 'warning' },
        ];
    }

    if (project.needsRebuild || buildState.status === 'stale') {
        return [
            { key: 'status', label: t('components.semanticSearchCard.statusPendingUpdate'), tone: 'warning' },
        ];
    }

    return [
        { key: 'status', label: t('components.semanticSearchCard.statusReady'), tone: 'success' },
    ];
}

// 知识图谱：把后端 build_state 翻译成可读的状态 pill
function getGraphRAGTags(project: GraphRAGProjectStatus): IndexRowTag[] {
    const buildState = project.buildState;
    const stage = (buildState.stage || '').toLowerCase();
    const progress = buildState.progress;

    if (buildState.status === 'error') {
        const tags: IndexRowTag[] = [
            { key: 'status', label: t('components.semanticSearchCard.statusError'), tone: 'error' },
        ];
        if (buildState.error) {
            tags.push({
                key: 'error-detail',
                label: truncateText(buildState.error),
                tone: 'error',
                title: buildState.error,
            });
        }
        return tags;
    }

    if (BUILDING_STATUSES.has(buildState.status)) {
        let stageLabel = t('components.semanticSearchCard.graphragStageBuilding');
        if (stage === 'prepare' || stage === 'queued') {
            stageLabel = t('components.semanticSearchCard.graphragStagePrepare');
        } else if (stage === 'splitting') {
            stageLabel = t('components.semanticSearchCard.graphragStageSplitting');
        } else if (stage === 'extracting') {
            stageLabel = t('components.semanticSearchCard.graphragStageExtracting');
        } else if (stage === 'persisting') {
            stageLabel = t('components.semanticSearchCard.graphragStagePersisting');
        }
        const detail = (progress.total_chunks || 0) > 0
            ? t('components.semanticSearchCard.graphragProgressChunks', {
                done: progress.done_chunks || 0,
                total: progress.total_chunks || 0,
                triplets: progress.triplets_collected || 0,
            })
            : t('components.semanticSearchCard.graphragProgressIdle');
        return [
            { key: 'status', label: stageLabel, tone: 'info' },
            { key: 'progress', label: detail, tone: 'info', title: detail },
        ];
    }

    if (!project.graphReady || buildState.status === 'not_built') {
        if (!project.enabled) {
            return [
                { key: 'status', label: t('components.semanticSearchCard.statusDisabled'), tone: 'muted' },
            ];
        }
        return [
            { key: 'status', label: t('components.semanticSearchCard.statusPending'), tone: 'warning' },
        ];
    }

    if (project.needsRebuild || buildState.status === 'stale') {
        return [
            { key: 'status', label: t('components.semanticSearchCard.statusPendingUpdate'), tone: 'warning' },
        ];
    }

    const summary = t('components.semanticSearchCard.graphragSummary', {
        nodes: project.metadata.nodes || 0,
        edges: project.metadata.edges || 0,
    });
    return [
        { key: 'status', label: t('components.semanticSearchCard.statusReady'), tone: 'success' },
        { key: 'summary', label: summary, tone: 'success', title: summary },
    ];
}

function syncStatusPolling() {
    clearStatusPolling();
    if (typeof window === 'undefined') {
        return;
    }
    if (!hasAnyBuilding()) {
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
        const [semanticStatus, graphragStatus, localStatus] = await Promise.all([
            fetchSemanticSearchStatus(),
            fetchGraphRAGStatus(),
            isAdmin.value ? fetchLocalEmbeddingStatus().catch(() => null) : Promise.resolve(null),
        ]);

        embeddingReady.value = semanticStatus.embedding_ready;
        embeddingModelName.value = semanticStatus.embedding_model_name || '';
        defaultEnabledSemantic.value = semanticStatus.default_enabled ?? false;
        defaultEnabledGraphRAG.value = graphragStatus.default_enabled ?? false;
        localEmbeddingStatus.value = localStatus?.status ?? null;
        if (localStatus) {
            localEmbeddingEnabled.value = localStatus.enabled === true;
        }

        const semanticLoadingMap = new Map(projects.value.map((project) => [project.projectName, Boolean(project._loading)]));
        const semanticRefreshingMap = new Map(projects.value.map((project) => [project.projectName, Boolean(project._refreshing)]));
        projects.value = semanticStatus.projects.map((project) => ({
            ...project,
            _loading: semanticLoadingMap.get(project.projectName) ?? false,
            _refreshing: semanticRefreshingMap.get(project.projectName) ?? false,
        }));

        const previousMap = graphragMap.value;
        const nextMap = new Map<string, GraphRAGRow>();
        for (const project of graphragStatus.projects) {
            const prev = previousMap.get(project.projectName);
            nextMap.set(project.projectName, {
                ...project,
                _loading: prev?._loading ?? false,
                _refreshing: prev?._refreshing ?? false,
            });
        }
        graphragMap.value = nextMap;
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

async function handleToggleSemantic(proj: SemanticRow, enabled: boolean) {
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
        const target = projects.value.find((project) => project.projectName === proj.projectName);
        if (target) {
            target._loading = false;
        } else {
            proj._loading = false;
        }
        syncStatusPolling();
    }
}

async function handleRefreshSemantic(proj: SemanticRow) {
    if (!proj.enabled) {
        message.warning(t('components.semanticSearchCard.refreshDisabledTooltip'));
        return;
    }
    if (proj._refreshing || isProjectBuilding(proj)) {
        return;
    }
    proj._refreshing = true;
    try {
        const result = await refreshSemanticSearchProject(proj.projectName);
        proj.buildState = result.buildState;
        proj.indexExists = result.indexExists;
        proj.needsRebuild = result.needsRebuild;
        if (result.triggered) {
            message.success(t('components.semanticSearchCard.refreshTriggered', { name: proj.projectName }));
        } else {
            message.info(t('components.semanticSearchCard.refreshUpToDate', { name: proj.projectName }));
        }
        await loadData({ silent: true });
    } catch (e: unknown) {
        const msg = e instanceof Error ? e.message : String(e);
        message.error(t('components.semanticSearchCard.refreshFailed', { reason: msg }));
    } finally {
        const target = projects.value.find((project) => project.projectName === proj.projectName);
        if (target) {
            target._refreshing = false;
        } else {
            proj._refreshing = false;
        }
        syncStatusPolling();
    }
}

async function handleToggleGraphRAG(projectName: string, enabled: boolean) {
    const row = graphragMap.value.get(projectName);
    if (!row) return;
    row._loading = true;
    try {
        if (enabled) {
            const result = await enableGraphRAG(projectName);
            row.enabled = true;
            row.buildState = result.buildState;
            row.graphReady = result.graphReady;
            row.metadataReady = result.metadataReady;
            row.needsRebuild = result.needsRebuild;
            row.metadata = result.metadata;
            message.success(t('components.semanticSearchCard.graphragEnableSuccess', { name: projectName }));
        } else {
            const result = await disableGraphRAG(projectName);
            row.enabled = false;
            row.buildState = result.buildState;
            row.graphReady = result.graphReady;
            row.metadataReady = result.metadataReady;
            row.needsRebuild = result.needsRebuild;
            row.metadata = result.metadata;
            message.success(t('components.semanticSearchCard.graphragDisableSuccess', { name: projectName }));
        }
        await loadData({ silent: true });
    } catch (e: unknown) {
        const msg = e instanceof Error ? e.message : String(e);
        if (enabled) {
            dialog.error({
                title: t('components.semanticSearchCard.graphragEnableFailed'),
                content: msg,
                positiveText: t('common.confirm'),
            });
            row.enabled = false;
        } else {
            message.error(msg);
        }
    } finally {
        const target = graphragMap.value.get(projectName);
        if (target) {
            target._loading = false;
        }
        syncStatusPolling();
    }
}

async function handleRefreshGraphRAG(projectName: string) {
    const row = graphragMap.value.get(projectName);
    if (!row) return;
    if (!row.enabled) {
        message.warning(t('components.semanticSearchCard.graphragRefreshDisabledTooltip'));
        return;
    }
    if (row._refreshing || isGraphRAGBuilding(row)) {
        return;
    }
    row._refreshing = true;
    try {
        const result = await refreshGraphRAGProject(projectName);
        row.buildState = result.buildState;
        row.graphReady = result.graphReady;
        row.metadataReady = result.metadataReady;
        row.needsRebuild = result.needsRebuild;
        row.metadata = result.metadata;
        if (result.triggered) {
            message.success(t('components.semanticSearchCard.graphragRefreshTriggered', { name: projectName }));
        } else {
            message.info(t('components.semanticSearchCard.graphragRefreshUpToDate', { name: projectName }));
        }
        await loadData({ silent: true });
    } catch (e: unknown) {
        const msg = e instanceof Error ? e.message : String(e);
        message.error(t('components.semanticSearchCard.graphragRefreshFailed', { reason: msg }));
    } finally {
        const target = graphragMap.value.get(projectName);
        if (target) {
            target._refreshing = false;
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

async function handleLocalEmbeddingToggle(enabled: boolean) {
    if (!isAdmin.value) {
        message.warning(t('components.semanticSearchCard.localEmbeddingAdminOnly'));
        return;
    }
    if (enabled) {
        const confirmed = await confirmLocalEmbeddingEnable();
        if (!confirmed) {
            return;
        }
    }
    togglingLocalEmbedding.value = true;
    try {
        const result = await setLocalEmbeddingEnabled(enabled);
        localEmbeddingStatus.value = result.status;
        localEmbeddingEnabled.value = result.enabled === true;
        message.success(
            enabled
                ? t('components.semanticSearchCard.localEmbeddingStartTriggered')
                : t('components.semanticSearchCard.localEmbeddingStoppedSuccess'),
        );
    } catch (e: unknown) {
        const msg = e instanceof Error ? e.message : String(e);
        dialog.error({
            title: t('components.semanticSearchCard.localEmbeddingToggleFailed'),
            content: msg,
            positiveText: t('common.confirm'),
        });
    } finally {
        togglingLocalEmbedding.value = false;
        await loadData({ silent: true });
        syncStatusPolling();
    }
}

function confirmLocalEmbeddingEnable(): Promise<boolean> {
    return new Promise((resolve) => {
        dialog.warning({
            title: t('components.semanticSearchCard.localEmbeddingEnableConfirmTitle'),
            content: t('components.semanticSearchCard.localEmbeddingEnableConfirmContent'),
            positiveText: t('components.semanticSearchCard.localEmbeddingEnableConfirmPositive'),
            negativeText: t('common.cancel'),
            onPositiveClick: () => resolve(true),
            onNegativeClick: () => resolve(false),
            onClose: () => resolve(false),
            onEsc: () => resolve(false),
            onMaskClick: () => resolve(false),
        });
    });
}

async function handleDefaultSemanticToggle(val: boolean) {
    try {
        const result = await setSemanticSearchDefaults(val);
        defaultEnabledSemantic.value = result.default_enabled;
    } catch (e: unknown) {
        const msg = e instanceof Error ? e.message : String(e);
        message.error(msg);
    }
}

async function handleDefaultGraphRAGToggle(val: boolean) {
    try {
        const result = await setGraphRAGDefaults(val);
        defaultEnabledGraphRAG.value = result.default_enabled;
    } catch (e: unknown) {
        const msg = e instanceof Error ? e.message : String(e);
        message.error(msg);
    }
}

onMounted(async () => {
    try {
        const user = await getUserInfo();
        isAdmin.value = Boolean(user?.is_admin);
    } catch {
        isAdmin.value = false;
    }
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
    margin-top: -8px;
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

.local-embedding-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding: 8px 0 10px;
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

.summary-pill-graphrag {
    background: color-mix(in srgb, #8b5cf6 14%, var(--spark-panel-bg));
    color: #6d28d9;
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
    grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
    gap: 8px;
    max-height: 360px;
    overflow: auto;
    padding-right: 2px;
}

.project-card {
    display: flex;
    flex-direction: column;
    gap: 6px;
    padding: 10px 12px;
    border: 1px solid color-mix(in srgb, var(--spark-border), transparent 15%);
    border-radius: 10px;
    background: var(--spark-panel-bg);
}

.project-card-header {
    display: flex;
    align-items: center;
    gap: 6px;
}

.project-card-rows {
    display: flex;
    flex-direction: column;
    gap: 0;
}

.project-name {
    font-size: var(--spark-fs-base);
    color: var(--spark-text);
    font-weight: 600;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
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
}

/* 底部 */
.card-footer {
    margin-top: 12px;
    padding-top: 12px;
    border-top: 1px solid color-mix(in srgb, var(--spark-border), transparent 10%);
}

.default-toggle-group {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 16px;
}

.default-toggle {
    display: flex;
    align-items: center;
    gap: 8px;
}

.default-toggle-label {
    font-size: var(--spark-fs-base);
    color: var(--spark-text);
}

.graphrag-fast-tip-icon {
    color: var(--spark-text-muted);
    cursor: help;
    transition: color 0.15s ease;
}

.graphrag-fast-tip-icon:hover {
    color: var(--spark-primary);
}

.graphrag-fast-tip {
    max-width: 280px;
    line-height: 1.5;
}

.graphrag-fast-tip-title {
    font-weight: 600;
    margin-bottom: 4px;
    color: var(--spark-text);
}

.graphrag-fast-tip-body {
    font-size: var(--spark-fs-sm);
    color: var(--spark-text-muted);
}

.auto-update-hint {
    font-size: var(--spark-fs-sm);
    color: var(--spark-text-muted);
    margin: 8px 0 0;
    padding-left: 0;
    white-space: pre-line;
}
</style>
