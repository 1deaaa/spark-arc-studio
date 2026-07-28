
import { ref, watch, onBeforeUnmount, onMounted, h, nextTick, computed } from 'vue';
import { useMessage, useDialog, NButton, NSpace } from 'naive-ui';
import { useProjectStore } from '../components/stores/projectStore';
import { useViewStore } from '../components/stores/viewStore';
import { igniteMuse, fetchWithAuth, createInspiration, updateInspiration, getInspirations, bindInspiration, fetchSynopsis, fetchBeatSheet } from '../services/api';
import bus from '../eventBus';
import { createStreamingTask, consumeTextReader, createAbortableEventSource, isAbortLikeError } from '@/utils/streamingRuntime';
import { extractLoglineFromInspiration, shouldRestoreInspirationWorkbenchCache } from '@/utils/inspiration';
import { i18n } from '@/i18n';
import { buildCreativeCacheKey, loadCreativeCache, saveCreativeCache } from '@/utils/creativeLocalCache';
import type { InspirationBindChangedPayload } from '@/services/aiContracts';

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

type GoToSynopsisOptions = {
    autoGenerateSynopsis?: boolean;
    autoGenerateBeats?: boolean;
};

type StreamingHandle = {
  close?: () => void;
};

type WorldWorkbenchCacheSnapshot = {
    museInput: string;
    museResult: string;
    currentInspirationId: string | null;
    selectedGenres: string[];
    selectedTones: string[];
    selectedWorldviews: string[];
    selectedPov?: string;
    selectedLength?: string;
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
    const isCurrentInspirationBound = computed(() => (
        !!currentInspirationId.value
        && !!projectStore.boundInspirationId
        && currentInspirationId.value === projectStore.boundInspirationId
    ));

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

    function buildWorldCacheKey(projectName: string | null | undefined = projectStore.currentProject) {
        return buildCreativeCacheKey('world-workbench', projectName || 'global');
    }

    function getWorldSnapshot(): WorldWorkbenchCacheSnapshot {
        return {
            museInput: museInput.value,
            museResult: museResult.value,
            currentInspirationId: currentInspirationId.value,
            selectedGenres: [...selectedGenres.value],
            selectedTones: [...selectedTones.value],
            selectedWorldviews: [...selectedWorldviews.value],
            selectedPov: selectedPov.value,
            selectedLength: selectedLength.value,
        };
    }

    function applyWorldSnapshot(snapshot: WorldWorkbenchCacheSnapshot | null | undefined) {
        const safe = snapshot || {
            museInput: '',
            museResult: '',
            currentInspirationId: null,
            selectedGenres: [],
            selectedTones: [],
            selectedWorldviews: [],
            selectedPov: undefined,
            selectedLength: undefined,
        };
        museInput.value = safe.museInput || '';
        museResult.value = safe.museResult || '';
        currentInspirationId.value = safe.currentInspirationId || null;
        projectStore.currentInspirationId = safe.currentInspirationId || null;
        selectedGenres.value = Array.isArray(safe.selectedGenres) ? [...safe.selectedGenres] : [];
        selectedTones.value = Array.isArray(safe.selectedTones) ? [...safe.selectedTones] : [];
        selectedWorldviews.value = Array.isArray(safe.selectedWorldviews) ? [...safe.selectedWorldviews] : [];
        selectedPov.value = safe.selectedPov;
        selectedLength.value = safe.selectedLength;
    }

    function clearCurrentInspirationEditor() {
        museInput.value = '';
        museResult.value = '';
        currentInspirationId.value = null;
        projectStore.currentInspirationId = null;
        projectStore.currentInspiration = '';
    }

    watch(museResult, (val) => { projectStore.currentInspiration = val; });

    watch(
        [museInput, museResult, currentInspirationId, selectedGenres, selectedTones, selectedWorldviews, selectedPov, selectedLength],
        () => {
            saveCreativeCache(buildWorldCacheKey(), getWorldSnapshot());
        },
        { deep: true }
    );

    watch([museInput, museResult, currentInspirationId, isCurrentInspirationBound], () => {
        if (!isCurrentInspirationBound.value || !currentInspirationId.value) return;
        projectStore.applyBoundInspiration({
            id: currentInspirationId.value,
            source: museInput.value,
            content: museResult.value,
        });
    });

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

    async function loadProjectStoryTags(projectName: string | null | undefined) {
        if (!projectName) {
            selectedGenres.value = [];
            selectedTones.value = [];
            selectedWorldviews.value = [];
            selectedPov.value = undefined;
            selectedLength.value = undefined;
            return;
        }
        try {
            const response = await fetchWithAuth(`/api/project/story-tags?projectName=${encodeURIComponent(projectName)}`);
            if (!response.ok) {
                selectedGenres.value = [];
                selectedTones.value = [];
                selectedWorldviews.value = [];
                selectedPov.value = undefined;
                selectedLength.value = undefined;
                return;
            }
            const data = await response.json();
            if (data.success && data.tags) {
                selectedGenres.value = data.tags.genres || [];
                selectedTones.value = data.tags.tones || [];
                selectedWorldviews.value = data.tags.worldviews || [];
                selectedPov.value = data.tags.pov || undefined;
                selectedLength.value = data.tags.length_hint || undefined;
                return;
            }
        } catch (e) {
            console.warn('加载项目 story tags 失败:', e);
        }
        selectedGenres.value = [];
        selectedTones.value = [];
        selectedWorldviews.value = [];
        selectedPov.value = undefined;
        selectedLength.value = undefined;
    }

    watch(() => projectStore.currentProject, async (nextProject, prevProject) => {
        if (nextProject === prevProject) return;
        const cacheKey = buildWorldCacheKey(nextProject);
        const cachedSnapshot = nextProject
            ? loadCreativeCache<WorldWorkbenchCacheSnapshot>(cacheKey)
            : null;

        // 项目工坊只能由后端当前灵感恢复；先清空，避免未绑定缓存短暂串入界面。
        applyWorldSnapshot(nextProject ? null : loadCreativeCache<WorldWorkbenchCacheSnapshot>(cacheKey));
        projectStore.currentInspiration = '';
        unreadCount.value = 0;
        await loadProjectStoryTags(nextProject);
        if (projectStore.currentProject !== nextProject) return;

        if (nextProject) {
            const boundInspiration = await projectStore.refreshCurrentProjectInspiration(nextProject);
            if (projectStore.currentProject !== nextProject) return;

            if (boundInspiration) {
                if (shouldRestoreInspirationWorkbenchCache(
                    cachedSnapshot?.currentInspirationId,
                    boundInspiration.id,
                )) {
                    applyWorldSnapshot(cachedSnapshot);
                } else {
                    handleMuseHistorySelect(boundInspiration);
                }
            } else {
                // 仅清空灵感编辑字段，保留已经加载的项目主题参数。
                clearCurrentInspirationEditor();
            }
            saveCreativeCache(cacheKey, getWorldSnapshot());
        } else {
            await loadLatestInspiration({ force: true });
        }

        museHistoryRef.value?.refresh();
        bus.emit('lorebook-refresh');
    }, { immediate: true });

    async function loadLatestInspiration({ force = false } = {}) {
        try {
            const { inspirations } = await getInspirations() as InspirationsResponse;
            const latest = Array.isArray(inspirations) ? inspirations[0] : null;
            if (!latest) return;

            if (!force && (museInput.value || museResult.value)) return;

            handleMuseHistorySelect(latest);
            saveCreativeCache(buildWorldCacheKey(), getWorldSnapshot());
        } catch (e: unknown) {
            console.warn('加载最新灵感失败:', e);
        }
    }

    async function handleIgnite() {
        if (museResult.value.trim()) {
            const shouldOverwrite = await new Promise<boolean>((resolve) => {
                dialog.warning({
                    title: i18n.global.t('views.world.museOverwriteTitle'),
                    content: i18n.global.t('views.world.museOverwriteContent'),
                    positiveText: i18n.global.t('views.world.museOverwriteConfirm'),
                    negativeText: i18n.global.t('common.cancel'),
                    onPositiveClick: () => resolve(true),
                    onNegativeClick: () => resolve(false),
                    onClose: () => resolve(false),
                });
            });
            if (!shouldOverwrite) return;
        }
        museLoading.value = true;
        museResult.value = '';
        let cancelled = false;
        const museTask = createStreamingTask('muse', {
            text: i18n.global.t('views.world.museThinking'),
            canCancel: true,
            onCancel: () => {
                cancelled = true;
                museLoading.value = false;
                message.info(i18n.global.t('views.world.museCancelled'));
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

                // 创建后直接设为当前项目灵感，无需用户手动采纳。
                if (projectStore.currentProject) {
                    bindInspiration(createResult.id, projectStore.currentProject)
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
            const pendingMuseText = `*${i18n.global.t('common.generating')}*`;
            museResult.value = pendingMuseText;
            await consumeTextReader(reader, {
                signal: museTask.signal,
                onChunk: (chunk) => {
                    museTask.push(chunk || '', i18n.global.t('views.world.museThinking'));
                    if (chunk) {
                        if (museResult.value === pendingMuseText) museResult.value = '';
                        museResult.value += chunk;
                    }
                }
            });
            if (cancelled || museTask.aborted) return;
            if (projectStore.currentProject && currentInspirationId.value) {
                projectStore.applyBoundInspiration({
                    id: currentInspirationId.value,
                    source: museInput.value,
                    content: museResult.value,
                });
            }
            saveCreativeCache(buildWorldCacheKey(), getWorldSnapshot());
            museHistoryRef.value?.refresh();
        } catch (e: unknown) {
            if (isAbortLikeError(e)) return;
            message.error(i18n.global.t('views.world.museGenerateFailed', { error: getErrorMessage(e) }));
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
        saveCreativeCache(buildWorldCacheKey(), getWorldSnapshot());
    }

    function handleInspirationBindChanged(payload: InspirationBindChangedPayload) {
        if (!payload?.projectName || payload.projectName !== projectStore.currentProject) return;

        if (payload.boundId) {
            if (payload.entry) {
                handleMuseHistorySelect(payload.entry);
                projectStore.applyBoundInspiration(payload.entry);
                return;
            }
            if (currentInspirationId.value === payload.boundId) {
                projectStore.applyBoundInspiration({
                    id: payload.boundId,
                    source: museInput.value,
                    content: museResult.value,
                });
                saveCreativeCache(buildWorldCacheKey(), getWorldSnapshot());
                return;
            }
            void projectStore.refreshCurrentProjectInspiration(payload.projectName);
            return;
        }

        const previousBoundId = projectStore.boundInspirationId;
        if (previousBoundId && !(payload.unboundIds || []).includes(previousBoundId)) return;
        projectStore.applyBoundInspiration(null);
        clearCurrentInspirationEditor();
        saveCreativeCache(buildWorldCacheKey(), getWorldSnapshot());
    }

    async function persistStoryTags(activeInspirationId: string | null = currentInspirationId.value) {
        if (!projectStore.currentProject) return;
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
                activeInspirationId: activeInspirationId || null,
            }),
        });
    }

    async function ensureCurrentInspirationBound() {
        if (!projectStore.currentProject) return false;
        if (!museResult.value.trim()) return false;

        if (currentInspirationId.value) {
            const result = await bindInspiration(currentInspirationId.value, projectStore.currentProject) as any;
            bus.emit('inspiration-bind-changed', {
                boundId: currentInspirationId.value,
                unboundIds: result?.unbound_ids || [],
                projectName: projectStore.currentProject,
            });
            projectStore.applyBoundInspiration({
                id: currentInspirationId.value,
                source: museInput.value,
                content: museResult.value,
            });
        }

        await persistStoryTags(currentInspirationId.value || null);
        return true;
    }

    async function handleGenerateFromMuse(options: { beforeGenerate?: () => void } = {}) {
        if (!museResult.value) return message.warning(i18n.global.t('views.world.needInspiration'));
        if (!projectStore.currentProject) return message.warning(i18n.global.t('common.selectProjectFirst'));

        let dialogReactive;
        dialogReactive = dialog.warning({
            title: i18n.global.t('views.world.worldOverwriteTitle'),
            content: i18n.global.t('views.world.worldOverwriteContent'),
            action: () => h(
                NSpace,
                { justify: 'end' },
                {
                    default: () => [
                        h(NButton, {
                            size: 'small',
                            onClick: () => dialogReactive?.destroy()
                        }, { default: () => i18n.global.t('common.cancel') }),
                        h(NButton, {
                            size: 'small',
                            class: 'btn-harmonious',
                            onClick: async () => {
                                dialogReactive?.destroy();
                                await projectStore.createProject();
                                if (!projectStore.currentProject) return;
                                options.beforeGenerate?.();
                                await startGenerateFromMuse();
                            }
                        }, { default: () => i18n.global.t('views.world.createProjectAndGenerate') }),
                        h(NButton, {
                            size: 'small',
                            type: 'primary',
                            onClick: async () => {
                                dialogReactive?.destroy();
                                options.beforeGenerate?.();
                                await startGenerateFromMuse();
                            }
                        }, { default: () => i18n.global.t('views.world.overwriteAndGenerate') })
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
            message.error(i18n.global.t('views.world.invalidProject'));
            return;
        }
        try {
            await ensureCurrentInspirationBound();
        } catch (e) {
            message.error(i18n.global.t('views.world.adoptInspirationFailed', { error: getErrorMessage(e) }));
            return;
        }

        isGenerating.value = true;
        let cancelled = false;
        let characterSource: StreamingHandle | null = null;
        const task = createStreamingTask('world', {
            text: i18n.global.t('views.world.generatingWorld'),
            progress: i18n.global.t('views.world.stepOne'),
            canCancel: true,
            onCancel: () => {
                if (cancelled) return;
                cancelled = true;
                isGenerating.value = false;
                characterSource?.close?.();
                message.info(i18n.global.t('views.world.museCancelled'));
            },
        });

        try {
            // 覆盖生成前，先清空当前项目的世界观与角色，避免角色追加
            const resetRes = await fetchWithAuth('/api/lorebook/reset', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ projectName: targetProjectName })
            });
            if (!resetRes.ok) throw new Error(i18n.global.t('views.world.resetSettingsFailed'));

            bus.emit('characters-cleared', { projectName: targetProjectName });
            bus.emit('lorebook-refresh');
            bus.emit('worldview-stream-start', { projectName: targetProjectName });

            const worldviewResponse = await fetchWithAuth('/api/ai/worldview/generate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ seed: museResult.value, projectName: targetProjectName, lengthHint: selectedLength.value }),
                signal: task.signal,
            });

            if (!worldviewResponse.ok) throw new Error(i18n.global.t('views.world.worldviewGenerateFailed'));
            if (!worldviewResponse.body) throw new Error(i18n.global.t('views.world.worldviewNoBody'));

            const worldviewReader = worldviewResponse.body.getReader();
            await consumeTextReader(worldviewReader, {
                signal: task.signal,
                onChunk: (chunk) => {
                    task.push(chunk, i18n.global.t('views.world.generatingWorld'), { progress: i18n.global.t('views.world.stepOne') });
                    bus.emit('worldview-stream-chunk', {
                        projectName: targetProjectName,
                        text: chunk,
                    });
                }
            });

            bus.emit('worldview-stream-end', { projectName: targetProjectName });

            if (cancelled || task.aborted) return;

            task.setProgress(i18n.global.t('views.world.stepTwo'));

            const url = `/api/ai/gen-characters/stream?projectName=${encodeURIComponent(targetProjectName)}&count=4&prompt=${encodeURIComponent(i18n.global.t('views.world.characterPrompt'))}`;
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
                        task.push(payload.delta || '', i18n.global.t('views.world.generatingCharacters'), { progress: i18n.global.t('views.world.stepTwo') });
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
                    cancelled ? resolve() : reject(new Error(i18n.global.t('views.world.charactersGenerateFailed')));
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
            message.success(i18n.global.t('views.world.worldGenerationSuccess'));
            bus.emit('saved');
            bus.emit('lorebook-refresh');
        } catch (e: unknown) {
            if (isAbortLikeError(e)) return;
            if (!cancelled) message.error(i18n.global.t('views.world.generateFailed', { error: getErrorMessage(e) }));
        } finally {
            characterSource?.close?.();
            task.dispose();
            isGenerating.value = false;
        }
    }

    async function refreshCurrentInspiration() {
        try {
            if (projectStore.currentProject) {
                const projectName = projectStore.currentProject;
                const bound = await projectStore.refreshCurrentProjectInspiration(projectName);
                if (projectStore.currentProject !== projectName) return;
                if (bound) {
                    handleMuseHistorySelect(bound);
                    projectStore.applyBoundInspiration(bound);
                } else {
                    clearCurrentInspirationEditor();
                    saveCreativeCache(buildWorldCacheKey(), getWorldSnapshot());
                }
                museHistoryRef.value?.refresh?.();
                return;
            }

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

    async function goToSynopsis(options: GoToSynopsisOptions = {}) {
        if (!museResult.value) return message.warning(i18n.global.t('views.world.needInspiration'));
        if (!projectStore.currentProject) return message.warning(i18n.global.t('common.selectProjectFirst'));

        try {
            const [existingSynopsis, existingBeatSheet] = await Promise.all([
                fetchSynopsis(projectStore.currentProject),
                fetchBeatSheet(projectStore.currentProject),
            ]);
            const hasSynopsis = !!existingSynopsis?.trim();
            const hasBeatSheet = !!existingBeatSheet?.trim();
            const shouldConfirmStepGeneration = options.autoGenerateSynopsis || options.autoGenerateBeats;

            if (shouldConfirmStepGeneration && (hasSynopsis || hasBeatSheet)) {
                return new Promise<void>((resolve) => {
                    dialog.warning({
                        title: i18n.global.t('views.world.synopsisOverwriteTitle'),
                        content: i18n.global.t('views.world.synopsisStepOverwriteContent'),
                        positiveText: i18n.global.t('views.world.synopsisStepOverwriteConfirm'),
                        negativeText: i18n.global.t('common.cancel'),
                        onPositiveClick: async () => {
                            await proceedToSynopsis(options);
                            resolve();
                        },
                        onClose: () => resolve(),
                    });
                });
            }
            if (!shouldConfirmStepGeneration && hasSynopsis) {
                return new Promise<void>((resolve) => {
                    dialog.warning({
                        title: i18n.global.t('views.world.synopsisOverwriteTitle'),
                        content: i18n.global.t('views.world.synopsisPageOverwriteContent'),
                        positiveText: i18n.global.t('views.world.synopsisPageOverwriteConfirm'),
                        negativeText: i18n.global.t('common.cancel'),
                        onPositiveClick: async () => {
                            await proceedToSynopsis(options);
                            resolve();
                        },
                        onClose: () => resolve(),
                    });
                });
            }
        } catch (e) {
            console.warn('检查现有梗概失败:', e);
        }

        await proceedToSynopsis(options);
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
                    activeInspirationId: projectStore.boundInspirationId || null,
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

    // 手动采纳灵感：设为项目当前灵感并保存 story tags（不跳转页面）
    async function handlePinInspiration() {
        if (!museResult.value) {
            message.warning(i18n.global.t('views.world.needGeneratedOrSelectedInspiration'));
            return;
        }
        if (!projectStore.currentProject) {
            message.warning(i18n.global.t('common.selectProjectFirst'));
            return;
        }

        try {
            await ensureCurrentInspirationBound();
            message.success('灵感已采纳到当前项目');
        } catch (e) {
            console.warn('采纳灵感失败:', e);
            message.error('采纳灵感失败');
        }
    }

    async function proceedToSynopsis(options: GoToSynopsisOptions = {}) {
        const logline = extractLoglineFromInspiration(museResult.value);
        if (projectStore.currentProject) {
            try {
                await ensureCurrentInspirationBound();
            } catch (e) {
                console.warn('进入梗概页前绑定灵感失败:', e);
            }
        }

        const adoptionPayload = {
            projectName: projectStore.currentProject,
            logline,
            inspiration: museResult.value,
            pov: selectedPov.value,
            lengthHint: selectedLength.value,
            autoGenerateSynopsis: !!options.autoGenerateSynopsis,
            autoGenerateBeats: !!options.autoGenerateBeats,
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
        bus.off('inspiration-bind-changed', handleInspirationBindChanged);
    });

    onMounted(() => {
        bus.on('muse-refresh', refreshCurrentInspiration);
        bus.on('inspiration-bind-changed', handleInspirationBindChanged);
    });

    return {
        museInput,
        museLoading,
        museResult,
        museHistoryRef,
        isGenerating,
        isHistoryCollapsed,
        currentInspirationId,
        isCurrentInspirationBound,
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
