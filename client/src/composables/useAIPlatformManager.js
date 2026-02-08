/**
 * AI 平台管理 Composable
 * 从 AIManager.vue 提取的平台 CRUD 和配置管理逻辑
 */
import { ref, onMounted, onUnmounted } from 'vue';
import { useMessage, useDialog } from 'naive-ui';
import { bus } from '../eventBus';
import { fetchWithAuth } from '../services/api';
import { getUserInfo } from '../services/authService';

export function useAIPlatformManager() {
    const message = useMessage();
    const dialog = useDialog();

    // === 状态 ===
    const loading = ref(false);
    const saving = ref(false);
    const platforms = ref([]);
    const defaultExpanded = ref([]);
    const systemConfig = ref({ llm_auto_key: false, use_sys_llm_config: false });
    const isAdmin = ref(false);

    // 弹窗状态
    const showAddPlatformModal = ref(false);
    const showEditPlatformModal = ref(false);
    const showKeyModal = ref(false);
    const newPlatform = ref({ name: '', baseUrl: '', apiKey: '' });
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
                const firstCustom = platforms.value.find(p => !p.is_sys);
                if (firstCustom) {
                    defaultExpanded.value = [firstCustom.platform_id];
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
            const res = await fetchWithAuth('/api/ai/platform', {
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
            message.success('平台创建成功');
            showAddPlatformModal.value = false;
            newPlatform.value = { name: '', baseUrl: '', apiKey: '' };
            await loadPlatforms();
        } catch (e) {
            message.error(e.message);
        } finally {
            saving.value = false;
        }
    }

    async function handleUpdatePlatform() {
        saving.value = true;
        try {
            const res = await fetchWithAuth('/api/ai/platform', {
                method: 'PUT',
                body: JSON.stringify({
                    id: editingPlatform.value.id,
                    name: editingPlatform.value.name,
                    base_url: editingPlatform.value.baseUrl
                }),
                headers: { 'Content-Type': 'application/json' }
            });
            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.detail || '更新失败');
            }
            message.success('平台更新成功');
            showEditPlatformModal.value = false;
            await loadPlatforms();
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

        saving.value = true;
        try {
            const res = await fetchWithAuth(`/api/ai/platform-config`, {
                method: 'POST',
                body: JSON.stringify({
                    platform_id: editingPlatform.value.id,
                    api_key: editingApiKey.value
                }),
                headers: { 'Content-Type': 'application/json' }
            });
            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.detail || '更新失败');
            }
            message.success('API Key 更新成功');
            showKeyModal.value = false;
            await loadPlatforms();
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
            onPositive: () => doDeletePlatform(plat)
        });
    }

    async function doDeletePlatform(plat) {
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
            message.success('平台已删除');
            await loadPlatforms();
        } catch (e) {
            message.error(e.message);
        }
    }

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
        defaultExpanded,
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
        doDeletePlatform
    };
}
