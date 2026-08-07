
import { ref, reactive, onMounted, onBeforeUnmount, watch } from 'vue';
import { useMessage, useDialog } from 'naive-ui';
import {
    fetchSynopsis, saveSynopsis, generateSynopsis, generateSynopsisStream,
    fetchBeatSheet, saveBeatSheet, generateBeatSheet,
    getOutline
} from '../services/api';
import { getStyleProfile } from '../services/storyService';
import { useProjectStore } from '../components/stores/projectStore';
import { useViewStore } from '../components/stores/viewStore';
import bus from '../eventBus';
import { createStreamingTask, consumeTextReader, isAbortLikeError } from '@/utils/streamingRuntime';
import type { BeatSheetBeat, BeatSheetData } from '@/services/aiContracts';
import { parseSynopsisMarkup, parseBeatSheetMarkup, serializeSynopsisToMarkup, serializeBeatSheetToMarkup } from '../utils/markupSerializer';
import { buildInspirationGuidance, extractLoglineFromInspiration } from '@/utils/inspiration';
import { buildCreativeCacheKey, isCreativeCacheEqual, loadCreativeCache, saveCreativeCache } from '@/utils/creativeLocalCache';

type SynopsisData = {
    title: string;
    logline: string;
    synopsis_text: string;
    guidance: string;
    themes: string[];
    pacing_guide: string;
    narrative_pov: string;
    estimated_chapters: string;
    [key: string]: unknown;
};

type InspirationAdoptionPayload = {
    projectName?: string;
    logline?: string;
    inspiration?: string;
    lengthHint?: unknown;
    pov?: string;
    autoGenerateSynopsis?: boolean;
    autoGenerateBeats?: boolean;
    [key: string]: unknown;
};

type GenerateOptions = {
    skipOverwriteConfirm?: boolean;
};

type SynopsisCacheSnapshot = {
    synopsisData: SynopsisData;
    beatSheet: BeatSheetData;
};

function getErrorMessage(error: unknown) {
    if (error instanceof Error) return error.message;
    return String(error || '未知错误');
}

export function useSynopsisLogic() {
    const projectStore = useProjectStore();
    const viewStore = useViewStore();
    const message = useMessage();
    const dialog = useDialog();

    // --- 梗概数据 ---
    const synopsisData = reactive<SynopsisData>({
        title: '',
        logline: '',
        synopsis_text: '',
        guidance: '', // 将 guidance 移入 synopsisData 以便统一保存
        themes: [],
        pacing_guide: '',
        narrative_pov: '',
        estimated_chapters: '',
    });

    const isGenerating = ref(false);
    const isSaving = ref(false);
    const currentLengthHint = ref<unknown>(null); // 篇幅提示，来自世界页
    let suppressAutoSave = false;

    // --- 节拍表数据 ---
    const beatSheet = reactive<BeatSheetData>({
        beats: [] as BeatSheetBeat[],
        global_emotional_arc: ''
    });
    const isGeneratingBeats = ref(false);

    function buildSynopsisCacheKey() {
        return buildCreativeCacheKey('synopsis-workbench', projectStore.currentProject);
    }

    function getSynopsisSnapshot(): SynopsisCacheSnapshot {
        return {
            synopsisData: {
                title: synopsisData.title,
                logline: synopsisData.logline,
                synopsis_text: synopsisData.synopsis_text,
                guidance: synopsisData.guidance,
                themes: [...synopsisData.themes],
                pacing_guide: synopsisData.pacing_guide,
                narrative_pov: synopsisData.narrative_pov,
                estimated_chapters: synopsisData.estimated_chapters,
            },
            beatSheet: {
                beats: beatSheet.beats.map((beat) => ({ ...beat })),
                global_emotional_arc: beatSheet.global_emotional_arc,
            },
        };
    }

    function applySynopsisSnapshot(snapshot: SynopsisCacheSnapshot) {
        suppressAutoSave = true;
        synopsisData.title = snapshot.synopsisData.title || '';
        synopsisData.logline = snapshot.synopsisData.logline || '';
        synopsisData.synopsis_text = snapshot.synopsisData.synopsis_text || '';
        synopsisData.guidance = snapshot.synopsisData.guidance || '';
        synopsisData.themes = Array.isArray(snapshot.synopsisData.themes) ? [...snapshot.synopsisData.themes] : [];
        synopsisData.pacing_guide = snapshot.synopsisData.pacing_guide || '';
        synopsisData.narrative_pov = snapshot.synopsisData.narrative_pov || '';
        synopsisData.estimated_chapters = snapshot.synopsisData.estimated_chapters || '';
        beatSheet.beats = Array.isArray(snapshot.beatSheet.beats) ? snapshot.beatSheet.beats.map((beat) => ({ ...beat })) : [];
        beatSheet.global_emotional_arc = snapshot.beatSheet.global_emotional_arc || '';
        suppressAutoSave = false;
    }

    function resetSynopsisState() {
        applySynopsisSnapshot({
            synopsisData: {
                title: '',
                logline: '',
                synopsis_text: '',
                guidance: '',
                themes: [],
                pacing_guide: '',
                narrative_pov: '',
                estimated_chapters: '',
            },
            beatSheet: {
                beats: [],
                global_emotional_arc: '',
            },
        });
    }

    const tensionOptions = [
        { label: '低', value: 'Low' },
        { label: '中', value: 'Medium' },
        { label: '高', value: 'High' },
        { label: '潮', value: 'Climax' }
    ];

    function getTensionHeight(level: string) {
        switch (level) {
            case 'Low': return '30%';
            case 'Medium': return '50%';
            case 'High': return '80%';
            case 'Climax': return '100%';
            default: return '40%';
        }
    }

    function getBeatColor(goal: string) {
        const goals: Record<string, string> = {
            '恐惧': '#f5222d',
            '惊喜': '#faad14',
            '悲伤': '#1890ff',
            '兴奋': '#52c41a',
            '平静': '#eb2f96'
        };
        return goals[goal] || 'var(--spark-primary)';
    }

    // --- 通用逻辑 ---
    const handleAdoptInspiration = (payload: unknown) => {
        if (!payload || typeof payload !== 'object') return;
        const data = payload as InspirationAdoptionPayload;
        if (data.projectName && data.projectName !== projectStore.currentProject) return;
        if (data.logline && !synopsisData.logline.trim()) {
            synopsisData.logline = data.logline;
        }
        if (data.inspiration && !synopsisData.guidance.trim()) {
            synopsisData.guidance = buildInspirationGuidance(data.inspiration);
        }
        if (data.lengthHint && currentLengthHint.value == null) {
            currentLengthHint.value = data.lengthHint;
        }
        if (data.pov && !synopsisData.narrative_pov.trim()) {
            synopsisData.narrative_pov = data.pov as string;
        }
    };

    function applyBoundInspirationIfNeeded() {
        const boundInspiration = (projectStore.boundInspiration || '').trim();
        if (!boundInspiration) return;
        if (!synopsisData.logline.trim()) {
            synopsisData.logline = extractLoglineFromInspiration(boundInspiration);
        }
        if (!synopsisData.guidance.trim()) {
            synopsisData.guidance = buildInspirationGuidance(boundInspiration);
        }
    }

    const consumePendingSynopsisAdoption = async () => {
        const pending = projectStore.pendingSynopsisAdoption as InspirationAdoptionPayload | null;
        if (!pending) return;
        if (pending.projectName && pending.projectName !== projectStore.currentProject) return;
        projectStore.clearPendingSynopsisAdoption();
        handleAdoptInspiration(pending);
        if (pending.autoGenerateSynopsis) {
            const synopsisGenerated = await handleGenerateSynopsis({ skipOverwriteConfirm: true });
            if (!synopsisGenerated) return;
        }
        if (pending.autoGenerateBeats && synopsisData.synopsis_text.trim()) {
            await handleGenerateBeats({ skipOverwriteConfirm: true });
        }
    };

    const handleSynopsisRefresh = () => {
        loadFromProject();
    };

    async function loadFromProject() {
        if (!projectStore.currentProject) return;
        try {
            const cacheKey = buildSynopsisCacheKey();
            const cached = loadCreativeCache<SynopsisCacheSnapshot>(cacheKey);
            if (cached) {
                applySynopsisSnapshot(cached);
            }

            const [synMarkup, bMarkup] = await Promise.all([
                fetchSynopsis(projectStore.currentProject),
                fetchBeatSheet(projectStore.currentProject),
            ]);
            const remoteSnapshot: SynopsisCacheSnapshot = {
                synopsisData: synMarkup && synMarkup.trim()
                    ? {
                        guidance: synopsisData.guidance || '',
                        ...parseSynopsisMarkup(synMarkup),
                    } as SynopsisData
                    : {
                        title: '',
                        logline: '',
                        synopsis_text: '',
                        guidance: '',
                        themes: [],
                        pacing_guide: '',
                        narrative_pov: '',
                        estimated_chapters: '',
                    },
                beatSheet: bMarkup && bMarkup.trim()
                    ? parseBeatSheetMarkup(bMarkup)
                    : { beats: [], global_emotional_arc: '' },
            };
            if (!isCreativeCacheEqual(getSynopsisSnapshot(), remoteSnapshot)) {
                applySynopsisSnapshot(remoteSnapshot);
            }
            saveCreativeCache(cacheKey, remoteSnapshot);
            applyBoundInspirationIfNeeded();
        } catch (e) {
            console.error('Failed to load project data:', e);
        }
    }

    async function handleSave() {
        if (!projectStore.currentProject) return;
        isSaving.value = true;
        try {
            // 序列化为 Markup 文本再传输
            const synMarkup = serializeSynopsisToMarkup({
                title: synopsisData.title,
                logline: synopsisData.logline,
                synopsis_text: synopsisData.synopsis_text,
                themes: synopsisData.themes,
                pacing_guide: synopsisData.pacing_guide,
                narrative_pov: synopsisData.narrative_pov,
                estimated_chapters: synopsisData.estimated_chapters,
            });
            const bMarkup = serializeBeatSheetToMarkup(beatSheet);
            await saveSynopsis(projectStore.currentProject, synMarkup);
            await saveBeatSheet(projectStore.currentProject, bMarkup);
            saveCreativeCache(buildSynopsisCacheKey(), getSynopsisSnapshot());
        } catch (e: unknown) {
            message.error('保存失败: ' + getErrorMessage(e));
        } finally {
            isSaving.value = false;
        }
    }

    async function handleGenerateSynopsis(options: GenerateOptions = {}) {
        if (!projectStore.currentProject) return false;
        if (synopsisData.synopsis_text.trim() && !options.skipOverwriteConfirm) {
            const shouldOverwrite = await new Promise<boolean>((resolve) => {
                dialog.warning({
                    title: '确认覆盖',
                    content: '当前梗概已有内容，继续生成将覆盖现有梗概。是否继续？',
                    positiveText: '覆盖并生成',
                    negativeText: '取消',
                    onPositiveClick: () => resolve(true),
                    onNegativeClick: () => resolve(false),
                    onClose: () => resolve(false),
                });
            });
            if (!shouldOverwrite) return false;
        }
        isGenerating.value = true;
        synopsisData.synopsis_text = '';
        const task = createStreamingTask('synopsis', {
            target: 'content',
            text: '正在生成梗概...',
            canCancel: true,
        });

        try {
            const styleProfile = await getStyleProfile(projectStore.currentProject, null);

            const reader = await generateSynopsisStream(
                projectStore.currentProject,
                synopsisData.logline,
                synopsisData.guidance,
                styleProfile,
                currentLengthHint.value,
                { signal: task.signal }
            );

            let fullContent = '';

            await consumeTextReader(reader, {
                signal: task.signal,
                onChunk: (chunk) => {
                    task.push(chunk, '正在生成梗概...');
                    fullContent += chunk;
                    // 直接显示 Markup 文本（不再解析 JSON）
                    synopsisData.synopsis_text = fullContent;
                }
            });

            if (task.aborted) return false;

            // 流结束后，解析 Markup 元数据
            try {
                const parsed = parseSynopsisMarkup(fullContent);
                if (parsed.title) synopsisData.title = parsed.title;
                if (parsed.logline && !synopsisData.logline) synopsisData.logline = parsed.logline;
                if (parsed.themes && parsed.themes.length > 0) synopsisData.themes = parsed.themes;
                if (parsed.pacing_guide) synopsisData.pacing_guide = parsed.pacing_guide;
                if (parsed.narrative_pov) synopsisData.narrative_pov = parsed.narrative_pov;
                if (parsed.estimated_chapters) synopsisData.estimated_chapters = parsed.estimated_chapters;
            } catch (parseError: unknown) {
                console.warn('梗概 Markup 解析失败:', getErrorMessage(parseError));
            }
            saveCreativeCache(buildSynopsisCacheKey(), getSynopsisSnapshot());

            message.success('梗概已生成');
            return true;
        } catch (e: unknown) {
            if (isAbortLikeError(e)) {
                message.info('已取消生成');
                return false;
            }
            message.error('生成失败: ' + getErrorMessage(e));
            return false;
        } finally {
            isGenerating.value = false;
            task.dispose();
        }
    }

    async function handleGenerateBeats(options: GenerateOptions = {}) {
        if (!projectStore.currentProject) return false;
        if (!synopsisData.synopsis_text) {
            message.warning('请先生成或编写梗概');
            return false;
        }

        if (Array.isArray(beatSheet.beats) && beatSheet.beats.length > 0 && !options.skipOverwriteConfirm) {
            const shouldOverwrite = await new Promise<boolean>((resolve) => {
                dialog.warning({
                    title: '确认覆盖',
                    content: '当前节奏表已有内容，继续生成将覆盖现有节奏。是否继续？',
                    positiveText: '覆盖并生成',
                    negativeText: '取消',
                    onPositiveClick: () => resolve(true),
                    onNegativeClick: () => resolve(false),
                    onClose: () => resolve(false)
                });
            });
            if (!shouldOverwrite) return false;
        }

        isGeneratingBeats.value = true;
        const task = createStreamingTask('synopsis', {
            target: 'beats',
            text: '正在从梗概生成节奏表...',
            progress: '请稍候',
            canCancel: true,
        });
        try {
            const styleProfile = await getStyleProfile(projectStore.currentProject, null);

            const result = await generateBeatSheet(
                projectStore.currentProject,
                synopsisData.synopsis_text,
                '',
                styleProfile,
                currentLengthHint.value,
                {
                    signal: task.signal,
                    onChunk: (chunk) => task.push(chunk, '正在从梗概生成节奏表...')
                }
            );
            if (task.aborted) return false;
            if (result && result.beats) {
                beatSheet.beats = result.beats;
                beatSheet.global_emotional_arc = result.global_emotional_arc;
                // 序列化为 Markup 保存
                const bMarkup = serializeBeatSheetToMarkup(result);
                await saveBeatSheet(projectStore.currentProject, bMarkup);
                saveCreativeCache(buildSynopsisCacheKey(), getSynopsisSnapshot());
                message.success('节奏表已生成');
                return true;
            } else {
                throw new Error('生成结果缺少有效节奏数据');
            }
        } catch (e: unknown) {
            if (isAbortLikeError(e)) {
                message.info('已取消生成');
                return false;
            }
            message.error('生成失败: ' + getErrorMessage(e));
            return false;
        } finally {
            isGeneratingBeats.value = false;
            task.dispose();
        }
    }

    function addBeat() {
        beatSheet.beats.push({
            beat_id: Date.now(),
            beat_type: 'New Beat',
            narrative_action: '',
            emotional_goal: '',
            reader_experience: '',
            tension_level: 'Medium'
        });
    }

    function removeBeat(index: number) {
        beatSheet.beats.splice(index, 1);
    }

    async function goToStructure(options: { autoGenerateOutline?: boolean; beforeNavigate?: () => void } = {}) {
        if (!synopsisData.synopsis_text) {
            message.warning('请先生成或编写梗概');
            return false;
        }

        // 在离开前自动保存当前页面的梗概和节拍表，确保下一个页面能读取到最新数据
        try {
            await handleSave();
        } catch (e) {
            console.warn('自动保存失败，但不影响跳转:', e);
        }

        const synopsisContext = (synopsisData.synopsis_text || '').trim();
        const synopsisGuidance = (synopsisData.pacing_guide || '').trim();
        const adoptionPayload = {
            projectName: projectStore.currentProject,
            context: synopsisContext,
            guidance: synopsisGuidance,
            lengthHint: synopsisData.estimated_chapters || currentLengthHint.value || null,
            autoGenerateOutline: !!options.autoGenerateOutline,
        };

        // 检查是否已有大纲
        try {
            const existingOutline = await getOutline(projectStore.currentProject);
            if (existingOutline && Array.isArray(existingOutline.nodes) && existingOutline.nodes.length > 0) {
                return new Promise<void>((resolve) => {
                    dialog.warning({
                        title: '确认前往',
                        content: options.autoGenerateOutline
                            ? '大纲页面已有内容，继续将覆盖现有大纲。是否继续？'
                            : '大纲页面已有内容。如果您在大纲页执行“重新生成”，当前梗概将覆盖现有大纲。是否确定前往？',
                        positiveText: options.autoGenerateOutline ? '覆盖并继续' : '确定前往',
                        negativeText: '取消',
                        onPositiveClick: () => {
                            options.beforeNavigate?.();
                            projectStore.setPendingStructureAdoption(adoptionPayload);
                            bus.emit('adopt-synopsis', adoptionPayload);
                            viewStore.setView('structure');
                            resolve();
                        },
                        onClose: () => resolve(),
                    });
                });
            }
        } catch (e) {
            console.warn('检查现有大纲失败:', e);
        }

        // 无已有大纲，直接跳转并传递梗概
        options.beforeNavigate?.();
        projectStore.setPendingStructureAdoption(adoptionPayload);
        bus.emit('adopt-synopsis', adoptionPayload);
        viewStore.setView('structure');
        return true;
    }

    // 简易防抖函数
    function debounce(fn: (...args: unknown[]) => unknown, delay: number) {
        let timer: ReturnType<typeof setTimeout> | null = null;
        return function (this: unknown, ...args: unknown[]) {
            if (timer) clearTimeout(timer);
            timer = setTimeout(() => {
                void fn.apply(this, args);
            }, delay);
        };
    }

    // 自动保存逻辑
    const debouncedSave = debounce(async () => {
        if (!projectStore.currentProject || isGenerating.value || isGeneratingBeats.value) return;
        isSaving.value = true;
        try {
            const synMarkup = serializeSynopsisToMarkup({
                title: synopsisData.title,
                logline: synopsisData.logline,
                synopsis_text: synopsisData.synopsis_text,
                themes: synopsisData.themes,
                pacing_guide: synopsisData.pacing_guide,
                narrative_pov: synopsisData.narrative_pov,
                estimated_chapters: synopsisData.estimated_chapters,
            });
            const bMarkup = serializeBeatSheetToMarkup(beatSheet);
            await saveSynopsis(projectStore.currentProject, synMarkup);
            await saveBeatSheet(projectStore.currentProject, bMarkup);
            saveCreativeCache(buildSynopsisCacheKey(), getSynopsisSnapshot());
        } catch (e) {
            console.error('Auto-save failed:', e);
        } finally {
            isSaving.value = false;
        }
    }, 3000);

    // 监听数据变化以触发自动保存
    watch(synopsisData, () => {
        if (suppressAutoSave) return;
        if (projectStore.currentProject) {
            saveCreativeCache(buildSynopsisCacheKey(), getSynopsisSnapshot());
        }
        debouncedSave();
    }, { deep: true });

    watch(beatSheet, () => {
        if (suppressAutoSave) return;
        if (projectStore.currentProject) {
            saveCreativeCache(buildSynopsisCacheKey(), getSynopsisSnapshot());
        }
        debouncedSave();
    }, { deep: true });

    // 监听项目切换，自动加载数据
    watch(() => projectStore.currentProject, async (newProj) => {
        if (newProj) {
            await loadFromProject();
            void consumePendingSynopsisAdoption();
            return;
        }
        resetSynopsisState();
    }, { immediate: false });

    watch(() => projectStore.pendingSynopsisAdoption, () => {
        void consumePendingSynopsisAdoption();
    });

    watch(() => [projectStore.boundInspirationId, projectStore.boundInspiration], () => {
        applyBoundInspirationIfNeeded();
    });

    onMounted(async () => {
        bus.on('adopt-inspiration', handleAdoptInspiration);
        bus.on('synopsis-refresh', handleSynopsisRefresh);
        await loadFromProject();
        applyBoundInspirationIfNeeded();
        void consumePendingSynopsisAdoption();
    });

    onBeforeUnmount(() => {
        bus.off('adopt-inspiration', handleAdoptInspiration);
        bus.off('synopsis-refresh', handleSynopsisRefresh);
    });

    return {
        synopsisData,
        isGenerating,
        isSaving,
        beatSheet,
        isGeneratingBeats,
        tensionOptions,
        getTensionHeight,
        getBeatColor,
        loadFromProject,
        handleGenerateSynopsis,
        handleGenerateBeats,
        addBeat,
        removeBeat,
        goToStructure
    };
}
