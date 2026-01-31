
<template>
  <div class="view-container">
    <div class="mobile-header">
       <h3>个人统计</h3>
       <n-button circle quaternary @click="refreshData">
         <template #icon><n-icon><RefreshOutline /></n-icon></template>
       </n-button>
    </div>

    <div class="mobile-content">
       <n-spin :show="loading">
          <n-card title="使用概览" size="small">
             <template #header-extra>
                <n-button-group size="tiny" class="spark-segment">
                  <n-button :type="usageRange === '24h' ? 'primary' : 'default'" @click="usageRange = '24h'; fetchMyUsageOnly()">24h</n-button>
                  <n-button :type="usageRange === '7d' ? 'primary' : 'default'" @click="usageRange = '7d'; fetchMyUsageOnly()">周</n-button>
                </n-button-group>
             </template>
             <n-statistic :label="usageRangeLabel">
               {{ formatTokens(myUsage?.range_stats?.tokens || 0) }}
                <template #suffix>tokens</template>
             </n-statistic>
             <n-grid :cols="2" style="margin-top: 12px">
                <n-gi>
                   <n-statistic label="请求" size="small">{{ myUsage?.range_stats?.requests || 0 }}</n-statistic>
                </n-gi>
                <n-gi>
                   <n-statistic label="错误" size="small">{{ myUsage?.range_stats?.errors || 0 }}</n-statistic>
                </n-gi>
             </n-grid>
          </n-card>

          <n-card title="模型使用" size="small" style="margin-top: 12px">
             <n-data-table
               :columns="modelColumns.map(c => ({...c, width: c.key === 'model' ? 120 : undefined}))"
               :data="myUsage?.by_model || []"
               :pagination="false"
               size="small"
               scroll-x="300"
             />
          </n-card>

          <div v-if="isAdmin" class="admin-only-hint">
             管理员：请在桌面端查看多用户统计与系统限额。
          </div>
       </n-spin>
    </div>
  </div>
</template>

<script setup>
import { NCard, NButton, NButtonGroup, NIcon, NStatistic, NGrid, NGi, NDataTable, NRadioGroup, NRadioButton, NSpin } from 'naive-ui';
import { RefreshOutline } from '@vicons/ionicons5';
import { useAdminLogic } from '../../composables/useAdminLogic';

const {
  loading,
  isAdmin,
  myUsage,
  usageRange,
  usageRangeLabel,
  refreshData,
  fetchMyUsageOnly,
  modelColumns
} = useAdminLogic();

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
</script>

<style scoped>
.view-container {
  height: 100%;
  background: var(--spark-bg);
  display: flex;
  flex-direction: column;
}

.mobile-header {
  padding: 16px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid var(--spark-border);
}

.mobile-header h3 {
  margin: 0;
  font-size: 18px;
}

.mobile-content {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
  padding-bottom: 80px;
}

.admin-only-hint {
  margin-top: 24px;
  padding: 16px;
  background: rgba(var(--spark-primary-rgb), 0.1);
  border-radius: 8px;
  font-size: 13px;
  color: var(--spark-text-muted);
  text-align: center;
}
</style>
