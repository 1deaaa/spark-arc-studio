
import { ref, watch, onMounted, onBeforeUnmount } from 'vue';
import { useMessage } from 'naive-ui';
import {
    generateOutline,
    getStyles,
    getOutline,
    saveOutline,
    fetchSynopsis
} from '../services/api';
import { getStyleProfile } from '../services/storyService';
import { fetchBeatSheet } from '../services/aiService';
import { useProjectStore } from '../components/stores/projectStore';
import bus from '../eventBus';

export function useStructureLogic() {
    const projectStore = useProjectStore();
    const message = useMessage();

    // Outline State
    const context = ref('');
    const guidance = ref('');
    const isLoading = ref(false);
    const currentOutline = ref(null);
    const outlineHistoryRef = ref(null);
    const chapterCount = ref(5);  // 默认5章
    const sceneCount = ref(3);    // 默认每章3场景
    const lengthType = ref('short'); // 默认短篇

    const lengthOptions = [
        { label: '短篇 (5章, 每章3场景)', value: 'short' },
        { label: '中篇 (10章, 每章4场景)', value: 'medium' },
        { label: '长篇 (20章, 每章5场景)', value: 'long' },
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
        }
    });

    // 风格选择
    const styleOptions = ref([]);
    const selectedStyle = ref(null);

    async function loadStyles() {
        try {
            const styles = await getStyles();
            styleOptions.value = styles.map(s => ({ label: s, value: s }));
        } catch (e) {
            console.error('Failed to load styles:', e);
        }
    }

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
        try {
            // Fetch beat sheet from server
            let beatSheet = null;
            try {
                const bData = await fetchBeatSheet(projectStore.currentProject);
                if (bData && bData.beats && bData.beats.length > 0) {
                    beatSheet = bData;
                }
            } catch (e) {
                console.warn('Failed to fetch beat sheet', e);
            }

            let styleProfile = null;
            if (selectedStyle.value) {
                styleProfile = await getStyleProfile(null, selectedStyle.value);
            }

            const outline = await generateOutline(
                projectStore.currentProject,
                context.value,
                guidance.value,
                {
                    chapterCount: chapterCount.value,
                    sceneCountPerChapter: sceneCount.value,
                    beatSheet: beatSheet,
                    styleProfile
                }
            );

            currentOutline.value = outline;
            message.success('大纲生成成功');
            outlineHistoryRef.value?.refresh();
        } catch (e) {
            message.error('生成大纲失败: ' + e.message);
        } finally {
            isLoading.value = false;
        }
    }

    function handleOutlineUpdate(newOutline) {
        currentOutline.value = newOutline;
    }

    async function handleSaveOutline(outline) {
        try {
            const payload = outline || currentOutline.value;
            await saveOutline(projectStore.currentProject, payload, false);
            message.success('大纲已保存');
        } catch (e) {
            message.error('保存失败: ' + e.message);
        }
    }

    async function handleSaveToHistory(outline) {
        try {
            await saveOutline(projectStore.currentProject, outline, true);
            message.success('已存档到历史记录');
            outlineHistoryRef.value?.refresh();
        } catch (e) {
            message.error('存档失败: ' + e.message);
        }
    }

    function handleOutlineHistorySelect(item) {
        if (item.outline) {
            currentOutline.value = item.outline;
        }
    }

    function handleOutlineRestore(outline) {
        currentOutline.value = outline;
        message.success('大纲已恢复');
    }

    function clearInspiration() {
        projectStore.currentInspiration = '';
    }

    // --- 自动读取灵感/梗概到上下文 ---
    watch(() => projectStore.currentProject, async (newProject) => {
        if (newProject) {
            await loadCurrentOutline();

            // 优先加载梗概作为初始上下文
            try {
                const syn = await fetchSynopsis(newProject);
                if (syn) {
                    if (typeof syn === 'string') {
                        context.value = syn;
                    } else {
                        // 组合核心概念、详细梗概、主题和节奏建议
                        const parts = [];
                        if (syn.logline) parts.push(`核心概念 (Logline): ${syn.logline}`);
                        if (syn.synopsis_text) parts.push(`详细梗概: ${syn.synopsis_text}`);
                        if (syn.themes && syn.themes.length > 0) parts.push(`主题/元素: ${syn.themes.join(', ')}`);
                        if (syn.pacing_guide) parts.push(`节奏建议: ${syn.pacing_guide}`);

                        const combined = parts.join('\n\n');
                        if (combined) {
                            context.value = combined;
                        } else {
                            context.value = syn.synopsis_text || syn.logline || '';
                        }
                    }
                }
            } catch (e) {
                console.warn('Failed to pre-load synopsis', e);
            }

            // 如果梗概为空且有灵感，则使用灵感作为 fallback
            if (!context.value && projectStore.currentInspiration) {
                context.value = projectStore.currentInspiration;
            }
        }
    }, { immediate: true });

    watch(() => projectStore.currentInspiration, (newInspiration) => {
        if (newInspiration && !context.value) {
            // 如果上下文仍然为空（既无梗概也无之前的上下文），自动填入灵感
            context.value = newInspiration;
        }
    });

    // 监听梗概页面发来的 adopt-synopsis 事件，更新上下文
    function handleAdoptSynopsis({ context: synopsisContext }) {
        if (synopsisContext) {
            context.value = synopsisContext;
        }
    }

    onMounted(() => {
        loadStyles();
        bus.on('adopt-synopsis', handleAdoptSynopsis);
    });

    onBeforeUnmount(() => {
        bus.off('adopt-synopsis', handleAdoptSynopsis);
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
        styleOptions,
        selectedStyle,
        handleGenerateOutline,
        handleOutlineUpdate,
        handleSaveOutline,
        handleSaveToHistory,
        handleOutlineHistorySelect,
        handleOutlineRestore,
        clearInspiration,
        projectStore
    };
}
