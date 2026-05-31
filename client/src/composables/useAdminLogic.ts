
import { ref, computed, onMounted, h } from 'vue';
import { useMessage, NTag, NButton, NIcon, NPopconfirm, NSpace, NTooltip } from 'naive-ui';
import { Trash, Ban, Unlock } from '@lucide/vue';
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
    setUserActiveStatus,
    deleteUser as deleteUserService,
    formatTokens,
    formatPrice,
    getAllUserCreditAccounts,
    adjustUserCredit,
    getModelCreditPricing,
    saveModelCreditPricing,
} from '../services/adminService';
import { getUserInfo } from '../services/authService';

type UsageRange = '24h' | '7d' | '30d' | 'total';

type UserItem = {
    user_id: number;
    username: string;
    is_admin: boolean;
    is_active: boolean;
};

type UsageSummary = {
    tokens?: number;
    requests?: number;
    errors?: number;
    [key: string]: unknown;
};

type UsageModelItem = {
    display_name?: string;
    platform_name?: string;
    total_tokens?: number;
    call_count?: number;
};

type UsageAgentItem = {
    agent_name?: string;
    tokens?: number;
    requests?: number;
};

type MyUsageData = {
    by_model?: UsageModelItem[];
    by_agent?: UsageAgentItem[];
    range_stats?: UsageSummary;
    last_24h?: UsageSummary;
    total?: UsageSummary;
};

type AllUserUsageRow = {
    user: UserItem;
    last_24h?: UsageSummary;
    total?: UsageSummary;
};

type QuotaStatusUsage = {
    tokens?: number;
    requests?: number;
    errors?: number;
};

type QuotaStatusBucket = {
    total?: {
        usage?: QuotaStatusUsage;
    };
};

type QuotaStatusData = {
    sys_paid?: QuotaStatusBucket;
    self_paid?: QuotaStatusBucket;
    [key: string]: unknown;
};

type CreditStatusData = {
    credit_used_from_usage?: number;
    [key: string]: unknown;
};

type UserCreditAccountItem = {
    user?: UserItem;
    account?: {
        credit_balance?: number;
        credit_total_granted?: number;
        credit_total_used?: number;
        requests?: number;
        status?: string;
    };
};

type ModelCreditPricingItem = {
    platform_id: number;
    model_id: number;
    display_name?: string;
    model_name?: string;
    model_input_price_per_million?: number | null;
    model_output_price_per_million?: number | null;
    remark?: string | null;
};

type QuotaItem = {
    id: number;
    platform_id: number;
    model_id: number | null;
    quota_value: number;
};

type SystemPlatformItem = {
    platform_id: number;
    platform_name: string;
    model_id?: number;
    display_name?: string;
};

type QuotasResponse = {
    quotas?: QuotaItem[];
    system_platforms?: SystemPlatformItem[];
};

type CreditAdjustForm = {
    deltaCredit: number;
    remark: string;
};

type PricingForm = {
    platformId: number | null;
    modelId: number | null;
    modelInputPricePerMillion: number;
    modelOutputPricePerMillion: number;
    remark: string;
};

type QuotaType = 'unlimited' | 'disabled' | 'limited';

type QuotaForm = {
    platformId: number | null;
    modelId: number | null;
    quotaType: QuotaType;
    quotaValue: number;
};

function getErrorMessage(error: unknown): string {
    if (error instanceof Error) return error.message;
    return String(error || '未知错误');
}

function createEmptyCreditAdjustForm(): CreditAdjustForm {
    return {
        deltaCredit: 0,
        remark: '',
    };
}

function createEmptyPricingForm(): PricingForm {
    return {
        platformId: null,
        modelId: null,
        modelInputPricePerMillion: 0,
        modelOutputPricePerMillion: 0,
        remark: '',
    };
}

export function useAdminLogic() {
    const message = useMessage();

    const loading = ref(false);
    const isAdmin = ref(false);
    const currentUserId = ref<number | null>(null);
    const myUsage = ref<MyUsageData | null>(null);
    const myQuotaStatus = ref<QuotaStatusData | null>(null);
    const myCreditStatus = ref<CreditStatusData | null>(null);
    const usageRange = ref<UsageRange>('24h');
    const allUsers = ref<UserItem[]>([]);
    const allUsersUsage = ref<AllUserUsageRow[]>([]);
    const userCreditAccounts = ref<UserCreditAccountItem[]>([]);
    const modelCreditPricing = ref<ModelCreditPricingItem[]>([]);
    const quotaList = ref<QuotaItem[]>([]);
    const systemPlatforms = ref<SystemPlatformItem[]>([]);

    const showQuotaModal = ref(false);
    const quotaSaving = ref(false);
    const quotaForm = ref<QuotaForm>({
        platformId: null,
        modelId: null,
        quotaType: 'unlimited',
        quotaValue: 100000,
    });

    const showCreditAdjustModal = ref(false);
    const creditAdjustSaving = ref(false);
    const activeCreditUser = ref<UserCreditAccountItem | null>(null);
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
            const uid = userInfo.user_id;
            currentUserId.value = typeof uid === 'number' ? uid : (uid != null ? Number(uid) : null);

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
                const quotasPayload = quotasData as QuotasResponse;
                quotaList.value = quotasPayload.quotas || [];
                systemPlatforms.value = quotasPayload.system_platforms || [];
            }
        } catch (error: unknown) {
            message.error('加载数据失败: ' + getErrorMessage(error));
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
        } catch (error: unknown) {
            message.error('更新统计失败: ' + getErrorMessage(error));
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
            render: (row: UsageModelItem) => formatTokens(row.total_tokens || 0)
        },
        { title: '调用', key: 'call_count', width: 72 },
    ];

    const agentColumns = [
        { title: 'Agent', key: 'agent_name', ellipsis: true },
        {
            title: 'Tokens',
            key: 'tokens',
            width: 100,
            render: (row: UsageAgentItem) => formatTokens(row.tokens || 0)
        },
        { title: '调用', key: 'requests', width: 60 },
    ];

    const userColumns = computed(() => {
        const myId = currentUserId.value;
        return [
            { title: 'ID', key: 'user_id', width: 56, align: 'center' as const },
            { title: '用户名', key: 'username', ellipsis: { tooltip: true } },
            {
                title: '管理员',
                key: 'is_admin',
                width: 80,
                align: 'center' as const,
                render: (row: UserItem) => h(NTag, {
                    type: row.is_admin ? 'success' : 'default',
                    size: 'small',
                    bordered: false,
                    round: true,
                }, () => row.is_admin ? '是' : '否')
            },
            {
                title: '状态',
                key: 'is_active',
                width: 90,
                align: 'center' as const,
                render: (row: UserItem) => h(NTag, {
                    type: row.is_active ? 'success' : 'error',
                    size: 'small',
                    bordered: false,
                    round: true,
                }, () => row.is_active ? '正常' : '已封禁')
            },
            {
                title: '操作',
                key: 'actions',
                width: 280,
                align: 'center' as const,
                render: (row: UserItem) => {
                    const isSelf = myId !== null && row.user_id === myId;
                    const isInitialAdmin = row.user_id === 1;
                    const protectedFromBan = isSelf || isInitialAdmin;
                    const protectedFromDelete = isSelf || isInitialAdmin;
                    const protectReason = isInitialAdmin ? '初始管理员受保护' : '不能对自己执行此操作';

                    const adminBtn = h(NButton, {
                        size: 'tiny',
                        type: row.is_admin ? 'warning' : 'primary',
                        secondary: true,
                        disabled: isInitialAdmin && row.is_admin,
                        onClick: () => toggleAdmin(row),
                    }, () => row.is_admin ? '取消管理员' : '设为管理员');

                    const banBtnRaw = h(NButton, {
                        size: 'tiny',
                        type: row.is_active ? 'error' : 'success',
                        secondary: true,
                        disabled: protectedFromBan,
                    }, {
                        icon: () => h(NIcon, null, () => h(row.is_active ? Ban : Unlock)),
                        default: () => row.is_active ? '封禁' : '解封',
                    });
                    const banBtn = protectedFromBan
                        ? h(NTooltip, null, {
                            trigger: () => h('span', { style: 'display:inline-flex' }, [banBtnRaw]),
                            default: () => protectReason,
                        })
                        : h(NPopconfirm, {
                            onPositiveClick: () => toggleUserActive(row),
                        }, {
                            trigger: () => banBtnRaw,
                            default: () => row.is_active
                                ? `确定封禁用户「${row.username}」？封禁后该用户将无法登录`
                                : `确定解封用户「${row.username}」？`,
                        });

                    const delBtnRaw = h(NButton, {
                        size: 'tiny',
                        type: 'error',
                        tertiary: true,
                        disabled: protectedFromDelete,
                    }, {
                        icon: () => h(NIcon, null, () => h(Trash)),
                        default: () => '删除',
                    });
                    const delBtn = protectedFromDelete
                        ? h(NTooltip, null, {
                            trigger: () => h('span', { style: 'display:inline-flex' }, [delBtnRaw]),
                            default: () => protectReason,
                        })
                        : h(NPopconfirm, {
                            onPositiveClick: () => deleteUser(row),
                        }, {
                            trigger: () => delBtnRaw,
                            default: () => `确定删除用户「${row.username}」？此操作不可恢复`,
                        });

                    return h(NSpace, { size: 6, align: 'center', justify: 'center', wrap: false }, () => [
                        adminBtn,
                        banBtn,
                        delBtn,
                    ]);
                }
            },
        ];
    });

    const userCreditColumns = computed(() => [
        {
            title: '用户',
            key: 'user.username',
            render: (row: UserCreditAccountItem) => row.user?.username || `用户 ${row.user?.user_id ?? '-'}`
        },
        {
            title: '当前火柴',
            key: 'account.credit_balance',
            render: (row: UserCreditAccountItem) => formatTokens(row.account?.credit_balance || 0)
        },
        {
            title: '累计发放',
            key: 'account.credit_total_granted',
            render: (row: UserCreditAccountItem) => formatTokens(row.account?.credit_total_granted || 0)
        },
        {
            title: '累计消耗',
            key: 'account.credit_total_used',
            render: (row: UserCreditAccountItem) => formatTokens(row.account?.credit_total_used || 0)
        },
        {
            title: '系统请求',
            key: 'account.requests',
            render: (row: UserCreditAccountItem) => row.account?.requests || 0
        },
        {
            title: '状态',
            key: 'account.status',
            render: (row: UserCreditAccountItem) => h(NTag, {
                size: 'small',
                type: row.account?.status === 'active' ? 'success' : 'warning',
            }, () => row.account?.status || 'active')
        },
        {
            title: '操作',
            key: 'actions',
            width: 88,
            render: (row: UserCreditAccountItem) => h(NButton, {
                size: 'tiny',
                type: 'primary',
                secondary: true,
                onClick: () => openCreditAdjustModal(row),
            }, () => '增减')
        },
    ]);

    const modelCreditPricingColumns = computed(() => [
        {
            title: '平台',
            key: 'platform_id',
            render: (row: ModelCreditPricingItem) => systemPlatforms.value.find(p => p.platform_id === row.platform_id)?.platform_name || `平台 ${row.platform_id}`
        },
        {
            title: '模型',
            key: 'model_id',
            render: (row: ModelCreditPricingItem) => row.display_name || row.model_name || `模型 ${row.model_id}`
        },
        {
            title: '输入价/1M',
            key: 'model_input_price_per_million',
            render: (row: ModelCreditPricingItem) => formatPrice(row.model_input_price_per_million || 0)
        },
        {
            title: '输出价/1M',
            key: 'model_output_price_per_million',
            render: (row: ModelCreditPricingItem) => formatPrice(row.model_output_price_per_million || 0)
        },
        {
            title: '操作',
            key: 'actions',
            width: 88,
            render: (row: ModelCreditPricingItem) => h(NButton, {
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
            render: (row: QuotaItem) => {
                const platform = systemPlatforms.value.find(p => p.platform_id === row.platform_id);
                return platform?.platform_name || `平台 ${row.platform_id}`;
            }
        },
        {
            title: '模型',
            key: 'model_id',
            render: (row: QuotaItem) => {
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
            render: (row: QuotaItem) => {
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
            render: (row: QuotaItem) => h(NPopconfirm, {
                onPositiveClick: () => removeQuota(row),
            }, {
                trigger: () => h(NButton, {
                    size: 'tiny',
                    type: 'error',
                    quaternary: true,
                }, () => h(NIcon, null, () => h(Trash))),
                default: () => '确定删除此限额配置？',
            })
        },
    ]);

    const allUsageColumns = [
        { title: '用户', key: 'user.username', ellipsis: true },
        {
            title: '24h Tokens',
            key: 'last_24h.tokens',
            render: (row: AllUserUsageRow) => formatTokens(row.last_24h?.tokens || 0)
        },
        {
            title: '24h 请求',
            key: 'last_24h.requests',
            render: (row: AllUserUsageRow) => row.last_24h?.requests || 0
        },
        {
            title: '累计 Tokens',
            key: 'total.tokens',
            render: (row: AllUserUsageRow) => formatTokens(row.total?.tokens || 0)
        },
        {
            title: '累计请求',
            key: 'total.requests',
            render: (row: AllUserUsageRow) => row.total?.requests || 0
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

    function openCreditAdjustModal(row: UserCreditAccountItem) {
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
            message.success('用户火柴已调整');
            showCreditAdjustModal.value = false;
            await refreshData();
            return true;
        } catch (error: unknown) {
            message.error(getErrorMessage(error));
            return false;
        } finally {
            creditAdjustSaving.value = false;
        }
    }

    async function openPricingModal(row: ModelCreditPricingItem | null = null) {
        if (row) {
            pricingForm.value = {
                platformId: row.platform_id,
                modelId: row.model_id,
                modelInputPricePerMillion: row.model_input_price_per_million || 0,
                modelOutputPricePerMillion: row.model_output_price_per_million || 0,
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
                model_input_price_per_million: Number(pricingForm.value.modelInputPricePerMillion || 0),
                model_output_price_per_million: Number(pricingForm.value.modelOutputPricePerMillion || 0),
                remark: pricingForm.value.remark || null,
            });
            message.success('模型点数定价已保存');
            showPricingModal.value = false;
            await refreshData();
            return true;
        } catch (error: unknown) {
            message.error(getErrorMessage(error));
            return false;
        } finally {
            pricingSaving.value = false;
        }
    }

    async function toggleAdmin(user: UserItem) {
        try {
            await setUserAdminStatus(user.user_id, !user.is_admin);
            message.success('管理员状态已更新');
            await refreshData();
        } catch (error: unknown) {
            message.error(getErrorMessage(error));
        }
    }

    async function toggleUserActive(user: UserItem) {
        try {
            await setUserActiveStatus(user.user_id, !user.is_active);
            message.success(user.is_active ? '用户已封禁' : '用户已解封');
            await refreshData();
        } catch (error: unknown) {
            message.error(getErrorMessage(error));
        }
    }

    async function deleteUser(user: UserItem) {
        try {
            await deleteUserService(user.user_id);
            message.success('用户已删除');
            await refreshData();
        } catch (error: unknown) {
            message.error(getErrorMessage(error));
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
        } catch (error: unknown) {
            message.error(getErrorMessage(error));
            return false;
        } finally {
            quotaSaving.value = false;
        }
    }

    async function removeQuota(quota: QuotaItem) {
        try {
            await deleteQuota(quota.platform_id, quota.model_id);
            message.success('限额配置已删除');
            await refreshData();
        } catch (error: unknown) {
            message.error(getErrorMessage(error));
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
        toggleUserActive,
        deleteUser,
        saveQuota,
        removeQuota,
        submitCreditAdjust,
        submitPricing,
    };
}
