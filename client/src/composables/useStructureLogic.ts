
import { computed, ref, watch, onMounted, onBeforeUnmount } from 'vue';
import { useMessage, useDialog } from 'naive-ui';
import {
    generateOutline,
    getOutline,
    saveOutline,
    fetchSynopsis,
    fetchWithAuth,
} from '../services/api';
import { getStyleProfile } from '../services/storyService';
import { fetchBeatSheet } from '../services/aiService';
import { parseOutlineMarkup, parseSynopsisMarkup } from '../utils/markupSerializer';
import { useProjectStore } from '../components/stores/projectStore';
import bus from '../eventBus';
import { i18n } from '@/i18n';
import { createStreamingTask, isAbortLikeError } from '@/utils/streamingRuntime';
import type { OutlineData } from '../services/aiContracts';
import { buildCreativeCacheKey, isCreativeCacheEqual, loadCreativeCache, saveCreativeCache } from '@/utils/creativeLocalCache';
import { createAutoSaveScheduler } from '@/utils/autoSaveScheduler';

type StructureAdoptionPayload = {
    projectName?: string;
    context?: string;
    guidance?: string;
    lengthHint?: unknown;
    estimatedChapters?: unknown;
    autoGenerateOutline?: boolean;
    [key: string]: unknown;
};

type StructureCacheSnapshot = {
    context: string;
    guidance: string;
    chapterCount: number;
    sceneCount: number;
    lengthType: string;
    currentOutline: OutlineData | null;
};

function getErrorMessage(error: unknown): string {
    if (error instanceof Error) return error.message;
    return String(error || '未知错误');
}

const DEFAULT_CHAPTER_COUNT = 5;
const DEFAULT_SCENE_COUNT = 3;
const DEFAULT_LENGTH_TYPE = 'short';

function resolveLengthTypeFromHint(raw: unknown): string | null {
    const value = String(raw || '').trim();
    if (!value) return null;
    if (value.includes('短')) return 'short';
    if (value.includes('中')) return 'medium';
    if (value.includes('长')) return 'long';
    if (value.includes('不限')) return 'unlimited';
    const lower = value.toLowerCase();
    if (lower.includes('short')) return 'short';
    if (lower.includes('medium')) return 'medium';
    if (lower.includes('long')) return 'long';
    if (lower.includes('unlimit')) return 'unlimited';
    return null;
}

function resolveEstimatedChapterCount(raw: unknown): number | null {
    const match = String(raw || '').match(/\d+/);
    if (!match) return null;
    const count = Number(match[0]);
    return Number.isFinite(count) && count > 0 ? Math.round(count) : null;
}

export function useStructureLogic() {
    const projectStore = useProjectStore();
    const message = useMessage();
    const dialog = useDialog();

    // Outline State
    const context = ref('');
    const guidance = ref('');
    const isLoading = ref(false);
    const currentOutline = ref<OutlineData | null>(null);
    const outlineHistoryRef = ref<{ refresh?: () => void } | null>(null);
    const chapterCount = ref(DEFAULT_CHAPTER_COUNT);
    const sceneCount = ref(DEFAULT_SCENE_COUNT);
    const lengthType = ref(DEFAULT_LENGTH_TYPE);

    const lengthOptions = computed(() => [
        { label: i18n.global.t('views.structure.lengthOptions.short'), value: 'short' },
        { label: i18n.global.t('views.structure.lengthOptions.medium'), value: 'medium' },
        { label: i18n.global.t('views.structure.lengthOptions.long'), value: 'long' },
        { label: i18n.global.t('views.structure.lengthOptions.unlimited'), value: 'unlimited' },
        { label: i18n.global.t('views.structure.lengthOptions.custom'), value: 'custom' }
    ]);

    function buildStructureCacheKey() {
        return buildCreativeCacheKey('structure-workbench', projectStore.currentProject);
    }

    function getStructureSnapshot(): StructureCacheSnapshot {
        return {
            context: context.value,
            guidance: guidance.value,
            chapterCount: chapterCount.value,
            sceneCount: sceneCount.value,
            lengthType: lengthType.value,
            currentOutline: currentOutline.value ? JSON.parse(JSON.stringify(currentOutline.value)) as OutlineData : null,
        };
    }

    function applyStructureSnapshot(snapshot: StructureCacheSnapshot | null | undefined) {
        if (!snapshot) return;
        context.value = snapshot.context || '';
        guidance.value = snapshot.guidance || '';
        chapterCount.value = Number.isFinite(Number(snapshot.chapterCount)) ? Number(snapshot.chapterCount) : DEFAULT_CHAPTER_COUNT;
        sceneCount.value = Number.isFinite(Number(snapshot.sceneCount)) ? Number(snapshot.sceneCount) : DEFAULT_SCENE_COUNT;
        lengthType.value = snapshot.lengthType || DEFAULT_LENGTH_TYPE;
        currentOutline.value = snapshot.currentOutline ? JSON.parse(JSON.stringify(snapshot.currentOutline)) as OutlineData : null;
    }

    function saveStructureSnapshot() {
        if (!projectStore.currentProject) return;
        saveCreativeCache(buildStructureCacheKey(), getStructureSnapshot());
    }

    function isStructureLengthPristine() {
        return (
            lengthType.value === DEFAULT_LENGTH_TYPE
            && chapterCount.value === DEFAULT_CHAPTER_COUNT
            && sceneCount.value === DEFAULT_SCENE_COUNT
        );
    }

    function applyLengthHintIfPristine(raw: unknown) {
        const nextLengthType = resolveLengthTypeFromHint(raw);
        if (!nextLengthType || !isStructureLengthPristine()) return;
        lengthType.value = nextLengthType;
    }

    async function loadProjectLengthHint(projectName: string) {
        try {
            const response = await fetchWithAuth(`/api/project/story-tags?projectName=${encodeURIComponent(projectName)}`);
            if (!response.ok) return null;
            const data = await response.json();
            return data?.success ? data?.tags?.length_hint || null : null;
        } catch (error) {
            console.warn('加载结构页作品规模偏好失败:', error);
            return null;
        }
    }

    watch(lengthType, (newVal) => {
        if (newVal === 'short') {
            chapterCount.value = DEFAULT_CHAPTER_COUNT;
            sceneCount.value = DEFAULT_SCENE_COUNT;
        } else if (newVal === 'medium') {
            chapterCount.value = 10;
            sceneCount.value = 4;
        } else if (newVal === 'long') {
            chapterCount.value = 20;
            sceneCount.value = 5;
        } else if (newVal === 'unlimited') {
            chapterCount.value = 0;
            sceneCount.value = 0;
        }
    });

    async function loadCurrentOutline() {
        if (!projectStore.currentProject) return;

        try {
            const outline = await getOutline(projectStore.currentProject);
            if (outline && !isCreativeCacheEqual(currentOutline.value, outline)) {
                currentOutline.value = outline;
            }
            saveStructureSnapshot();
        } catch (e) {
            console.log('No existing outline found');
        }
    }

    async function handleGenerateOutline(options: { skipOverwriteConfirm?: boolean } = {}) {
        if (!projectStore.currentProject) return false;

        if (!context.value && !guidance.value) {
            message.warning('请提供剧情上下文或导演意图');
            return false;
        }

        if (
            currentOutline.value
            && Array.isArray(currentOutline.value.nodes)
            && currentOutline.value.nodes.length > 0
            && !options.skipOverwriteConfirm
        ) {
            const shouldOverwrite = await new Promise<boolean>((resolve) => {
                dialog.warning({
                    title: '确认覆盖',
                    content: '当前大纲已有内容，继续生成将覆盖现有大纲。是否继续？',
                    positiveText: '覆盖并生成',
                    negativeText: '取消',
                    onPositiveClick: () => resolve(true),
                    onNegativeClick: () => resolve(false),
                    onClose: () => resolve(false),
                });
            });
            if (!shouldOverwrite) return false;
        }

        isLoading.value = true;
        const task = createStreamingTask('outline', {
            text: '文案策划 正在规划故事结构...',
            canCancel: true,
        });
        try {
            // Fetch beat sheet from server (returns Markup text)
            let beatSheet: string | null = null;
            try {
                const bMarkup = await fetchBeatSheet(projectStore.currentProject);
                if (bMarkup && bMarkup.trim()) {
                    beatSheet = bMarkup;
                }
            } catch (e: unknown) {
                console.warn('Failed to fetch beat sheet', e);
            }

            const styleProfile = await getStyleProfile(projectStore.currentProject, null);

            const outline = await generateOutline(
                projectStore.currentProject,
                context.value,
                guidance.value,
                {
                    chapterCount: lengthType.value === 'unlimited' ? "不限" : chapterCount.value,
                    sceneCountPerChapter: lengthType.value === 'unlimited' ? "不限" : sceneCount.value,
                    beatSheet: beatSheet,
                    styleProfile,
                    signal: task.signal,
                    onChunk: (chunk) => task.push(chunk, '文案策划 正在规划故事结构...')
                }
            );

            if (task.aborted) return false;
            currentOutline.value = outline;
            saveStructureSnapshot();
            message.success('大纲生成成功');
            outlineHistoryRef.value?.refresh?.();
            return true;
        } catch (e: unknown) {
            if (isAbortLikeError(e)) {
                message.info('已取消生成');
                return false;
            }
            message.error('生成大纲失败: ' + getErrorMessage(e));
            return false;
        } finally {
            task.dispose();
            isLoading.value = false;
        }
    }

    const outlineSaveScheduler = createAutoSaveScheduler<{
        projectName: string;
        outline: OutlineData;
    }>(async payload => {
        await saveOutline(payload.projectName, payload.outline, false);
    }, {
        delay: 800,
        maxWait: 5000,
        onError: error => message.error('自动保存失败: ' + getErrorMessage(error)),
    });

    function handleOutlineUpdate(newOutline: OutlineData | null) {
        currentOutline.value = newOutline;
        saveStructureSnapshot();
        if (newOutline && projectStore.currentProject) {
            outlineSaveScheduler.schedule({
                projectName: projectStore.currentProject,
                outline: JSON.parse(JSON.stringify(newOutline)),
            });
        }
    }

    async function handleSaveToHistory(outline: OutlineData | null) {
        try {
            if (!outline) {
                message.warning('暂无可存档的大纲');
                return;
            }
            await saveOutline(projectStore.currentProject, outline, true);
            saveStructureSnapshot();
            message.success('已存档到历史记录');
            outlineHistoryRef.value?.refresh?.();
        } catch (e: unknown) {
            message.error('存档失败: ' + getErrorMessage(e));
        }
    }

    function handleOutlineHistorySelect(item: { markup?: string; outline?: OutlineData | null }) {
        // 优先使用 markup 字段（新格式），回退到 outline 字段（旧格式）
        if (item?.markup) {
            const parsed = parseOutlineMarkup(item.markup);
            if (parsed.nodes.length > 0) {
                currentOutline.value = parsed;
                saveStructureSnapshot();
            }
        } else if (item?.outline) {
            currentOutline.value = item.outline;
            saveStructureSnapshot();
        }
    }

    function handleOutlineRestore(outline: OutlineData | null) {
        currentOutline.value = outline;
        saveStructureSnapshot();
        message.success('大纲已恢复');
    }

    async function handleOutlineRefresh() {
        await loadCurrentOutline();
        outlineHistoryRef.value?.refresh?.();
    }

    // --- 自动读取梗概到上下文 ---
    watch(() => projectStore.currentProject, async (newProject) => {
        // 切换项目时先清空所有旧状态，防止残留
        context.value = '';
        guidance.value = '';
        currentOutline.value = null;
        lengthType.value = DEFAULT_LENGTH_TYPE;
        chapterCount.value = DEFAULT_CHAPTER_COUNT;
        sceneCount.value = DEFAULT_SCENE_COUNT;

        if (newProject) {
            applyStructureSnapshot(loadCreativeCache<StructureCacheSnapshot>(buildStructureCacheKey()));
            applyLengthHintIfPristine(await loadProjectLengthHint(newProject));
            await loadCurrentOutline();

            // 仅加载“详细梗概”为上下文，不再回退灵感
            try {
                const synMarkup = await fetchSynopsis(newProject);
                if (synMarkup && synMarkup.trim() && !context.value.trim()) {
                    // fetchSynopsis 现在返回 Markup 文本，直接用作上下文
                    context.value = synMarkup;
                }
                if (synMarkup && synMarkup.trim()) {
                    const synopsisMeta = parseSynopsisMarkup(synMarkup);
                    const estimatedChapters = resolveEstimatedChapterCount(synopsisMeta.estimated_chapters);
                    if (estimatedChapters && isStructureLengthPristine()) {
                        lengthType.value = 'custom';
                        chapterCount.value = estimatedChapters;
                    }
                }
            } catch (e) {
                console.warn('Failed to pre-load synopsis', e);
            }
            saveStructureSnapshot();
            void consumePendingStructureAdoption();
        }
    }, { immediate: true });

    // 监听梗概页面发来的 adopt-synopsis 事件，更新上下文
    function handleAdoptSynopsis(payload: unknown) {
        const data = payload && typeof payload === 'object'
            ? payload as StructureAdoptionPayload
            : null;
        if (data?.projectName && data.projectName !== projectStore.currentProject) return;
        const synopsisContext = data?.context ?? null;
        if (synopsisContext) {
            context.value = String(synopsisContext);
        }
        if (typeof data?.guidance === 'string') {
            guidance.value = data.guidance;
        }
        applyLengthHintIfPristine(data?.lengthHint);
        const estimatedChapters = resolveEstimatedChapterCount(data?.estimatedChapters);
        if (estimatedChapters && isStructureLengthPristine()) {
            lengthType.value = 'custom';
            chapterCount.value = estimatedChapters;
        }
        saveStructureSnapshot();
    }

    async function consumePendingStructureAdoption() {
        const pending = projectStore.pendingStructureAdoption as StructureAdoptionPayload | null;
        if (!pending) return;
        if (pending.projectName && pending.projectName !== projectStore.currentProject) return;
        projectStore.clearPendingStructureAdoption();
        handleAdoptSynopsis(pending);
        if (pending.autoGenerateOutline) {
            await handleGenerateOutline({ skipOverwriteConfirm: true });
        }
    }

    onMounted(() => {
        bus.on('adopt-synopsis', handleAdoptSynopsis);
        bus.on('outline-refresh', handleOutlineRefresh);
        void consumePendingStructureAdoption();
    });

    onBeforeUnmount(() => {
        bus.off('adopt-synopsis', handleAdoptSynopsis);
        bus.off('outline-refresh', handleOutlineRefresh);
        void outlineSaveScheduler.flush();
    });

    watch(() => projectStore.pendingStructureAdoption, () => {
        void consumePendingStructureAdoption();
    });

    watch([context, guidance, chapterCount, sceneCount, lengthType], () => {
        saveStructureSnapshot();
    });

    watch(currentOutline, () => {
        saveStructureSnapshot();
    }, { deep: true });

    return {
        context,
        guidance,
        isLoading,
        currentOutline,
        outlineHistoryRef,
        chapterCount,
        sceneCount,
        lengthType,
        lengthOptions,
        handleGenerateOutline,
        handleOutlineUpdate,
        handleSaveToHistory,
        handleOutlineHistorySelect,
        handleOutlineRestore,
        projectStore
    };
}
