<template>
  <div class="view-container">
    <div class="panel-header spark-desktop-header">
      <div class="spark-desktop-header__left">
        <h2 class="spark-desktop-title">管理中心</h2>
        <p class="spark-desktop-subtitle">使用统计、点数账户与全站概览</p>
      </div>
      <div class="header-actions spark-desktop-header__actions">
        <n-tag v-if="isAdmin" type="success" size="small">
          <template #icon>
            <n-icon><ShieldCheckmarkOutline /></n-icon>
          </template>
          管理员
        </n-tag>
        <n-button quaternary size="small" @click="refreshData">
          <template #icon>
            <n-icon><RefreshOutline /></n-icon>
          </template>
          刷新
        </n-button>
      </div>
    </div>

    <div class="content-area">
      <n-spin :show="loading">
        <div class="admin-container">
          <div class="admin-column">
            <n-card title="我的使用统计" size="small">
              <template #header-extra>
                <n-space :size="6" align="center">
                  <n-button-group size="tiny" class="spark-segment">
                    <n-button :type="usageRange === '24h' ? 'primary' : 'default'" @click="usageRange = '24h'; fetchMyUsageOnly()">24h</n-button>
                    <n-button :type="usageRange === '7d' ? 'primary' : 'default'" @click="usageRange = '7d'; fetchMyUsageOnly()">周</n-button>
                    <n-button :type="usageRange === '30d' ? 'primary' : 'default'" @click="usageRange = '30d'; fetchMyUsageOnly()">月</n-button>
                    <n-button :type="usageRange === 'total' ? 'primary' : 'default'" @click="usageRange = 'total'; fetchMyUsageOnly()">全部</n-button>
                  </n-button-group>
                  <n-button circle quaternary size="tiny" @click="fetchMyUsageOnly()" title="刷新统计">
                    <template #icon><n-icon><RefreshOutline /></n-icon></template>
                  </n-button>
                </n-space>
              </template>

              <n-space vertical>
                <n-statistic :label="usageRangeLabel">
                  {{ formatTokenWithCredit(myUsage?.range_stats?.tokens || 0, myCreditStatus?.credit_used_from_usage || 0) }}
                </n-statistic>

                <n-grid :cols="2" :x-gap="12">
                  <n-gi>
                    <n-statistic label="请求次数" tabular-nums>
                      {{ myUsage?.range_stats?.requests || 0 }}
                    </n-statistic>
                  </n-gi>
                  <n-gi>
                    <n-statistic label="错误次数" tabular-nums>
                      <n-text :type="(myUsage?.range_stats?.errors || 0) > 0 ? 'error' : 'default'">
                        {{ myUsage?.range_stats?.errors || 0 }}
                      </n-text>
                    </n-statistic>
                  </n-gi>
                </n-grid>

                <n-grid :cols="3" :x-gap="12">
                  <n-gi>
                    <n-statistic label="系统点数余额" tabular-nums>
                      {{ formatTokens(myCreditStatus?.credit_balance || 0) }}
                    </n-statistic>
                  </n-gi>
                  <n-gi>
                    <n-statistic label="累计发放点数" tabular-nums>
                      {{ formatTokens(myCreditStatus?.credit_total_granted || 0) }}
                    </n-statistic>
                  </n-gi>
                  <n-gi>
                    <n-statistic label="系统付费请求" tabular-nums>
                      {{ myCreditStatus?.requests || 0 }}
                    </n-statistic>
                  </n-gi>
                </n-grid>

                <n-grid :cols="2" :x-gap="12">
                  <n-gi>
                    <n-statistic label="系统付费" tabular-nums>
                      {{ formatTokenWithCredit(myQuotaStatus?.sys_paid?.total?.usage?.tokens || 0, myCreditStatus?.credit_used_from_usage || 0) }}
                    </n-statistic>
                  </n-gi>
                  <n-gi>
                    <n-statistic label="自身付费" tabular-nums>
                      {{ formatTokenWithCredit(myQuotaStatus?.self_paid?.total?.usage?.tokens || 0, null, true) }}
                    </n-statistic>
                  </n-gi>
                </n-grid>

                <n-grid :cols="2" :x-gap="12">
                  <n-gi>
                    <n-statistic label="系统请求次数" tabular-nums>
                      {{ myCreditStatus?.requests || 0 }}
                    </n-statistic>
                  </n-gi>
                  <n-gi>
                    <n-statistic label="总错误数" tabular-nums>
                      {{ myUsage?.range_stats?.errors || 0 }}
                    </n-statistic>
                  </n-gi>
                </n-grid>
              </n-space>
            </n-card>

            <n-card title="按模型统计" size="small" style="margin-top: 16px;">
              <n-data-table
                class="usage-model-table"
                :columns="modelColumnsForTable"
                :data="myUsage?.by_model || []"
                :pagination="false"
                size="small"
                :max-height="300"
              />
            </n-card>

            <n-card title="按Agent统计" size="small" style="margin-top: 16px;">
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
          </div>

          <div class="admin-column" v-if="isAdmin">
            <n-card title="用户管理" size="small">
              <template #header-extra>
                <n-text depth="3">共 {{ allUsers.length }} 位用户</n-text>
              </template>

              <n-data-table
                :columns="userColumns"
                :data="allUsers"
                :pagination="{ pageSize: 10 }"
                size="small"
                :max-height="300"
              />
            </n-card>

            <n-card title="用户系统点数账户" size="small" style="margin-top: 16px;">
              <n-alert type="info" style="margin-bottom: 12px;">
                这里只管理系统托管调用的点数余额；用户自费调用只做统计，不参与点数限制。
              </n-alert>
              <n-data-table
                :columns="userCreditColumns"
                :data="userCreditAccounts"
                :pagination="{ pageSize: 8 }"
                size="small"
                :max-height="320"
              />
            </n-card>

            <n-card title="全部用户使用概览" size="small" style="margin-top: 16px;">
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
        :title="`调整用户点数：${activeCreditUser?.user?.username || ''}`"
        :bordered="false"
        size="huge"
        role="dialog"
        aria-modal="true"
      >
        <n-form :model="creditAdjustForm" label-placement="top">
          <n-form-item label="点数变动">
            <n-input-number v-model:value="creditAdjustForm.deltaCredit" style="width: 100%" />
          </n-form-item>
          <n-form-item label="备注">
            <n-input v-model:value="creditAdjustForm.remark" placeholder="例如：首发赠送、手工补偿、测试扣减" />
          </n-form-item>
        </n-form>

        <template #footer>
          <div style="display: flex; justify-content: flex-end; gap: 12px;">
            <n-button @click="showCreditAdjustModal = false">取消</n-button>
            <n-button type="primary" :loading="creditAdjustSaving" @click="submitCreditAdjust">保存</n-button>
          </div>
        </template>
      </n-card>
    </n-modal>

  </div>
</template>

<script setup lang="ts">
import {
  NCard, NButton, NButtonGroup, NIcon, NInput, NInputNumber, NTag, NText, NStatistic,
  NGrid, NGi, NDivider, NDataTable, NModal, NForm, NFormItem,
  NSpace, NSpin, NAlert
} from 'naive-ui';
import {
  ShieldCheckmarkOutline, RefreshOutline
} from '@vicons/ionicons5';
import MCPConnectCard from '../../components/settings/MCPConnectCard.vue';
import { useAdminLogic } from '../../composables/useAdminLogic';

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
  return `${num.toFixed(3).replace(/0+$/, '').replace(/\.$/, '')}🔥`;
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
