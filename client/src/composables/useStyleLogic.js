
import { ref, onMounted, onActivated, computed } from 'vue';
import { useMessage } from 'naive-ui';
import { analyzeStyleStream, getStyles, deleteStyle, applyStyle } from '../services/aiService';
import { getStyleProfile } from '../services/storyService';
import { useProjectStore } from '../components/stores/projectStore';
import {
    ChatbubblesOutline, PulseOutline, BookOutline, LayersOutline,
    ChatboxEllipsesOutline, EyeOutline, ImageOutline, SearchOutline,
    GitNetworkOutline, ColorPaletteOutline
} from '@vicons/ionicons5';

// 模块级单例：任务列表在页面导航、组件卸载后仍然存活，后台分析任务可继续运行并更新进度
const analyzingTasks = ref([]);

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

    // Create State（仅用于 Modal 表单输入）
    const newStyleName = ref('');
    const isDragOver = ref(false);
    const fileInput = ref(null);

    // analyzingTasks 使用模块级单例（已在函数外声明）

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
        fileInput.value.click();
    };

    const handleFileChange = (event) => {
        const file = event.target.files[0];
        if (file) processFile(file);
        event.target.value = '';
    };

    const handleDrop = (event) => {
        isDragOver.value = false;
        const file = event.dataTransfer.files[0];
        if (file) processFile(file);
    };

    /**
     * 开始后台分析任务
     * 立即关闭 Modal，将任务推入 analyzingTasks，在后台异步执行
     */
    const processFile = async (file) => {
        if (!newStyleName.value.trim()) {
            message.warning('请输入风格名称');
            return;
        }

        if (styles.value.includes(newStyleName.value)) {
            message.warning('风格名称已存在，请换一个');
            return;
        }

        const taskId = Date.now();
        const styleName = newStyleName.value;

        // 创建任务对象并推入列表
        const task = {
            id: taskId,
            styleName,
            progressMessage: '正在初始化分析...',
            analysisProgress: 0,
            status: 'running', // 'running' | 'done' | 'error'
            error: null,
        };
        analyzingTasks.value.unshift(task);

        // 立即关闭 Modal，让用户自由操作
        showCreateModal.value = false;
        newStyleName.value = '';

        // 在后台异步执行分析（不 await，不阻塞）
        _runAnalysisTask(task, file, projectStore.currentProject);
    };

    /**
     * 后台执行分析的内部函数
     */
    const _runAnalysisTask = async (task, file, currentProject) => {
        try {
            const profile = await analyzeStyleStream(
                currentProject,
                file,
                task.styleName,
                (data) => {
                    // 找到对应任务并更新进度
                    const t = analyzingTasks.value.find(t => t.id === task.id);
                    if (!t) return;

                    if (data.message) {
                        t.progressMessage = data.message;
                    }

                    if (data.step === 'analyzing_chunk') {
                        if (data.total > 0) {
                            // 分析阶段占 10%~95%
                            t.analysisProgress = 10 + Math.floor((data.current / data.total) * 85);
                        }
                    } else if (data.step === 'chunking_complete') {
                        t.analysisProgress = 10;
                    } else if (data.step === 'save_complete') {
                        t.analysisProgress = 100;
                    } else if (data.step === 'preprocessing') {
                        t.analysisProgress = 5;
                    }
                }
            );

            if (!profile) {
                throw new Error('分析未返回结果');
            }

            // 更新任务状态为完成
            const t = analyzingTasks.value.find(t => t.id === task.id);
            if (t) {
                t.status = 'done';
                t.analysisProgress = 100;
                t.progressMessage = '分析完成！';
            }

            message.success(`风格 "${task.styleName}" 分析完成！`);
            // 刷新风格列表
            await loadStyles();

        } catch (e) {
            const t = analyzingTasks.value.find(t => t.id === task.id);
            if (t) {
                t.status = 'error';
                t.error = e.message;
                t.progressMessage = '分析失败';
            }
            message.error(`风格 "${task.styleName}" 分析失败: ` + e.message);
        }
    };

    /**
     * 关闭/移除一个任务卡片
     */
    const dismissTask = (taskId) => {
        const idx = analyzingTasks.value.findIndex(t => t.id === taskId);
        if (idx !== -1) {
            analyzingTasks.value.splice(idx, 1);
        }
    };

    const getGradient = (str) => {
        let hash = 0;
        for (let i = 0; i < str.length; i++) {
            hash = str.charCodeAt(i) + ((hash << 5) - hash);
        }
        const c1 = Math.floor(Math.abs(Math.sin(hash) * 16777215) % 16777215).toString(16);
        const c2 = Math.floor(Math.abs(Math.sin(hash + 1) * 16777215) % 16777215).toString(16);
        return `linear-gradient(135deg, #${c1.padStart(6, '0')} 0%, #${c2.padStart(6, '0')} 100%)`;
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
        isDragOver,
        fileInput,
        isApplying,
        analyzingTasks,
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
        dismissTask,
        getGradient,
        projectStore
    };
}
