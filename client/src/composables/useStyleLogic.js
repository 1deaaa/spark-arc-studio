
import { ref, onMounted, onActivated, computed } from 'vue';
import { useMessage } from 'naive-ui';
import { analyzeStyle, analyzeStyleStream, getStyles, deleteStyle, applyStyle } from '../services/aiService';
import { getStyleProfile } from '../services/storyService';
import { useProjectStore } from '../components/stores/projectStore';
import {
    ChatbubblesOutline, PulseOutline, BookOutline, LayersOutline,
    ChatboxEllipsesOutline, EyeOutline, ImageOutline, SearchOutline,
    GitNetworkOutline, ColorPaletteOutline
} from '@vicons/ionicons5';

export function useStyleLogic() {
    const projectStore = useProjectStore();
    const message = useMessage();

    // State
    const styles = ref([]);
    const isLoadingList = ref(false);
    const showCreateModal = ref(false);
    const showDetailsDrawer = ref(false);
    const selectedStyleName = ref(null);
    const currentProfile = ref(null);
    const isLoadingProfile = ref(false);

    // Create State
    const newStyleName = ref('');
    const isAnalyzing = ref(false);
    const progressMessage = ref('');
    const analysisProgress = ref(0); // Add progress tracking
    const isDragOver = ref(false);
    const fileInput = ref(null);

    // Apply State
    const isApplying = ref(false);

    const hasProjectStyle = computed(() => {
        if (!projectStore.currentProject) return false;
        return styles.value.some(s => s.includes(projectStore.currentProject));
    });

    const projectStyleTitle = computed(() => hasProjectStyle.value ? '当前项目已配置风格' : '当前项目未配置风格');
    const projectStyleMessage = computed(() => hasProjectStyle.value
        ? `项目 "${projectStore.currentProject}" 已有专属风格配置，AI 将按照此风格进行创作。`
        : `项目 "${projectStore.currentProject}" 尚未绑定风格。请选择下方任一风格卡片，在详情页点击 "应用到当前项目"。`
    );

    const sectionMap = {
        inner_monologue: { title: '内心独白 (Inner Monologue)', icon: ChatbubblesOutline },
        emotional_progression: { title: '情感推进 (Emotional Progression)', icon: PulseOutline },
        theme_tendency: { title: '主题倾向 (Theme Tendency)', icon: BookOutline },
        subtext_layer: { title: '潜台词 (Subtext Layer)', icon: LayersOutline },
        dialogue_system: { title: '对话系统 (Dialogue System)', icon: ChatboxEllipsesOutline },
        perspective_system: { title: '视角系统 (Perspective System)', icon: EyeOutline },
        scene_construction: { title: '场景构建 (Scene Construction)', icon: ImageOutline },
        detail_craftsmanship: { title: '细节描写 (Detail Craftsmanship)', icon: SearchOutline },
        structural_breathing: { title: '结构节奏 (Structural Breathing)', icon: GitNetworkOutline }
    };

    const getSectionTitle = (key) => sectionMap[key]?.title || key;
    const getSectionIcon = (key) => sectionMap[key]?.icon || ColorPaletteOutline;

    const formatKey = (key) => {
        if (!key || typeof key !== 'string') return String(key);
        return key.split('_').map(word => word.charAt(0).toUpperCase() + word.slice(1)).join(' ');
    };

    // Methods
    const loadStyles = async () => {
        isLoadingList.value = true;
        try {
            styles.value = await getStyles();
        } catch (e) {
            message.error('加载风格列表失败: ' + e.message);
        } finally {
            isLoadingList.value = false;
        }
    };

    const openCreateModal = () => {
        newStyleName.value = '';
        showCreateModal.value = true;
    };

    const openStyleDetails = async (styleName) => {
        selectedStyleName.value = styleName;
        showDetailsDrawer.value = true;
        currentProfile.value = null;
        isLoadingProfile.value = true;

        try {
            currentProfile.value = await getStyleProfile(null, styleName);
        } catch (e) {
            message.error('加载风格详情失败: ' + e.message);
        } finally {
            isLoadingProfile.value = false;
        }
    };

    const handleDelete = async (styleName) => {
        try {
            await deleteStyle(styleName);
            message.success(`已删除风格: ${styleName}`);
            if (selectedStyleName.value === styleName) {
                showDetailsDrawer.value = false;
            }
            await loadStyles();
        } catch (e) {
            message.error('删除失败: ' + e.message);
        }
    };

    const handleApplyToProject = async () => {
        if (!projectStore.currentProject) {
            message.warning('请先打开一个项目');
            return;
        }

        isApplying.value = true;
        try {
            await applyStyle(selectedStyleName.value, projectStore.currentProject);
            message.success(`已将 "${selectedStyleName.value}" 应用到当前项目`);
        } catch (e) {
            message.error('应用失败: ' + e.message);
        } finally {
            isApplying.value = false;
        }
    };

    // Upload Logic
    const triggerFileInput = () => {
        if (isAnalyzing.value) return;
        fileInput.value.click();
    };

    const handleFileChange = (event) => {
        const file = event.target.files[0];
        if (file) processFile(file);
        event.target.value = '';
    };

    const handleDrop = (event) => {
        isDragOver.value = false;
        if (isAnalyzing.value) return;
        const file = event.dataTransfer.files[0];
        if (file) processFile(file);
    };

    const processFile = async (file) => {
        if (!newStyleName.value.trim()) {
            message.warning('请输入风格名称');
            return;
        }

        if (styles.value.includes(newStyleName.value)) {
            message.warning('风格名称已存在，请换一个');
            return;
        }

        isAnalyzing.value = true;
        progressMessage.value = '正在初始化分析...';
        analysisProgress.value = 0;

        try {
            const profile = await analyzeStyleStream(
                projectStore.currentProject,
                file,
                newStyleName.value,
                (data) => {
                    if (data.message) {
                        progressMessage.value = data.message;
                    }

                    // Handle new serial analysis events
                    if (data.step === 'analyzing_chunk') {
                        // data.current is 1-based index, data.total is total chunks
                        if (data.total > 0) {
                            const percent = Math.floor((data.current / data.total) * 100);
                            analysisProgress.value = percent;
                        }
                    } else if (data.step === 'chunking_complete') {
                        analysisProgress.value = 5; // Initial progress
                    } else if (data.step === 'save_complete') {
                        analysisProgress.value = 100;
                    }

                    // Legacy support (if needed, or just remove)
                    if (data.step === 'vectorizing_batch' && typeof data.progress === 'number') {
                        analysisProgress.value = Math.floor(data.progress * 100);
                    } else if (data.step === 'vectorizing_complete') {
                        analysisProgress.value = 100;
                    }
                }
            );

            if (!profile) {
                throw new Error('分析未返回结果');
            }

            message.success('风格分析完成！');
            showCreateModal.value = false;
            await loadStyles();
            openStyleDetails(newStyleName.value);
            newStyleName.value = '';
        } catch (e) {
            message.error('分析失败: ' + e.message);
        } finally {
            isAnalyzing.value = false;
            progressMessage.value = '';
        }
    };

    const getGradient = (str) => {
        let hash = 0;
        for (let i = 0; i < str.length; i++) {
            hash = str.charCodeAt(i) + ((hash << 5) - hash);
        }
        const c1 = Math.floor(Math.abs(Math.sin(hash) * 16777215) % 16777215).toString(16);
        const c2 = Math.floor(Math.abs(Math.sin(hash + 1) * 16777215) % 16777215).toString(16);
        return `linear - gradient(135deg, #${c1.padStart(6, '0')} 0 %, #${c2.padStart(6, '0')} 100 %)`;
    };

    onMounted(() => {
        loadStyles();
    });

    onActivated(() => {
        loadStyles();
    });

    return {
        styles,
        isLoadingList,
        showCreateModal,
        showDetailsDrawer,
        selectedStyleName,
        currentProfile,
        isLoadingProfile,
        newStyleName,
        isAnalyzing,
        progressMessage,
        analysisProgress,
        isDragOver,
        fileInput,
        isApplying,
        hasProjectStyle,
        projectStyleTitle,
        projectStyleMessage,
        getSectionTitle,
        getSectionIcon,
        formatKey,
        loadStyles,
        openCreateModal,
        openStyleDetails,
        handleDelete,
        handleApplyToProject,
        triggerFileInput,
        handleFileChange,
        handleDrop,
        getGradient,
        projectStore
    };
}
