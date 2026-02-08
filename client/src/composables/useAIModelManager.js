/**
 * AI 模型管理 Composable
 * 从 AIManager.vue 提取的模型 CRUD、测速、内联编辑逻辑
 */
import { ref, computed, nextTick, onMounted } from 'vue';
import { useMessage, useDialog } from 'naive-ui';
import {
    fetchWithAuth,
    createModel,
    updateModel,
    deleteModel,
    adminCreateSysModel,
    adminUpdateSysModel,
    adminDeleteSysModel,
    getFriendlyErrorMessage
} from '../services/api';

export function useAIModelManager(loadDataCallback) {
    const message = useMessage();
    const dialog = useDialog();

    // === 状态 ===
    const saving = ref(false);
    const fetching = ref(false);
    const testing = ref(false);
    const testingModelId = ref(null);
    const speedTestingModelIds = ref(new Set());
    const speedResults = ref({});

    // 弹窗状态
    const showAddModelModal = ref(false);
    const showEditModelModal = ref(false);
    const currentPlatform = ref(null);
    const newModel = ref({ modelName: '', displayName: '', extraBody: '' });
    const editingModel = ref({ id: null, modelName: '', displayName: '', extraBody: '' });
    const searchKeyword = ref('');
    const remoteModels = ref([]);

    // 内联编辑
    const editingDisplayNameModelId = ref(null);
    const editingDisplayNameValue = ref('');
    const editingDisplayNamePlatform = ref(null);
    const inlineInputRef = ref(null);

    // 缓存
    const modelCache = ref({});
    const CACHE_TTL_MS = 5 * 60 * 1000;
    const CACHE_KEY = 'sparkarc_speed_test_results';

    const filteredRemoteModels = computed(() => {
        if (!searchKeyword.value) return remoteModels.value;
        const keyword = searchKeyword.value.toLowerCase();
        return remoteModels.value.filter(m => m.toLowerCase().includes(keyword));
    });

    // === 缓存处理 ===
    function saveSpeedResultsToCache() {
        localStorage.setItem(CACHE_KEY, JSON.stringify(speedResults.value));
    }

    function loadSpeedResultsFromCache() {
        try {
            const cached = localStorage.getItem(CACHE_KEY);
            if (cached) {
                speedResults.value = JSON.parse(cached);
            }
        } catch (e) {
            console.error('加载测速缓存失败:', e);
        }
    }

    // === 模型操作 ===
    function openAddModelModal(plat) {
        currentPlatform.value = plat;
        newModel.value = { modelName: '', displayName: '', extraBody: '' };
        searchKeyword.value = '';
        showAddModelModal.value = true;

        const cached = modelCache.value[plat.platform_id];
        remoteModels.value = cached ? cached.models : [];

        fetchRemoteModels(false);
    }

    function openEditModelModal(plat, model) {
        currentPlatform.value = plat;
        let extraBodyStr = '';
        if (model.extra_body != null) {
            if (typeof model.extra_body === 'object') {
                extraBodyStr = JSON.stringify(model.extra_body, null, 2);
            } else if (typeof model.extra_body === 'string' && model.extra_body !== 'null') {
                extraBodyStr = model.extra_body;
            }
        }
        editingModel.value = {
            id: model.model_id,
            modelName: model.model_name,
            displayName: model.display_name,
            extraBody: extraBodyStr
        };
        showEditModelModal.value = true;
    }

    async function fetchRemoteModels(showError = true) {
        if (!currentPlatform.value) return;
        fetching.value = true;
        try {
            const res = await fetchWithAuth(`/api/ai/platform/${currentPlatform.value.platform_id}/list-models`, {
                method: 'POST'
            });
            if (!res.ok) {
                const err = await res.json();
                throw new Error(getFriendlyErrorMessage(err.detail, res.status));
            }
            const data = await res.json();
            const models = data.models || [];
            remoteModels.value = models;

            modelCache.value[currentPlatform.value.platform_id] = {
                models: models,
                timestamp: Date.now()
            };

            if (models.length === 0 && showError) {
                message.info('未能获取到模型列表');
            }
        } catch (e) {
            if (showError) {
                message.error(e.message);
            }
        } finally {
            fetching.value = false;
        }
    }

    function selectRemoteModel(modelName) {
        newModel.value.modelName = modelName;
        newModel.value.displayName = modelName;
    }

    async function testModelConnection() {
        if (!currentPlatform.value || !newModel.value.modelName) return;
        testing.value = true;
        try {
            const res = await fetchWithAuth(`/api/ai/platform/${currentPlatform.value.platform_id}/test-model`, {
                method: 'POST',
                body: JSON.stringify({
                    model_name: newModel.value.modelName,
                    extra_body: newModel.value.extraBody || null
                }),
                headers: { 'Content-Type': 'application/json' }
            });
            if (!res.ok) {
                const err = await res.json();
                throw new Error(getFriendlyErrorMessage(err.detail, res.status));
            }
            const data = await res.json();
            dialog.success({
                title: '连接测试成功',
                content: `模型响应: ${data.response}`,
                positiveText: '确定'
            });
        } catch (e) {
            dialog.error({
                title: '测试失败',
                content: e.message,
                positiveText: '关闭'
            });
        } finally {
            testing.value = false;
        }
    }

    async function speedTestModel(plat, model) {
        if (speedTestingModelIds.value.has(model.model_id)) return;

        speedTestingModelIds.value.add(model.model_id);
        speedResults.value[model.model_id] = { speed: 0, ftl: 0 };

        try {
            const response = await fetchWithAuth(`/api/ai/platform/${plat.platform_id}/speed-test`, {
                method: 'POST',
                body: JSON.stringify({ model_name: model.model_name }),
                headers: { 'Content-Type': 'application/json' }
            });

            if (!response.ok) {
                const err = await response.json();
                throw new Error(getFriendlyErrorMessage(err.detail, response.status));
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop();

                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        const data = JSON.parse(line.slice(6));
                        if (data.error) throw new Error(getFriendlyErrorMessage(data.error));

                        if (!speedResults.value[model.model_id]) {
                            speedResults.value[model.model_id] = { speed: 0, ftl: 0 };
                        }

                        if (data.type === 'first_token') {
                            speedResults.value[model.model_id].ftl = data.ftl;
                        } else if (data.type === 'update') {
                            speedResults.value[model.model_id].speed = data.speed;
                            saveSpeedResultsToCache();
                        } else if (data.type === 'final') {
                            speedResults.value[model.model_id] = {
                                speed: data.speed,
                                ftl: data.ftl
                            };
                            saveSpeedResultsToCache();
                        }
                    }
                }
            }
            if (speedResults.value[model.model_id]?.speed > 0) {
                message.success(`${model.display_name} 测速完成: ${speedResults.value[model.model_id].speed.toFixed(1)} char/s`);
            }
        } catch (e) {
            message.error(`${model.display_name} 测速失败: ${e.message}`);
            if (speedResults.value[model.model_id]?.speed === 0) {
                delete speedResults.value[model.model_id];
            }
        } finally {
            speedTestingModelIds.value.delete(model.model_id);
        }
    }

    async function testExistingModel(plat, model) {
        testingModelId.value = model.model_id;
        try {
            const res = await fetchWithAuth(`/api/ai/platform/${plat.platform_id}/test-model`, {
                method: 'POST',
                body: JSON.stringify({ model_name: model.model_name }),
                headers: { 'Content-Type': 'application/json' }
            });
            if (!res.ok) {
                const err = await res.json();
                throw new Error(getFriendlyErrorMessage(err.detail, res.status));
            }
            const data = await res.json();
            dialog.success({
                title: `测试成功: ${model.display_name}`,
                content: `模型响应: ${data.response}`,
                positiveText: '确定'
            });
        } catch (e) {
            dialog.error({
                title: '测试失败',
                content: e.message,
                positiveText: '关闭'
            });
        } finally {
            testingModelId.value = null;
        }
    }

    async function handleAddModel() {
        if (!newModel.value.modelName) {
            message.warning('请填写模型标识');
            return;
        }
        saving.value = true;
        try {
            if (currentPlatform.value.is_sys) {
                await adminCreateSysModel(
                    currentPlatform.value.platform_id,
                    newModel.value.modelName,
                    newModel.value.displayName || newModel.value.modelName,
                    newModel.value.extraBody || null
                );
            } else {
                await createModel(
                    currentPlatform.value.platform_id,
                    newModel.value.modelName,
                    newModel.value.displayName || newModel.value.modelName,
                    newModel.value.extraBody || null
                );
            }
            message.success('模型添加成功');
            showAddModelModal.value = false;
            if (loadDataCallback) await loadDataCallback();
        } catch (e) {
            message.error(e.message || '添加失败');
        } finally {
            saving.value = false;
        }
    }

    async function handleUpdateModel() {
        saving.value = true;
        try {
            if (currentPlatform.value?.is_sys) {
                await adminUpdateSysModel(
                    editingModel.value.id,
                    editingModel.value.displayName,
                    editingModel.value.extraBody || null
                );
            } else {
                await updateModel(
                    editingModel.value.id,
                    editingModel.value.displayName,
                    editingModel.value.extraBody || null
                );
            }
            if (loadDataCallback) await loadDataCallback();
            message.success('模型更新成功');
            showEditModelModal.value = false;
        } catch (e) {
            message.error(e.message || '更新失败');
        } finally {
            saving.value = false;
        }
    }

    async function doDeleteModel(modelId, isSys = false) {
        try {
            if (isSys) {
                await adminDeleteSysModel(modelId);
            } else {
                await deleteModel(modelId);
            }
            if (loadDataCallback) await loadDataCallback();
            message.success('模型已删除');
        } catch (e) {
            message.error(e.message || '删除失败');
        }
    }

    // === 内联编辑 ===
    function startEditDisplayName(plat, model) {
        editingDisplayNameModelId.value = model.model_id;
        editingDisplayNameValue.value = model.display_name;
        editingDisplayNamePlatform.value = plat;
        nextTick(() => {
            if (inlineInputRef.value) {
                inlineInputRef.value.focus();
            }
        });
    }

    function cancelEditDisplayName() {
        editingDisplayNameModelId.value = null;
        editingDisplayNameValue.value = '';
        editingDisplayNamePlatform.value = null;
    }

    async function confirmEditDisplayName(plat, model) {
        const newName = editingDisplayNameValue.value.trim();
        if (!newName || newName === model.display_name) {
            cancelEditDisplayName();
            return;
        }

        let extraBodyStr = null;
        if (model.extra_body) {
            if (typeof model.extra_body === 'object') {
                extraBodyStr = JSON.stringify(model.extra_body);
            } else {
                extraBodyStr = String(model.extra_body);
            }
        }

        try {
            if (plat.is_sys) {
                await adminUpdateSysModel(model.model_id, newName, extraBodyStr);
            } else {
                await updateModel(model.model_id, newName, extraBodyStr);
            }
            message.success('显示名称已更新');
            if (loadDataCallback) await loadDataCallback();
        } catch (e) {
            message.error(e.message || '更新失败');
        } finally {
            cancelEditDisplayName();
        }
    }

    onMounted(() => {
        loadSpeedResultsFromCache();
    });

    return {
        // 状态
        saving,
        fetching,
        testing,
        testingModelId,
        speedTestingModelIds,
        speedResults,
        // 弹窗
        showAddModelModal,
        showEditModelModal,
        currentPlatform,
        newModel,
        editingModel,
        searchKeyword,
        remoteModels,
        filteredRemoteModels,
        // 内联编辑
        editingDisplayNameModelId,
        editingDisplayNameValue,
        editingDisplayNamePlatform,
        inlineInputRef,
        // 方法
        openAddModelModal,
        openEditModelModal,
        fetchRemoteModels,
        selectRemoteModel,
        testModelConnection,
        speedTestModel,
        testExistingModel,
        handleAddModel,
        handleUpdateModel,
        doDeleteModel,
        startEditDisplayName,
        cancelEditDisplayName,
        confirmEditDisplayName
    };
}
