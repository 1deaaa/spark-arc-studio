
import { ref, onMounted, onActivated, computed, watch } from 'vue';
import { useMessage } from 'naive-ui';
import { useI18n } from 'vue-i18n';
import {
    analyzeStyleStream,
    getStyles,
    deleteStyle,
    applyStyle,
    exportStyleProfile,
    importStyleProfile,
    type StyleSummary,
} from '../services/aiService';
import { getStyleProfile, getStyleProfileMeta } from '../services/storyService';
import { useProjectStore } from '../components/stores/projectStore';
import { createStreamingTask, isAbortLikeError } from '@/utils/streamingRuntime';

type StreamTaskLike = {
    signal?: AbortSignal;
    setProgress?: (text: string) => void;
    dispose?: () => void;
};

type StyleAnalysisTask = {
    id: number;
    styleName: string;
    progressMessage: string;
    analysisProgress: number;
    status: 'running' | 'done' | 'cancelled' | 'error';
    error: string | null;
    streamTask: StreamTaskLike | null;
};

function getErrorMessage(error: unknown): string {
    if (error instanceof Error) return error.message;
    return String(error || '未知错误');
}

// 模块级单例：分析任务在页面导航、组件卸载后仍然存活，后台分析任务可继续运行
const currentAnalysisTask = ref<StyleAnalysisTask | null>(null);

export function useStyleLogic() {
    const projectStore = useProjectStore();
    const message = useMessage();
    const { t } = useI18n();

    // State
    const styles = ref<StyleSummary[]>([]);
    const isLoadingList = ref(false);
    const isImportingStyleProfile = ref(false);
    const styleProfileImportInput = ref<HTMLInputElement | null>(null);
    const showCreateModal = ref(false);
    const showDetailsDrawer = ref(false);
    const selectedStyleId = ref('');
    const selectedStyle = computed(() =>
        styles.value.find((style) => style.style_id === selectedStyleId.value) || null
    );
    const selectedStyleName = computed(() => selectedStyle.value?.style_name || '');
    const currentProfile = ref<string | null>(null);
    const isLoadingProfile = ref(false);

    // Create State（仅用于 Modal 表单输入）
    const newStyleName = ref('');

    // Apply State
    const isApplying = ref(false);
    const applyingStyleId = ref('');
    const hasRunningAnalysis = computed(() => currentAnalysisTask.value?.status === 'running');
    const currentProjectBinding = ref<StyleSummary | null>(null);

    const isStyleAppliedToCurrentProject = (style: StyleSummary | null | undefined) => {
        if (!projectStore.currentProject || !style) return false;
        return style.style_id === currentProjectBinding.value?.style_id;
    };


    // Methods
    const loadStyles = async () => {
        isLoadingList.value = true;
        try {
            const result = await getStyles();
            styles.value = result.styles;
            if (projectStore.currentProject) {
                const profileMeta = await getStyleProfileMeta(projectStore.currentProject, null);
                currentProjectBinding.value = profileMeta?.project_binding || null;
            } else {
                currentProjectBinding.value = null;
            }
        } catch (e: unknown) {
            message.error(t('views.style.messages.loadListFailed', { reason: getErrorMessage(e) }));
        } finally {
            isLoadingList.value = false;
        }
    };

    const openCreateModal = () => {
        newStyleName.value = '';
        showCreateModal.value = true;
    };

    const openStyleDetails = async (style: StyleSummary) => {
        selectedStyleId.value = style.style_id;
        showDetailsDrawer.value = true;
        currentProfile.value = null;
        isLoadingProfile.value = true;

        try {
            const profile = await getStyleProfile(null, style.style_id);
            currentProfile.value = typeof profile === 'string' ? profile : null;
        } catch (e: unknown) {
            message.error(t('views.style.messages.loadProfileFailed', { reason: getErrorMessage(e) }));
        } finally {
            isLoadingProfile.value = false;
        }
    };

    const handleDelete = async (style: StyleSummary) => {
        try {
            await deleteStyle(style.style_id);
            message.success(t('views.style.messages.deleteSuccess', { name: style.style_name }));
            if (selectedStyleId.value === style.style_id) {
                showDetailsDrawer.value = false;
            }
            await loadStyles();
        } catch (e: unknown) {
            message.error(t('views.style.messages.deleteFailed', { reason: getErrorMessage(e) }));
        }
    };

    const handleExportStyle = async (style: StyleSummary | null) => {
        if (!style) return;
        try {
            await exportStyleProfile(style);
            message.success(t('views.style.messages.exportSuccess', { name: style.style_name }));
        } catch (e: unknown) {
            message.error(t('views.style.messages.exportFailed', { reason: getErrorMessage(e) }));
        }
    };

    const triggerStyleProfileImport = () => {
        styleProfileImportInput.value?.click();
    };

    const handleStyleProfileImportFile = async (event: Event) => {
        const input = event.target as HTMLInputElement | null;
        const file = input?.files?.[0];
        if (input) input.value = '';
        if (!file) return;
        if (!file.name.toLowerCase().endsWith('.md')) {
            message.warning(t('views.style.messages.importMarkdownOnly'));
            return;
        }

        isImportingStyleProfile.value = true;
        try {
            const result = await importStyleProfile(file);
            await loadStyles();
            message.success(t('views.style.messages.importSuccess', { name: result.style_name || file.name }));
        } catch (e: unknown) {
            message.error(t('views.style.messages.importFailed', { reason: getErrorMessage(e) }));
        } finally {
            isImportingStyleProfile.value = false;
        }
    };

    const handleApplyToProject = async (style: StyleSummary | null = selectedStyle.value) => {
        if (!projectStore.currentProject) {
            message.warning(t('views.style.messages.openProjectFirst'));
            return;
        }
        if (!style) {
            message.warning(t('views.style.messages.selectStyleFirst'));
            return;
        }

        const shouldApply = !isStyleAppliedToCurrentProject(style);
        isApplying.value = true;
        applyingStyleId.value = style.style_id;
        try {
            await applyStyle(style.style_id, projectStore.currentProject, shouldApply);
            await loadStyles();
            message.success(shouldApply
                ? t('views.style.messages.applySuccess', { name: style.style_name })
                : t('views.style.messages.cancelApplySuccess', { name: style.style_name })
            );
        } catch (e: unknown) {
            message.error(t('views.style.messages.applyFailed', { reason: getErrorMessage(e) }));
        } finally {
            isApplying.value = false;
            applyingStyleId.value = '';
        }
    };

    const handleImportedFile = async (file: File) => {
        await processFile(file);
    };

    const handleInvalidImportedFile = (text: string) => {
        message.warning(text);
    };

    /**
     * 开始后台分析任务
     * 立即关闭 Modal，将任务推入 analyzingTasks，在后台异步执行
     */
    const processFile = async (file: Blob | File) => {
        if (hasRunningAnalysis.value) {
            message.warning(t('views.style.messages.analysisAlreadyRunning'));
            return;
        }

        if (!newStyleName.value.trim()) {
            message.warning(t('views.style.messages.styleNameRequired'));
            return;
        }

        if (styles.value.some((style) => style.style_name === newStyleName.value)) {
            message.warning(t('views.style.messages.styleNameExists'));
            return;
        }

        const taskId = Date.now();
        const styleName = newStyleName.value;

        // 创建任务对象并推入列表
        const task: StyleAnalysisTask = {
            id: taskId,
            styleName,
            progressMessage: t('views.style.messages.analysisInitializing'),
            analysisProgress: 0,
            status: 'running',
            error: null,
            streamTask: createStreamingTask('style', {
                text: t('views.style.messages.analysisRunning', { name: styleName }),
                progress: t('views.style.messages.analysisInitializing'),
                canCancel: true,
                statsMode: 'elapsed',
            }),
        };
        currentAnalysisTask.value = task;

        // 立即关闭 Modal，让用户自由操作
        showCreateModal.value = false;
        newStyleName.value = '';

        // 在后台异步执行分析（不 await，不阻塞）
        _runAnalysisTask(task, file, projectStore.currentProject);
    };

    /**
     * 后台执行分析的内部函数
     */
    const _runAnalysisTask = async (task: StyleAnalysisTask, file: Blob | File, currentProject: string | null) => {
        try {
            const profile = await analyzeStyleStream(
                currentProject,
                file,
                task.styleName,
                (data) => {
                    const activeTask = currentAnalysisTask.value?.id === task.id ? currentAnalysisTask.value : null;
                    if (!activeTask) return;

                    if (data.message) {
                        activeTask.progressMessage = data.message;
                    }

                    if (data.step === 'analyzing_chunk') {
                        if (typeof data.total === 'number' && data.total > 0 && typeof data.current === 'number') {
                            // 分析阶段占 10%~95%
                            activeTask.analysisProgress = 10 + Math.floor((data.current / data.total) * 85);
                        }
                    } else if (data.step === 'chunking_complete') {
                        activeTask.analysisProgress = 10;
                    } else if (data.step === 'save_complete') {
                        activeTask.analysisProgress = 100;
                    } else if (data.step === 'preprocessing') {
                        activeTask.analysisProgress = 5;
                    }

                    const progressText = activeTask.analysisProgress > 0 && activeTask.analysisProgress < 100
                        ? `${activeTask.progressMessage}（${activeTask.analysisProgress}%）`
                        : activeTask.progressMessage;
                    activeTask.streamTask?.setProgress?.(progressText);
                },
                { signal: task.streamTask?.signal }
            );

            if (!profile) {
                throw new Error(t('views.style.messages.analysisNoResult'));
            }

            // 更新任务状态为完成
            const activeTask = currentAnalysisTask.value?.id === task.id ? currentAnalysisTask.value : null;
            if (activeTask) {
                activeTask.status = 'done';
                activeTask.analysisProgress = 100;
                activeTask.progressMessage = t('views.style.messages.analysisComplete');
                activeTask.streamTask?.setProgress?.(t('views.style.messages.analysisComplete'));
            }

            message.success(t('views.style.messages.analysisSuccess', { name: task.styleName }));
            // 刷新风格列表
            await loadStyles();

        } catch (e: unknown) {
            if (isAbortLikeError(e)) {
                const activeTask = currentAnalysisTask.value?.id === task.id ? currentAnalysisTask.value : null;
                if (activeTask) {
                    activeTask.status = 'cancelled';
                    activeTask.error = null;
                    activeTask.progressMessage = t('views.style.messages.analysisCancelled');
                    activeTask.streamTask?.setProgress?.(t('views.style.messages.analysisCancelled'));
                }
                message.info(t('views.style.messages.analysisCancelledMessage', { name: task.styleName }));
                return;
            }
            const activeTask = currentAnalysisTask.value?.id === task.id ? currentAnalysisTask.value : null;
            if (activeTask) {
                activeTask.status = 'error';
                activeTask.error = getErrorMessage(e);
                activeTask.progressMessage = t('views.style.messages.analysisFailed');
                activeTask.streamTask?.setProgress?.(t('views.style.messages.analysisFailed'));
            }
            message.error(t('views.style.messages.analysisFailedMessage', {
                name: task.styleName,
                reason: getErrorMessage(e),
            }));
        } finally {
            if (task.streamTask) {
                task.streamTask.dispose?.();
                task.streamTask = null;
            }
            if (currentAnalysisTask.value?.id === task.id) {
                currentAnalysisTask.value = null;
            }
        }
    };

    /**
     * 生成绝对随动于当前主题色 var(--spark-primary) 的渐变
     * 无论用户怎么切换系统主题色（或亮暗模式），这里永远完美融合。
     */
    const getGradient = (str: string | null | undefined) => {
        if (!str) return 'linear-gradient(135deg, var(--spark-primary) 0%, var(--spark-primary-dim) 100%)';
        
        let hash = 0;
        for (let i = 0; i < str.length; i++) {
            hash = str.charCodeAt(i) + ((hash << 5) - hash);
        }
        
        // 1. 基于主题色的色相偏移 (利用 oklch 的色相参数 h 进行角度偏转)
        // 使每种风格获得一个独特的偏转角度，偏移在 [-90, 90] 度之间
        const hueShift = (Math.abs(hash) % 180) - 90;
        
        // 2. 利用现代 CSS oklch(from color) 语法，根据起点主题色动态推导终点色
        const targetColor = `oklch(from var(--spark-primary) l c calc(h + ${hueShift}))`;
        
        return `linear-gradient(135deg, var(--spark-primary) 0%, ${targetColor} 100%)`;
    };

    // 项目切换时自动刷新当前项目的风格绑定状态
    watch(() => projectStore.currentProject, async (newProject) => {
        if (newProject) {
            try {
                const profileMeta = await getStyleProfileMeta(newProject, null);
                currentProjectBinding.value = profileMeta?.project_binding || null;
            } catch {
                currentProjectBinding.value = null;
            }
        } else {
            currentProjectBinding.value = null;
        }
    });

    onMounted(() => {
        loadStyles();
    });

    onActivated(() => {
        loadStyles();
    });

    return {
        styles,
        isLoadingList,
        isImportingStyleProfile,
        styleProfileImportInput,
        showCreateModal,
        showDetailsDrawer,
        selectedStyle,
        selectedStyleName,
        currentProfile,
        isLoadingProfile,
        newStyleName,
        isApplying,
        applyingStyleId,
        hasRunningAnalysis,
        isStyleAppliedToCurrentProject,
        loadStyles,
        openCreateModal,
        openStyleDetails,
        handleDelete,
        handleExportStyle,
        triggerStyleProfileImport,
        handleStyleProfileImportFile,
        handleApplyToProject,
        handleImportedFile,
        handleInvalidImportedFile,
        getGradient,
        projectStore
    };
}
