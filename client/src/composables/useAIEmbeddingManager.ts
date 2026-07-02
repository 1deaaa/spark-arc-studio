/**
 * AI Embedding 管理 Composable
 * 只负责默认 Embedding 选择、检测和列表合并；模型增删改统一走模型管理器。
 */
import { ref, type Ref } from 'vue';
import { useMessage, useDialog } from 'naive-ui';
import {
    fetchPlatformsWithEmbeddings,
    fetchUserEmbeddingSelection,
    saveUserEmbeddingSelection as apiSaveUserEmbeddingSelection,
    fetchEmbeddingStatus,
    testEmbedding,
} from '../services/api';
import type {
    AiEmbeddingItem,
    AiPlatform,
    ApiId,
    EmbeddingSelectionCurrent,
} from '../services/aiContracts';

type EmbeddingSelectionState = { platform_id: ApiId | null; model_id: ApiId | null };

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

    const embeddingSelection = ref<EmbeddingSelectionState>({ platform_id: null, model_id: null });
    const embeddingSaving = ref(false);

    function notifyAiStoreSync() {
        syncAiStoreSilently?.();
    }

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
        embeddingSelection,
        embeddingSaving,
        loadEmbeddings,
        testEmbeddingModel,
        saveUserEmbeddingSelection
    };
}
