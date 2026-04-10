<template>
  <div class="view-container">
    <div class="panel-header spark-desktop-header">
      <div class="spark-desktop-header__left">
        <h2 class="spark-desktop-title">{{ t('views.admin.desktop.title') }}</h2>
        <p class="spark-desktop-subtitle">{{ t('views.admin.desktop.subtitle') }}</p>
      </div>
      <div class="header-actions spark-desktop-header__actions">
        <SparkTag v-if="isAdmin" type="success" size="small">{{ t('views.admin.desktop.adminTag') }}</SparkTag>
        <n-button quaternary size="small" @click="refreshData">
          <template #icon>
            <n-icon><RefreshOutline /></n-icon>
          </template>
          {{ t('views.common.refresh') }}
        </n-button>
      </div>
    </div>

    <div class="content-area">
      <n-spin :show="loading">
        <div class="admin-container">
          <div class="admin-column">
            <n-card :title="t('views.admin.desktop.myUsageStats')" size="small">
              <template #header-extra>
                <n-space :size="6" align="center">
                  <SparkSegment
                    :model-value="usageRange"
                    :options="usageRangeOptions"
                    size="tiny"
                    @update:model-value="handleUsageRangeChange"
                  />
                  <n-button circle quaternary size="tiny" @click="fetchMyUsageOnly()" :title="t('views.admin.desktop.refreshStats')">
                    <template #icon><n-icon><RefreshOutline /></n-icon></template>
                  </n-button>
                </n-space>
              </template>

              <n-space vertical>
                <n-statistic :label="usageRangeLabel">
                  {{ formatTokenWithCredit(myUsage?.range_stats?.tokens || 0, myCreditStatus?.credit_used_from_usage || 0) }}<SparkIcon />
                </n-statistic>

                <n-grid :cols="2" :x-gap="12">
                  <n-gi>
                    <n-statistic :label="t('views.admin.desktop.requestCount')" tabular-nums>
                      {{ myUsage?.range_stats?.requests || 0 }}
                    </n-statistic>
                  </n-gi>
                  <n-gi>
                    <n-statistic :label="t('views.admin.desktop.errorCount')" tabular-nums>
                      <n-text :type="(myUsage?.range_stats?.errors || 0) > 0 ? 'error' : 'default'">
                        {{ myUsage?.range_stats?.errors || 0 }}
                      </n-text>
                    </n-statistic>
                  </n-gi>
                </n-grid>

                <n-grid :cols="3" :x-gap="12">
                  <n-gi>
                    <n-statistic :label="t('views.admin.desktop.systemCreditBalance')" tabular-nums>
                      {{ formatTokens(myCreditStatus?.credit_balance || 0) }}
                    </n-statistic>
                  </n-gi>
                  <n-gi>
                    <n-statistic :label="t('views.admin.desktop.totalGrantedCredit')" tabular-nums>
                      {{ formatTokens(myCreditStatus?.credit_total_granted || 0) }}
                    </n-statistic>
                  </n-gi>
                  <n-gi>
                    <n-statistic :label="t('views.admin.desktop.systemPaidRequests')" tabular-nums>
                      {{ myCreditStatus?.requests || 0 }}
                    </n-statistic>
                  </n-gi>
                </n-grid>

                <n-grid :cols="2" :x-gap="12">
                  <n-gi>
                    <n-statistic :label="t('views.admin.desktop.systemPaid')" tabular-nums>
                      {{ formatTokenWithCredit(myQuotaStatus?.sys_paid?.total?.usage?.tokens || 0, myCreditStatus?.credit_used_from_usage || 0) }}<SparkIcon />
                    </n-statistic>
                  </n-gi>
                  <n-gi>
                    <n-statistic :label="t('views.admin.desktop.selfPaid')" tabular-nums>
                      {{ formatTokenWithCredit(myQuotaStatus?.self_paid?.total?.usage?.tokens || 0, null, true) }}
                    </n-statistic>
                  </n-gi>
                </n-grid>

                <n-grid :cols="2" :x-gap="12">
                  <n-gi>
                    <n-statistic :label="t('views.admin.desktop.systemRequestCount')" tabular-nums>
                      {{ myCreditStatus?.requests || 0 }}
                    </n-statistic>
                  </n-gi>
                  <n-gi>
                    <n-statistic :label="t('views.admin.desktop.totalErrorCount')" tabular-nums>
                      {{ myUsage?.range_stats?.errors || 0 }}
                    </n-statistic>
                  </n-gi>
                </n-grid>
              </n-space>
            </n-card>

            <n-card :title="t('views.admin.desktop.byModel')" size="small" style="margin-top: 16px;">
              <n-data-table
                class="usage-model-table"
                :columns="modelColumnsForTable"
                :data="myUsage?.by_model || []"
                :pagination="false"
                size="small"
                :max-height="300"
              />
            </n-card>

            <n-card :title="t('views.admin.desktop.byAgent')" size="small" style="margin-top: 16px;">
              <n-data-table
                :columns="agentColumns"
                :data="myUsage?.by_agent || []"
                :pagination="false"
                size="small"
                :max-height="200"
              />
            </n-card>

          </div>

          <div class="admin-column">
            <MCPConnectCard />
            <AdminRedeemCodeManager v-if="isAdmin" style="margin-top: 16px;" />
          </div>

          <div class="admin-column" v-if="isAdmin">
            <n-card :title="t('views.admin.desktop.userManagement')" size="small">
              <template #header-extra>
                <n-text depth="3">{{ t('views.admin.desktop.totalUsers', { count: allUsers.length }) }}</n-text>
              </template>

              <n-data-table
                :columns="userColumns"
                :data="allUsers"
                :pagination="{ pageSize: 10 }"
                size="small"
                :max-height="300"
              />
            </n-card>

            <n-card :title="t('views.admin.desktop.userSystemCreditAccount')" size="small" style="margin-top: 16px;">
              <SparkAlert type="info" style="margin-bottom: 12px;">
                {{ t('views.admin.desktop.creditAccountHint') }}
              </SparkAlert>
              <n-data-table
                :columns="userCreditColumns"
                :data="userCreditAccounts"
                :pagination="{ pageSize: 8 }"
                size="small"
                :max-height="320"
              />
            </n-card>

            <n-card :title="t('views.admin.desktop.allUsersUsageOverview')" size="small" style="margin-top: 16px;">
              <n-data-table
                :columns="allUsageColumns"
                :data="allUsersUsage"
                :pagination="{ pageSize: 10 }"
                size="small"
                :max-height="400"
              />
            </n-card>
          </div>
        </div>
      </n-spin>
    </div>

    <n-modal v-model:show="showCreditAdjustModal">
      <n-card
        style="width: 520px; max-width: calc(100vw - 48px);"
        :title="t('views.admin.desktop.adjustUserCreditTitle', { username: activeCreditUser?.user?.username || '' })"
        :bordered="false"
        size="huge"
        role="dialog"
        aria-modal="true"
      >
        <n-form :model="creditAdjustForm" label-placement="top">
          <n-form-item :label="t('views.admin.desktop.creditDelta')">
            <n-input-number v-model:value="creditAdjustForm.deltaCredit" style="width: 100%" />
          </n-form-item>
          <n-form-item :label="t('views.common.remark')">
            <n-input v-model:value="creditAdjustForm.remark" :placeholder="t('views.admin.desktop.remarkPlaceholder')" />
          </n-form-item>
        </n-form>

        <template #footer>
          <div style="display: flex; justify-content: flex-end; gap: 12px;">
            <n-button @click="showCreditAdjustModal = false">{{ t('views.common.cancel') }}</n-button>
            <n-button type="primary" :loading="creditAdjustSaving" @click="submitCreditAdjust">{{ t('views.common.save') }}</n-button>
          </div>
        </template>
      </n-card>
    </n-modal>

  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';
import {
  NCard, NButton, NIcon, NInput, NInputNumber, NText, NStatistic,
  NGrid, NGi, NDivider, NDataTable, NModal, NForm, NFormItem,
  NSpace, NSpin
} from 'naive-ui';
import SparkTag from '../../components/share/SparkTag.vue';
import SparkSegment from '../../components/share/SparkSegment.vue';
import SparkAlert from '../../components/share/SparkAlert.vue';
import SparkIcon from '../../components/share/CreditIcon.vue';
import {
  ShieldCheckmarkOutline, RefreshOutline
} from '@vicons/ionicons5';
import MCPConnectCard from '../../components/settings/MCPConnectCard.vue';
import AdminRedeemCodeManager from '../../components/settings/AdminRedeemCodeManager.vue';
import { useAdminLogic } from '../../composables/useAdminLogic';

const { t } = useI18n();

const {
  loading,
  isAdmin,
  myUsage,
  myQuotaStatus,
  myCreditStatus,
  usageRange,
  allUsers,
  allUsersUsage,
  userCreditAccounts,
  showCreditAdjustModal,
  creditAdjustSaving,
  activeCreditUser,
  creditAdjustForm,
  usageRangeLabel,
  refreshData,
  fetchMyUsageOnly,
  modelColumns,
  agentColumns,
  userColumns,
  userCreditColumns,
  allUsageColumns,
  submitCreditAdjust,
} = useAdminLogic();

const modelColumnsForTable = modelColumns;

const usageRangeOptions = computed(() => [
  { value: '24h', label: '24h' },
  { value: '7d', label: t('views.admin.desktop.rangeWeek') },
  { value: '30d', label: t('views.admin.desktop.rangeMonth') },
  { value: 'total', label: t('views.admin.desktop.rangeAll') },
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
  return `${num}`;
}

function formatCredit(value) {
  const num = Number(value) || 0;
  return `${num.toFixed(3).replace(/0+$/, '').replace(/\.$/, '')}`;
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
  width: 100%;
  min-width: 0;
  display: flex;
  flex-direction: column;
  background-color: var(--spark-bg);
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.content-area {
  flex: 1;
  width: 100%;
  min-width: 0;
  overflow-y: auto;
  padding: var(--spark-panel-padding);
}

.admin-container {
  display: grid;
  grid-template-columns: 0.74fr 1.06fr 1fr;
  gap: 24px;
  max-width: 100%;
}

.admin-column {
  display: flex;
  flex-direction: column;
}

.usage-model-table {
  min-width: 0;
}

.usage-model-table :deep(.n-data-table-th),
.usage-model-table :deep(.n-data-table-td) {
  white-space: nowrap;
}

.usage-model-table :deep(.n-data-table-td__ellipsis) {
  white-space: nowrap;
}

@media (max-width: 1200px) {
  .admin-container {
    grid-template-columns: 1fr;
  }
}
</style>
