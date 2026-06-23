
import { computed, ref, watch, onMounted, onBeforeUnmount } from 'vue';
import { useMessage, useDialog } from 'naive-ui';
import {
    generateOutline,
    getOutline,
    saveOutline,
    fetchSynopsis
} from '../services/api';
import { getStyleProfile } from '../services/storyService';
import { fetchBeatSheet } from '../services/aiService';
import { parseOutlineMarkup } from '../utils/markupSerializer';
import { useProjectStore } from '../components/stores/projectStore';
import bus from '../eventBus';
import { i18n } from '@/i18n';
import { createStreamingTask, isAbortLikeError } from '@/utils/streamingRuntime';
import type { OutlineData } from '../services/aiContracts';
import { buildCreativeCacheKey, isCreativeCacheEqual, loadCreativeCache, saveCreativeCache } from '@/utils/creativeLocalCache';

type StructureAdoptionPayload = {
    projectName?: string;
    context?: string;
    guidance?: string;
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
    const chapterCount = ref(5);  // 默认5章
    const sceneCount = ref(3);    // 默认场景密度参考约3场/章
    const lengthType = ref('short'); // 默认短篇

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
        chapterCount.value = Number.isFinite(Number(snapshot.chapterCount)) ? Number(snapshot.chapterCount) : 5;
        sceneCount.value = Number.isFinite(Number(snapshot.sceneCount)) ? Number(snapshot.sceneCount) : 3;
        lengthType.value = snapshot.lengthType || 'short';
        currentOutline.value = snapshot.currentOutline ? JSON.parse(JSON.stringify(snapshot.currentOutline)) as OutlineData : null;
    }

    function saveStructureSnapshot() {
        if (!projectStore.currentProject) return;
        saveCreativeCache(buildStructureCacheKey(), getStructureSnapshot());
    }

    watch(lengthType, (newVal) => {
        if (newVal === 'short') {
            chapterCount.value = 5;
            sceneCount.value = 3;
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

    function handleOutlineUpdate(newOutline: OutlineData | null) {
        currentOutline.value = newOutline;
        saveStructureSnapshot();
    }

    async function handleSaveOutline(outline?: unknown) {
        try {
            const payload = (outline || currentOutline.value) as OutlineData | null;
            if (!payload) {
                message.warning('暂无可保存的大纲');
                return;
            }
            await saveOutline(projectStore.currentProject, payload, false);
            saveStructureSnapshot();
            message.success('大纲已保存');
        } catch (e: unknown) {
            message.error('保存失败: ' + getErrorMessage(e));
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
        lengthType.value = 'short';
        chapterCount.value = 5;
        sceneCount.value = 3;

        if (newProject) {
            applyStructureSnapshot(loadCreativeCache<StructureCacheSnapshot>(buildStructureCacheKey()));
            await loadCurrentOutline();

            // 仅加载“详细梗概”为上下文，不再回退灵感
            try {
                const synMarkup = await fetchSynopsis(newProject);
                if (synMarkup && synMarkup.trim() && !context.value.trim()) {
                    // fetchSynopsis 现在返回 Markup 文本，直接用作上下文
                    context.value = synMarkup;
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
        handleSaveOutline,
        handleSaveToHistory,
        handleOutlineHistorySelect,
        handleOutlineRestore,
        projectStore
    };
}
