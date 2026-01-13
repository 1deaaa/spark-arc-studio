
import { ref, computed, onMounted, h } from 'vue';
import { useMessage, NTag, NButton, NIcon, NPopconfirm } from 'naive-ui';
import { TrashOutline } from '@vicons/ionicons5';
import {
    getMyUsage, getAllUsers, getAllUsersUsage, getAllQuotas,
    setQuota, deleteQuota, setUserAdminStatus, formatTokens
} from '../services/adminService';
import { getUserInfo } from '../services/authService';

export function useAdminLogic() {
    const message = useMessage();

    // 状态
    const loading = ref(false);
    const isAdmin = ref(false);
    const myUsage = ref(null);
    const usageRange = ref('24h');
    const allUsers = ref([]);
    const allUsersUsage = ref([]);
    const quotaList = ref([]);
    const systemPlatforms = ref([]);

    // 限额表单
    const showQuotaModal = ref(false);
    const quotaSaving = ref(false);
    const quotaForm = ref({
        platformId: null,
        modelId: null,
        quotaType: 'unlimited',
        quotaValue: 100000,
    });

    const usageRangeLabel = computed(() => {
        switch (usageRange.value) {
            case '24h': return '过去24小时';
            case '7d': return '最近7天';
            case '30d': return '最近30天';
            default: return '统计';
        }
    });

    // 加载数据
    async function refreshData() {
        loading.value = true;
        try {
            // 获取用户信息
            const userInfo = await getUserInfo();
            isAdmin.value = userInfo.is_admin || false;

            // 获取我的使用统计
            myUsage.value = await getMyUsage(usageRange.value);

            // 如果是管理员，加载管理数据
            if (isAdmin.value) {
                const [users, usersUsage, quotasData] = await Promise.all([
                    getAllUsers(),
                    getAllUsersUsage(),
                    getAllQuotas(),
                ]);

                allUsers.value = users;
                allUsersUsage.value = usersUsage;
                quotaList.value = quotasData.quotas || [];
                systemPlatforms.value = quotasData.system_platforms || [];
            }
        } catch (error) {
            message.error('加载数据失败: ' + error.message);
        } finally {
            loading.value = false;
        }
    }

    // 仅刷新我的统计（用于切换时间范围）
    async function fetchMyUsageOnly() {
        try {
            myUsage.value = await getMyUsage(usageRange.value);
        } catch (error) {
            message.error('更新统计失败: ' + error.message);
        }
    }

    // 表格列定义
    const modelColumns = [
        { title: '模型', key: 'display_name', ellipsis: true },
        { title: '平台', key: 'platform_name', width: 100 },
        {
            title: 'Tokens',
            key: 'total_tokens',
            width: 100,
            render: (row) => formatTokens(row.total_tokens || 0)
        },
        { title: '调用', key: 'call_count', width: 60 },
    ];

    const agentColumns = [
        { title: 'Agent', key: 'agent_name', ellipsis: true },
        {
            title: 'Tokens',
            key: 'tokens',
            width: 100,
            render: (row) => formatTokens(row.tokens || 0)
        },
        { title: '调用', key: 'requests', width: 60 },
    ];

    const userColumns = computed(() => [
        { title: 'ID', key: 'user_id', width: 50 },
        { title: '用户名', key: 'username', ellipsis: true },
        {
            title: '管理员',
            key: 'is_admin',
            width: 80,
            render: (row) => h(NTag, {
                type: row.is_admin ? 'success' : 'default',
                size: 'small',
            }, () => row.is_admin ? '是' : '否')
        },
        {
            title: '状态',
            key: 'is_active',
            width: 70,
            render: (row) => h(NTag, {
                type: row.is_active ? 'success' : 'error',
                size: 'small',
            }, () => row.is_active ? '正常' : '禁用')
        },
        {
            title: '操作',
            key: 'actions',
            width: 100,
            render: (row) => h(NButton, {
                size: 'tiny',
                type: row.is_admin ? 'warning' : 'primary',
                onClick: () => toggleAdmin(row),
            }, () => row.is_admin ? '取消管理员' : '设为管理员')
        },
    ]);

    const quotaColumns = computed(() => [
        {
            title: '平台',
            key: 'platform_id',
            render: (row) => {
                const platform = systemPlatforms.value.find(p => p.platform_id === row.platform_id);
                return platform?.platform_name || `平台 ${row.platform_id}`;
            }
        },
        {
            title: '模型',
            key: 'model_id',
            render: (row) => {
                if (!row.model_id) return h(NTag, { size: 'small' }, () => '平台级');
                const model = systemPlatforms.value.find(
                    p => p.platform_id === row.platform_id && p.model_id === row.model_id
                );
                return model?.display_name || `模型 ${row.model_id}`;
            }
        },
        {
            title: '限额',
            key: 'quota_value',
            render: (row) => {
                if (row.quota_value === -1) {
                    return h(NTag, { type: 'success', size: 'small' }, () => '无限制');
                } else if (row.quota_value === 0) {
                    return h(NTag, { type: 'error', size: 'small' }, () => '已禁用');
                } else {
                    return h(NTag, { type: 'warning', size: 'small' }, () => formatTokens(row.quota_value) + '/日');
                }
            }
        },
        {
            title: '操作',
            key: 'actions',
            width: 80,
            render: (row) => h(NPopconfirm, {
                onPositiveClick: () => removeQuota(row),
            }, {
                trigger: () => h(NButton, {
                    size: 'tiny',
                    type: 'error',
                    quaternary: true,
                }, () => h(NIcon, null, () => h(TrashOutline))),
                default: () => '确定删除此限额配置？',
            })
        },
    ]);

    const allUsageColumns = [
        { title: '用户', key: 'user.username', ellipsis: true },
        {
            title: '24h Tokens',
            key: 'last_24h.tokens',
            render: (row) => formatTokens(row.last_24h?.tokens || 0)
        },
        {
            title: '24h 请求',
            key: 'last_24h.requests',
            render: (row) => row.last_24h?.requests || 0
        },
        {
            title: '累计 Tokens',
            key: 'total.tokens',
            render: (row) => formatTokens(row.total?.tokens || 0)
        },
        {
            title: '累计请求',
            key: 'total.requests',
            render: (row) => row.total?.requests || 0
        },
    ];

    // 平台选项
    const platformOptions = computed(() => {
        const seen = new Set();
        return systemPlatforms.value
            .filter(p => {
                if (seen.has(p.platform_id)) return false;
                seen.add(p.platform_id);
                return true;
            })
            .map(p => ({
                label: p.platform_name,
                value: p.platform_id,
            }));
    });

    // 模型选项（根据选中的平台过滤）
    const modelOptions = computed(() => {
        if (!quotaForm.value.platformId) return [];
        return systemPlatforms.value
            .filter(p => p.platform_id === quotaForm.value.platformId)
            .map(p => ({
                label: p.display_name,
                value: p.model_id,
            }));
    });

    function onPlatformChange() {
        quotaForm.value.modelId = null;
    }

    // 切换管理员状态
    async function toggleAdmin(user) {
        try {
            await setUserAdminStatus(user.user_id, !user.is_admin);
            message.success('管理员状态已更新');
            await refreshData();
        } catch (error) {
            message.error(error.message);
        }
    }

    // 保存限额
    async function saveQuota() {
        if (!quotaForm.value.platformId) {
            message.warning('请选择平台');
            return false;
        }

        let quotaValue;
        switch (quotaForm.value.quotaType) {
            case 'unlimited':
                quotaValue = -1;
                break;
            case 'disabled':
                quotaValue = 0;
                break;
            case 'limited':
                quotaValue = quotaForm.value.quotaValue || 100000;
                break;
            default:
                quotaValue = -1;
        }

        quotaSaving.value = true;
        try {
            await setQuota(quotaForm.value.platformId, quotaForm.value.modelId, quotaValue);
            message.success('限额已保存');
            showQuotaModal.value = false;

            // 重置表单
            quotaForm.value = {
                platformId: null,
                modelId: null,
                quotaType: 'unlimited',
                quotaValue: 100000,
            };

            await refreshData();
            return true;
        } catch (error) {
            message.error(error.message);
            return false;
        } finally {
            quotaSaving.value = false;
        }
    }

    // 删除限额
    async function removeQuota(quota) {
        try {
            await deleteQuota(quota.platform_id, quota.model_id);
            message.success('限额配置已删除');
            await refreshData();
        } catch (error) {
            message.error(error.message);
        }
    }

    onMounted(() => {
        refreshData();
    });

    return {
        loading,
        isAdmin,
        myUsage,
        usageRange,
        allUsers,
        allUsersUsage,
        quotaList,
        systemPlatforms,
        showQuotaModal,
        quotaSaving,
        quotaForm,
        usageRangeLabel,
        refreshData,
        fetchMyUsageOnly,
        modelColumns,
        agentColumns,
        userColumns,
        quotaColumns,
        allUsageColumns,
        platformOptions,
        modelOptions,
        onPlatformChange,
        toggleAdmin,
        saveQuota,
        removeQuota
    };
}
