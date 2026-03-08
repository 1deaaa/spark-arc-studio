/**
 * AI 平台管理 Composable
 * 从 AIManager.vue 提取的平台 CRUD 和配置管理逻辑
 */
import { ref, watch, onMounted, onUnmounted } from 'vue';
import { useMessage, useDialog } from 'naive-ui';
import { bus } from '../eventBus';
import { fetchWithAuth } from '../services/api';
import { getUserInfo } from '../services/authService';

export function useAIPlatformManager(options = {}) {
    const { syncAiStoreSilently } = options;
    const message = useMessage();
    const dialog = useDialog();

    // === 状态 ===
    const loading = ref(false);
    const saving = ref(false);
    const platforms = ref([]);
    // 折叠状态持久化
    const EXPAND_CACHE_KEY = 'sparkarc_ai_expanded_platforms';
    const expandedNames = ref(loadExpandedFromCache());
    const systemConfig = ref({ llm_auto_key: false, use_sys_llm_config: false });
    const isAdmin = ref(false);

    // 弹窗状态
    const showAddPlatformModal = ref(false);
    const showEditPlatformModal = ref(false);
    const showKeyModal = ref(false);
    const newPlatform = ref({ name: '', baseUrl: '', apiKey: '', isSys: false });
    const editingPlatform = ref({ id: null, name: '', baseUrl: '', is_sys: false });
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
                platforms.value = await res.json();
                // 仅在没有缓存记录时，默认展开第一个自定义平台
                if (expandedNames.value.length === 0) {
                    const firstCustom = platforms.value.find(p => !p.is_sys);
                    if (firstCustom) {
                        expandedNames.value = [firstCustom.platform_id];
                    }
                }
            }
        } catch (e) {
            console.error('加载平台数据失败:', e);
        } finally {
            loading.value = false;
        }
    }

    // === 系统配置 ===
    async function toggleSystemConfigLock(val) {
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
        } catch (e) {
            message.error('切换配置失败: ' + e.message);
        }
    }

    function handleSystemConfigUpdate(payload) {
        if (payload) {
            systemConfig.value = { ...systemConfig.value, ...payload };
        }
        loadPlatforms();
    }

    function notifyAiStoreSync() {
        syncAiStoreSilently?.();
    }

    function buildLocalPlatform({ platformId, name, baseUrl, isSys, apiKey }) {
        return {
            platform_id: platformId,
            name,
            base_url: baseUrl,
            api_key_set: Boolean(apiKey),
            sys_key_set: Boolean(apiKey),
            is_sys: Boolean(isSys),
            user_key_override: false,
            disabled: false,
            models: [],
            embeddings: []
        };
    }

    function findPlatformById(platformId) {
        return platforms.value.find(p => p.platform_id === platformId) || null;
    }

    // === 平台 CRUD ===
    function openKeyModal(plat) {
        editingPlatform.value = {
            id: plat.platform_id,
            name: plat.name,
            baseUrl: plat.base_url,
            is_sys: plat.is_sys
        };
        editingApiKey.value = '';
        showKeyModal.value = true;
    }

    function openEditPlatformModal(plat) {
        editingPlatform.value = { id: plat.platform_id, name: plat.name, baseUrl: plat.base_url };
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
            const res = await fetchWithAuth(url, {
                method: 'POST',
                body: JSON.stringify({
                    name: newPlatform.value.name,
                    base_url: newPlatform.value.baseUrl,
                    api_key: newPlatform.value.apiKey || null
                }),
                headers: { 'Content-Type': 'application/json' }
            });
            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.detail || '创建失败');
            }
            const result = await res.json();
            const createdPlatformId = result.platform_id ?? result.id;
            platforms.value.push(buildLocalPlatform({
                platformId: createdPlatformId,
                name: newPlatform.value.name,
                baseUrl: newPlatform.value.baseUrl,
                isSys: isSysPlatform,
                apiKey: newPlatform.value.apiKey || null
            }));
            showAddPlatformModal.value = false;
            newPlatform.value = { name: '', baseUrl: '', apiKey: '', isSys: false };
            notifyAiStoreSync();
        } catch (e) {
            message.error(e.message);
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
            const res = await fetchWithAuth('/api/ai/platform', {
                method: 'PUT',
                body: JSON.stringify({
                    id: platformId,
                    name: nextName,
                    base_url: nextBaseUrl
                }),
                headers: { 'Content-Type': 'application/json' }
            });
            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.detail || '更新失败');
            }
            const plat = findPlatformById(platformId);
            if (plat) {
                plat.name = nextName;
                plat.base_url = nextBaseUrl;
            }
            showEditPlatformModal.value = false;
            notifyAiStoreSync();
        } catch (e) {
            message.error(e.message);
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
                const err = await res.json();
                throw new Error(err.detail || '更新失败');
            }
            const plat = findPlatformById(platformId);
            if (plat) {
                if (plat.is_sys && isAdmin.value) {
                    plat.sys_key_set = Boolean(nextApiKey);
                    plat.api_key_set = Boolean(nextApiKey) || Boolean(plat.user_key_override);
                } else if (plat.is_sys) {
                    plat.user_key_override = Boolean(nextApiKey);
                    plat.api_key_set = Boolean(nextApiKey) || Boolean(plat.sys_key_set);
                } else {
                    plat.api_key_set = Boolean(nextApiKey);
                }
            }
            showKeyModal.value = false;
            notifyAiStoreSync();
        } catch (e) {
            message.error(e.message);
        } finally {
            saving.value = false;
        }
    }

    function confirmDeletePlatform(plat) {
        const isSystemPlatform = !!plat.is_sys;
        const extraWarning = isSystemPlatform
            ? '\n\n⚠️ 警告：这是系统平台，删除后所有用户将立即无法使用该平台。'
            : '';
        dialog.warning({
            title: '确认删除',
            content: `确定要删除平台「${plat.name}」及其所有模型吗？${extraWarning}`,
            positiveText: '删除',
            negativeText: '取消',
            onPositiveClick: () => doDeletePlatform(plat)
        });
    }

    async function doDeletePlatform(plat) {
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
                const err = await res.json();
                throw new Error(err.detail || '删除失败');
            }
            notifyAiStoreSync();
        } catch (e) {
            if (index !== -1) {
                platforms.value.splice(index, 0, plat);
                expandedNames.value = prevExpanded;
            }
            message.error(e.message);
        }
    }

    // === 管理员：拖拽排序 ===

    /**
     * 重新排序系统平台（管理员专用）
     * @param {number[]} orderedIds - 按新顺序排列的平台 ID 列表
     */
    async function reorderPlatforms(orderedIds) {
        try {
            const res = await fetchWithAuth('/api/ai/admin/reorder-platforms', {
                method: 'POST',
                body: JSON.stringify({ ordered_ids: orderedIds }),
                headers: { 'Content-Type': 'application/json' }
            });
            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.detail || '排序失败');
            }
            // 排序现在为静默操作，本地由于 drag&drop 已更新，不需要也不应该重新拉取全量导致列表闪屏
        } catch (e) {
            message.error('平台排序失败: ' + e.message);
        }
    }

    /**
     * 重新排序指定平台下的模型（管理员专用）
     * @param {number} platformId - 平台 ID
     * @param {number[]} orderedIds - 按新顺序排列的模型 ID 列表
     */
    async function reorderModels(platformId, orderedIds) {
        try {
            const res = await fetchWithAuth('/api/ai/admin/reorder-models', {
                method: 'POST',
                body: JSON.stringify({ platform_id: platformId, ordered_ids: orderedIds }),
                headers: { 'Content-Type': 'application/json' }
            });
            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.detail || '排序失败');
            }
            // 静默更新后台排序，无需重新加载列表数据
        } catch (e) {
            message.error('模型排序失败: ' + e.message);
        }
    }

    /**
     * 设为默认平台（管理员专用，sort_order 设为 0）
     * @param {number} platformId - 平台 ID
     */
    async function setDefaultPlatform(platformId) {
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
                const err = await res.json();
                throw new Error(err.detail || '设置失败');
            }
            notifyAiStoreSync();
        } catch (e) {
            platforms.value = oldOrder;
            message.error('设置默认平台失败: ' + e.message);
        }
    }

    // === 折叠状态缓存 ===
    function loadExpandedFromCache() {
        try {
            const cached = localStorage.getItem(EXPAND_CACHE_KEY);
            return cached ? JSON.parse(cached) : [];
        } catch {
            return [];
        }
    }

    function saveExpandedToCache() {
        localStorage.setItem(EXPAND_CACHE_KEY, JSON.stringify(expandedNames.value));
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
        // 管理员排序
        reorderPlatforms,
        reorderModels,
        setDefaultPlatform
    };
}
