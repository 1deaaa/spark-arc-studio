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

export function useAIModelManager(platforms, syncAiStoreSilently) {
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
    const newModel = ref({
        modelName: '',
        displayName: '',
        extraBody: '',
        temperatureEnabled: false,
        temperature: 0.7,
    });
    const editingModel = ref({
        id: null,
        modelName: '',
        displayName: '',
        extraBody: '',
        temperatureEnabled: false,
        temperature: 0.7,
    });
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
    const TEMP_MIN = 0.3;
    const TEMP_MAX = 1.5;

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

    function notifyAiStoreSync() {
        syncAiStoreSilently?.();
    }

    function findPlatformById(platformId) {
        return platforms.value.find(p => p.platform_id === platformId) || null;
    }

    function parseExtraBodyForView(extraBodyText) {
        const raw = (extraBodyText || '').trim();
        if (!raw) return null;
        return parseExtraBodyObject(raw);
    }

    function findModelInPlatform(platformId, modelId) {
        const plat = findPlatformById(platformId);
        if (!plat?.models) return { plat: null, model: null, index: -1 };
        const index = plat.models.findIndex(m => m.model_id === modelId);
        return {
            plat,
            model: index >= 0 ? plat.models[index] : null,
            index
        };
    }

    // === 模型操作 ===
    function openAddModelModal(plat) {
        currentPlatform.value = plat;
        newModel.value = {
            modelName: '',
            displayName: '',
            extraBody: '',
            temperatureEnabled: false,
            temperature: 0.7,
        };
        searchKeyword.value = '';
        showAddModelModal.value = true;

        const cached = modelCache.value[plat.platform_id];
        remoteModels.value = cached ? cached.models : [];

        fetchRemoteModels(false);
    }

    function parseExtraBodyObject(extraBodyText) {
        const raw = (extraBodyText || '').trim();
        if (!raw) return {};
        const parsed = JSON.parse(raw);
        if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) {
            throw new Error('Extra Body 必须是 JSON 对象');
        }
        return parsed;
    }

    function buildExtraBodyForNewModel() {
        const extraObj = parseExtraBodyObject(newModel.value.extraBody);

        return Object.keys(extraObj).length > 0 ? JSON.stringify(extraObj) : null;
    }

    function buildTemperatureForNewModel() {
        if (!newModel.value.temperatureEnabled) return undefined;
        const temp = Number(newModel.value.temperature);
        if (!Number.isFinite(temp) || temp < TEMP_MIN || temp > TEMP_MAX) {
            throw new Error(`Temperature 必须在 ${TEMP_MIN} 到 ${TEMP_MAX} 之间`);
        }
        return temp;
    }

    function onNewModelTemperatureToggle(enabled) {
        return enabled;
    }

    function onEditModelTemperatureToggle(enabled) {
        return enabled;
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
        let modelTemp = model.temperature;
        let extraObj = null;
        if (model.extra_body != null) {
            if (typeof model.extra_body === 'object') {
                extraObj = { ...model.extra_body };
            } else if (typeof model.extra_body === 'string' && model.extra_body !== 'null') {
                try {
                    extraObj = JSON.parse(model.extra_body);
                } catch {
                    extraObj = null;
                }
            }
        }

        if ((modelTemp === null || modelTemp === undefined) && extraObj && Object.prototype.hasOwnProperty.call(extraObj, 'temperature')) {
            const legacyTemp = Number(extraObj.temperature);
            if (Number.isFinite(legacyTemp)) {
                modelTemp = legacyTemp;
            }
            delete extraObj.temperature;
            extraBodyStr = Object.keys(extraObj).length > 0 ? JSON.stringify(extraObj, null, 2) : '';
        }

        editingModel.value = {
            id: model.model_id,
            modelName: model.model_name,
            displayName: model.display_name,
            extraBody: extraBodyStr,
            temperatureEnabled: modelTemp !== null && modelTemp !== undefined,
            temperature: modelTemp ?? 0.7,
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
            const extraBodyPayload = buildExtraBodyForNewModel();
            const res = await fetchWithAuth(`/api/ai/platform/${currentPlatform.value.platform_id}/test-model`, {
                method: 'POST',
                body: JSON.stringify({
                    model_name: newModel.value.modelName,
                    extra_body: extraBodyPayload
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
            const extraBodyPayload = buildExtraBodyForNewModel();
            const temperature = buildTemperatureForNewModel();
            const displayName = newModel.value.displayName || newModel.value.modelName;
            const targetPlatform = currentPlatform.value;
            let result;
            if (currentPlatform.value.is_sys) {
                result = await adminCreateSysModel(
                    currentPlatform.value.platform_id,
                    newModel.value.modelName,
                    displayName,
                    extraBodyPayload,
                    temperature,
                );
            } else {
                result = await createModel(
                    currentPlatform.value.platform_id,
                    newModel.value.modelName,
                    displayName,
                    extraBodyPayload,
                    temperature,
                );
            }
            targetPlatform.models = targetPlatform.models || [];
            targetPlatform.models.push({
                model_id: result.id,
                model_name: newModel.value.modelName,
                display_name: displayName,
                extra_body: parseExtraBodyForView(newModel.value.extraBody),
                temperature: temperature ?? null
            });
            showAddModelModal.value = false;
            notifyAiStoreSync();
        } catch (e) {
            message.error(e.message || '添加失败');
        } finally {
            saving.value = false;
        }
    }

    async function handleUpdateModel() {
        saving.value = true;
        try {
            let temperature = null;
            if (editingModel.value.temperatureEnabled) {
                const temp = Number(editingModel.value.temperature);
                if (!Number.isFinite(temp) || temp < TEMP_MIN || temp > TEMP_MAX) {
                    throw new Error(`Temperature 必须在 ${TEMP_MIN} 到 ${TEMP_MAX} 之间`);
                }
                temperature = temp;
            }
            const targetModelId = editingModel.value.id;
            const displayName = editingModel.value.displayName;
            const extraBodyInput = editingModel.value.extraBody || null;
            if (currentPlatform.value?.is_sys) {
                await adminUpdateSysModel(
                    targetModelId,
                    displayName,
                    extraBodyInput,
                    { includeTemperature: true, temperature }
                );
            } else {
                await updateModel(
                    targetModelId,
                    displayName,
                    extraBodyInput,
                    { includeTemperature: true, temperature }
                );
            }
            const { model } = findModelInPlatform(currentPlatform.value?.platform_id, targetModelId);
            if (model) {
                model.display_name = displayName;
                model.extra_body = parseExtraBodyForView(editingModel.value.extraBody);
                model.temperature = temperature;
            }
            showEditModelModal.value = false;
            notifyAiStoreSync();
        } catch (e) {
            message.error(e.message || '更新失败');
        } finally {
            saving.value = false;
        }
    }

    async function doDeleteModel(modelId, plat, isSys = false) {
        const { model, index } = findModelInPlatform(plat?.platform_id, modelId);
        if (plat && index >= 0) {
            plat.models.splice(index, 1);
        }
        delete speedResults.value[modelId];
        try {
            if (isSys) {
                await adminDeleteSysModel(modelId);
            } else {
                await deleteModel(modelId);
            }
            notifyAiStoreSync();
        } catch (e) {
            if (plat && index >= 0 && model) {
                plat.models.splice(index, 0, model);
            }
            message.error(e.message || '删除失败');
        }
    }

    function confirmDeleteModel(model, plat) {
        dialog.warning({
            title: '删除模型',
            content: `确定要删除模型「${model.display_name}」吗？`,
            positiveText: '删除',
            negativeText: '取消',
            onPositiveClick: () => doDeleteModel(model.model_id, plat, plat.is_sys)
        });
    }

    // === 内联编辑 ===
    function startEditDisplayName(plat, model) {
        editingDisplayNameModelId.value = model.model_id;
        editingDisplayNameValue.value = model.display_name;
        editingDisplayNamePlatform.value = plat;
        nextTick(() => {
            if (inlineInputRef.value) {
                // Check if inlineInputRef.value is an array or component instance and access focus accordingly
                const el = Array.isArray(inlineInputRef.value) ? inlineInputRef.value[0] : inlineInputRef.value;
                if (el && typeof el.focus === 'function') {
                    el.focus();
                }
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
            model.display_name = newName;
            notifyAiStoreSync();
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
        TEMP_MIN,
        TEMP_MAX,
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
        onNewModelTemperatureToggle,
        onEditModelTemperatureToggle,
        testModelConnection,
        speedTestModel,
        testExistingModel,
        handleAddModel,
        handleUpdateModel,
        confirmDeleteModel,
        doDeleteModel,
        startEditDisplayName,
        cancelEditDisplayName,
        confirmEditDisplayName
    };
}
