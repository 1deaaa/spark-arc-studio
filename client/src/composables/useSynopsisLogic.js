
import { ref, reactive, onMounted, onBeforeUnmount, watch } from 'vue';
import { useMessage } from 'naive-ui';
import {
    fetchSynopsis, saveSynopsis, generateSynopsis,
    fetchBeatSheet, saveBeatSheet, generateBeatSheet,
    getStyles
} from '../services/api';
import { getStyleProfile } from '../services/storyService';
import { useProjectStore } from '../components/stores/projectStore';
import { useViewStore } from '../components/stores/viewStore';
import bus from '../eventBus';

export function useSynopsisLogic() {
    const projectStore = useProjectStore();
    const viewStore = useViewStore();
    const message = useMessage();

    // --- 梗概数据 ---
    const synopsisData = reactive({
        title: '',
        logline: '',
        synopsis_text: '',
        guidance: '', // 将 guidance 移入 synopsisData 以便统一保存
        themes: [],
        pacing_guide: ''
    });

    const isGenerating = ref(false);
    const isSaving = ref(false);

    // --- 风格选择 ---
    const styleOptions = ref([]);
    const selectedStyle = ref(null);

    // --- 节拍表数据 ---
    const beatSheet = reactive({
        beats: [],
        global_emotional_arc: ''
    });
    const isGeneratingBeats = ref(false);

    const tensionOptions = [
        { label: '低', value: 'Low' },
        { label: '中', value: 'Medium' },
        { label: '高', value: 'High' },
        { label: '潮', value: 'Climax' }
    ];

    function getTensionHeight(level) {
        switch (level) {
            case 'Low': return '30%';
            case 'Medium': return '50%';
            case 'High': return '80%';
            case 'Climax': return '100%';
            default: return '40%';
        }
    }

    function getBeatColor(goal) {
        const goals = {
            '恐惧': '#f5222d',
            '惊喜': '#faad14',
            '悲伤': '#1890ff',
            '兴奋': '#52c41a',
            '平静': '#eb2f96'
        };
        return goals[goal] || 'var(--spark-primary)';
    }

    // --- 通用逻辑 ---
    const handleAdoptInspiration = (data) => {
        if (data.logline) {
            synopsisData.logline = data.logline;
        }
        if (data.inspiration) {
            synopsisData.guidance = `基于以下灵感扩展：\n${data.inspiration}`;
        }
    };

    async function loadStyles() {
        try {
            const styles = await getStyles();
            styleOptions.value = styles.map(s => ({ label: s, value: s }));
        } catch (e) {
            console.error('Failed to load styles:', e);
        }
    }

    async function loadFromProject() {
        if (!projectStore.currentProject) return;
        try {
            const synData = await fetchSynopsis(projectStore.currentProject);
            if (synData) {
                if (typeof synData === 'string') {
                    synopsisData.synopsis_text = synData;
                } else {
                    // 先重置当前数据，防止旧数据残留
                    synopsisData.logline = '';
                    synopsisData.guidance = '';
                    synopsisData.synopsis_text = '';
                    Object.assign(synopsisData, synData);
                }
            } else {
                synopsisData.logline = '';
                synopsisData.guidance = '';
                synopsisData.synopsis_text = '';
            }
            // 加载节拍表
            const bData = await fetchBeatSheet(projectStore.currentProject);
            if (bData && bData.beats) {
                beatSheet.beats = bData.beats;
                beatSheet.global_emotional_arc = bData.global_emotional_arc;
            } else {
                beatSheet.beats = [];
                beatSheet.global_emotional_arc = '';
            }
        } catch (e) {
            console.error('Failed to load project data:', e);
        }
    }

    async function handleSave() {
        if (!projectStore.currentProject) return;
        isSaving.value = true;
        try {
            await Promise.all([
                saveSynopsis(projectStore.currentProject, synopsisData),
                saveBeatSheet(projectStore.currentProject, beatSheet)
            ]);
            message.success('梗概与节拍表已保存');
        } catch (e) {
            message.error('保存失败: ' + e.message);
        } finally {
            isSaving.value = false;
        }
    }

    async function handleGenerateSynopsis() {
        if (!projectStore.currentProject) return;
        isGenerating.value = true;
        try {
            let styleProfile = null;
            if (selectedStyle.value) {
                styleProfile = await getStyleProfile(null, selectedStyle.value);
            }

            const result = await generateSynopsis(
                projectStore.currentProject,
                synopsisData.logline,
                synopsisData.guidance,
                styleProfile
            );
            if (typeof result === 'string') {
                synopsisData.synopsis_text = result;
            } else {
                Object.assign(synopsisData, result);
            }
            message.success('梗概已生成');
        } catch (e) {
            message.error('生成失败: ' + e.message);
        } finally {
            isGenerating.value = false;
        }
    }

    async function handleGenerateBeats() {
        if (!projectStore.currentProject) return;
        if (!synopsisData.synopsis_text) {
            message.warning('请先生成或编写梗概');
            return;
        }
        isGeneratingBeats.value = true;
        try {
            let styleProfile = null;
            if (selectedStyle.value) {
                styleProfile = await getStyleProfile(null, selectedStyle.value);
            }

            const result = await generateBeatSheet(
                projectStore.currentProject,
                synopsisData.synopsis_text,
                '',
                styleProfile
            );
            if (result && result.beats) {
                beatSheet.beats = result.beats;
                beatSheet.global_emotional_arc = result.global_emotional_arc;
                message.success('节拍表已生成');
            }
        } catch (e) {
            message.error('生成失败: ' + e.message);
        } finally {
            isGeneratingBeats.value = false;
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

    function removeBeat(index) {
        beatSheet.beats.splice(index, 1);
    }

    function goToStructure() {
        viewStore.setView('structure');
    }

    // 简易防抖函数
    function debounce(fn, delay) {
        let timer = null;
        return function (...args) {
            if (timer) clearTimeout(timer);
            timer = setTimeout(() => {
                fn.apply(this, args);
            }, delay);
        };
    }

    // 自动保存逻辑
    const debouncedSave = debounce(async () => {
        if (!projectStore.currentProject || isGenerating.value || isGeneratingBeats.value) return;
        isSaving.value = true;
        try {
            await Promise.all([
                saveSynopsis(projectStore.currentProject, synopsisData),
                saveBeatSheet(projectStore.currentProject, beatSheet)
            ]);
            console.log('Auto-saved synopsis and beat sheet');
        } catch (e) {
            console.error('Auto-save failed:', e);
        } finally {
            isSaving.value = false;
        }
    }, 3000);

    // 监听数据变化以触发自动保存
    watch(synopsisData, () => {
        debouncedSave();
    }, { deep: true });

    watch(beatSheet, () => {
        debouncedSave();
    }, { deep: true });

    // 监听项目切换，自动加载数据
    watch(() => projectStore.currentProject, (newProj) => {
        if (newProj) {
            loadFromProject();
        }
    }, { immediate: false });

    onMounted(() => {
        loadFromProject();
        loadStyles();
        bus.on('adopt-inspiration', handleAdoptInspiration);
    });

    onBeforeUnmount(() => {
        bus.off('adopt-inspiration', handleAdoptInspiration);
    });

    return {
        synopsisData,
        isGenerating,
        isSaving,
        styleOptions,
        selectedStyle,
        beatSheet,
        isGeneratingBeats,
        tensionOptions,
        getTensionHeight,
        getBeatColor,
        loadFromProject,
        handleSave,
        handleGenerateSynopsis,
        handleGenerateBeats,
        addBeat,
        removeBeat,
        goToStructure
    };
}
