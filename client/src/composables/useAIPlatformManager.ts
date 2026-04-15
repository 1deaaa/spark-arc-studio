/**
 * AI 平台管理 Composable
 * 从 AIManager.vue 提取的平台 CRUD 和配置管理逻辑
 */
import { ref, watch, onMounted, onUnmounted } from 'vue';
import { useMessage, useDialog } from 'naive-ui';
import { bus } from '../eventBus';
import { fetchWithAuth } from '../services/api';
import { getUserInfo } from '../services/authService';
import type { AiPlatform, ApiId } from '../services/aiContracts';

type SystemConfig = { llm_auto_key: boolean; use_sys_llm_config: boolean };

type NewPlatformForm = {
    name: string;
    baseUrl: string;
    apiKey: string;
    isSys: boolean;
};

type EditingPlatformForm = {
    id: ApiId | null;
    name: string;
    baseUrl: string;
    is_sys: boolean;
    api_key_status?: string;
    api_key_message?: string;
    sys_key_status?: string;
    sys_key_message?: string;
    user_key_status?: string;
    user_key_message?: string;
    user_key_saved?: boolean;
    user_key_override?: boolean;
};

type PlatformCreatePayload = {
    name: string;
    base_url: string;
    api_key: string | null;
};

function getErrorMessage(error: unknown): string {
    if (error instanceof Error) return error.message;
    return String(error || '未知错误');
}

function asDetailPayload(value: unknown): { detail?: string } {
    if (value && typeof value === 'object') {
        return value as { detail?: string };
    }
    return {};
}

export function useAIPlatformManager(options: { syncAiStoreSilently?: () => void } = {}) {
    const { syncAiStoreSilently } = options;
    const message = useMessage();
    const dialog = useDialog();

    // === 状态 ===
    const loading = ref(false);
    const saving = ref(false);
    const platforms = ref<AiPlatform[]>([]);
    // 折叠状态持久化
    const EXPAND_CACHE_KEY = 'sparkarc_ai_expanded_platforms';
    const expandedNames = ref<ApiId[]>(loadExpandedFromCache());
    const systemConfig = ref<SystemConfig>({ llm_auto_key: false, use_sys_llm_config: false });
    const isAdmin = ref(false);

    // 弹窗状态
    const showAddPlatformModal = ref(false);
    const showEditPlatformModal = ref(false);
    const showKeyModal = ref(false);
    const newPlatform = ref<NewPlatformForm>({ name: '', baseUrl: '', apiKey: '', isSys: false });
    const editingPlatform = ref<EditingPlatformForm>({
        id: null,
        name: '',
        baseUrl: '',
        is_sys: false,
        api_key_status: 'missing',
        api_key_message: '',
        sys_key_status: 'missing',
        sys_key_message: '',
        user_key_status: 'missing',
        user_key_message: '',
        user_key_saved: false,
        user_key_override: false,
    });
    const editingApiKey = ref('');

    // === 数据加载 ===
    async function loadPlatforms() {
        loading.value = true;
        try {
            const [res, configRes, userInfoRes] = await Promise.all([
                fetchWithAuth('/api/ai/platforms-with-models'),
                fetchWithAuth('/api/ai/system-config'),
                getUserInfo()
            ]);

            isAdmin.value = userInfoRes?.is_admin || false;

            if (configRes.ok) {
                systemConfig.value = await configRes.json();
            }

            if (res.ok) {
                platforms.value = await res.json() as AiPlatform[];
                // 仅在没有缓存记录时，默认展开第一个自定义平台
                if (expandedNames.value.length === 0) {
                    const firstCustom = platforms.value.find(p => !p.is_sys);
                    if (firstCustom) {
                        expandedNames.value = [firstCustom.platform_id];
                    }
                }
            }
        } catch (e: unknown) {
            console.error('加载平台数据失败:', e);
        } finally {
            loading.value = false;
        }
    }

    // === 系统配置 ===
    async function toggleSystemConfigLock(val: boolean) {
        try {
            const res = await fetchWithAuth('/api/ai/system-config', {
                method: 'POST',
                body: JSON.stringify({ use_sys_llm_config: val }),
                headers: { 'Content-Type': 'application/json' }
            });
            if (!res.ok) {
                throw new Error('操作失败');
            }
            systemConfig.value.use_sys_llm_config = val;
            bus.emit('system-config-updated', { use_sys_llm_config: val });
            message.success(val ? '已开启强制系统配置模式' : '已关闭强制系统配置模式');
        } catch (e: unknown) {
            message.error('切换配置失败: ' + getErrorMessage(e));
        }
    }

    function handleSystemConfigUpdate(payload: unknown) {
        if (payload && typeof payload === 'object') {
            systemConfig.value = { ...systemConfig.value, ...(payload as Partial<SystemConfig>) };
        }
        loadPlatforms();
    }

    function notifyAiStoreSync() {
        syncAiStoreSilently?.();
    }

    function buildLocalPlatform({ platformId, name, baseUrl, isSys, apiKey }: {
        platformId: ApiId;
        name: string;
        baseUrl: string;
        isSys: boolean;
        apiKey: string | null;
    }): AiPlatform {
        return {
            platform_id: platformId,
            name,
            base_url: baseUrl,
            api_key_set: Boolean(apiKey),
            api_key_status: apiKey ? 'ok' : 'missing',
            api_key_message: apiKey ? '当前平台 API Key 已配置并可用。' : '未配置 API Key。',
            sys_key_set: Boolean(apiKey),
            sys_key_status: apiKey ? 'ok' : 'missing',
            sys_key_message: apiKey ? '站长托管 API Key 已配置并可用。' : '未配置托管 API Key。',
            is_sys: Boolean(isSys),
            user_key_override: false,
            user_key_saved: false,
            user_key_status: 'missing',
            user_key_message: '您尚未为该系统平台配置个人 API Key。',
            disabled: false,
            models: [],
            embeddings: []
        };
    }

    function findPlatformById(platformId: ApiId) {
        return platforms.value.find(p => p.platform_id === platformId) || null;
    }

    // === 平台 CRUD ===
    function openKeyModal(plat: AiPlatform) {
        editingPlatform.value = {
            id: plat.platform_id,
            name: plat.name,
            baseUrl: plat.base_url,
            is_sys: plat.is_sys,
            api_key_status: plat.api_key_status || 'missing',
            api_key_message: plat.api_key_message || '',
            sys_key_status: plat.sys_key_status || 'missing',
            sys_key_message: plat.sys_key_message || '',
            user_key_status: plat.user_key_status || 'missing',
            user_key_message: plat.user_key_message || '',
            user_key_saved: Boolean(plat.user_key_saved),
            user_key_override: Boolean(plat.user_key_override),
        };
        editingApiKey.value = '';
        showKeyModal.value = true;
    }

    function openEditPlatformModal(plat: AiPlatform) {
        editingPlatform.value = {
            id: plat.platform_id,
            name: plat.name,
            baseUrl: plat.base_url,
            is_sys: Boolean(plat.is_sys),
            api_key_status: plat.api_key_status || 'missing',
            api_key_message: plat.api_key_message || '',
            sys_key_status: plat.sys_key_status || 'missing',
            sys_key_message: plat.sys_key_message || '',
            user_key_status: plat.user_key_status || 'missing',
            user_key_message: plat.user_key_message || '',
            user_key_saved: Boolean(plat.user_key_saved),
            user_key_override: Boolean(plat.user_key_override),
        };
        editingApiKey.value = '';
        showEditPlatformModal.value = true;
    }

    async function handleAddPlatform() {
        if (!newPlatform.value.name || !newPlatform.value.baseUrl) {
            message.warning('请填写平台名称和 Base URL');
            return;
        }
        saving.value = true;
        try {
            // 管理员勾选了“系统平台”时，调用管理员专用接口
            const isSysPlatform = newPlatform.value.isSys && isAdmin.value;
            const url = isSysPlatform ? '/api/ai/admin/sys-platform' : '/api/ai/platform';
            const payload: PlatformCreatePayload = {
                name: newPlatform.value.name,
                base_url: newPlatform.value.baseUrl,
                api_key: newPlatform.value.apiKey || null,
            };
            const res = await fetchWithAuth(url, {
                method: 'POST',
                body: JSON.stringify(payload),
                headers: { 'Content-Type': 'application/json' }
            });
            if (!res.ok) {
                const err = asDetailPayload(await res.json());
                throw new Error(err.detail || '创建失败');
            }
            const result = await res.json() as { platform_id?: ApiId; id?: ApiId };
            const createdPlatformId = result.platform_id ?? result.id;
            if (createdPlatformId == null) {
                throw new Error('创建平台返回缺少 platform_id');
            }
            platforms.value.push(buildLocalPlatform({
                platformId: createdPlatformId,
                name: newPlatform.value.name,
                baseUrl: newPlatform.value.baseUrl,
                isSys: isSysPlatform,
                apiKey: newPlatform.value.apiKey || null,
            }));
            await loadPlatforms();
            showAddPlatformModal.value = false;
            newPlatform.value = { name: '', baseUrl: '', apiKey: '', isSys: false };
            notifyAiStoreSync();
        } catch (e: unknown) {
            message.error(getErrorMessage(e));
        } finally {
            saving.value = false;
        }
    }

    async function handleUpdatePlatform() {
        saving.value = true;
        try {
            const platformId = editingPlatform.value.id;
            const nextName = editingPlatform.value.name;
            const nextBaseUrl = editingPlatform.value.baseUrl;
            const isSysPlatform = Boolean(editingPlatform.value.is_sys && isAdmin.value);

            // 管理员编辑系统平台 → 更新 name/baseUrl + Key
            // 普通用户编辑系统平台 → 仅保存 Key（无权修改 name/baseUrl）
            // 普通用户编辑自定义平台 → 更新 name/baseUrl + Key
            if (!editingPlatform.value.is_sys || isAdmin.value) {
                const url = isSysPlatform ? '/api/ai/admin/sys-platform' : '/api/ai/platform';
                const payload = isSysPlatform
                    ? {
                        platform_id: platformId,
                        name: nextName,
                        base_url: nextBaseUrl,
                    }
                    : {
                        id: platformId,
                        name: nextName,
                        base_url: nextBaseUrl,
                    };
                const res = await fetchWithAuth(url, {
                    method: 'PUT',
                    body: JSON.stringify(payload),
                    headers: { 'Content-Type': 'application/json' }
                });
                if (!res.ok) {
                    const err = asDetailPayload(await res.json());
                    throw new Error(err.detail || '更新失败');
                }
            }

            // 若用户填写了 API Key，同时保存密钥
            if (editingApiKey.value) {
                const isAdminSysPlatform = isAdmin.value && editingPlatform.value.is_sys;
                const keyUrl = isAdminSysPlatform
                    ? '/api/ai/admin/sys-platform/api-key'
                    : '/api/ai/platform-config';
                const keyRes = await fetchWithAuth(keyUrl, {
                    method: 'POST',
                    body: JSON.stringify({
                        platform_id: platformId,
                        api_key: editingApiKey.value
                    }),
                    headers: { 'Content-Type': 'application/json' }
                });
                if (!keyRes.ok) {
                    const err = asDetailPayload(await keyRes.json());
                    throw new Error(err.detail || '密钥保存失败');
                }
            }

            await loadPlatforms();
            showEditPlatformModal.value = false;
            notifyAiStoreSync();
        } catch (e: unknown) {
            message.error(getErrorMessage(e));
        } finally {
            saving.value = false;
        }
    }

    async function handleUpdateKey() {
        if (!editingApiKey.value && !editingPlatform.value.is_sys) {
            message.warning('请输入 API Key');
            return;
        }

        // 管理员设置系统平台密钥 → 写入系统默认 key（对所有用户生效）
        // 普通用户设置系统平台密钥 → 写入自己的 key
        const isAdminSysPlatform = isAdmin.value && editingPlatform.value.is_sys;
        const url = isAdminSysPlatform
            ? '/api/ai/admin/sys-platform/api-key'
            : '/api/ai/platform-config';

        saving.value = true;
        try {
            const platformId = editingPlatform.value.id;
            const nextApiKey = editingApiKey.value;
            const res = await fetchWithAuth(url, {
                method: 'POST',
                body: JSON.stringify({
                    platform_id: platformId,
                    api_key: nextApiKey
                }),
                headers: { 'Content-Type': 'application/json' }
            });
            if (!res.ok) {
                const err = asDetailPayload(await res.json());
                throw new Error(err.detail || '更新失败');
            }
            await loadPlatforms();
            showKeyModal.value = false;
            notifyAiStoreSync();
        } catch (e: unknown) {
            message.error(getErrorMessage(e));
        } finally {
            saving.value = false;
        }
    }

    function confirmDeletePlatform(plat: AiPlatform) {
        const isSystemPlatform = !!plat.is_sys;
        const extraWarning = isSystemPlatform
            ? '\n\n注意：这是系统平台，删除后所有用户将立即无法使用该平台。\n此外，模型增量同步将绕过此平台，除非手动重新添加此URL的平台。'
            : '';
        dialog.warning({
            title: '确认删除',
            content: `确定要删除平台「${plat.name}」及其所有模型吗？${extraWarning}`,
            positiveText: '删除',
            negativeText: '取消',
            onPositiveClick: () => doDeletePlatform(plat)
        });
    }

    async function doDeletePlatform(plat: AiPlatform) {
        const index = platforms.value.findIndex(p => p.platform_id === plat.platform_id);
        const prevExpanded = [...expandedNames.value];
        if (index !== -1) {
            platforms.value.splice(index, 1);
            expandedNames.value = expandedNames.value.filter(name => name !== plat.platform_id);
        }
        try {
            const isSystemPlatform = !!plat.is_sys && isAdmin.value;
            const url = isSystemPlatform
                ? `/api/ai/admin/sys-platform?id=${plat.platform_id}`
                : `/api/ai/platform?id=${plat.platform_id}`;
            const res = await fetchWithAuth(url, { method: 'DELETE' });
            if (!res.ok) {
                const err = asDetailPayload(await res.json());
                throw new Error(err.detail || '删除失败');
            }
            notifyAiStoreSync();
        } catch (e: unknown) {
            if (index !== -1) {
                platforms.value.splice(index, 0, plat);
                expandedNames.value = prevExpanded;
            }
            message.error(getErrorMessage(e));
        }
    }

    // === 管理员：拖拽排序 ===

    /**
     * 重新排序系统平台（管理员专用）
     * @param {number[]} orderedIds - 按新顺序排列的平台 ID 列表
     */
    async function reorderPlatforms(orderedIds: ApiId[]) {
        try {
            const res = await fetchWithAuth('/api/ai/admin/reorder-platforms', {
                method: 'POST',
                body: JSON.stringify({ ordered_ids: orderedIds }),
                headers: { 'Content-Type': 'application/json' }
            });
            if (!res.ok) {
                const err = asDetailPayload(await res.json());
                throw new Error(err.detail || '排序失败');
            }
            // 排序现在为静默操作，本地由于 drag&drop 已更新，不需要也不应该重新拉取全量导致列表闪屏
        } catch (e: unknown) {
            message.error('平台排序失败: ' + getErrorMessage(e));
        }
    }

    /**
     * 重新排序指定平台下的模型（管理员专用）
     * @param {number} platformId - 平台 ID
     * @param {number[]} orderedIds - 按新顺序排列的模型 ID 列表
     */
    async function reorderModels(platformId: ApiId, orderedIds: ApiId[]) {
        try {
            const res = await fetchWithAuth('/api/ai/admin/reorder-models', {
                method: 'POST',
                body: JSON.stringify({ platform_id: platformId, ordered_ids: orderedIds }),
                headers: { 'Content-Type': 'application/json' }
            });
            if (!res.ok) {
                const err = asDetailPayload(await res.json());
                throw new Error(err.detail || '排序失败');
            }
            // 静默更新后台排序，无需重新加载列表数据
        } catch (e: unknown) {
            message.error('模型排序失败: ' + getErrorMessage(e));
        }
    }

    /**
     * 设为默认平台（管理员专用，sort_order 设为 0）
     * @param {number} platformId - 平台 ID
     */
    async function setDefaultPlatform(platformId: ApiId) {
        const oldOrder = [...platforms.value];
        try {
            const index = platforms.value.findIndex(p => p.platform_id === platformId);
            if (index > 0) {
                const [plat] = platforms.value.splice(index, 1);
                platforms.value.unshift(plat);
            }
            const res = await fetchWithAuth('/api/ai/admin/set-default-platform', {
                method: 'POST',
                body: JSON.stringify({ platform_id: platformId }),
                headers: { 'Content-Type': 'application/json' }
            });
            if (!res.ok) {
                const err = asDetailPayload(await res.json());
                throw new Error(err.detail || '设置失败');
            }
            notifyAiStoreSync();
        } catch (e: unknown) {
            platforms.value = oldOrder;
            message.error('设置默认平台失败: ' + getErrorMessage(e));
        }
    }

    // === 折叠状态缓存 ===
    function loadExpandedFromCache() {
        try {
            const cached = localStorage.getItem(EXPAND_CACHE_KEY);
            return cached ? JSON.parse(cached) as ApiId[] : [];
        } catch {
            return [];
        }
    }

    function saveExpandedToCache() {
        localStorage.setItem(EXPAND_CACHE_KEY, JSON.stringify(expandedNames.value));
    }

    async function downloadSysConfig() {
        try {
            const res = await fetchWithAuth('/api/ai/admin/export-to-yaml/download');
            if (!res.ok) {
                const err = asDetailPayload(await res.json());
                throw new Error(err.detail || '下载配置失败');
            }
            const blob = await res.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'matchbox_cfg.yaml';
            document.body.appendChild(a);
            a.click();
            a.remove();
            window.URL.revokeObjectURL(url);
            message.success('系统平台配置已导出并下载');
        } catch (e: unknown) {
            message.error('导出系统配置失败: ' + getErrorMessage(e));
        }
    }

    async function saveSysConfigToYaml() {
        try {
            const res = await fetchWithAuth('/api/ai/admin/save-to-yaml', { method: 'POST' });
            if (!res.ok) {
                const err = asDetailPayload(await res.json());
                throw new Error(err.detail || '覆盖写入失败');
            }
            message.success('系统平台配置已成功覆盖写入 matchbox_cfg.yaml');
        } catch (e: unknown) {
            message.error('覆盖配置文件失败: ' + getErrorMessage(e));
        }
    }

    // 监听展开变化并持久化
    watch(expandedNames, saveExpandedToCache, { deep: true });

    // === 生命周期 ===
    onMounted(() => {
        bus.on('system-config-updated', handleSystemConfigUpdate);
    });

    onUnmounted(() => {
        bus.off('system-config-updated', handleSystemConfigUpdate);
    });

    return {
        // 状态
        loading,
        saving,
        platforms,
        expandedNames,
        systemConfig,
        isAdmin,
        // 弹窗状态
        showAddPlatformModal,
        showEditPlatformModal,
        showKeyModal,
        newPlatform,
        editingPlatform,
        editingApiKey,
        // 方法
        loadPlatforms,
        toggleSystemConfigLock,
        openKeyModal,
        openEditPlatformModal,
        handleAddPlatform,
        handleUpdatePlatform,
        handleUpdateKey,
        confirmDeletePlatform,
        doDeletePlatform,
        downloadSysConfig,
        saveSysConfigToYaml,
        // 管理员排序
        reorderPlatforms,
        reorderModels,
        setDefaultPlatform
    };
}
