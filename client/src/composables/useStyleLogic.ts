
import { ref, onMounted, onActivated, computed, watch } from 'vue';
import { useMessage } from 'naive-ui';
import { useI18n } from 'vue-i18n';
import {
    analyzeStyleStream,
    getStyles,
    deleteStyle,
    applyStyle,
    setDefaultStyle,
    exportStyleProfile,
    importStyleProfile,
} from '../services/aiService';
import { getStyleProfile, getStyleProfileMeta } from '../services/storyService';
import { useProjectStore } from '../components/stores/projectStore';
import { createStreamingTask, isAbortLikeError } from '@/utils/streamingRuntime';
import type { JsonObject } from '../services/aiContracts';
import { Activity, Book, Eye, Image as ImageIcon, Layers, MessageSquare, MessagesSquare, Palette, Search, Workflow } from '@lucide/vue';

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
    const styles = ref<string[]>([]);
    const isLoadingList = ref(false);
    const isImportingStyleProfile = ref(false);
    const styleProfileImportInput = ref<HTMLInputElement | null>(null);
    const showCreateModal = ref(false);
    const showDetailsDrawer = ref(false);
    const selectedStyleName = ref('');
    const currentProfile = ref<JsonObject | null>(null);
    const isLoadingProfile = ref(false);

    // Create State（仅用于 Modal 表单输入）
    const newStyleName = ref('');

    // Apply State
    const isApplying = ref(false);
    const applyingStyleName = ref('');
    const hasRunningAnalysis = computed(() => currentAnalysisTask.value?.status === 'running');
    const currentProjectStyleName = ref('');
    const defaultStyleName = ref('');

    const hasProjectStyle = computed(() => !!currentProjectStyleName.value);

    const projectStyleTitle = computed(() => {
        if (hasProjectStyle.value) return '当前项目已配置风格';
        if (defaultStyleName.value) return '当前项目未配置风格（将使用默认风格）';
        return '当前项目未配置风格';
    });
    const projectStyleMessage = computed(() => {
        if (hasProjectStyle.value) {
            return `项目 "${projectStore.currentProject}" 已绑定风格「${currentProjectStyleName.value}」，AI 将按该风格进行创作。`;
        }
        if (defaultStyleName.value) {
            return `项目 "${projectStore.currentProject}" 尚未绑定风格，将使用默认风格「${defaultStyleName.value}」。你也可以选择下方任一风格卡片应用到当前项目。`;
        }
        return `项目 "${projectStore.currentProject}" 尚未绑定风格，且未设置默认风格。请选择下方任一风格卡片，直接点击"应用至当前项目"，或将某个风格设为默认。`;
    });

    const isStyleAppliedToCurrentProject = (styleName: string | null | undefined) => {
        if (!projectStore.currentProject || !styleName) return false;
        return String(styleName) === String(currentProjectStyleName.value || '');
    };

    const isDefaultStyle = (styleName: string | null | undefined) => {
        if (!styleName) return false;
        return String(styleName) === String(defaultStyleName.value || '');
    };

    const handleSetDefault = async (styleName: string) => {
        if (!styleName) return;
        try {
            const result = await setDefaultStyle(styleName);
            defaultStyleName.value = result;
            message.success(`已将「${styleName}」设为默认风格`);
        } catch (e: unknown) {
            message.error('设置默认风格失败: ' + getErrorMessage(e));
        }
    };

    const handleClearDefault = async () => {
        try {
            await setDefaultStyle(null);
            defaultStyleName.value = '';
            message.success('已取消默认风格');
        } catch (e: unknown) {
            message.error('取消默认风格失败: ' + getErrorMessage(e));
        }
    };

    // 顶层区块映射：对应真实 JSON 根键名
    const sectionMap = {
        cognitive_fingerprint:  { title: '认知指纹', icon: Workflow },
        verbal_physicality:     { title: '语言质感', icon: Search },
        emotional_processing:   { title: '情感处理', icon: Activity },
        sensory_and_attention:  { title: '感官与注意力', icon: Eye },
        interpersonal_field:    { title: '人际场域', icon: MessageSquare },
        coordinator:            { title: '风格总览', icon: Book },
        // 兼容旧格式（如果服务端返回 writing_style_analysis_framework 包装）
        inner_monologue:        { title: '内心独白', icon: MessagesSquare },
        emotional_progression:  { title: '情感推进', icon: Activity },
        theme_tendency:         { title: '主题倾向', icon: Book },
        subtext_layer:          { title: '潜台词层', icon: Layers },
        dialogue_system:        { title: '对话系统', icon: MessageSquare },
        perspective_system:     { title: '视角系统', icon: Eye },
        scene_construction:     { title: '场景构建', icon: ImageIcon },
        detail_craftsmanship:   { title: '细节描写', icon: Search },
        structural_breathing:   { title: '结构节奏', icon: Workflow },
    };

    // 字段键名 → 中文文学术语映射表
    const fieldKeyMap = {
        // cognitive_fingerprint
        association_pathway:       '联想路径',
        abstraction_tendency:      '抽象化倾向',
        causal_logic:              '因果逻辑',
        observation_angle:         '观察视角',
        // verbal_physicality
        sentence_weight_and_breath:'句子重量与呼吸',
        modifier_density:          '修饰词密度',
        verb_subject_preference:   '动词与主语偏好',
        metaphor_gene:             '比喻基因',
        // emotional_processing
        emotion_presentation:      '情感呈现方式',
        climax_handling:           '高潮处理',
        vulnerability_expression:  '脆弱的表达',
        // sensory_and_attention
        sensory_priority:          '感官优先级',
        focus_shifting:            '焦点转移',
        temporal_rhythm:           '时间密度节奏',
        // interpersonal_field
        dialogue_efficiency:       '对话效率',
        silence_mechanism:         '沉默机制',
        narrator_temperature:      '叙述者温度',
        // coordinator
        signature_style:           '标志性风格',
        style_coherence:           '风格一致性',
        distinctive_summary:       '独特风格摘要',
        negative_constraints:      '反向约束（不会出现的写法）',
    };

    const getSectionTitle = (key: string) => sectionMap[key as keyof typeof sectionMap]?.title || key;
    const getSectionIcon = (key: string) => sectionMap[key as keyof typeof sectionMap]?.icon || Palette;

    // 字段名翻译：优先查中文表，找不到则做驼峰美化兜底
    const formatKey = (key: unknown) => {
        if (!key || typeof key !== 'string') return String(key);
        if (fieldKeyMap[key as keyof typeof fieldKeyMap]) return fieldKeyMap[key as keyof typeof fieldKeyMap];
        return key.split('_').map(word => word.charAt(0).toUpperCase() + word.slice(1)).join(' ');
    };

    // Methods
    const loadStyles = async () => {
        isLoadingList.value = true;
        try {
            const result = await getStyles();
            styles.value = result.styles.map((item) => String(item));
            defaultStyleName.value = result.default_style_name || '';
            if (projectStore.currentProject) {
                const profileMeta = await getStyleProfileMeta(projectStore.currentProject, null);
                currentProjectStyleName.value = profileMeta?.style_name || '';
            } else {
                currentProjectStyleName.value = '';
            }
        } catch (e: unknown) {
            message.error('加载风格列表失败: ' + getErrorMessage(e));
        } finally {
            isLoadingList.value = false;
        }
    };

    const openCreateModal = () => {
        newStyleName.value = '';
        showCreateModal.value = true;
    };

    const openStyleDetails = async (styleName: string) => {
        selectedStyleName.value = styleName;
        showDetailsDrawer.value = true;
        currentProfile.value = null;
        isLoadingProfile.value = true;

        try {
            currentProfile.value = await getStyleProfile(null, styleName);
        } catch (e: unknown) {
            message.error('加载风格详情失败: ' + getErrorMessage(e));
        } finally {
            isLoadingProfile.value = false;
        }
    };

    const handleDelete = async (styleName: string) => {
        try {
            await deleteStyle(styleName);
            message.success(`已删除风格: ${styleName}`);
            if (selectedStyleName.value === styleName) {
                showDetailsDrawer.value = false;
            }
            await loadStyles();
        } catch (e: unknown) {
            message.error('删除失败: ' + getErrorMessage(e));
        }
    };

    const handleExportStyle = async (styleName: string) => {
        if (!styleName) return;
        try {
            await exportStyleProfile(styleName);
            message.success(t('views.style.messages.exportSuccess', { name: styleName }));
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
        if (!file.name.toLowerCase().endsWith('.json')) {
            message.warning(t('views.style.messages.importJsonOnly'));
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

    const handleApplyToProject = async (styleName: string = selectedStyleName.value) => {
        if (!projectStore.currentProject) {
            message.warning('请先打开一个项目');
            return;
        }
        if (!styleName) {
            message.warning('请选择要应用的风格');
            return;
        }

        isApplying.value = true;
        applyingStyleName.value = styleName;
        try {
            await applyStyle(styleName, projectStore.currentProject);
            await loadStyles();
            message.success(`已将 "${styleName}" 应用到当前项目`);
        } catch (e: unknown) {
            message.error('应用失败: ' + getErrorMessage(e));
        } finally {
            isApplying.value = false;
            applyingStyleName.value = '';
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
            message.warning('已有风格分析任务在进行中');
            return;
        }

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
        const task: StyleAnalysisTask = {
            id: taskId,
            styleName,
            progressMessage: '正在初始化分析...',
            analysisProgress: 0,
            status: 'running',
            error: null,
            streamTask: createStreamingTask('style', {
                text: `正在分析风格「${styleName}」...`,
                progress: '正在初始化分析...',
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
                    const t = currentAnalysisTask.value?.id === task.id ? currentAnalysisTask.value : null;
                    if (!t) return;

                    if (data.message) {
                        t.progressMessage = data.message;
                    }

                    if (data.step === 'analyzing_chunk') {
                        if (typeof data.total === 'number' && data.total > 0 && typeof data.current === 'number') {
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

                    const progressText = t.analysisProgress > 0 && t.analysisProgress < 100
                        ? `${t.progressMessage}（${t.analysisProgress}%）`
                        : t.progressMessage;
                    t.streamTask?.setProgress?.(progressText);
                },
                { signal: task.streamTask?.signal }
            );

            if (!profile) {
                throw new Error('分析未返回结果');
            }

            // 更新任务状态为完成
            const t = currentAnalysisTask.value?.id === task.id ? currentAnalysisTask.value : null;
            if (t) {
                t.status = 'done';
                t.analysisProgress = 100;
                t.progressMessage = '分析完成！';
                t.streamTask?.setProgress?.('分析完成');
            }

            message.success(`风格 "${task.styleName}" 分析完成！`);
            // 刷新风格列表
            await loadStyles();

        } catch (e: unknown) {
            if (isAbortLikeError(e)) {
                const t = currentAnalysisTask.value?.id === task.id ? currentAnalysisTask.value : null;
                if (t) {
                    t.status = 'cancelled';
                    t.error = null;
                    t.progressMessage = '已取消';
                    t.streamTask?.setProgress?.('已取消');
                }
                message.info(`已取消风格 "${task.styleName}" 分析`);
                return;
            }
            const t = currentAnalysisTask.value?.id === task.id ? currentAnalysisTask.value : null;
            if (t) {
                t.status = 'error';
                t.error = getErrorMessage(e);
                t.progressMessage = '分析失败';
                t.streamTask?.setProgress?.('分析失败');
            }
            message.error(`风格 "${task.styleName}" 分析失败: ` + getErrorMessage(e));
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
                currentProjectStyleName.value = profileMeta?.style_name || '';
            } catch {
                currentProjectStyleName.value = '';
            }
        } else {
            currentProjectStyleName.value = '';
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
        selectedStyleName,
        currentProfile,
        isLoadingProfile,
        newStyleName,
        isApplying,
        applyingStyleName,
        hasRunningAnalysis,
        hasProjectStyle,
        projectStyleTitle,
        projectStyleMessage,
        defaultStyleName,
        isStyleAppliedToCurrentProject,
        isDefaultStyle,
        handleSetDefault,
        handleClearDefault,
        getSectionTitle,
        getSectionIcon,
        formatKey,
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
