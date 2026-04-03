<template>
  <div class="settings-section">
    <div class="section-header">
      <div>
        <h3>我的点数与消耗</h3>
        <p class="section-desc">系统托管模型按点数结算；自费调用仅统计，不受额度限制。</p>
      </div>
      <n-button quaternary size="small" @click="loadStatus" :loading="loading">
        <template #icon><n-icon><RefreshOutline /></n-icon></template>
        刷新
      </n-button>
    </div>

    <SparkAlert type="info" :show-icon="false" style="margin-bottom: 12px;">
      系统付费 = 使用站点托管密钥并扣减点数；自身付费 = 使用你自己的 API Key，不做额度限制。
    </SparkAlert>

    <n-spin :show="loading">
      <div class="scope-switch">
        <SparkSegment
          v-model="selectedScope"
          :options="[{value:'total',label:'总览'},{value:'sys_paid',label:'系统付费'},{value:'self_paid',label:'自身付费'}]"
        />
      </div>

      <template v-if="quotaStatus">
        <template v-if="selectedScope === 'total'">
          <div class="stats-grid stats-grid--main">
            <n-card size="small">
              <n-statistic label="系统点数余额">{{ formatTokens(creditStatus?.credit_balance || 0) }}</n-statistic>
            </n-card>
            <n-card size="small">
              <n-statistic label="累计系统消耗点数">{{ formatTokens(creditStatus?.credit_total_used || 0) }}</n-statistic>
            </n-card>
            <n-card size="small">
              <n-statistic label="累计发放点数">{{ formatTokens(creditStatus?.credit_total_granted || 0) }}</n-statistic>
            </n-card>
          </div>

          <div class="stats-grid stats-grid--sub">
            <n-card size="small" title="系统付费">
              <div class="sub-line">Tokens：{{ formatTokens(quotaStatus.sys_paid?.total?.usage?.tokens || 0) }}</div>
              <div class="sub-line">请求：{{ quotaStatus.sys_paid?.total?.usage?.requests || 0 }}</div>
              <div class="sub-line">扣点：{{ formatTokens(creditStatus?.credit_used_from_usage || 0) }}</div>
            </n-card>
            <n-card size="small" title="自身付费">
              <div class="sub-line">Tokens：{{ formatTokens(quotaStatus.self_paid?.total?.usage?.tokens || 0) }}</div>
              <div class="sub-line">请求：{{ quotaStatus.self_paid?.total?.usage?.requests || 0 }}</div>
            </n-card>
          </div>
        </template>

        <template v-else-if="selectedScope === 'sys_paid'">
          <div class="stats-grid stats-grid--main">
            <n-card size="small">
              <n-statistic label="系统点数余额">{{ formatTokens(creditStatus?.credit_balance || 0) }}</n-statistic>
            </n-card>
            <n-card size="small">
              <n-statistic label="累计扣点">{{ formatTokens(creditStatus?.credit_used_from_usage || 0) }}</n-statistic>
            </n-card>
            <n-card size="small">
              <n-statistic label="系统请求数">{{ creditStatus?.requests || 0 }}</n-statistic>
            </n-card>
          </div>

          <n-card size="small" title="系统点数概览" style="margin-top: 12px;">
            <div class="detail-grid">
              <div class="detail-item">
                <span class="detail-label">当前余额</span>
                <span class="detail-value">{{ formatTokens(creditStatus?.credit_balance || 0) }}</span>
              </div>
              <div class="detail-item">
                <span class="detail-label">累计发放</span>
                <span class="detail-value">{{ formatTokens(creditStatus?.credit_total_granted || 0) }}</span>
              </div>
              <div class="detail-item">
                <span class="detail-label">累计消耗</span>
                <span class="detail-value">{{ formatTokens(creditStatus?.credit_total_used || 0) }}</span>
              </div>
              <div class="detail-item">
                <span class="detail-label">系统请求</span>
                <span class="detail-value">{{ creditStatus?.requests || 0 }}</span>
              </div>
            </div>
            <n-tag :type="(creditStatus?.credit_balance || 0) > 0 ? 'success' : 'error'" size="small" style="margin-top: 10px;">
              {{ (creditStatus?.credit_balance || 0) > 0 ? '系统点数可用' : '系统点数不足' }}
            </n-tag>
          </n-card>
        </template>

        <template v-else>
          <div class="stats-grid stats-grid--main">
            <n-card size="small">
              <n-statistic label="累计 Tokens">{{ formatTokens(quotaStatus.self_paid?.total?.usage?.tokens || 0) }}</n-statistic>
            </n-card>
            <n-card size="small">
              <n-statistic label="累计请求">{{ quotaStatus.self_paid?.total?.usage?.requests || 0 }}</n-statistic>
            </n-card>
            <n-card size="small">
              <n-statistic label="错误次数">{{ quotaStatus.self_paid?.total?.usage?.errors || 0 }}</n-statistic>
            </n-card>
          </div>

          <n-card size="small" title="自身付费说明" style="margin-top: 12px;">
            <div class="detail-grid">
              <div class="detail-item">
                <span class="detail-label">额度限制</span>
                <span class="detail-value">不限制</span>
              </div>
              <div class="detail-item">
                <span class="detail-label">计费归属</span>
                <span class="detail-value">用户自费</span>
              </div>
              <div class="detail-item">
                <span class="detail-label">累计 Tokens</span>
                <span class="detail-value">{{ formatTokens(quotaStatus.self_paid?.total?.usage?.tokens || 0) }}</span>
              </div>
              <div class="detail-item">
                <span class="detail-label">累计请求</span>
                <span class="detail-value">{{ quotaStatus.self_paid?.total?.usage?.requests || 0 }}</span>
              </div>
            </div>
          </n-card>
        </template>
      </template>
    </n-spin>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { NButton, NCard, NIcon, NSpin, NStatistic, NTag, useMessage } from 'naive-ui';
import SparkAlert from '../share/SparkAlert.vue';
import SparkSegment from '../share/SparkSegment.vue';
import { RefreshOutline } from '@vicons/ionicons5';
import { getMyQuotaStatus, getMyCreditStatus, formatTokens } from '../../services/adminService';

const message = useMessage();
const loading = ref(false);
const quotaStatus = ref(null);
const creditStatus = ref(null);
const selectedScope = ref('total');

async function loadStatus() {
  loading.value = true;
  try {
    const [quotaData, creditData] = await Promise.all([
      getMyQuotaStatus(),
      getMyCreditStatus(),
    ]);
    quotaStatus.value = quotaData;
    creditStatus.value = creditData;
  } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error || '未知错误');
      message.error(errorMessage || '获取点数状态失败');
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  loadStatus();
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

.scope-switch {
  margin-bottom: 14px;
}

.scope-segment {
  flex-wrap: wrap;
}

.stats-grid {
  display: grid;
  gap: 12px;
}

.stats-grid--main {
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
}

.stats-grid--sub {
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  margin-top: 12px;
}

.sub-line {
  font-size: 13px;
  line-height: 1.8;
}

.detail-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 10px 16px;
}

.detail-item {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  font-size: 13px;
}

.detail-label {
  color: var(--spark-text-muted);
}

.detail-value {
  font-weight: 600;
}
</style>
