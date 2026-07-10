/**
 * AI 模型管理 Composable
 * 从 AIManager.vue 提取的模型 CRUD、测速、内联编辑逻辑
 */
import { ref, computed, nextTick, onMounted, type Ref } from 'vue';
import { useI18n } from 'vue-i18n';
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
import { consumeSSEReader } from '@/utils/streamingRuntime';
import type { AiModelItem, AiPlatform, ApiId, SpeedTestEvent, RemoteModelInfo } from '../services/aiContracts';
import {
    getModelModalities,
    isEmbeddingModel,
    isImageModel,
    isTextModel,
    normalizeModelModalities,
    type ModelModality,
} from '../services/modelModalities';
import {
    DEFAULT_IMAGE_GENERATION_ADAPTER,
    normalizeImageGenerationAdapter,
    type ImageGenerationAdapterKey,
} from '../services/imageGenerationAdapters';

type SpeedResult = { speed: number; ftl: number };

type ModelCacheRecord = {
    models: RemoteModelInfo[];
    timestamp: number;
};

type NewModelForm = {
    modelName: string;
    displayName: string;
    extraBody: string;
    inputModalities: ModelModality[];
    outputModalities: ModelModality[];
    imageAdapter: ImageGenerationAdapterKey;
    temperatureEnabled: boolean;
    temperature: number;
    maxContextTokens: number | null;
    maxOutputTokens: number | null;
    inputPricePerMillion: number | null;
    cachedInputPricePerMillion: number | null;
    outputPricePerMillion: number | null;
};

type EditingModelForm = {
    id: ApiId | null;
    modelName: string;
    displayName: string;
    extraBody: string;
    inputModalities: ModelModality[];
    outputModalities: ModelModality[];
    imageAdapter: ImageGenerationAdapterKey;
    temperatureEnabled: boolean;
    temperature: number;
    maxContextTokens: number | null;
    maxOutputTokens: number | null;
    inputPricePerMillion: number | null;
    cachedInputPricePerMillion: number | null;
    outputPricePerMillion: number | null;
};

function getErrorMessage(error: unknown): string {
    if (error instanceof Error) return error.message;
    return String(error || '未知错误');
}

async function extractDetailError(response: Response, fallback: string): Promise<string> {
    try {
        const payload = await response.json() as { detail?: string; error?: string };
        return getFriendlyErrorMessage(payload.detail || payload.error || fallback, response.status);
    } catch {
        return fallback;
    }
}

export function useAIModelManager(
    platforms: Ref<AiPlatform[]>,
    syncAiStoreSilently?: () => void,
    systemConfig?: Ref<{ billing_enabled?: boolean }>
) {
    const message = useMessage();
    const dialog = useDialog();
    const { t } = useI18n();

    // === 状态 ===
    const saving = ref(false);
    const fetching = ref(false);
    const testing = ref(false);
    const testingModelId = ref<ApiId | null>(null);
    const speedTestingModelIds = ref(new Set<ApiId>());
    const speedResults = ref<Record<string, SpeedResult>>({});

    // 弹窗状态
    const showAddModelModal = ref(false);
    const showEditModelModal = ref(false);
    const currentPlatform = ref<AiPlatform | null>(null);
    const newModel = ref<NewModelForm>({
        modelName: '',
        displayName: '',
        extraBody: '',
        ...defaultModelModalities(),
        imageAdapter: DEFAULT_IMAGE_GENERATION_ADAPTER,
        temperatureEnabled: false,
        temperature: 0.7,
        maxContextTokens: null,
        maxOutputTokens: null,
        inputPricePerMillion: null,
        cachedInputPricePerMillion: null,
        outputPricePerMillion: null,
    });
    const editingModel = ref<EditingModelForm>({
        id: null,
        modelName: '',
        displayName: '',
        extraBody: '',
        ...defaultModelModalities(),
        imageAdapter: DEFAULT_IMAGE_GENERATION_ADAPTER,
        temperatureEnabled: false,
        temperature: 0.7,
        maxContextTokens: null,
        maxOutputTokens: null,
        inputPricePerMillion: null,
        cachedInputPricePerMillion: null,
        outputPricePerMillion: null,
    });
    const searchKeyword = ref('');
    const remoteModels = ref<RemoteModelInfo[]>([]);

    // 内联编辑
    const editingDisplayNameModelId = ref<ApiId | null>(null);
    const editingDisplayNameValue = ref('');
    const editingDisplayNamePlatform = ref<AiPlatform | null>(null);
    const inlineInputRef = ref<unknown>(null);

    // 缓存
    const modelCache = ref<Record<string, ModelCacheRecord>>({});
    const CACHE_TTL_MS = 5 * 60 * 1000;
    const CACHE_KEY = 'sparkarc_speed_test_results';
    const TEMP_MIN = 0.3;
    const TEMP_MAX = 1.5;
    function defaultModelModalities() {
        return normalizeModelModalities();
    }

    function isPlainObject(value: unknown): value is Record<string, unknown> {
        return typeof value === 'object' && value !== null && !Array.isArray(value);
    }

    function extractImageAdapter(adapterValue: unknown): ImageGenerationAdapterKey {
        return normalizeImageGenerationAdapter(adapterValue);
    }

    function sanitizeExtraBodyObject(baseExtra: Record<string, unknown>): Record<string, unknown> {
        const cleaned: Record<string, unknown> = { ...baseExtra };
        if (isPlainObject(cleaned.image_generation)) {
            const imageConfig = { ...cleaned.image_generation };
            delete imageConfig.adapter;
            if (Object.keys(imageConfig).length > 0) {
                cleaned.image_generation = imageConfig;
            } else {
                delete cleaned.image_generation;
            }
        }
        return cleaned;
    }

    const filteredRemoteModels = computed(() => {
        if (!searchKeyword.value) return remoteModels.value;
        const keyword = searchKeyword.value.toLowerCase();
        return remoteModels.value.filter(m => m.id.toLowerCase().includes(keyword));
    });

    // === 缓存处理 ===
    function saveSpeedResultsToCache() {
        localStorage.setItem(CACHE_KEY, JSON.stringify(speedResults.value));
    }

    function loadSpeedResultsFromCache() {
        try {
            const cached = localStorage.getItem(CACHE_KEY);
            if (cached) {
                speedResults.value = JSON.parse(cached) as Record<string, SpeedResult>;
            }
        } catch (e: unknown) {
            console.error('加载测速缓存失败:', e);
        }
    }

    function notifyAiStoreSync() {
        syncAiStoreSilently?.();
    }

    function findPlatformById(platformId: ApiId | null | undefined) {
        return platforms.value.find(p => p.platform_id === platformId) || null;
    }

    function parseExtraBodyForView(extraBodyText: string) {
        const raw = (extraBodyText || '').trim();
        if (!raw) return null;
        const parsed = sanitizeExtraBodyObject(parseExtraBodyObject(raw));
        return Object.keys(parsed).length > 0 ? parsed : null;
    }

    function findModelInPlatform(platformId: ApiId | null | undefined, modelId: ApiId | null | undefined) {
        const plat = findPlatformById(platformId);
        if (!plat?.models) return { plat: null, model: null, index: -1 };
        const index = plat.models.findIndex(m => m.model_id === modelId);
        return {
            plat,
            model: index >= 0 ? plat.models[index] : null,
            index
        };
    }

    function isBillingEnabled() {
        return Boolean(systemConfig?.value?.billing_enabled);
    }

    function validateSystemModelPricing(inputPrice: number | null, cachedInputPrice: number | null, outputPrice: number | null) {
        if (!currentPlatform.value?.is_sys) return;
        if (!isBillingEnabled()) {
            if (inputPrice !== null || cachedInputPrice !== null || outputPrice !== null) {
                throw new Error(t('components.aiManager.messages.enableBillingBeforePricing'));
            }
            return;
        }
        if (inputPrice === null || cachedInputPrice === null || outputPrice === null) {
            throw new Error(t('components.aiManager.messages.modelPriceRequired'));
        }
    }

    // === 模型操作 ===
    function openAddModelModal(plat: AiPlatform) {
        currentPlatform.value = plat;
        newModel.value = {
            modelName: '',
            displayName: '',
            extraBody: '',
            ...defaultModelModalities(),
            imageAdapter: DEFAULT_IMAGE_GENERATION_ADAPTER,
            temperatureEnabled: false,
            temperature: 0.7,
            maxContextTokens: null,
            maxOutputTokens: null,
            inputPricePerMillion: null,
            cachedInputPricePerMillion: null,
            outputPricePerMillion: null,
        };
        searchKeyword.value = '';
        showAddModelModal.value = true;

        const cached = modelCache.value[String(plat.platform_id)];
        remoteModels.value = cached ? cached.models : [];

        fetchRemoteModels(false);
    }

    function parseExtraBodyObject(extraBodyText: string) {
        const raw = (extraBodyText || '').trim();
        if (!raw) return {};
        const parsed = JSON.parse(raw);
        if (!isPlainObject(parsed)) {
            throw new Error('Extra Body 必须是 JSON 对象');
        }
        return parsed;
    }

    function serializeExtraBodyForModel(extraBodyText: string) {
        const extraObj = sanitizeExtraBodyObject(parseExtraBodyObject(extraBodyText));
        return Object.keys(extraObj).length > 0 ? JSON.stringify(extraObj) : null;
    }

    function imageAdapterForModel(model: NewModelForm | EditingModelForm, adapter: ImageGenerationAdapterKey) {
        return isImageModel(model) ? adapter : null;
    }

    function buildExtraBodyForNewModel() {
        return serializeExtraBodyForModel(newModel.value.extraBody);
    }

    function buildExtraBodyForEditingModel() {
        return serializeExtraBodyForModel(editingModel.value.extraBody);
    }

    function buildTemperatureForNewModel() {
        if (!isTextModel(newModel.value)) return undefined;
        if (!newModel.value.temperatureEnabled) return undefined;
        const temp = Number(newModel.value.temperature);
        if (!Number.isFinite(temp) || temp < TEMP_MIN || temp > TEMP_MAX) {
            throw new Error(`Temperature 必须在 ${TEMP_MIN} 到 ${TEMP_MAX} 之间`);
        }
        return temp;
    }

    function onNewModelTemperatureToggle(enabled: boolean) {
        return enabled;
    }

    function onEditModelTemperatureToggle(enabled: boolean) {
        return enabled;
    }

    function openEditModelModal(plat: AiPlatform, model: AiModelItem) {
        currentPlatform.value = plat;
        let rawExtraObj: Record<string, unknown> | null = null;
        if (model.extra_body != null) {
            if (typeof model.extra_body === 'object') {
                rawExtraObj = { ...model.extra_body };
            } else if (typeof model.extra_body === 'string' && model.extra_body !== 'null') {
                try {
                    const parsed = JSON.parse(model.extra_body);
                    rawExtraObj = isPlainObject(parsed) ? parsed : null;
                } catch {
                    rawExtraObj = null;
                }
            }
        }
        let modelTemp = model.temperature;
        let extraObj: Record<string, unknown> | null = rawExtraObj ? sanitizeExtraBodyObject(rawExtraObj) : null;

        if ((modelTemp === null || modelTemp === undefined) && extraObj && Object.prototype.hasOwnProperty.call(extraObj, 'temperature')) {
            const legacyTemp = Number(extraObj.temperature);
            if (Number.isFinite(legacyTemp)) {
                modelTemp = legacyTemp;
            }
            delete extraObj.temperature;
        }
        const extraBodyStr = extraObj && Object.keys(extraObj).length > 0 ? JSON.stringify(extraObj, null, 2) : '';

        const modalities = getModelModalities(model);
        editingModel.value = {
            id: model.model_id,
            modelName: model.model_name,
            displayName: model.display_name,
            extraBody: extraBodyStr,
            ...modalities,
            imageAdapter: extractImageAdapter(model.image_generation_adapter),
            temperatureEnabled: modelTemp !== null && modelTemp !== undefined,
            temperature: modelTemp ?? 0.7,
            maxContextTokens: model.max_context_tokens ?? null,
            maxOutputTokens: model.max_output_tokens ?? null,
            inputPricePerMillion: model.sys_credit_input_price_per_million ?? null,
            cachedInputPricePerMillion: model.sys_credit_cached_input_price_per_million ?? null,
            outputPricePerMillion: model.sys_credit_output_price_per_million ?? null,
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
                throw new Error(await extractDetailError(res, '获取远程模型列表失败'));
            }
            const data = await res.json() as { models?: RemoteModelInfo[] };
            const models = data.models || [];
            remoteModels.value = models;

            modelCache.value[String(currentPlatform.value.platform_id)] = {
                models: models,
                timestamp: Date.now()
            };

            if (models.length === 0 && showError) {
                message.info('未能获取到模型列表');
            }
        } catch (e: unknown) {
            if (showError) {
                message.error(getErrorMessage(e));
            }
        } finally {
            fetching.value = false;
        }
    }

    function selectRemoteModel(modelInfo: RemoteModelInfo) {
        newModel.value.modelName = modelInfo.id;
        newModel.value.displayName = modelInfo.id;
        // 自动填充从远程获取的 token 上限
        newModel.value.maxContextTokens = modelInfo.max_context_tokens ?? null;
        newModel.value.maxOutputTokens = modelInfo.max_output_tokens ?? null;
    }

    async function testModelConnection() {
        if (!currentPlatform.value || !newModel.value.modelName) return;
        if (isImageModel(newModel.value)) {
            message.info(t('components.aiManager.messages.imageModelTestPending'));
            return;
        }
        testing.value = true;
        try {
            const extraBodyPayload = buildExtraBodyForNewModel();
            const endpoint = isEmbeddingModel(newModel.value) ? 'test-embedding' : 'test-model';
            const res = await fetchWithAuth(`/api/ai/platform/${currentPlatform.value.platform_id}/${endpoint}`, {
                method: 'POST',
                body: JSON.stringify({
                    model_name: newModel.value.modelName,
                    extra_body: extraBodyPayload
                }),
                headers: { 'Content-Type': 'application/json' }
            });
            if (!res.ok) {
                throw new Error(await extractDetailError(res, '模型连接测试失败'));
            }
            const data = await res.json() as { response?: unknown };
            dialog.success({
                title: '连接测试成功',
                content: `模型响应: ${String(data.response ?? '')}`,
                positiveText: '确定'
            });
        } catch (e: unknown) {
            dialog.error({
                title: '测试失败',
                content: getErrorMessage(e),
                positiveText: '关闭'
            });
        } finally {
            testing.value = false;
        }
    }

    async function speedTestModel(plat: AiPlatform, model: AiModelItem) {
        if (!isTextModel(model)) return;
        if (speedTestingModelIds.value.has(model.model_id)) return;

        const modelKey = String(model.model_id);

        speedTestingModelIds.value.add(model.model_id);
        speedResults.value[modelKey] = { speed: 0, ftl: 0 };

        try {
            const response = await fetchWithAuth(`/api/ai/platform/${plat.platform_id}/speed-test`, {
                method: 'POST',
                body: JSON.stringify({ model_name: model.model_name }),
                headers: { 'Content-Type': 'application/json' }
            });

            if (!response.ok) {
                throw new Error(await extractDetailError(response, '测速失败'));
            }

            if (!response.body) {
                throw new Error('测速接口未返回流式响应');
            }

            const reader = response.body.getReader();
            await consumeSSEReader(reader, {
                onEvent: async (evt) => {
                    if (!evt?.data) return;
                    const data = JSON.parse(evt.data) as SpeedTestEvent;
                    if ('error' in data) {
                        throw new Error(getFriendlyErrorMessage(data.error));
                    }

                    if (!speedResults.value[modelKey]) {
                        speedResults.value[modelKey] = { speed: 0, ftl: 0 };
                    }

                    if (data.type === 'first_token') {
                        speedResults.value[modelKey].ftl = data.ftl;
                    } else if (data.type === 'update') {
                        speedResults.value[modelKey].speed = data.speed;
                        saveSpeedResultsToCache();
                    } else if (data.type === 'final') {
                        speedResults.value[modelKey] = {
                            speed: data.speed,
                            ftl: data.ftl
                        };
                        saveSpeedResultsToCache();
                    }
                }
            });
            if (speedResults.value[modelKey]?.speed > 0) {
                message.success(`${model.display_name} 测速完成: ${speedResults.value[modelKey].speed.toFixed(1)} token/s`);
            }
        } catch (e: unknown) {
            message.error(`${model.display_name} 测速失败: ${getErrorMessage(e)}`);
            if (speedResults.value[modelKey]?.speed === 0) {
                delete speedResults.value[modelKey];
            }
        } finally {
            speedTestingModelIds.value.delete(model.model_id);
        }
    }

    async function testExistingModel(plat: AiPlatform, model: AiModelItem) {
        if (!isTextModel(model)) return;
        testingModelId.value = model.model_id;
        try {
            const res = await fetchWithAuth(`/api/ai/platform/${plat.platform_id}/test-model`, {
                method: 'POST',
                body: JSON.stringify({ model_name: model.model_name }),
                headers: { 'Content-Type': 'application/json' }
            });
            if (!res.ok) {
                throw new Error(await extractDetailError(res, '模型测试失败'));
            }
            const data = await res.json() as { response?: unknown };
            dialog.success({
                title: `测试成功: ${model.display_name}`,
                content: `模型响应: ${String(data.response ?? '')}`,
                positiveText: '确定'
            });
        } catch (e: unknown) {
            dialog.error({
                title: '测试失败',
                content: getErrorMessage(e),
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
        if (!currentPlatform.value) {
            message.warning('请先选择平台');
            return;
        }
        saving.value = true;
        try {
            const displayName = newModel.value.displayName || newModel.value.modelName;
            const targetPlatform = currentPlatform.value;
            const modalities = getModelModalities(newModel.value);
            const extraBodyPayload = buildExtraBodyForNewModel();
            const textModel = isTextModel(newModel.value);
            const temperature = buildTemperatureForNewModel();
            const imageGenerationAdapter = imageAdapterForModel(newModel.value, newModel.value.imageAdapter);

            if (textModel) {
                validateSystemModelPricing(
                    newModel.value.inputPricePerMillion,
                    newModel.value.cachedInputPricePerMillion,
                    newModel.value.outputPricePerMillion,
                );
            }

            const inputPrice = textModel && isBillingEnabled() ? newModel.value.inputPricePerMillion ?? undefined : undefined;
            const cachedInputPrice = textModel && isBillingEnabled() ? newModel.value.cachedInputPricePerMillion ?? undefined : undefined;
            const outputPrice = textModel && isBillingEnabled() ? newModel.value.outputPricePerMillion ?? undefined : undefined;
            let result;
            if (currentPlatform.value.is_sys) {
                result = await adminCreateSysModel(
                    currentPlatform.value.platform_id,
                    newModel.value.modelName,
                    displayName,
                    extraBodyPayload,
                    temperature,
                    inputPrice,
                    cachedInputPrice,
                    outputPrice,
                    textModel ? newModel.value.maxContextTokens : null,
                    textModel ? newModel.value.maxOutputTokens : null,
                    modalities.inputModalities,
                    modalities.outputModalities,
                    imageGenerationAdapter,
                );
            } else {
                result = await createModel(
                    currentPlatform.value.platform_id,
                    newModel.value.modelName,
                    displayName,
                    extraBodyPayload,
                    temperature,
                    textModel ? newModel.value.maxContextTokens : null,
                    textModel ? newModel.value.maxOutputTokens : null,
                    modalities.inputModalities,
                    modalities.outputModalities,
                    imageGenerationAdapter,
                );
            }
            targetPlatform.models = targetPlatform.models || [];
            targetPlatform.models.push({
                model_id: result.id,
                model_name: newModel.value.modelName,
                display_name: displayName,
                input_modalities: modalities.inputModalities,
                output_modalities: modalities.outputModalities,
                image_generation_adapter: imageGenerationAdapter,
                extra_body: parseExtraBodyForView(extraBodyPayload || ''),
                temperature: textModel ? temperature ?? null : null,
                max_context_tokens: textModel ? newModel.value.maxContextTokens ?? null : null,
                max_output_tokens: textModel ? newModel.value.maxOutputTokens ?? null : null,
                sys_credit_input_price_per_million: textModel ? newModel.value.inputPricePerMillion ?? null : null,
                sys_credit_cached_input_price_per_million: textModel ? newModel.value.cachedInputPricePerMillion ?? null : null,
                sys_credit_output_price_per_million: textModel ? newModel.value.outputPricePerMillion ?? null : null,
            });
            showAddModelModal.value = false;
            notifyAiStoreSync();
        } catch (e: unknown) {
            message.error(getErrorMessage(e) || '添加失败');
        } finally {
            saving.value = false;
        }
    }

    async function handleUpdateModel() {
        if (!currentPlatform.value) {
            message.warning('请先选择平台');
            return;
        }
        if (editingModel.value.id == null) {
            message.warning('无效的模型目标');
            return;
        }
        saving.value = true;
        try {
            const modalities = getModelModalities(editingModel.value);
            const textModel = isTextModel(editingModel.value);
            let temperature: number | null = null;
            if (textModel && editingModel.value.temperatureEnabled) {
                const temp = Number(editingModel.value.temperature);
                if (!Number.isFinite(temp) || temp < TEMP_MIN || temp > TEMP_MAX) {
                    throw new Error(`Temperature 必须在 ${TEMP_MIN} 到 ${TEMP_MAX} 之间`);
                }
                temperature = temp;
            }
            const targetModelId = editingModel.value.id;
            const displayName = editingModel.value.displayName;
            const extraBodyInput = buildExtraBodyForEditingModel();
            const imageGenerationAdapter = imageAdapterForModel(editingModel.value, editingModel.value.imageAdapter);
            if (currentPlatform.value?.is_sys && isBillingEnabled() && textModel) {
                validateSystemModelPricing(
                    editingModel.value.inputPricePerMillion,
                    editingModel.value.cachedInputPricePerMillion,
                    editingModel.value.outputPricePerMillion,
                );
            }
            if (currentPlatform.value?.is_sys) {
                await adminUpdateSysModel(
                    targetModelId,
                    displayName,
                    extraBodyInput,
                    {
                        includeTemperature: true,
                        temperature,
                        includeSysCreditPrices: isBillingEnabled() && textModel,
                        inputPricePerMillion: isBillingEnabled() && textModel ? editingModel.value.inputPricePerMillion ?? null : null,
                        cachedInputPricePerMillion: isBillingEnabled() && textModel ? editingModel.value.cachedInputPricePerMillion ?? null : null,
                        outputPricePerMillion: isBillingEnabled() && textModel ? editingModel.value.outputPricePerMillion ?? null : null,
                        includeMaxTokens: true,
                        maxContextTokens: textModel ? editingModel.value.maxContextTokens : null,
                        maxOutputTokens: textModel ? editingModel.value.maxOutputTokens : null,
                        includeModalities: true,
                        inputModalities: modalities.inputModalities,
                        outputModalities: modalities.outputModalities,
                        includeImageGenerationAdapter: true,
                        imageGenerationAdapter,
                    }
                );
            } else {
                await updateModel(
                    targetModelId,
                    displayName,
                    extraBodyInput,
                    {
                        includeTemperature: true,
                        temperature,
                        includeMaxTokens: true,
                        maxContextTokens: textModel ? editingModel.value.maxContextTokens : null,
                        maxOutputTokens: textModel ? editingModel.value.maxOutputTokens : null,
                        includeModalities: true,
                        inputModalities: modalities.inputModalities,
                        outputModalities: modalities.outputModalities,
                        includeImageGenerationAdapter: true,
                        imageGenerationAdapter,
                    }
                );
            }
            const { plat, model } = findModelInPlatform(currentPlatform.value?.platform_id, targetModelId);
            if (model) {
                model.display_name = displayName;
                model.input_modalities = modalities.inputModalities;
                model.output_modalities = modalities.outputModalities;
                model.image_generation_adapter = imageGenerationAdapter;
                model.extra_body = parseExtraBodyForView(extraBodyInput || '');
                model.temperature = textModel ? temperature : null;
                model.max_context_tokens = textModel ? editingModel.value.maxContextTokens ?? null : null;
                model.max_output_tokens = textModel ? editingModel.value.maxOutputTokens ?? null : null;
                model.sys_credit_input_price_per_million = textModel ? editingModel.value.inputPricePerMillion ?? null : null;
                model.sys_credit_cached_input_price_per_million = textModel ? editingModel.value.cachedInputPricePerMillion ?? null : null;
                model.sys_credit_output_price_per_million = textModel ? editingModel.value.outputPricePerMillion ?? null : null;
            }
            showEditModelModal.value = false;
            notifyAiStoreSync();
        } catch (e: unknown) {
            message.error(getErrorMessage(e) || '更新失败');
        } finally {
            saving.value = false;
        }
    }

    async function doDeleteModel(modelId: ApiId, plat: AiPlatform, isSys = false) {
        const { model, index } = findModelInPlatform(plat?.platform_id, modelId);
        if (plat && index >= 0) {
            plat.models = plat.models || [];
            plat.models.splice(index, 1);
        }
        delete speedResults.value[String(modelId)];
        try {
            if (isSys) {
                await adminDeleteSysModel(modelId);
            } else {
                await deleteModel(modelId);
            }
            notifyAiStoreSync();
        } catch (e: unknown) {
            if (plat && index >= 0 && model) {
                plat.models = plat.models || [];
                plat.models.splice(index, 0, model);
            }
            message.error(getErrorMessage(e) || '删除失败');
        }
    }

    function confirmDeleteModel(model: AiModelItem, plat: AiPlatform) {
        dialog.warning({
            title: '删除模型',
            content: `确定要删除模型「${model.display_name}」吗？`,
            positiveText: '删除',
            negativeText: '取消',
            onPositiveClick: () => doDeleteModel(model.model_id, plat, plat.is_sys)
        });
    }

    // === 内联编辑 ===
    function startEditDisplayName(plat: AiPlatform, model: AiModelItem) {
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

    async function confirmEditDisplayName(plat: AiPlatform, model: AiModelItem) {
        const newName = editingDisplayNameValue.value.trim();
        if (!newName || newName === model.display_name) {
            cancelEditDisplayName();
            return;
        }

        let extraBodyStr: string | null = null;
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
        } catch (e: unknown) {
            message.error(getErrorMessage(e) || '更新失败');
        } finally {
            cancelEditDisplayName();
        }
    }

    function clearSpeedResult(modelId: ApiId) {
        const key = String(modelId);
        delete speedResults.value[key];
        saveSpeedResultsToCache();
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
        clearSpeedResult,
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
