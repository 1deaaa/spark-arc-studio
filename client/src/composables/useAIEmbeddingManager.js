/**
 * AI Embedding 管理 Composable
 * 从 AIManager.vue 提取的 Embedding CRUD 和选择逻辑
 */
import { ref, computed } from 'vue';
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

export function useAIEmbeddingManager(platforms, loadDataCallback) {
    const message = useMessage();
    const dialog = useDialog();

    // === 状态 ===
    const embeddingSelection = ref({ platform_id: null, model_id: null });
    const embeddingSaving = ref(false);
    const showAddEmbeddingModal = ref(false);
    const showEditEmbeddingModal = ref(false);
    const embeddingCurrentPlatform = ref(null);
    const newEmbedding = ref({ modelName: '', displayName: '', extraBody: '' });
    const editingEmbedding = ref({ id: null, modelName: '', displayName: '', extraBody: '' });

    const currentEmbeddingName = computed(() => {
        if (!embeddingSelection.value.model_id) return '';
        for (const p of platforms.value) {
            if (!p.embeddings) continue;
            const found = p.embeddings.find(m => m.model_id === embeddingSelection.value.model_id);
            if (found) return found.display_name;
        }
        return '';
    });

    // === 加载 Embedding 数据 ===
    async function loadEmbeddings() {
        const [embeddingPlatforms, embeddingSelectionRes, embeddingStatus] = await Promise.all([
            fetchPlatformsWithEmbeddings(),
            fetchUserEmbeddingSelection(),
            fetchEmbeddingStatus()
        ]);

        // 合并 embeddings 到 platforms
        const platformMap = new Map(platforms.value.map(p => [p.platform_id, p]));
        embeddingPlatforms.forEach(ep => {
            if (platformMap.has(ep.platform_id)) {
                platformMap.get(ep.platform_id).embeddings = ep.embeddings || [];
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
            embeddingSelection.value = {
                platform_id: embeddingSelectionRes.current.platform_id,
                model_id: embeddingSelectionRes.current.model_id
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
            } catch (e) {
                console.warn('自动设置 Embedding 失败:', e);
            }
        }
    }

    // === Embedding CRUD ===
    function openAddEmbeddingModal(plat) {
        embeddingCurrentPlatform.value = plat;
        newEmbedding.value = { modelName: '', displayName: '', extraBody: '' };
        showAddEmbeddingModal.value = true;
    }

    function openEditEmbeddingModal(plat, model) {
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
        embeddingSaving.value = true;
        try {
            if (embeddingCurrentPlatform.value?.is_sys) {
                await adminCreateSysEmbedding(
                    embeddingCurrentPlatform.value.platform_id,
                    newEmbedding.value.modelName,
                    newEmbedding.value.displayName || newEmbedding.value.modelName,
                    newEmbedding.value.extraBody || null
                );
            } else {
                await createEmbedding(
                    embeddingCurrentPlatform.value.platform_id,
                    newEmbedding.value.modelName,
                    newEmbedding.value.displayName || newEmbedding.value.modelName,
                    newEmbedding.value.extraBody || null
                );
            }
            message.success('Embedding 添加成功');
            showAddEmbeddingModal.value = false;
            if (loadDataCallback) await loadDataCallback();
        } catch (e) {
            message.error(e.message || '添加失败');
        } finally {
            embeddingSaving.value = false;
        }
    }

    async function handleUpdateEmbedding() {
        embeddingSaving.value = true;
        try {
            if (embeddingCurrentPlatform.value?.is_sys) {
                await adminUpdateSysEmbedding(
                    editingEmbedding.value.id,
                    editingEmbedding.value.displayName,
                    editingEmbedding.value.extraBody || null
                );
            } else {
                await updateEmbedding(
                    editingEmbedding.value.id,
                    editingEmbedding.value.displayName,
                    editingEmbedding.value.extraBody || null
                );
            }
            if (loadDataCallback) await loadDataCallback();
            message.success('Embedding 更新成功');
            showEditEmbeddingModal.value = false;
        } catch (e) {
            message.error(e.message || '更新失败');
        } finally {
            embeddingSaving.value = false;
        }
    }

    async function doDeleteEmbedding(modelId, isSys = false) {
        try {
            if (isSys) {
                await adminDeleteSysEmbedding(modelId);
            } else {
                await deleteEmbedding(modelId);
            }
            if (loadDataCallback) await loadDataCallback();
            message.success('Embedding 已删除');
        } catch (e) {
            message.error(e.message || '删除失败');
        }
    }

    async function testEmbeddingModel(plat, model) {
        try {
            const res = await testEmbedding(plat.platform_id, model.model_name);
            dialog.success({
                title: `Embedding 测试成功: ${model.display_name}`,
                content: `向量维度: ${res.response?.dims ?? res.dims ?? '未知'}`,
                positiveText: '确定'
            });
        } catch (e) {
            dialog.error({
                title: 'Embedding 测试失败',
                content: e.message,
                positiveText: '关闭'
            });
        }
    }

    async function saveUserEmbeddingSelection(platform_id, model_id) {
        embeddingSaving.value = true;
        try {
            const res = await apiSaveUserEmbeddingSelection(platform_id, model_id);
            if (res) {
                embeddingSelection.value = {
                    platform_id: res.platform_id,
                    model_id: res.model_id
                };
                message.success('已设为默认 Embedding');
            }
            return res;
        } catch (e) {
            message.error(e.message || '设置失败');
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
        doDeleteEmbedding,
        testEmbeddingModel,
        saveUserEmbeddingSelection
    };
}
