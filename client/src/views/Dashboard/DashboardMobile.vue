
<template>
  <div class="view-container">
    <div class="mobile-content">
       <n-spin :show="loading">
          <n-card :title="t('views.dashboard.mobile.usageOverview')" size="small">
             <template #header-extra>
                <n-space :size="6" align="center">
                  <SparkSegment
                    :model-value="usageRange"
                    :options="usageRangeOptions"
                    size="tiny"
                    @update:model-value="handleUsageRangeChange"
                  />
                  <n-tooltip trigger="hover">
                    <template #trigger>
                      <n-button circle quaternary size="tiny" @click="fetchMyUsageOnly()">
                        <template #icon><n-icon><RefreshCw /></n-icon></template>
                      </n-button>
                    </template>
                    {{ t('views.dashboard.desktop.refreshStats') }}
                  </n-tooltip>
                </n-space>
             </template>
             <n-space vertical>
               <n-statistic :label="usageRangeLabel">
                 {{ formatTokenWithCredit(myUsage?.range_stats?.tokens || 0, myUsage?.range_stats?.credit_cost || 0) }}<n-tooltip trigger="hover"><template #trigger><SparkIcon style="cursor:help" /></template>{{ t('views.dashboard.desktop.creditIconHint') }}</n-tooltip>
               </n-statistic>
               <n-grid :cols="2" x-gap="8" y-gap="8" style="margin-top: 12px">
                  <n-gi>
                  <n-statistic :label="t('views.dashboard.mobile.request')" size="small">{{ myUsage?.range_stats?.requests || 0 }}</n-statistic>
                  </n-gi>
                  <n-gi>
                  <n-statistic :label="t('views.dashboard.mobile.error')" size="small">{{ myUsage?.range_stats?.errors || 0 }}</n-statistic>
                  </n-gi>
               </n-grid>
               <n-grid :cols="2" x-gap="8" y-gap="8" style="margin-top: 12px">
                  <n-gi>
                  <n-statistic :label="t('views.dashboard.desktop.systemCreditBalance')" size="small">{{ formatCreditExact(myCreditStatus?.credit_balance || 0) }}<n-tooltip trigger="hover"><template #trigger><SparkIcon style="cursor:help" /></template>{{ t('views.dashboard.desktop.creditIconHint') }}</n-tooltip></n-statistic>
                  </n-gi>
                  <n-gi>
                  <n-statistic :label="t('views.dashboard.desktop.totalGrantedCredit')" size="small">{{ formatCreditExact(myCreditStatus?.credit_total_granted || 0) }}</n-statistic>
                  </n-gi>
               </n-grid>
               <n-grid :cols="2" x-gap="8" y-gap="8" style="margin-top: 12px">
                  <n-gi>
                  <n-statistic :label="t('views.dashboard.desktop.systemPaid')" size="small">{{ formatTokenWithCredit(myQuotaStatus?.sys_paid?.total?.usage?.tokens || 0, myCreditStatus?.credit_used_from_usage || 0) }}<n-tooltip trigger="hover"><template #trigger><SparkIcon style="cursor:help" /></template>{{ t('views.dashboard.desktop.creditIconHint') }}</n-tooltip></n-statistic>
                  </n-gi>
                  <n-gi>
                  <n-statistic :label="t('views.dashboard.desktop.selfPaid')" size="small">{{ formatTokenWithCredit(myQuotaStatus?.self_paid?.total?.usage?.tokens || 0, null, true) }}</n-statistic>
                  </n-gi>
               </n-grid>
               <n-grid :cols="2" x-gap="8" y-gap="8" style="margin-top: 12px">
                  <n-gi>
                  <n-statistic :label="t('views.dashboard.desktop.systemRequestCount')" size="small">{{ myCreditStatus?.requests || 0 }}</n-statistic>
                  </n-gi>
                  <n-gi>
                  <n-statistic :label="t('views.dashboard.desktop.totalErrorCount')" size="small">{{ myUsage?.range_stats?.errors || 0 }}</n-statistic>
                  </n-gi>
               </n-grid>
             </n-space>
          </n-card>

          <UserRedeemCard style="margin-top: 12px" />
          <FeedbackCard :is-admin="isAdmin" style="margin-top: 12px" />

           <n-card :title="t('views.dashboard.mobile.modelUsage')" size="small" style="margin-top: 12px">
             <n-data-table
               class="usage-model-table"
               :columns="modelColumnsForTable"
               :data="myUsage?.by_model || []"
               :pagination="false"
               size="small"
               scroll-x="420"
             />
          </n-card>

          <AdminRedeemCodeManager v-if="isAdmin" style="margin-top: 12px" />

          <div v-if="isAdmin" class="admin-only-hint">
         {{ t('views.dashboard.mobile.adminOnlyHint') }}
          </div>
       </n-spin>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';
import { NCard, NButton, NIcon, NStatistic, NGrid, NGi, NDataTable, NSpin, NSpace, NTooltip } from 'naive-ui';
import SparkSegment from '../../components/share/SparkSegment.vue';
import SparkIcon from '../../components/share/CreditIcon.vue';
import { RefreshCw } from '@lucide/vue';
import AdminRedeemCodeManager from '../../components/settings/AdminRedeemCodeManager.vue';
import UserRedeemCard from '../../components/settings/UserRedeemCard.vue';
import FeedbackCard from '../../components/settings/FeedbackCard.vue';
import { useAdminLogic } from '../../composables/useAdminLogic';

const { t } = useI18n();

const {
  loading,
  isAdmin,
  myUsage,
  myQuotaStatus,
  myCreditStatus,
  usageRange,
  usageRangeLabel,
  refreshData,
  fetchMyUsageOnly,
  modelColumns
} = useAdminLogic();

const modelColumnsForTable = modelColumns;

const usageRangeOptions = computed(() => [
  { value: '24h', label: '24h' },
  { value: '7d', label: t('views.dashboard.desktop.rangeWeek') },
  { value: '30d', label: t('views.dashboard.desktop.rangeMonth') },
  { value: 'total', label: t('views.dashboard.desktop.rangeAll') },
]);

function handleUsageRangeChange(v: string) {
  if (v === '24h' || v === '7d' || v === '30d' || v === 'total') {
    usageRange.value = v;
    fetchMyUsageOnly();
  }
}

function formatTokens(value) {
  const num = Number(value) || 0;
  if (num >= 1_000_000) {
    const v = (num / 1_000_000).toFixed(1).replace(/\.0$/, '');
    return `${v}M`;
  }
  if (num >= 1_000) {
    const v = (num / 1_000).toFixed(1).replace(/\.0$/, '');
    return `${v}K`;
  }
  if (Number.isInteger(num)) return `${num}`;
  return `${num.toFixed(2).replace(/0+$/, '').replace(/\.$/, '')}`;
}

function formatCredit(value) {
  const num = Number(value) || 0;
  if (Number.isInteger(num)) return `${num}`;
  return `${num.toFixed(2).replace(/0+$/, '').replace(/\.$/, '')}`;
}

function formatCreditExact(value) {
  const num = Number(value) || 0;
  if (Number.isInteger(num)) return `${num}`;
  return `${num.toFixed(2).replace(/0+$/, '').replace(/\.$/, '')}`;
}

function formatTokenWithCredit(tokens, credit, noCredit = false) {
  const tokenText = `${formatTokens(tokens)} Token`;
  if (noCredit) return tokenText;
  return `${tokenText}/${formatCredit(credit || 0)}`;
}
</script>

<style scoped>
.view-container {
  height: 100%;
  background: transparent;
  display: flex;
  flex-direction: column;
}

.mobile-content {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 0 6px;
  padding-bottom: calc(var(--mobile-bottom-nav-height, 60px) + var(--sab, 0px));
}

.usage-model-table :deep(.n-data-table-th),
.usage-model-table :deep(.n-data-table-td) {
  white-space: nowrap;
}

.usage-model-table :deep(.n-data-table-td__ellipsis) {
  white-space: nowrap;
}

.admin-only-hint {
  margin-top: 24px;
  padding: 16px;
  background: rgba(var(--spark-primary-rgb), 0.1);
  border-radius: 8px;
  font-size: var(--spark-fs-sm);
  color: var(--spark-text-muted);
  text-align: center;
}
</style>
