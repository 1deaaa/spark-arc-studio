
import { ref, watch, onMounted, onBeforeUnmount } from 'vue';
import { useMessage } from 'naive-ui';
import {
    generateOutline,
    getOutline,
    saveOutline,
    fetchSynopsis
} from '../services/api';
import { getStyleProfile } from '../services/storyService';
import { fetchBeatSheet } from '../services/aiService';
import { useProjectStore } from '../components/stores/projectStore';
import bus from '../eventBus';
import { createStreamingTask, isAbortLikeError } from '@/utils/streamingRuntime';
import type { BeatSheetData, OutlineData } from '../services/aiContracts';

function getErrorMessage(error: unknown): string {
    if (error instanceof Error) return error.message;
    return String(error || '未知错误');
}

export function useStructureLogic() {
    const projectStore = useProjectStore();
    const message = useMessage();

    // Outline State
    const context = ref('');
    const guidance = ref('');
    const isLoading = ref(false);
    const currentOutline = ref<OutlineData | null>(null);
    const outlineHistoryRef = ref<{ refresh?: () => void } | null>(null);
    const chapterCount = ref(5);  // 默认5章
    const sceneCount = ref(3);    // 默认每章3场景
    const lengthType = ref('short'); // 默认短篇

    const lengthOptions = [
        { label: '短篇 (5章, 每章3场景)', value: 'short' },
        { label: '中篇 (10章, 每章4场景)', value: 'medium' },
        { label: '长篇 (20章, 每章5场景)', value: 'long' },
        { label: '不限 (由大模型决定)', value: 'unlimited' },
        { label: '自定义', value: 'custom' }
    ];

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
            if (outline) {
                currentOutline.value = outline;
            }
        } catch (e) {
            console.log('No existing outline found');
        }
    }

    async function handleGenerateOutline() {
        if (!projectStore.currentProject) return;

        if (!context.value && !guidance.value) {
            message.warning('请提供剧情上下文或导演意图');
            return;
        }

        isLoading.value = true;
        const task = createStreamingTask('outline', {
            text: '文案策划 正在规划故事结构...',
            canCancel: true,
        });
        try {
            // Fetch beat sheet from server
            let beatSheet: BeatSheetData | null = null;
            try {
                const bData = await fetchBeatSheet(projectStore.currentProject);
                if (bData && bData.beats && bData.beats.length > 0) {
                    beatSheet = bData;
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

            if (task.aborted) return;
            currentOutline.value = outline;
            message.success('大纲生成成功');
            outlineHistoryRef.value?.refresh?.();
        } catch (e: unknown) {
            if (isAbortLikeError(e)) {
                message.info('已取消生成');
                return;
            }
            message.error('生成大纲失败: ' + getErrorMessage(e));
        } finally {
            task.dispose();
            isLoading.value = false;
        }
    }

    function handleOutlineUpdate(newOutline: OutlineData | null) {
        currentOutline.value = newOutline;
    }

    async function handleSaveOutline(outline?: unknown) {
        try {
            const payload = (outline || currentOutline.value) as OutlineData | null;
            if (!payload) {
                message.warning('暂无可保存的大纲');
                return;
            }
            await saveOutline(projectStore.currentProject, payload, false);
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
            message.success('已存档到历史记录');
            outlineHistoryRef.value?.refresh?.();
        } catch (e: unknown) {
            message.error('存档失败: ' + getErrorMessage(e));
        }
    }

    function handleOutlineHistorySelect(item: { outline?: OutlineData | null }) {
        if (item?.outline) {
            currentOutline.value = item.outline;
        }
    }

    function handleOutlineRestore(outline: OutlineData | null) {
        currentOutline.value = outline;
        message.success('大纲已恢复');
    }

    async function handleOutlineRefresh() {
        await loadCurrentOutline();
        outlineHistoryRef.value?.refresh?.();
    }

    // --- 自动读取梗概到上下文 ---
    watch(() => projectStore.currentProject, async (newProject) => {
        if (newProject) {
            await loadCurrentOutline();

            // 仅加载“详细梗概”为上下文，不再回退灵感
            try {
                const syn = await fetchSynopsis(newProject);
                if (syn) {
                    if (typeof syn === 'string') {
                        context.value = syn;
                    } else if (typeof syn === 'object' && syn !== null && 'synopsis_text' in syn) {
                        const synopsisText = (syn as { synopsis_text?: unknown }).synopsis_text;
                        context.value = typeof synopsisText === 'string' ? synopsisText : '';
                    }
                }
            } catch (e) {
                console.warn('Failed to pre-load synopsis', e);
            }
        }
    }, { immediate: true });

    // 监听梗概页面发来的 adopt-synopsis 事件，更新上下文
    function handleAdoptSynopsis(payload: unknown) {
        const synopsisContext = payload && typeof payload === 'object' && 'context' in payload
            ? (payload as { context?: unknown }).context
            : null;
        if (synopsisContext) {
            context.value = String(synopsisContext);
        }
    }

    onMounted(() => {
        bus.on('adopt-synopsis', handleAdoptSynopsis);
        bus.on('outline-refresh', handleOutlineRefresh);
    });

    onBeforeUnmount(() => {
        bus.off('adopt-synopsis', handleAdoptSynopsis);
        bus.off('outline-refresh', handleOutlineRefresh);
    });

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
