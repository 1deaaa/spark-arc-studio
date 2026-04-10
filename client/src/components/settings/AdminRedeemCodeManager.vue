<template>
  <div class="settings-section">
    <div class="section-header">
      <div>
        <h3>{{ t('components.redeemCode.title') }}</h3>
        <p class="section-desc">{{ t('components.redeemCode.description') }}</p>
      </div>
      <n-button type="primary" size="small" @click="showCreateModal = true">
        <template #icon><n-icon><AddOutline /></n-icon></template>
        {{ t('components.redeemCode.create') }}
      </n-button>
    </div>

    <!-- 筛选栏 -->
    <div class="filter-bar">
      <n-select
        v-model:value="filterStatus"
        :options="statusOptions"
        :placeholder="t('components.redeemCode.filterStatus')"
        size="small"
        clearable
        style="width: 130px"
        @update:value="loadCodes"
      />
      <n-select
        v-model:value="filterType"
        :options="typeOptions"
        :placeholder="t('components.redeemCode.filterType')"
        size="small"
        clearable
        style="width: 130px"
        @update:value="() => loadCodes()"
      />
      <n-button quaternary size="small" @click="() => loadCodes()" :loading="loading">
        <template #icon><n-icon><RefreshOutline /></n-icon></template>
      </n-button>
    </div>

    <!-- 兑换码表格 -->
    <n-spin :show="loading">
      <n-data-table
        :columns="columns"
        :data="codes"
        :pagination="pagination"
        size="small"
        :max-height="400"
        :row-key="(row) => row.id"
      />
    </n-spin>

    <!-- 创建兑换码弹窗 -->
    <n-modal v-model:show="showCreateModal">
      <n-card
        style="width: 520px; max-width: calc(100vw - 48px);"
        :title="t('components.redeemCode.createTitle')"
        :bordered="false"
        size="huge"
        role="dialog"
        aria-modal="true"
      >
        <n-form :model="createForm" label-placement="top">
          <n-form-item :label="t('components.redeemCode.creditAmount')">
            <n-input-number v-model:value="createForm.credit_amount" :min="1" style="width: 100%" />
          </n-form-item>
          <n-form-item :label="t('components.redeemCode.codeType')">
            <n-radio-group v-model:value="createForm.code_type">
              <n-space>
                <n-radio value="single">{{ t('components.redeemCode.typeSingle') }}</n-radio>
                <n-radio value="per_user">{{ t('components.redeemCode.typePerUser') }}</n-radio>
              </n-space>
            </n-radio-group>
          </n-form-item>
          <n-form-item :label="t('components.redeemCode.customCode')">
            <n-input
              v-model:value="createForm.code"
              :placeholder="t('components.redeemCode.customCodePlaceholder')"
              clearable
            />
          </n-form-item>
          <n-form-item :label="t('components.redeemCode.batchCount')">
            <n-input-number v-model:value="createForm.count" :min="1" :max="100" style="width: 100%" />
          </n-form-item>
          <n-form-item :label="t('components.redeemCode.remark')">
            <n-input
              v-model:value="createForm.remark"
              :placeholder="t('components.redeemCode.remarkPlaceholder')"
              clearable
            />
          </n-form-item>
        </n-form>

        <template #footer>
          <div style="display: flex; justify-content: flex-end; gap: 12px;">
            <n-button @click="showCreateModal = false">{{ t('views.common.cancel') }}</n-button>
            <n-button type="primary" :loading="creating" @click="handleCreate">{{ t('components.redeemCode.create') }}</n-button>
          </div>
        </template>
      </n-card>
    </n-modal>

    <!-- 兑换码详情弹窗 -->
    <n-modal v-model:show="showDetailModal">
      <n-card
        style="width: 600px; max-width: calc(100vw - 48px);"
        :title="t('components.redeemCode.detailTitle')"
        :bordered="false"
        size="huge"
        role="dialog"
        aria-modal="true"
      >
        <template v-if="detailData">
          <n-descriptions label-placement="left" :column="2" bordered size="small">
            <n-descriptions-item :label="t('components.redeemCode.code')">
              <n-text code>{{ detailData.code }}</n-text>
            </n-descriptions-item>
            <n-descriptions-item :label="t('components.redeemCode.creditAmount')">
              {{ detailData.credit_amount }}<SparkIcon />
            </n-descriptions-item>
            <n-descriptions-item :label="t('components.redeemCode.codeType')">
              {{ detailData.code_type === 'single' ? t('components.redeemCode.typeSingle') : t('components.redeemCode.typePerUser') }}
            </n-descriptions-item>
            <n-descriptions-item :label="t('components.redeemCode.status')">
              <SparkTag :type="statusTagType(detailData.status)" size="small">
                {{ statusLabel(detailData.status) }}
              </SparkTag>
            </n-descriptions-item>
            <n-descriptions-item :label="t('components.redeemCode.remark')">
              {{ detailData.remark || '-' }}
            </n-descriptions-item>
            <n-descriptions-item :label="t('components.redeemCode.createdAt')">
              {{ formatDate(detailData.created_at) }}
            </n-descriptions-item>
          </n-descriptions>

          <!-- 使用记录 -->
          <n-divider style="margin: 12px 0">{{ t('components.redeemCode.usageRecords') }}</n-divider>
          <n-data-table
            v-if="detailData.usages && detailData.usages.length"
            :columns="usageColumns"
            :data="detailData.usages"
            :pagination="false"
            size="small"
            :max-height="200"
          />
          <n-empty v-else :description="t('components.redeemCode.noUsage')" size="small" />
        </template>

        <template #footer>
          <div style="display: flex; justify-content: flex-end; gap: 12px;">
            <n-button
              v-if="detailData?.status === 'active'"
              type="warning"
              @click="handleRevoke(detailData.id)"
            >{{ t('components.redeemCode.revoke') }}</n-button>
            <n-button @click="showDetailModal = false">{{ t('views.common.cancel') }}</n-button>
          </div>
        </template>
      </n-card>
    </n-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, h } from 'vue';
import { useI18n } from 'vue-i18n';
import { useMessage, NButton, NIcon, NTag, NPopconfirm, NText } from 'naive-ui';
import { AddOutline, RefreshOutline, EyeOutline, TrashOutline, BanOutline, CopyOutline } from '@vicons/ionicons5';
import SparkTag from '../share/SparkTag.vue';
import SparkIcon from '@/components/share/CreditIcon.vue';
import {
  listRedeemCodes,
  createRedeemCode,
  getRedeemCodeDetail,
  revokeRedeemCode,
  deleteRedeemCode,
} from '../../services/adminService';

const { t } = useI18n();
const message = useMessage();

const loading = ref(false);
const creating = ref(false);
const codes = ref<any[]>([]);
const total = ref(0);

const filterStatus = ref<string | null>(null);
const filterType = ref<string | null>(null);

const showCreateModal = ref(false);
const showDetailModal = ref(false);
const detailData = ref<any>(null);

const createForm = ref({
  credit_amount: 1000,
  code_type: 'single',
  code: '',
  remark: '',
  count: 1,
});

const pagination = computed(() => ({
  page: 1,
  pageSize: 20,
  itemCount: total.value,
}));

const statusOptions = computed(() => [
  { label: t('components.redeemCode.statusActive'), value: 'active' },
  { label: t('components.redeemCode.statusRevoked'), value: 'revoked' },
  { label: t('components.redeemCode.statusExhausted'), value: 'exhausted' },
]);

const typeOptions = computed(() => [
  { label: t('components.redeemCode.typeSingle'), value: 'single' },
  { label: t('components.redeemCode.typePerUser'), value: 'per_user' },
]);

function statusLabel(status: string) {
  const map: Record<string, string> = {
    active: t('components.redeemCode.statusActive'),
    revoked: t('components.redeemCode.statusRevoked'),
    exhausted: t('components.redeemCode.statusExhausted'),
  };
  return map[status] || status;
}

function statusTagType(status: string): 'success' | 'danger' | 'warning' | 'default' {
  const map: Record<string, 'success' | 'danger' | 'warning' | 'default'> = {
    active: 'success',
    revoked: 'danger',
    exhausted: 'warning',
  };
  return map[status] || 'default';
}

function formatDate(iso: string | null) {
  if (!iso) return '-';
  return new Date(iso).toLocaleString();
}

function copyCode(code: string) {
  navigator.clipboard.writeText(code).then(() => {
    message.success(t('components.redeemCode.copied'));
  });
}

const columns = computed(() => [
  {
    title: t('components.redeemCode.code'),
    key: 'code',
    width: 200,
    render: (row: any) =>
      h('div', { style: 'display: flex; align-items: center; gap: 4px;' }, [
        h(NText, { code: true }, () => row.code),
        h(NButton, {
          quaternary: true,
          size: 'tiny',
          onClick: () => copyCode(row.code),
        }, {
          icon: () => h(NIcon, null, () => h(CopyOutline)),
        }),
      ]),
  },
  {
    title: t('components.redeemCode.creditAmount'),
    key: 'credit_amount',
    width: 100,
    render: (row: any) => `${row.credit_amount}`,
  },
  {
    title: t('components.redeemCode.codeType'),
    key: 'code_type',
    width: 100,
    render: (row: any) =>
      h(SparkTag, { type: row.code_type === 'single' ? 'warning' : 'primary', size: 'tiny' }, () =>
        row.code_type === 'single' ? t('components.redeemCode.typeSingle') : t('components.redeemCode.typePerUser'),
      ),
  },
  {
    title: t('components.redeemCode.status'),
    key: 'status',
    width: 90,
    render: (row: any) =>
      h(SparkTag, { type: statusTagType(row.status), size: 'tiny' }, () => statusLabel(row.status)),
  },
  {
    title: t('components.redeemCode.usageCount'),
    key: 'usage_count',
    width: 80,
  },
  {
    title: t('components.redeemCode.createdAt'),
    key: 'created_at',
    width: 140,
    render: (row: any) => formatDate(row.created_at),
  },
  {
    title: t('components.redeemCode.actions'),
    key: 'actions',
    width: 120,
    render: (row: any) =>
      h('div', { style: 'display: flex; gap: 4px;' }, [
        h(NButton, {
          quaternary: true,
          size: 'tiny',
          onClick: () => handleDetail(row.id),
        }, {
          icon: () => h(NIcon, null, () => h(EyeOutline)),
        }),
        row.status === 'active'
          ? h(NPopconfirm, { onPositiveClick: () => handleRevoke(row.id) }, {
              trigger: () => h(NButton, { quaternary: true, size: 'tiny', type: 'warning' }, {
                icon: () => h(NIcon, null, () => h(BanOutline)),
              }),
              default: () => t('components.redeemCode.revokeConfirm'),
            })
          : null,
        h(NPopconfirm, { onPositiveClick: () => handleDelete(row.id) }, {
          trigger: () => h(NButton, { quaternary: true, size: 'tiny', type: 'error' }, {
            icon: () => h(NIcon, null, () => h(TrashOutline)),
          }),
          default: () => t('components.redeemCode.deleteConfirm'),
        }),
      ].filter(Boolean)),
  },
]);

const usageColumns = computed(() => [
  { title: 'User ID', key: 'user_id', width: 120 },
  { title: t('components.redeemCode.creditAmount'), key: 'delta_credit', width: 100 },
  { title: t('components.redeemCode.balanceAfter'), key: 'balance_after', width: 100 },
  { title: t('components.redeemCode.usedAt'), key: 'used_at', width: 160, render: (row: any) => formatDate(row.used_at) },
]);

async function loadCodes(page = 1) {
  loading.value = true;
  try {
    const offset = (page - 1) * 20;
    const data = await listRedeemCodes({
      status: filterStatus.value || undefined,
      code_type: filterType.value || undefined,
      limit: 20,
      offset,
    });
    codes.value = data.items || [];
    total.value = data.total || 0;
  } catch (e: any) {
    message.error(e.message || t('components.redeemCode.loadFailed'));
  } finally {
    loading.value = false;
  }
}

async function handleCreate() {
  creating.value = true;
  try {
    const payload: any = {
      credit_amount: createForm.value.credit_amount,
      code_type: createForm.value.code_type,
      count: createForm.value.count,
    };
    if (createForm.value.code?.trim()) {
      payload.code = createForm.value.code.trim();
    }
    if (createForm.value.remark?.trim()) {
      payload.remark = createForm.value.remark.trim();
    }
    const result = await createRedeemCode(payload);
    const count = Array.isArray(result) ? result.length : 1;
    message.success(t('components.redeemCode.created', { count }));
    showCreateModal.value = false;
    // 重置表单
    createForm.value = { credit_amount: 1000, code_type: 'single', code: '', remark: '', count: 1 };
    loadCodes();
  } catch (e: any) {
    message.error(e.message || t('components.redeemCode.createFailed'));
  } finally {
    creating.value = false;
  }
}

async function handleDetail(codeId: number) {
  try {
    detailData.value = await getRedeemCodeDetail(codeId);
    showDetailModal.value = true;
  } catch (e: any) {
    message.error(e.message || t('components.redeemCode.detailFailed'));
  }
}

async function handleRevoke(codeId: number) {
  try {
    await revokeRedeemCode(codeId);
    message.success(t('components.redeemCode.revoked'));
    showDetailModal.value = false;
    loadCodes();
  } catch (e: any) {
    message.error(e.message || t('components.redeemCode.revokeFailed'));
  }
}

async function handleDelete(codeId: number) {
  try {
    await deleteRedeemCode(codeId);
    message.success(t('components.redeemCode.deleted'));
    loadCodes();
  } catch (e: any) {
    message.error(e.message || t('components.redeemCode.deleteFailed'));
  }
}

onMounted(() => {
  loadCodes();
});
</script>

<style scoped>
.settings-section {
  background: var(--spark-panel-bg);
  border: 1px solid var(--spark-border);
  border-radius: var(--spark-radius);
  padding: var(--spark-panel-padding);
  margin-bottom: 20px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 8px;
}

.section-header h3 {
  margin: 0;
  font-size: 18px;
}

.section-desc {
  margin: 6px 0 0;
  color: var(--spark-text-muted);
  font-size: 13px;
}

.filter-bar {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-bottom: 12px;
}
</style>
