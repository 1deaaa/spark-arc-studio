/**
 * AI 平台管理 Composable
 * 从 AIManager.vue 提取的平台 CRUD 和配置管理逻辑
 */
import { ref, watch, onMounted, onUnmounted } from 'vue';
import { useI18n } from 'vue-i18n';
import { useMessage, useDialog } from 'naive-ui';
import { bus } from '../eventBus';
import { fetchWithAuth } from '../services/api';
import { getUserInfo } from '../services/authService';
import type { AiPlatform, ApiId } from '../services/aiContracts';

type SystemConfig = { llm_auto_key: boolean; use_sys_llm_config: boolean; billing_enabled: boolean };

type NewPlatformForm = {
    name: string;
    baseUrl: string;
    apiKey: string;
    rechargeUrl: string;
    isSys: boolean;
    sysCreditBalance: number | null;
};

type EditingPlatformForm = {
    id: ApiId | null;
    name: string;
    baseUrl: string;
    rechargeUrl: string;
    is_sys: boolean;
    api_key_status?: string;
    api_key_message?: string;
    sys_key_status?: string;
    sys_key_message?: string;
    user_key_status?: string;
    user_key_message?: string;
    user_key_saved?: boolean;
    user_key_override?: boolean;
    sysCreditBalance?: number | null;
};

type PlatformCreatePayload = {
    name: string;
    base_url: string;
    api_key: string | null;
    recharge_url?: string | null;
    sys_credit_balance?: number | null;
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

function normalizeCreditBalance(rawValue: number | null | undefined): number | null {
    if (rawValue === null || rawValue === undefined) return null;
    const value = Number(rawValue);
    if (!Number.isFinite(value)) return null;
    return Math.round(value * 100) / 100;
}

function normalizeOptionalText(rawValue: string | null | undefined): string | null {
    const value = String(rawValue || '').trim();
    return value || null;
}

export function useAIPlatformManager(options: { syncAiStoreSilently?: () => void } = {}) {
    const { syncAiStoreSilently } = options;
    const message = useMessage();
    const dialog = useDialog();
    const { t } = useI18n();

    // === 状态 ===
    const loading = ref(false);
    const saving = ref(false);
    const platforms = ref<AiPlatform[]>([]);
    // 折叠状态持久化
    const EXPAND_CACHE_KEY = 'sparkarc_ai_expanded_platforms';
    const expandedNames = ref<ApiId[]>(loadExpandedFromCache());
    const systemConfig = ref<SystemConfig>({ llm_auto_key: false, use_sys_llm_config: false, billing_enabled: false });
    const isAdmin = ref(false);

    // 弹窗状态
    const showAddPlatformModal = ref(false);
    const showEditPlatformModal = ref(false);
    const showKeyModal = ref(false);
    const originalBaseUrl = ref('');
    const newPlatform = ref<NewPlatformForm>({ name: '', baseUrl: '', apiKey: '', rechargeUrl: '', isSys: false, sysCreditBalance: null });
    const editingPlatform = ref<EditingPlatformForm>({
        id: null,
        name: '',
        baseUrl: '',
        rechargeUrl: '',
        is_sys: false,
        api_key_status: 'missing',
        api_key_message: '',
        sys_key_status: 'missing',
        sys_key_message: '',
        user_key_status: 'missing',
        user_key_message: '',
        user_key_saved: false,
        user_key_override: false,
        sysCreditBalance: null,
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
                const loadedPlatforms = await res.json() as AiPlatform[];
                platforms.value = loadedPlatforms.map(platform => ({
                    ...platform,
                    sys_credit_balance: normalizeCreditBalance(platform.sys_credit_balance),
                }));
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
            message.success(val ? t('components.aiManager.messages.systemLockEnabled') : t('components.aiManager.messages.systemLockDisabled'));
        } catch (e: unknown) {
            message.error(t('components.aiManager.messages.configToggleFailed', { error: getErrorMessage(e) }));
        }
    }

    async function toggleBillingEnabled(val: boolean) {
        try {
            const res = await fetchWithAuth('/api/ai/system-config', {
                method: 'POST',
                body: JSON.stringify({ billing_enabled: val }),
                headers: { 'Content-Type': 'application/json' }
            });
            if (!res.ok) {
                throw new Error(t('components.aiManager.messages.operationFailed'));
            }
            systemConfig.value.billing_enabled = val;
            bus.emit('system-config-updated', { billing_enabled: val });
            message.success(val ? t('components.aiManager.messages.billingEnabled') : t('components.aiManager.messages.billingDisabled'));
        } catch (e: unknown) {
            message.error(t('components.aiManager.messages.billingToggleFailed', { error: getErrorMessage(e) }));
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

    function buildLocalPlatform({ platformId, name, baseUrl, rechargeUrl, isSys, apiKey, sysCreditBalance }: {
        platformId: ApiId;
        name: string;
        baseUrl: string;
        rechargeUrl?: string | null;
        isSys: boolean;
        apiKey: string | null;
        sysCreditBalance?: number | null;
    }): AiPlatform {
        return {
            platform_id: platformId,
            name,
            base_url: baseUrl,
            recharge_url: normalizeOptionalText(rechargeUrl),
            api_key_set: Boolean(apiKey),
            api_key_status: apiKey ? 'ok' : 'missing',
            api_key_message: apiKey ? '当前平台 API Key 已配置并可用。' : '该平台需要配置 API Key。',
            sys_key_set: Boolean(apiKey),
            sys_key_status: apiKey ? 'ok' : 'missing',
            sys_key_message: apiKey ? '站长托管 API Key 已配置并可用。' : '该平台需要配置托管 API Key。',
            sys_credit_balance: normalizeCreditBalance(sysCreditBalance),
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
            rechargeUrl: plat.recharge_url || '',
            is_sys: plat.is_sys,
            api_key_status: plat.api_key_status || 'missing',
            api_key_message: plat.api_key_message || '',
            sys_key_status: plat.sys_key_status || 'missing',
            sys_key_message: plat.sys_key_message || '',
            user_key_status: plat.user_key_status || 'missing',
            user_key_message: plat.user_key_message || '',
            user_key_saved: Boolean(plat.user_key_saved),
            user_key_override: Boolean(plat.user_key_override),
            sysCreditBalance: normalizeCreditBalance(plat.sys_credit_balance),
        };
        editingApiKey.value = '';
        showKeyModal.value = true;
    }

    function openEditPlatformModal(plat: AiPlatform) {
        originalBaseUrl.value = plat.base_url;
        editingPlatform.value = {
            id: plat.platform_id,
            name: plat.name,
            baseUrl: plat.base_url,
            rechargeUrl: plat.recharge_url || '',
            is_sys: Boolean(plat.is_sys),
            api_key_status: plat.api_key_status || 'missing',
            api_key_message: plat.api_key_message || '',
            sys_key_status: plat.sys_key_status || 'missing',
            sys_key_message: plat.sys_key_message || '',
            user_key_status: plat.user_key_status || 'missing',
            user_key_message: plat.user_key_message || '',
            user_key_saved: Boolean(plat.user_key_saved),
            user_key_override: Boolean(plat.user_key_override),
            sysCreditBalance: normalizeCreditBalance(plat.sys_credit_balance),
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
                recharge_url: normalizeOptionalText(newPlatform.value.rechargeUrl),
            };
            if (isSysPlatform) {
                payload.sys_credit_balance = normalizeCreditBalance(newPlatform.value.sysCreditBalance);
            }
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
                rechargeUrl: newPlatform.value.rechargeUrl,
                isSys: isSysPlatform,
                apiKey: newPlatform.value.apiKey || null,
                sysCreditBalance: isSysPlatform ? normalizeCreditBalance(newPlatform.value.sysCreditBalance) : null,
            }));
            await loadPlatforms();
            showAddPlatformModal.value = false;
            newPlatform.value = { name: '', baseUrl: '', apiKey: '', rechargeUrl: '', isSys: false, sysCreditBalance: null };
            notifyAiStoreSync();
        } catch (e: unknown) {
            message.error(getErrorMessage(e));
        } finally {
            saving.value = false;
        }
    }

    async function handleUpdatePlatform() {
        saving.value = true;
        const prevBaseUrl = originalBaseUrl.value;
        try {
            const platformId = editingPlatform.value.id;
            const nextName = editingPlatform.value.name;
            const nextBaseUrl = editingPlatform.value.baseUrl;
            const nextRechargeUrl = normalizeOptionalText(editingPlatform.value.rechargeUrl);
            const isSysPlatform = Boolean(editingPlatform.value.is_sys && isAdmin.value);
            const baseUrlChanged = prevBaseUrl !== nextBaseUrl;

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
                        recharge_url: nextRechargeUrl,
                        sys_credit_balance: normalizeCreditBalance(editingPlatform.value.sysCreditBalance),
                    }
                    : {
                        id: platformId,
                        name: nextName,
                        base_url: nextBaseUrl,
                        recharge_url: nextRechargeUrl,
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

            // base_url 变更后，现有模型名称可能不匹配新端点
            if (baseUrlChanged) {
                message.warning('端点地址已变更，现有模型名称可能不匹配新端点。建议重新探测模型并更新模型列表。');
            }
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
            ? `\n\n${t('components.aiManager.confirm.disableSystemPlatformExtra')}`
            : '';
        dialog.warning({
            title: t('components.aiManager.confirm.disablePlatformTitle'),
            content: `${t('components.aiManager.confirm.disablePlatformContent', { name: plat.name })}${extraWarning}`,
            positiveText: t('components.aiManager.confirm.disableConfirm'),
            negativeText: t('views.common.cancel'),
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
            a.download = 'matchbox_config.matchbox';
            document.body.appendChild(a);
            a.click();
            a.remove();
            window.URL.revokeObjectURL(url);
            message.success('系统平台配置与密钥文件已打包下载');
        } catch (e: unknown) {
            message.error('导出系统配置失败: ' + getErrorMessage(e));
        }
    }

    async function uploadSysConfigFromYaml(file: File) {
        const formData = new FormData();
        formData.append('file', file);
        try {
            const res = await fetchWithAuth('/api/ai/admin/import-from-yaml', {
                method: 'POST',
                body: formData,
            });
            if (!res.ok) {
                const err = asDetailPayload(await res.json());
                throw new Error(err.detail || '导入配置失败');
            }
            message.success('系统平台配置已导入并即时生效');
        } catch (e: unknown) {
            message.error('导入配置文件失败: ' + getErrorMessage(e));
            throw e;
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
        toggleBillingEnabled,
        openKeyModal,
        openEditPlatformModal,
        handleAddPlatform,
        handleUpdatePlatform,
        handleUpdateKey,
        confirmDeletePlatform,
        doDeletePlatform,
        downloadSysConfig,
        uploadSysConfigFromYaml,
        // 管理员排序
        reorderPlatforms,
        reorderModels,
        setDefaultPlatform
    };
}
