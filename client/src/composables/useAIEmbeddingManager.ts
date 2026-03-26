/**
 * AI Embedding 管理 Composable
 * 从 AIManager.vue 提取的 Embedding CRUD 和选择逻辑
 */
import { ref, computed, type Ref } from 'vue';
import { useMessage, useDialog } from 'naive-ui';
import {
    fetchPlatformsWithEmbeddings,
    fetchUserEmbeddingSelection,
    saveUserEmbeddingSelection as apiSaveUserEmbeddingSelection,
    fetchEmbeddingStatus,
    createEmbedding,
    updateEmbedding,
    deleteEmbedding,
    testEmbedding,
    adminCreateSysEmbedding,
    adminUpdateSysEmbedding,
    adminDeleteSysEmbedding
} from '../services/api';
import type {
    AiEmbeddingItem,
    AiPlatform,
    ApiId,
    EmbeddingSelectionCurrent,
    JsonObject,
} from '../services/aiContracts';

type EmbeddingSelectionState = { platform_id: ApiId | null; model_id: ApiId | null };

type NewEmbeddingForm = {
    modelName: string;
    displayName: string;
    extraBody: string;
};

type EditingEmbeddingForm = {
    id: ApiId | null;
    modelName: string;
    displayName: string;
    extraBody: string;
};

function getErrorMessage(error: unknown): string {
    if (error instanceof Error) return error.message;
    return String(error || '未知错误');
}

function getEmbeddingDims(result: { response: unknown; dims?: number }): number | null {
    if (typeof result.dims === 'number') return result.dims;
    if (result.response && typeof result.response === 'object' && 'dims' in result.response) {
        const dims = (result.response as { dims?: unknown }).dims;
        return typeof dims === 'number' ? dims : null;
    }
    return null;
}

export function useAIEmbeddingManager(platforms: Ref<AiPlatform[]>, syncAiStoreSilently?: () => void) {
    const message = useMessage();
    const dialog = useDialog();

    // === 状态 ===
    const embeddingSelection = ref<EmbeddingSelectionState>({ platform_id: null, model_id: null });
    const embeddingSaving = ref(false);
    const showAddEmbeddingModal = ref(false);
    const showEditEmbeddingModal = ref(false);
    const embeddingCurrentPlatform = ref<AiPlatform | null>(null);
    const newEmbedding = ref<NewEmbeddingForm>({ modelName: '', displayName: '', extraBody: '' });
    const editingEmbedding = ref<EditingEmbeddingForm>({ id: null, modelName: '', displayName: '', extraBody: '' });

    const currentEmbeddingName = computed(() => {
        if (!embeddingSelection.value.model_id) return '';
        for (const p of platforms.value) {
            if (!p.embeddings) continue;
            const found = p.embeddings.find(m => m.model_id === embeddingSelection.value.model_id);
            if (found) return found.display_name;
        }
        return '';
    });

    function notifyAiStoreSync() {
        syncAiStoreSilently?.();
    }

    function parseExtraBodyForView(extraBodyText: string) {
        const raw = (extraBodyText || '').trim();
        if (!raw) return null;
        return JSON.parse(raw) as JsonObject;
    }

    function findEmbeddingInPlatform(platformId: ApiId | null | undefined, modelId: ApiId | null | undefined) {
        const plat = platforms.value.find(p => p.platform_id === platformId) || null;
        if (!plat?.embeddings) return { plat: null, model: null, index: -1 };
        const index = plat.embeddings.findIndex(m => m.model_id === modelId);
        return {
            plat,
            model: index >= 0 ? plat.embeddings[index] : null,
            index
        };
    }

    // === 加载 Embedding 数据 ===
    async function loadEmbeddings() {
        const [embeddingPlatforms, embeddingSelectionRes, embeddingStatus] = await Promise.all([
            fetchPlatformsWithEmbeddings(),
            fetchUserEmbeddingSelection(),
            fetchEmbeddingStatus()
        ]);

        // 合并 embeddings 到 platforms
        const platformMap = new Map<ApiId, AiPlatform>(platforms.value.map((p) => [p.platform_id, p]));
        embeddingPlatforms.forEach(ep => {
            if (platformMap.has(ep.platform_id)) {
                const target = platformMap.get(ep.platform_id);
                if (target) {
                    target.embeddings = ep.embeddings || [];
                }
            } else {
                platformMap.set(ep.platform_id, {
                    ...ep,
                    models: [],
                    embeddings: ep.embeddings || []
                });
            }
        });
        platforms.value = Array.from(platformMap.values());

        if (embeddingSelectionRes && embeddingSelectionRes.current) {
            const current = embeddingSelectionRes.current as EmbeddingSelectionCurrent;
            embeddingSelection.value = {
                platform_id: current.platform_id,
                model_id: current.model_id
            };
        } else if (embeddingStatus && embeddingStatus.recommended) {
            try {
                const res = await apiSaveUserEmbeddingSelection(
                    embeddingStatus.recommended.platform_id,
                    embeddingStatus.recommended.model_id
                );
                if (res) {
                    embeddingSelection.value = {
                        platform_id: res.platform_id,
                        model_id: res.model_id
                    };
                }
            } catch (e: unknown) {
                console.warn('自动设置 Embedding 失败:', e);
            }
        }
    }

    // === Embedding CRUD ===
    function openAddEmbeddingModal(plat: AiPlatform) {
        embeddingCurrentPlatform.value = plat;
        newEmbedding.value = { modelName: '', displayName: '', extraBody: '' };
        showAddEmbeddingModal.value = true;
    }

    function openEditEmbeddingModal(plat: AiPlatform, model: AiEmbeddingItem) {
        embeddingCurrentPlatform.value = plat;
        let extraBodyStr = '';
        if (model.extra_body != null) {
            if (typeof model.extra_body === 'object') {
                extraBodyStr = JSON.stringify(model.extra_body, null, 2);
            } else if (typeof model.extra_body === 'string' && model.extra_body !== 'null') {
                extraBodyStr = model.extra_body;
            }
        }
        editingEmbedding.value = {
            id: model.model_id,
            modelName: model.model_name,
            displayName: model.display_name,
            extraBody: extraBodyStr
        };
        showEditEmbeddingModal.value = true;
    }

    async function handleAddEmbedding() {
        if (!newEmbedding.value.modelName) {
            message.warning('请填写 Embedding 模型标识');
            return;
        }
        if (!embeddingCurrentPlatform.value) {
            message.warning('请先选择平台');
            return;
        }
        embeddingSaving.value = true;
        try {
            const targetPlatform = embeddingCurrentPlatform.value;
            const displayName = newEmbedding.value.displayName || newEmbedding.value.modelName;
            let result;
            if (embeddingCurrentPlatform.value?.is_sys) {
                result = await adminCreateSysEmbedding(
                    embeddingCurrentPlatform.value.platform_id,
                    newEmbedding.value.modelName,
                    displayName,
                    newEmbedding.value.extraBody || null
                );
            } else {
                result = await createEmbedding(
                    embeddingCurrentPlatform.value.platform_id,
                    newEmbedding.value.modelName,
                    displayName,
                    newEmbedding.value.extraBody || null
                );
            }
            targetPlatform.embeddings = targetPlatform.embeddings || [];
            targetPlatform.embeddings.push({
                model_id: result.id,
                model_name: newEmbedding.value.modelName,
                display_name: displayName,
                extra_body: parseExtraBodyForView(newEmbedding.value.extraBody)
            });
            showAddEmbeddingModal.value = false;
            notifyAiStoreSync();
        } catch (e: unknown) {
            message.error(getErrorMessage(e) || '添加失败');
        } finally {
            embeddingSaving.value = false;
        }
    }

    async function handleUpdateEmbedding() {
        if (!embeddingCurrentPlatform.value) {
            message.warning('请先选择平台');
            return;
        }
        if (editingEmbedding.value.id == null) {
            message.warning('无效的 Embedding 目标');
            return;
        }
        embeddingSaving.value = true;
        try {
            const targetModelId = editingEmbedding.value.id;
            const displayName = editingEmbedding.value.displayName;
            const extraBodyInput = editingEmbedding.value.extraBody || null;
            if (embeddingCurrentPlatform.value?.is_sys) {
                await adminUpdateSysEmbedding(
                    targetModelId,
                    displayName,
                    extraBodyInput
                );
            } else {
                await updateEmbedding(
                    targetModelId,
                    displayName,
                    extraBodyInput
                );
            }
            const { model } = findEmbeddingInPlatform(embeddingCurrentPlatform.value?.platform_id, targetModelId);
            if (model) {
                model.display_name = displayName;
                model.extra_body = parseExtraBodyForView(editingEmbedding.value.extraBody);
            }
            showEditEmbeddingModal.value = false;
            notifyAiStoreSync();
        } catch (e: unknown) {
            message.error(getErrorMessage(e) || '更新失败');
        } finally {
            embeddingSaving.value = false;
        }
    }

    async function doDeleteEmbedding(modelId: ApiId, plat: AiPlatform, isSys = false) {
        const { model, index } = findEmbeddingInPlatform(plat?.platform_id, modelId);
        if (plat && index >= 0) {
            plat.embeddings = plat.embeddings || [];
            plat.embeddings.splice(index, 1);
        }
        try {
            if (isSys) {
                await adminDeleteSysEmbedding(modelId);
            } else {
                await deleteEmbedding(modelId);
            }
            notifyAiStoreSync();
        } catch (e: unknown) {
            if (plat && index >= 0 && model) {
                plat.embeddings = plat.embeddings || [];
                plat.embeddings.splice(index, 0, model);
            }
            message.error(getErrorMessage(e) || '删除失败');
        }
    }

    function confirmDeleteEmbedding(model: AiEmbeddingItem, plat: AiPlatform) {
        dialog.warning({
            title: '删除 Embedding',
            content: `确定要删除 Embedding「${model.display_name}」吗？`,
            positiveText: '删除',
            negativeText: '取消',
            onPositiveClick: () => doDeleteEmbedding(model.model_id, plat, plat.is_sys)
        });
    }

    async function testEmbeddingModel(plat: AiPlatform, model: AiEmbeddingItem) {
        try {
            const res = await testEmbedding(plat.platform_id, model.model_name);
            const dims = getEmbeddingDims(res);
            dialog.success({
                title: `Embedding 测试成功: ${model.display_name}`,
                content: `向量维度: ${dims ?? '未知'}`,
                positiveText: '确定'
            });
        } catch (e: unknown) {
            dialog.error({
                title: 'Embedding 测试失败',
                content: getErrorMessage(e),
                positiveText: '关闭'
            });
        }
    }

    async function saveUserEmbeddingSelection(platform_id: ApiId, model_id: ApiId) {
        embeddingSaving.value = true;
        try {
            const res = await apiSaveUserEmbeddingSelection(platform_id, model_id);
            if (res) {
                embeddingSelection.value = {
                    platform_id: res.platform_id,
                    model_id: res.model_id
                };
            }
            return res;
        } catch (e: unknown) {
            message.error(getErrorMessage(e) || '设置失败');
            throw e;
        } finally {
            embeddingSaving.value = false;
        }
    }

    return {
        // 状态
        embeddingSelection,
        embeddingSaving,
        showAddEmbeddingModal,
        showEditEmbeddingModal,
        embeddingCurrentPlatform,
        newEmbedding,
        editingEmbedding,
        currentEmbeddingName,
        // 方法
        loadEmbeddings,
        openAddEmbeddingModal,
        openEditEmbeddingModal,
        handleAddEmbedding,
        handleUpdateEmbedding,
        confirmDeleteEmbedding,
        doDeleteEmbedding,
        testEmbeddingModel,
        saveUserEmbeddingSelection
    };
}
