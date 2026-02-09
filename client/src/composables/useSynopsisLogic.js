
import { ref, reactive, onMounted, onBeforeUnmount, watch } from 'vue';
import { useMessage, useDialog } from 'naive-ui';
import {
    fetchSynopsis, saveSynopsis, generateSynopsis, generateSynopsisStream,
    fetchBeatSheet, saveBeatSheet, generateBeatSheet,
    getStyles, getOutline
} from '../services/api';
import { getStyleProfile } from '../services/storyService';
import { useProjectStore } from '../components/stores/projectStore';
import { useViewStore } from '../components/stores/viewStore';
import bus from '../eventBus';

export function useSynopsisLogic() {
    const projectStore = useProjectStore();
    const viewStore = useViewStore();
    const message = useMessage();
    const dialog = useDialog();

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
        if (!data) return;
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
        synopsisData.synopsis_text = '';

        try {
            let styleProfile = null;
            if (selectedStyle.value) {
                styleProfile = await getStyleProfile(null, selectedStyle.value);
            }

            const reader = await generateSynopsisStream(
                projectStore.currentProject,
                synopsisData.logline,
                synopsisData.guidance,
                styleProfile
            );

            const decoder = new TextDecoder();
            let fullContent = '';
            let displayContent = '';
            let inSynopsisText = false;
            let synopsisBuffer = '';

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                const chunk = decoder.decode(value, { stream: true });
                fullContent += chunk;

                // 实时解析 JSON 流，只提取 synopsis_text 的内容
                for (const char of chunk) {
                    if (!inSynopsisText) {
                        // 检测是否进入 synopsis_text 字段
                        synopsisBuffer += char;
                        if (synopsisBuffer.includes('"synopsis_text"')) {
                            // 找到字段名，等待冒号和引号
                            const match = synopsisBuffer.match(/"synopsis_text"\s*:\s*"/);
                            if (match) {
                                inSynopsisText = true;
                                synopsisBuffer = '';
                            }
                        }
                        // 保持 buffer 不要太长
                        if (synopsisBuffer.length > 50) {
                            synopsisBuffer = synopsisBuffer.slice(-30);
                        }
                    } else {
                        // 在 synopsis_text 字段内容中
                        if (char === '"' && !displayContent.endsWith('\\')) {
                            // 遇到未转义的引号，字段结束
                            inSynopsisText = false;
                        } else if (char === '\\' && displayContent.endsWith('\\')) {
                            // 双反斜杠，添加一个反斜杠
                            displayContent = displayContent.slice(0, -1) + '\\';
                        } else if (char === 'n' && displayContent.endsWith('\\')) {
                            // 转义换行符 \n
                            displayContent = displayContent.slice(0, -1) + '\n';
                        } else {
                            displayContent += char;
                        }
                        synopsisData.synopsis_text = displayContent;
                    }
                }
            }

            // 流结束后，尝试解析 JSON 并提取字段
            try {
                // 清理可能的 markdown 代码块标记
                let jsonStr = fullContent.trim();

                // 移除开头的 ```json 或 ```
                const jsonBlockMatch = jsonStr.match(/^```(?:json)?\s*\n?([\s\S]*?)\n?```$/);
                if (jsonBlockMatch) {
                    jsonStr = jsonBlockMatch[1].trim();
                } else {
                    // 尝试其他清理方式
                    if (jsonStr.startsWith('```json')) {
                        jsonStr = jsonStr.slice(7);
                    } else if (jsonStr.startsWith('```')) {
                        jsonStr = jsonStr.slice(3);
                    }
                    if (jsonStr.endsWith('```')) {
                        jsonStr = jsonStr.slice(0, -3);
                    }
                    jsonStr = jsonStr.trim();
                }

                // 确保是 JSON 对象
                if (jsonStr.startsWith('{') && jsonStr.includes('"synopsis_text"')) {
                    const parsed = JSON.parse(jsonStr);

                    // 分配解析后的字段
                    if (parsed.synopsis_text) {
                        synopsisData.synopsis_text = parsed.synopsis_text;
                    }
                    if (parsed.title) {
                        synopsisData.title = parsed.title;
                    }
                    if (parsed.logline && !synopsisData.logline) {
                        synopsisData.logline = parsed.logline;
                    }
                    if (parsed.themes) {
                        synopsisData.themes = parsed.themes;
                    }
                    if (parsed.pacing_guide) {
                        synopsisData.pacing_guide = parsed.pacing_guide;
                    }
                    console.log('梗概 JSON 解析成功:', Object.keys(parsed));
                } else {
                    console.log('内容不是有效的梗概 JSON 格式，保持原始文本');
                }
            } catch (parseError) {
                // 如果解析失败，保持原始文本
                console.warn('梗概 JSON 解析失败:', parseError.message);
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

    async function goToStructure() {
        if (!synopsisData.synopsis_text) return message.warning('请先生成或编写梗概');

        // 在离开前自动保存当前页面的梗概和节拍表，确保下一个页面能读取到最新数据
        try {
            await handleSave();
        } catch (e) {
            console.warn('自动保存失败，但不影响跳转:', e);
        }

        // 检查是否已有大纲
        try {
            const existingOutline = await getOutline(projectStore.currentProject);
            if (existingOutline && existingOutline.chapters && existingOutline.chapters.length > 0) {
                return new Promise((resolve) => {
                    dialog.warning({
                        title: '确认前往',
                        content: '大纲页面已有内容。如果您在大纲页执行“重新生成”，当前梗概将覆盖现有大纲。是否确定前往？',
                        positiveText: '确定前往',
                        negativeText: '取消',
                        onPositiveClick: () => {
                            viewStore.setView('structure');
                            resolve();
                        }
                    });
                });
            }
        } catch (e) {
            console.warn('检查现有大纲失败:', e);
        }
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
