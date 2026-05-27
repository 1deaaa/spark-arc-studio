
import { ref, watch, onBeforeUnmount, onMounted, h, nextTick } from 'vue';
import { useMessage, useDialog, NButton, NSpace } from 'naive-ui';
import { useProjectStore } from '../components/stores/projectStore';
import { useViewStore } from '../components/stores/viewStore';
import { igniteMuse, fetchWithAuth, createInspiration, updateInspiration, getInspirations, bindInspiration } from '../services/api';
import { resolveApiUrl } from '../services/apiClient';
import bus from '../eventBus';
import { createStreamingTask, consumeTextReader, createAbortableEventSource, isAbortLikeError } from '@/utils/streamingRuntime';

// 简单的 debounce 函数
function debounce<T extends (...args: any[]) => any>(func: T, wait: number): (...args: Parameters<T>) => void {
    let timeout: ReturnType<typeof setTimeout> | null = null;
    return (...args: Parameters<T>) => {
        if (timeout) clearTimeout(timeout);
        timeout = setTimeout(() => func(...args), wait);
    };
}

type InspirationTags = {
    styles?: string[];
    genres?: string[];
    tones?: string[];
    worldviews?: string[];
    pov?: string[];
    lengthHint?: string[];
};

type InspirationItem = {
    id: string;
    source?: string;
    content?: string;
    tags?: InspirationTags;
};

type InspirationsResponse = {
    inspirations?: InspirationItem[];
};

type CreateInspirationResponse = {
    id: string;
};

type SynopsisApiPayload = {
    logline?: string;
    synopsis_text?: string;
};

type StreamingHandle = {
    close?: () => void;
};

function getErrorMessage(error: unknown): string {
    if (error instanceof Error) return error.message;
    return String(error || '未知错误');
}

export function useWorldLogic() {
    const viewStore = useViewStore();
    const projectStore = useProjectStore();
    const message = useMessage();
    const dialog = useDialog();

    // Muse 状态
    const museInput = ref('');
    const museLoading = ref(false);
    const museResult = ref('');
    const museHistoryRef = ref<{ refresh: () => void } | null>(null);
    const isGenerating = ref(false);
    const isHistoryCollapsed = ref(false);
    const currentInspirationId = ref<string | null>(null);  // 当前正在编辑的灵感ID
    const unreadCount = ref(0);  // 未读灵感数量

    function toggleHistoryCollapse() {
        isHistoryCollapsed.value = !isHistoryCollapsed.value;
    }

    function handleUnreadChange(count: number) {
        unreadCount.value = count;
    }

    // 标签选择状态
    const selectedGenres = ref<string[]>([]);
    const selectedTones = ref<string[]>([]);
    const selectedWorldviews = ref<string[]>([]);
    const selectedPov = ref<string | undefined>(undefined);
    const selectedLength = ref<string | undefined>(undefined);

    watch(museResult, (val) => { projectStore.currentInspiration = val; });

    // 自动保存灵感条目内容（source/content 编辑时 debounce 写回后端）
    const autoSaveInspirationEntry = debounce(async () => {
        if (!currentInspirationId.value) return;
        try {
            await updateInspiration(currentInspirationId.value, {
                source: museInput.value || undefined,
                content: museResult.value || undefined,
            });
        } catch (e) {
            console.warn('自动保存灵感条目失败:', e);
        }
    }, 800);

    // 监听灵感输入和结果变化，自动保存到灵感条目
    watch([museInput, museResult], () => {
        if (currentInspirationId.value) {
            autoSaveInspirationEntry();
        }
    });

    watch(() => projectStore.currentProject, async (nextProject, prevProject) => {
        if (nextProject === prevProject) return;
        museInput.value = '';
        museResult.value = '';
        currentInspirationId.value = null;
        projectStore.currentInspiration = '';
        projectStore.currentInspirationId = null;
        unreadCount.value = 0;
        
        // 从后端加载项目的 story tags
        if (nextProject) {
            try {
                const response = await fetchWithAuth(`/api/project/story-tags?projectName=${encodeURIComponent(nextProject)}`);
                if (response.ok) {
                    const data = await response.json();
                    if (data.success && data.tags) {
                        selectedGenres.value = data.tags.genres || [];
                        selectedTones.value = data.tags.tones || [];
                        selectedWorldviews.value = data.tags.worldviews || [];
                        selectedPov.value = data.tags.pov || undefined;
                        selectedLength.value = data.tags.length_hint || undefined;
                    } else {
                        // 如果没有 story tags，重置为空
                        selectedGenres.value = [];
                        selectedTones.value = [];
                        selectedWorldviews.value = [];
                        selectedPov.value = undefined;
                        selectedLength.value = undefined;
                    }
                }
            } catch (e) {
                console.warn('加载项目 story tags 失败:', e);
                // 失败时重置为空
                selectedGenres.value = [];
                selectedTones.value = [];
                selectedWorldviews.value = [];
                selectedPov.value = undefined;
                selectedLength.value = undefined;
            }
        } else {
            // 没有项目时重置
            selectedGenres.value = [];
            selectedTones.value = [];
            selectedWorldviews.value = [];
            selectedPov.value = undefined;
            selectedLength.value = undefined;
        }
        
        museHistoryRef.value?.refresh();
        bus.emit('lorebook-refresh');
    });

    async function loadLatestInspiration({ force = false } = {}) {
        try {
            const { inspirations } = await getInspirations() as InspirationsResponse;
            const latest = Array.isArray(inspirations) ? inspirations[0] : null;
            if (!latest) return;

            if (!force && (museInput.value || museResult.value)) return;

            handleMuseHistorySelect(latest);
        } catch (e: unknown) {
            console.warn('加载最新灵感失败:', e);
        }
    }

    async function handleIgnite() {
        museLoading.value = true;
        museResult.value = '';
        let cancelled = false;
        const museTask = createStreamingTask('muse', {
            text: '正在开动脑筋\(￣︶￣*\))...',
            canCancel: true,
            onCancel: () => {
                cancelled = true;
                museLoading.value = false;
                message.info('已取消生成');
            },
        });

        const rawInput = museInput.value.trim();

        // 构建标签
        const tags = {
            styles: [],
            genres: selectedGenres.value.length > 0 ? selectedGenres.value : [],
            tones: selectedTones.value.length > 0 ? selectedTones.value : [],
            worldviews: selectedWorldviews.value.length > 0 ? selectedWorldviews.value : [],
            pov: selectedPov.value ? [selectedPov.value] : [],
            lengthHint: selectedLength.value ? [selectedLength.value] : []
        };

        try {
            let inspirationId: string | undefined;

            if (rawInput) {
                // 有输入：先创建灵感条目（content 为空，等待生成）
                const createResult = await createInspiration(rawInput, '', tags) as CreateInspirationResponse;
                inspirationId = createResult.id;
                currentInspirationId.value = createResult.id;
                projectStore.currentInspirationId = createResult.id;

                // 自动排他绑定到当前项目：创建灵感后立即关联，无需用户手动点 Pin
                if (projectStore.currentProject) {
                    bindInspiration(createResult.id, projectStore.currentProject, true)
                        .then((result: any) => {
                            // 通知 HistoryPanel 局部更新绑定状态
                            bus.emit('inspiration-bind-changed', {
                                boundId: createResult.id,
                                unboundIds: result?.unbound_ids || [],
                                projectName: projectStore.currentProject,
                            });
                        })
                        .catch(e => console.warn('自动绑定灵感失败:', e));
                }
            }
            // 无输入：跳过预创建，由后端生成完成后自动创建带 [AI] 前缀的条目

            const reader = await igniteMuse(
                projectStore.currentProject,
                rawInput,
                {
                    genres: selectedGenres.value.length > 0 ? selectedGenres.value : null,
                    tones: selectedTones.value.length > 0 ? selectedTones.value : null,
                    worldviews: selectedWorldviews.value.length > 0 ? selectedWorldviews.value : null,
                    pov: selectedPov.value || null,
                    lengthHint: selectedLength.value,
                    inspirationId,
                    signal: museTask.signal,
                }
            );
            museResult.value = '*思考中...*';
            await consumeTextReader(reader, {
                signal: museTask.signal,
                onChunk: (chunk) => {
                    museTask.push(chunk || '', '正在开动脑筋\(￣︶￣*\))...');
                    if (chunk) {
                        if (museResult.value === '*思考中...*') museResult.value = '';
                        museResult.value += chunk;
                    }
                }
            });
            if (cancelled || museTask.aborted) return;
            museHistoryRef.value?.refresh();
        } catch (e: unknown) {
            if (isAbortLikeError(e)) return;
            message.error('灵感生成失败: ' + getErrorMessage(e));
            museResult.value = '';
        } finally {
            museLoading.value = false;
            museTask.dispose();
        }
    }

    function handleMuseHistorySelect(item: InspirationItem) {
        // 新格式: source 是原始输入，content 是扩展内容
        if (item.content) museResult.value = item.content;
        if (item.source) museInput.value = item.source;
        currentInspirationId.value = item.id;
        projectStore.currentInspirationId = item.id || null;
        // 恢复该灵感条目的 tags 到灵感主题参数面板
        if (item.tags) {
            selectedGenres.value = item.tags.genres || [];
            selectedTones.value = item.tags.tones || [];
            selectedWorldviews.value = item.tags.worldviews || [];
            selectedPov.value = item.tags.pov?.[0] || undefined;
            selectedLength.value = item.tags.lengthHint?.[0] || undefined;
        } else {
            selectedGenres.value = [];
            selectedTones.value = [];
            selectedWorldviews.value = [];
            selectedPov.value = undefined;
            selectedLength.value = undefined;
        }
        // 注意：选择历史灵感时不自动绑定到项目
        // 用户可能只是想查看，绑定应该在明确采纳时进行
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
        const targetProjectName = typeof projectStore.currentProject === 'string'
            ? projectStore.currentProject.trim()
            : '';
        if (!targetProjectName || targetProjectName === 'null' || targetProjectName === 'undefined') {
            message.error('当前项目无效，请重新选择项目后再试');
            return;
        }

        isGenerating.value = true;
        let cancelled = false;
        let characterSource: StreamingHandle | null = null;
        const task = createStreamingTask('world', {
            text: '正在生成世界观...',
            progress: '步骤 1/2',
            canCancel: true,
            onCancel: () => {
                if (cancelled) return;
                cancelled = true;
                isGenerating.value = false;
                characterSource?.close?.();
                message.info('已取消生成');
            },
        });

        try {
            // 覆盖生成前，先清空当前项目的世界观与角色，避免角色追加
            const resetRes = await fetchWithAuth('/api/lorebook/reset', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ projectName: targetProjectName })
            });
            if (!resetRes.ok) throw new Error('重置现有设定失败');

            bus.emit('characters-cleared', { projectName: targetProjectName });
            bus.emit('lorebook-refresh');
            bus.emit('worldview-stream-start', { projectName: targetProjectName });

            const worldviewResponse = await fetchWithAuth('/api/ai/worldview/generate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ seed: museResult.value, projectName: targetProjectName, lengthHint: selectedLength.value }),
                signal: task.signal,
            });

            if (!worldviewResponse.ok) throw new Error('世界观生成失败');
            if (!worldviewResponse.body) throw new Error('世界观流无响应体');

            const worldviewReader = worldviewResponse.body.getReader();
            await consumeTextReader(worldviewReader, {
                signal: task.signal,
                onChunk: (chunk) => {
                    task.push(chunk, '正在生成世界观...', { progress: '步骤 1/2' });
                    bus.emit('worldview-stream-chunk', {
                        projectName: targetProjectName,
                        text: chunk,
                    });
                }
            });

            bus.emit('worldview-stream-end', { projectName: targetProjectName });

            if (cancelled || task.aborted) return;

            task.setProgress('步骤 2/2');

            const url = `/api/ai/gen-characters/stream?projectName=${encodeURIComponent(targetProjectName)}&count=4&prompt=${encodeURIComponent('根据刚生成的世界观创建主要角色')}`;
            const esHandle = createAbortableEventSource(url, {
                withCredentials: true,
                signal: task.signal,
            });
            const es = esHandle.source;
            characterSource = esHandle;

            await new Promise<void>((resolve, reject) => {
                es.addEventListener('character-start', (evt) => {
                    try {
                        const payload = JSON.parse((evt as MessageEvent).data || '{}') as { id?: number; name?: string };
                        bus.emit('character-streamed', {
                            projectName: targetProjectName,
                            character: {
                                id: payload.id,
                                name: payload.name ?? '',
                            },
                        });
                    } catch {
                        // ignore malformed event payload
                    }
                });
                es.addEventListener('character-streamed', (evt) => {
                    try {
                        const payload = JSON.parse((evt as MessageEvent).data || '{}') as { id?: number; name?: string };
                        bus.emit('character-streamed', {
                            projectName: targetProjectName,
                            character: {
                                id: payload.id,
                                name: payload.name ?? '',
                            },
                        });
                    } catch {
                        // ignore malformed event payload
                    }
                });
                es.addEventListener('character-delta', (evt) => {
                    try {
                        const payload = JSON.parse((evt as MessageEvent).data || '{}') as { id?: number; delta?: string };
                        task.push(payload.delta || '', '正在生成角色...', { progress: '步骤 2/2' });
                        bus.emit('character-streamed', {
                            projectName: targetProjectName,
                            character: {
                                id: payload.id,
                                appendContent: payload.delta || '',
                            },
                        });
                    } catch {
                        // ignore malformed event payload
                    }
                });
                es.addEventListener('character-end', (evt) => {
                    try {
                        const payload = JSON.parse((evt as MessageEvent).data || '{}') as { id?: number; name?: string; content?: string };
                        bus.emit('character-streamed', {
                            projectName: targetProjectName,
                            character: {
                                id: payload.id,
                                name: payload.name ?? '',
                                content: payload.content ?? '',
                            },
                        });
                    } catch {
                        // ignore malformed event payload
                    }
                });
                es.addEventListener('done', () => {
                    esHandle.close();
                    resolve();
                });
                es.addEventListener('error', () => {
                    esHandle.close();
                    cancelled ? resolve() : reject(new Error('角色生成失败'));
                });
                const check = setInterval(() => {
                    if (cancelled || task.aborted) {
                        clearInterval(check);
                        esHandle.close();
                        resolve();
                    }
                }, 100);
            });

            if (cancelled || task.aborted) return;
            message.success('世界观和角色生成完成！');
            bus.emit('saved');
            bus.emit('lorebook-refresh');
        } catch (e: unknown) {
            if (isAbortLikeError(e)) return;
            if (!cancelled) message.error('生成失败: ' + getErrorMessage(e));
        } finally {
            characterSource?.close?.();
            task.dispose();
            isGenerating.value = false;
        }
    }

    async function refreshCurrentInspiration() {
        try {
            const { inspirations } = await getInspirations() as InspirationsResponse;
            const items = Array.isArray(inspirations) ? inspirations : [];
            const target = currentInspirationId.value
                ? items.find(item => item.id === currentInspirationId.value)
                : items[0];
            if (target) {
                handleMuseHistorySelect(target);
            }
            museHistoryRef.value?.refresh?.();
        } catch (e) {
            console.warn('刷新当前灵感失败:', e);
        }
    }

    async function goToSynopsis() {
        if (!museResult.value) return message.warning('请先生成灵感');

        // 检查是否已有梗概，如果有则提示覆盖
        try {
            const existingSynopsis = await fetchWithAuth(`/api/story/synopsis?projectName=${encodeURIComponent(projectStore.currentProject)}`).then(res => res.json()) as SynopsisApiPayload;
            if (existingSynopsis && (existingSynopsis.logline || existingSynopsis.synopsis_text)) {
                return new Promise<void>((resolve) => {
                    dialog.warning({
                        title: '确认覆盖',
                        content: '梗概页面已有内容，是否使用当前的灵感和核心概念覆盖它？',
                        positiveText: '确定覆盖',
                        negativeText: '取消',
                        onPositiveClick: () => {
                            proceedToSynopsis();
                            resolve();
                        }
                    });
                });
            }
        } catch (e) {
            console.warn('检查现有梗概失败:', e);
        }

        proceedToSynopsis();
    }

    // 保存 story tags 到后端的函数（带 debounce）
    const saveStoryTags = debounce(async () => {
        if (!projectStore.currentProject) return;
        
        try {
            const response = await fetchWithAuth('/api/project/story-tags', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    projectName: projectStore.currentProject,
                    genres: selectedGenres.value,
                    tones: selectedTones.value,
                    worldviews: selectedWorldviews.value,
                    pov: selectedPov.value || null,
                    lengthHint: selectedLength.value || null,
                }),
            });
            
            if (!response.ok) {
                console.warn('保存 story tags 失败:', response.status);
            }
        } catch (e) {
            console.warn('保存 story tags 失败:', e);
        }
    }, 500); // 500ms debounce

    // 监听 tags 变化，自动保存到后端
    watch([selectedGenres, selectedTones, selectedWorldviews, selectedPov, selectedLength], () => {
        saveStoryTags();
    });

    // 手动采纳灵感：排他绑定 + 保存 story tags（不跳转页面）
    async function handlePinInspiration() {
        if (!museResult.value) {
            message.warning('请先生成或选择一条灵感');
            return;
        }
        if (!projectStore.currentProject) {
            message.warning('请先选择项目');
            return;
        }

        try {
            // 排他绑定当前灵感到项目
            if (currentInspirationId.value) {
                const result = await bindInspiration(currentInspirationId.value, projectStore.currentProject, true) as any;
                // 通知 HistoryPanel 局部更新绑定状态
                bus.emit('inspiration-bind-changed', {
                    boundId: currentInspirationId.value,
                    unboundIds: result?.unbound_ids || [],
                    projectName: projectStore.currentProject,
                });
            }

            // 立即保存 story tags
            await fetchWithAuth('/api/project/story-tags', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    projectName: projectStore.currentProject,
                    genres: selectedGenres.value,
                    tones: selectedTones.value,
                    worldviews: selectedWorldviews.value,
                    pov: selectedPov.value || null,
                    lengthHint: selectedLength.value || null,
                    activeInspirationId: currentInspirationId.value || null,
                }),
            });

            message.success('灵感已采纳到当前项目');
        } catch (e) {
            console.warn('采纳灵感失败:', e);
            message.error('采纳灵感失败');
        }
    }

    function proceedToSynopsis() {
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

        // 立即保存 story tags（不等待 debounce）+ 兜底排他绑定灵感
        if (projectStore.currentProject) {
            fetchWithAuth('/api/project/story-tags', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    projectName: projectStore.currentProject,
                    genres: selectedGenres.value,
                    tones: selectedTones.value,
                    worldviews: selectedWorldviews.value,
                    pov: selectedPov.value || null,
                    lengthHint: selectedLength.value || null,
                    activeInspirationId: currentInspirationId.value || null,
                }),
            }).catch(e => console.warn('保存 story tags 失败:', e));

            // 兜底：确保当前灵感已排他绑定到项目（防止前序自动绑定因网络等原因失败）
            if (currentInspirationId.value) {
                bindInspiration(currentInspirationId.value, projectStore.currentProject, true)
                    .then((result: any) => {
                        // 通知 HistoryPanel 局部更新绑定状态
                        bus.emit('inspiration-bind-changed', {
                            boundId: currentInspirationId.value,
                            unboundIds: result?.unbound_ids || [],
                            projectName: projectStore.currentProject,
                        });
                    })
                    .catch(e => console.warn('兜底绑定灵感失败:', e));
            }
        }

        const adoptionPayload = {
            projectName: projectStore.currentProject,
            logline,
            inspiration: museResult.value,
            pov: selectedPov.value,
            lengthHint: selectedLength.value,
        };

        // 将灵感结果和 Logline 传递给下一个环节。
        // 这里既保留事件链路，也写入 store 作为切页时的兜底，避免梗概页未挂载时丢事件。
        projectStore.currentInspiration = museResult.value;
        projectStore.setPendingSynopsisAdoption(adoptionPayload);
        viewStore.setView('synopsis');
        nextTick(() => {
            bus.emit('adopt-inspiration', adoptionPayload);
        });
    }

    onBeforeUnmount(() => {
        bus.off('muse-refresh', refreshCurrentInspiration);
    });

    onMounted(() => {
        bus.on('muse-refresh', refreshCurrentInspiration);
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
        selectedGenres,
        selectedTones,
        selectedWorldviews,
        selectedPov,
        selectedLength,
        handleIgnite,
        handleMuseHistorySelect,
        handleGenerateFromMuse,
        handlePinInspiration,
        goToSynopsis
    };
}
