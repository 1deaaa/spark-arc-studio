
import { ref, watch, onBeforeUnmount, onMounted, h } from 'vue';
import { useMessage, useDialog, NButton, NSpace } from 'naive-ui';
import { useProjectStore } from '../components/stores/projectStore';
import { useViewStore } from '../components/stores/viewStore';
import { igniteMuse, fetchWithAuth, createInspiration, updateInspiration, getInspirations } from '../services/api';
import { resolveApiUrl } from '../services/apiClient';
import bus from '../eventBus';

export function useWorldLogic() {
    const viewStore = useViewStore();
    const projectStore = useProjectStore();
    const message = useMessage();
    const dialog = useDialog();

    // Muse 状态
    const museInput = ref('');
    const museLoading = ref(false);
    const museResult = ref('');
    const museHistoryRef = ref(null);
    const isGenerating = ref(false);
    const isHistoryCollapsed = ref(false);
    const currentInspirationId = ref(null);  // 当前正在编辑的灵感ID
    const unreadCount = ref(0);  // 未读灵感数量

    function toggleHistoryCollapse() {
        isHistoryCollapsed.value = !isHistoryCollapsed.value;
    }

    function handleUnreadChange(count) {
        unreadCount.value = count;
    }

    // 标签选择状态
    const selectedStyle = ref(null);
    const selectedGenres = ref([]);
    const selectedTones = ref([]);
    const selectedWorldviews = ref([]);
    const selectedLength = ref(null);

    watch(museResult, (val) => { projectStore.currentInspiration = val; });

    watch(() => projectStore.currentProject, (nextProject, prevProject) => {
        if (nextProject === prevProject) return;
        museInput.value = '';
        museResult.value = '';
        currentInspirationId.value = null;
        unreadCount.value = 0;
        selectedStyle.value = null;
        selectedGenres.value = [];
        selectedTones.value = [];
        selectedWorldviews.value = [];
        selectedLength.value = null;
        museHistoryRef.value?.refresh();
        bus.emit('lorebook-refresh');
    });

    async function loadLatestInspiration({ force = false } = {}) {
        try {
            const { inspirations } = await getInspirations();
            const latest = Array.isArray(inspirations) ? inspirations[0] : null;
            if (!latest) return;

            if (!force && (museInput.value || museResult.value)) return;

            handleMuseHistorySelect(latest);
        } catch (e) {
            console.warn('加载最新灵感失败:', e);
        }
    }

    async function handleIgnite() {
        if (!museInput.value.trim()) return message.warning('请输入灵感');

        museLoading.value = true;
        museResult.value = '';

        // 构建标签
        const tags = {
            styles: selectedStyle.value ? [selectedStyle.value] : [],
            genres: selectedGenres.value.length > 0 ? selectedGenres.value : [],
            tones: selectedTones.value.length > 0 ? selectedTones.value : [],
            worldviews: selectedWorldviews.value.length > 0 ? selectedWorldviews.value : [],
            lengthHint: selectedLength.value ? [selectedLength.value] : []
        };

        try {
            // 先创建灵感条目（content 为空，等待生成）
            const createResult = await createInspiration(museInput.value, '', tags);
            currentInspirationId.value = createResult.id;

            // 然后调用 AI 生成扩展内容
            const reader = await igniteMuse(
                projectStore.currentProject,
                museInput.value,
                {
                    style: selectedStyle.value,
                    genres: selectedGenres.value.length > 0 ? selectedGenres.value : null,
                    tones: selectedTones.value.length > 0 ? selectedTones.value : null,
                    worldviews: selectedWorldviews.value.length > 0 ? selectedWorldviews.value : null,
                    lengthHint: selectedLength.value,
                    inspirationId: createResult.id  // 传递灵感ID，让后端更新 content
                }
            );
            const decoder = new TextDecoder();
            museResult.value = '*思考中...*';
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                const chunk = decoder.decode(value, { stream: true });
                if (museResult.value === '*思考中...*') museResult.value = '';
                museResult.value += chunk;
            }
            museHistoryRef.value?.refresh();
        } catch (e) {
            message.error('灵感生成失败: ' + e.message);
            museResult.value = '';
        } finally {
            museLoading.value = false;
        }
    }

    function handleMuseHistorySelect(item) {
        // 新格式: source 是原始输入，content 是扩展内容
        if (item.content) museResult.value = item.content;
        if (item.source) museInput.value = item.source;
        currentInspirationId.value = item.id;

        // 恢复标签选择
        if (item.tags) {
            selectedStyle.value = item.tags.styles?.[0] || null;
            selectedGenres.value = item.tags.genres || [];
            selectedTones.value = item.tags.tones || [];
            selectedWorldviews.value = item.tags.worldviews || [];

            // 处理篇幅建议：可能是字符串（旧数据）或列表（新数据）
            const lh = item.tags.lengthHint;
            selectedLength.value = Array.isArray(lh) ? (lh[0] || null) : (lh || null);
        }
    }

    async function handleGenerateFromMuse() {
        if (!museResult.value) return message.warning('请先生成灵感');
        if (!projectStore.currentProject) return message.warning('请先选择项目');

        let dialogReactive;
        dialogReactive = dialog.warning({
            title: '覆盖确认',
            content: '生成新的世界观和角色将覆盖当前项目的所有设定。如果需要保存当前世界观，请先新建一个项目。是否继续？',
            action: () => h(
                NSpace,
                { justify: 'end' },
                {
                    default: () => [
                        h(NButton, {
                            size: 'small',
                            onClick: () => dialogReactive?.destroy()
                        }, { default: () => '取消' }),
                        h(NButton, {
                            size: 'small',
                            class: 'btn-harmonious',
                            onClick: async () => {
                                dialogReactive?.destroy();
                                await projectStore.createProject();
                                if (!projectStore.currentProject) return;
                                await startGenerateFromMuse();
                            }
                        }, { default: () => '新建项目并生成' }),
                        h(NButton, {
                            size: 'small',
                            type: 'primary',
                            onClick: async () => {
                                dialogReactive?.destroy();
                                await startGenerateFromMuse();
                            }
                        }, { default: () => '确定覆盖并生成' })
                    ]
                }
            )
        });
    }

    async function startGenerateFromMuse() {
        isGenerating.value = true;
        let cancelled = false;

        const onCancel = () => {
            cancelled = true;
            isGenerating.value = false;
            bus.emit('global-loading', { show: false, scope: 'world' });
            message.info('已取消生成');
        };
        bus.on('cancel-loading', onCancel);

        try {
            // 覆盖生成前，先清空当前项目的世界观与角色，避免角色追加
            const resetRes = await fetchWithAuth('/api/lorebook/reset', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ projectName: projectStore.currentProject })
            });
            if (!resetRes.ok) throw new Error('重置现有设定失败');

            bus.emit('lorebook-refresh');

            bus.emit('global-loading', { show: true, text: '正在生成世界观...', progress: '步骤 1/2', canCancel: true, scope: 'world' });
            if (cancelled) return;

            const worldviewResponse = await fetchWithAuth('/api/ai/worldview/generate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ seed: museResult.value, projectName: projectStore.currentProject })
            });

            if (!worldviewResponse.ok) throw new Error('世界观生成失败');

            const worldviewReader = worldviewResponse.body.getReader();
            const decoder = new TextDecoder();
            while (true) {
                if (cancelled) return;
                const { done, value } = await worldviewReader.read();
                if (done) break;
                decoder.decode(value, { stream: true });
            }

            if (cancelled) return;

            bus.emit('global-loading', { show: true, text: '正在生成角色...', progress: '步骤 2/2', canCancel: true, scope: 'world' });

            const url = `/api/ai/gen-characters/stream?projectName=${encodeURIComponent(projectStore.currentProject)}&count=4&prompt=${encodeURIComponent('根据刚生成的世界观创建主要角色')}`;
            const es = new EventSource(url, { withCredentials: true });

            await new Promise((resolve, reject) => {
                es.addEventListener('done', () => { es.close(); resolve(); });
                es.addEventListener('error', () => {
                    es.close();
                    cancelled ? resolve() : reject(new Error('角色生成失败'));
                });
                const check = setInterval(() => {
                    if (cancelled) { clearInterval(check); es.close(); resolve(); }
                }, 100);
            });

            if (cancelled) return;
            bus.emit('global-loading', { show: false, scope: 'world' });
            message.success('世界观和角色生成完成！');
            bus.emit('saved');
            bus.emit('lorebook-refresh');
        } catch (e) {
            if (!cancelled) message.error('生成失败: ' + e.message);
        } finally {
            bus.off('cancel-loading', onCancel);
            isGenerating.value = false;
            bus.emit('global-loading', { show: false, scope: 'world' });
        }
    }

    function goToSynopsis() {
        if (!museResult.value) return message.warning('请先生成灵感');
        // 提取 Logline
        let logline = '';
        const text = museResult.value;

        // 优化后的提取策略
        // 1. 尝试匹配明确的 "核心概念 (Logline)" 块，支持有无数字编号
        // 匹配模式： (可选数字.) 核心概念 (Logline) (可选冒号) (内容) (直到下一个类似格式的标题或结尾)
        const loglineMatch = text.match(/(?:(?:\d+\.)?\s*核心概念\s*\(Logline\)|Logline)\s*[:：]?\s*\n?([\s\S]+?)(?=\n+(?:\d+\.)?\s*[\u4e00-\u9fa5]+\s*\(|$)/i);

        if (loglineMatch && loglineMatch[1].trim()) {
            logline = loglineMatch[1].replace(/[\[\]]/g, '').trim();
        } else {
            // 2. 备选策略：寻找包含 "Logline" 或 "核心概念" 的行
            const lines = text.split('\n').filter(l => l.trim());
            const foundIndex = lines.findIndex(l => l.includes('Logline') || l.includes('核心概念'));

            if (foundIndex !== -1) {
                const foundLine = lines[foundIndex];
                const parts = foundLine.split(/[:：]/);
                if (parts.length > 1 && parts[1].trim()) {
                    logline = parts[1].replace(/[\[\]]/g, '').trim();
                } else if (foundIndex + 1 < lines.length) {
                    // 如果当前行只有标题，尝试取下一行
                    logline = lines[foundIndex + 1].replace(/[\[\]]/g, '').trim();
                } else {
                    logline = foundLine.trim();
                }
            } else {
                // 3. 最后手段：取最后一段
                logline = lines[lines.length - 1]?.replace(/[\[\]]/g, '').trim() || '';
            }
        }

        // 将灵感结果和 Logline 传递给下一个环节
        projectStore.currentInspiration = museResult.value;
        bus.emit('adopt-inspiration', { logline, inspiration: museResult.value });

        viewStore.setView('synopsis');
    }

    onBeforeUnmount(() => {
        // 原代码这里虽然是空的，但保持结构
    });

    onMounted(() => {
        loadLatestInspiration({ force: true });
    });

    return {
        museInput,
        museLoading,
        museResult,
        museHistoryRef,
        isGenerating,
        isHistoryCollapsed,
        currentInspirationId,
        unreadCount,
        toggleHistoryCollapse,
        handleUnreadChange,
        selectedStyle,
        selectedGenres,
        selectedTones,
        selectedWorldviews,
        selectedLength,
        handleIgnite,
        handleMuseHistorySelect,
        handleGenerateFromMuse,
        goToSynopsis
    };
}
