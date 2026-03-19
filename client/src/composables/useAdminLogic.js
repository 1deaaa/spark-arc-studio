
import { ref, computed, onMounted, h } from 'vue';
import { useMessage, NTag, NButton, NIcon, NPopconfirm } from 'naive-ui';
import { TrashOutline } from '@vicons/ionicons5';
import {
    getMyUsage,
    getMyQuotaStatus,
    getMyCreditStatus,
    getAllUsers,
    getAllUsersUsage,
    getAllQuotas,
    setQuota,
    deleteQuota,
    setUserAdminStatus,
    formatTokens,
    getAllUserCreditAccounts,
    getUserCreditAccount,
    adjustUserCredit,
    getModelCreditPricing,
    saveModelCreditPricing,
} from '../services/adminService';
import { getUserInfo } from '../services/authService';

function createEmptyCreditAdjustForm() {
    return {
        deltaCredit: 0,
        remark: '',
    };
}

function createEmptyPricingForm() {
    return {
        platformId: null,
        modelId: null,
        requestBaseCost: 0,
        promptTokenCostPer1k: 0,
        completionTokenCostPer1k: 0,
        isEnabled: true,
        remark: '',
    };
}

export function useAdminLogic() {
    const message = useMessage();

    const loading = ref(false);
    const isAdmin = ref(false);
    const myUsage = ref(null);
    const myQuotaStatus = ref(null);
    const myCreditStatus = ref(null);
    const usageRange = ref('24h');
    const allUsers = ref([]);
    const allUsersUsage = ref([]);
    const userCreditAccounts = ref([]);
    const modelCreditPricing = ref([]);
    const quotaList = ref([]);
    const systemPlatforms = ref([]);

    const showQuotaModal = ref(false);
    const quotaSaving = ref(false);
    const quotaForm = ref({
        platformId: null,
        modelId: null,
        quotaType: 'unlimited',
        quotaValue: 100000,
    });

    const showCreditAdjustModal = ref(false);
    const creditAdjustSaving = ref(false);
    const activeCreditUser = ref(null);
    const creditAdjustForm = ref(createEmptyCreditAdjustForm());

    const showPricingModal = ref(false);
    const pricingSaving = ref(false);
    const pricingForm = ref(createEmptyPricingForm());

    const usageRangeLabel = computed(() => {
        switch (usageRange.value) {
            case '24h': return '过去24小时';
            case '7d': return '最近7天';
            case '30d': return '最近30天';
            case 'total': return '全部';
            default: return '统计';
        }
    });

    async function refreshData() {
        loading.value = true;
        try {
            const userInfo = await getUserInfo();
            isAdmin.value = userInfo.is_admin || false;

            const [usageData, quotaStatus, creditStatus] = await Promise.all([
                getMyUsage(usageRange.value),
                getMyQuotaStatus(),
                getMyCreditStatus(),
            ]);
            myUsage.value = usageData;
            myQuotaStatus.value = quotaStatus;
            myCreditStatus.value = creditStatus;

            if (isAdmin.value) {
                const [users, usersUsage, quotasData, creditAccounts, pricingList] = await Promise.all([
                    getAllUsers(),
                    getAllUsersUsage(),
                    getAllQuotas(),
                    getAllUserCreditAccounts(),
                    getModelCreditPricing(),
                ]);

                allUsers.value = users;
                allUsersUsage.value = usersUsage;
                userCreditAccounts.value = creditAccounts;
                modelCreditPricing.value = pricingList;
                quotaList.value = quotasData.quotas || [];
                systemPlatforms.value = quotasData.system_platforms || [];
            }
        } catch (error) {
            message.error('加载数据失败: ' + error.message);
        } finally {
            loading.value = false;
        }
    }

    async function fetchMyUsageOnly() {
        try {
            const [usageData, quotaStatus, creditStatus] = await Promise.all([
                getMyUsage(usageRange.value),
                getMyQuotaStatus(),
                getMyCreditStatus(),
            ]);
            myUsage.value = usageData;
            myQuotaStatus.value = quotaStatus;
            myCreditStatus.value = creditStatus;
        } catch (error) {
            message.error('更新统计失败: ' + error.message);
        }
    }

    const modelColumns = [
        { title: '模型', key: 'display_name', ellipsis: { tooltip: true } },
        { title: '平台', key: 'platform_name', width: 160, ellipsis: { tooltip: true } },
        {
            title: 'Tokens',
            key: 'total_tokens',
            width: 120,
            ellipsis: { tooltip: true },
            render: (row) => formatTokens(row.total_tokens || 0)
        },
        { title: '调用', key: 'call_count', width: 72 },
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

    const userCreditColumns = computed(() => [
        {
            title: '用户',
            key: 'user.username',
            render: (row) => row.user?.username || `用户 ${row.user?.user_id ?? '-'}`
        },
        {
            title: '当前点数',
            key: 'account.credit_balance',
            render: (row) => formatTokens(row.account?.credit_balance || 0)
        },
        {
            title: '累计发放',
            key: 'account.credit_total_granted',
            render: (row) => formatTokens(row.account?.credit_total_granted || 0)
        },
        {
            title: '累计消耗',
            key: 'account.credit_total_used',
            render: (row) => formatTokens(row.account?.credit_total_used || 0)
        },
        {
            title: '系统请求',
            key: 'account.requests',
            render: (row) => row.account?.requests || 0
        },
        {
            title: '状态',
            key: 'account.status',
            render: (row) => h(NTag, {
                size: 'small',
                type: row.account?.status === 'active' ? 'success' : 'warning',
            }, () => row.account?.status || 'active')
        },
        {
            title: '操作',
            key: 'actions',
            width: 88,
            render: (row) => h(NButton, {
                size: 'tiny',
                type: 'primary',
                secondary: true,
                onClick: () => openCreditAdjustModal(row),
            }, () => '调账')
        },
    ]);

    const modelCreditPricingColumns = computed(() => [
        {
            title: '平台',
            key: 'platform_id',
            render: (row) => systemPlatforms.value.find(p => p.platform_id === row.platform_id)?.platform_name || `平台 ${row.platform_id}`
        },
        {
            title: '模型',
            key: 'model_id',
            render: (row) => row.display_name || row.model_name || `模型 ${row.model_id}`
        },
        {
            title: '基础费',
            key: 'request_base_cost',
            render: (row) => formatTokens(row.request_base_cost || 0)
        },
        {
            title: '输入/1K',
            key: 'prompt_token_cost_per_1k',
            render: (row) => formatTokens(row.prompt_token_cost_per_1k || 0)
        },
        {
            title: '输出/1K',
            key: 'completion_token_cost_per_1k',
            render: (row) => formatTokens(row.completion_token_cost_per_1k || 0)
        },
        {
            title: '状态',
            key: 'is_enabled',
            render: (row) => h(NTag, {
                size: 'small',
                type: row.is_enabled ? 'success' : 'default',
            }, () => row.is_enabled ? '启用' : '停用')
        },
        {
            title: '操作',
            key: 'actions',
            width: 88,
            render: (row) => h(NButton, {
                size: 'tiny',
                type: 'primary',
                secondary: true,
                onClick: () => openPricingModal(row),
            }, () => '编辑')
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

    const modelOptions = computed(() => {
        if (!quotaForm.value.platformId) return [];
        return systemPlatforms.value
            .filter(p => p.platform_id === quotaForm.value.platformId)
            .map(p => ({
                label: p.display_name,
                value: p.model_id,
            }));
    });

    const pricingModelOptions = computed(() => {
        if (!pricingForm.value.platformId) return [];
        return systemPlatforms.value
            .filter(p => p.platform_id === pricingForm.value.platformId)
            .map(p => ({
                label: p.display_name,
                value: p.model_id,
            }));
    });

    function onPlatformChange() {
        quotaForm.value.modelId = null;
    }

    function onPricingPlatformChange() {
        pricingForm.value.modelId = null;
    }

    function openCreditAdjustModal(row) {
        activeCreditUser.value = row;
        creditAdjustForm.value = createEmptyCreditAdjustForm();
        showCreditAdjustModal.value = true;
    }

    async function submitCreditAdjust() {
        if (!activeCreditUser.value?.user?.user_id) {
            message.warning('未选择用户');
            return false;
        }
        creditAdjustSaving.value = true;
        try {
            await adjustUserCredit(
                activeCreditUser.value.user.user_id,
                Number(creditAdjustForm.value.deltaCredit || 0),
                creditAdjustForm.value.remark || ''
            );
            message.success('用户点数已调整');
            showCreditAdjustModal.value = false;
            await refreshData();
            return true;
        } catch (error) {
            message.error(error.message);
            return false;
        } finally {
            creditAdjustSaving.value = false;
        }
    }

    async function openPricingModal(row = null) {
        if (row) {
            pricingForm.value = {
                platformId: row.platform_id,
                modelId: row.model_id,
                requestBaseCost: row.request_base_cost || 0,
                promptTokenCostPer1k: row.prompt_token_cost_per_1k || 0,
                completionTokenCostPer1k: row.completion_token_cost_per_1k || 0,
                isEnabled: !!row.is_enabled,
                remark: row.remark || '',
            };
        } else {
            pricingForm.value = createEmptyPricingForm();
        }
        showPricingModal.value = true;
    }

    async function submitPricing() {
        if (!pricingForm.value.platformId || !pricingForm.value.modelId) {
            message.warning('请选择平台和模型');
            return false;
        }
        pricingSaving.value = true;
        try {
            await saveModelCreditPricing({
                platform_id: pricingForm.value.platformId,
                model_id: pricingForm.value.modelId,
                request_base_cost: Number(pricingForm.value.requestBaseCost || 0),
                prompt_token_cost_per_1k: Number(pricingForm.value.promptTokenCostPer1k || 0),
                completion_token_cost_per_1k: Number(pricingForm.value.completionTokenCostPer1k || 0),
                is_enabled: !!pricingForm.value.isEnabled,
                remark: pricingForm.value.remark || null,
            });
            message.success('模型点数定价已保存');
            showPricingModal.value = false;
            await refreshData();
            return true;
        } catch (error) {
            message.error(error.message);
            return false;
        } finally {
            pricingSaving.value = false;
        }
    }

    async function toggleAdmin(user) {
        try {
            await setUserAdminStatus(user.user_id, !user.is_admin);
            message.success('管理员状态已更新');
            await refreshData();
        } catch (error) {
            message.error(error.message);
        }
    }

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
        myQuotaStatus,
        myCreditStatus,
        usageRange,
        allUsers,
        allUsersUsage,
        userCreditAccounts,
        modelCreditPricing,
        quotaList,
        systemPlatforms,
        showQuotaModal,
        quotaSaving,
        quotaForm,
        showCreditAdjustModal,
        creditAdjustSaving,
        activeCreditUser,
        creditAdjustForm,
        showPricingModal,
        pricingSaving,
        pricingForm,
        usageRangeLabel,
        refreshData,
        fetchMyUsageOnly,
        modelColumns,
        agentColumns,
        userColumns,
        userCreditColumns,
        modelCreditPricingColumns,
        quotaColumns,
        allUsageColumns,
        platformOptions,
        modelOptions,
        pricingModelOptions,
        onPlatformChange,
        onPricingPlatformChange,
        openCreditAdjustModal,
        openPricingModal,
        toggleAdmin,
        saveQuota,
        removeQuota,
        submitCreditAdjust,
        submitPricing,
    };
}
