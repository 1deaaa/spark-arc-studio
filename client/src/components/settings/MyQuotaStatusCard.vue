<template>
  <div class="settings-section">
    <div class="section-header">
      <div>
        <h3>{{ t('settings.quota.title') }}</h3>
        <p class="section-desc">{{ t('settings.quota.description') }}</p>
      </div>
      <n-button quaternary size="small" @click="loadStatus" :loading="loading">
        <template #icon><n-icon><RefreshCw /></n-icon></template>
        {{ t('settings.quota.refresh') }}
      </n-button>
    </div>

    <SparkAlert type="info" :show-icon="false" style="margin-bottom: 12px;">
      {{ t('settings.quota.info') }}
    </SparkAlert>

    <n-spin :show="loading">
      <div class="scope-switch">
        <SparkSegment
          v-model="selectedScope"
          :options="scopeOptions"
        />
      </div>

      <template v-if="quotaStatus">
        <template v-if="selectedScope === 'total'">
          <div class="stats-grid stats-grid--main">
            <n-card size="small">
              <n-statistic :label="t('settings.quota.total.balance')">{{ formatTokens(creditStatus?.credit_balance || 0) }}</n-statistic>
            </n-card>
            <n-card size="small">
              <n-statistic :label="t('settings.quota.total.used')">{{ formatTokens(creditStatus?.credit_total_used || 0) }}</n-statistic>
            </n-card>
            <n-card size="small">
              <n-statistic :label="t('settings.quota.total.granted')">{{ formatTokens(creditStatus?.credit_total_granted || 0) }}</n-statistic>
            </n-card>
          </div>

          <div class="stats-grid stats-grid--sub">
            <n-card size="small" :title="t('settings.quota.scope.sysPaid')">
              <div class="sub-line">{{ t('settings.quota.common.tokens') }}：{{ formatTokens(quotaStatus.sys_paid?.total?.usage?.tokens || 0) }}</div>
              <div class="sub-line">{{ t('settings.quota.common.requests') }}：{{ quotaStatus.sys_paid?.total?.usage?.requests || 0 }}</div>
              <div class="sub-line">{{ t('settings.quota.common.creditDeduction') }}：{{ formatTokens(creditStatus?.credit_used_from_usage || 0) }}</div>
            </n-card>
            <n-card size="small" :title="t('settings.quota.scope.selfPaid')">
              <div class="sub-line">{{ t('settings.quota.common.tokens') }}：{{ formatTokens(quotaStatus.self_paid?.total?.usage?.tokens || 0) }}</div>
              <div class="sub-line">{{ t('settings.quota.common.requests') }}：{{ quotaStatus.self_paid?.total?.usage?.requests || 0 }}</div>
            </n-card>
          </div>
        </template>

        <template v-else-if="selectedScope === 'sys_paid'">
          <div class="stats-grid stats-grid--main">
            <n-card size="small">
              <n-statistic :label="t('settings.quota.total.balance')">{{ formatTokens(creditStatus?.credit_balance || 0) }}</n-statistic>
            </n-card>
            <n-card size="small">
              <n-statistic :label="t('settings.quota.sysPaid.totalDeduction')">{{ formatTokens(creditStatus?.credit_used_from_usage || 0) }}</n-statistic>
            </n-card>
            <n-card size="small">
              <n-statistic :label="t('settings.quota.sysPaid.systemRequests')">{{ creditStatus?.requests || 0 }}</n-statistic>
            </n-card>
          </div>

          <n-card size="small" :title="t('settings.quota.sysPaid.overviewTitle')" style="margin-top: 12px;">
            <div class="detail-grid">
              <div class="detail-item">
                <span class="detail-label">{{ t('settings.quota.sysPaid.currentBalance') }}</span>
                <span class="detail-value">{{ formatTokens(creditStatus?.credit_balance || 0) }}</span>
              </div>
              <div class="detail-item">
                <span class="detail-label">{{ t('settings.quota.total.granted') }}</span>
                <span class="detail-value">{{ formatTokens(creditStatus?.credit_total_granted || 0) }}</span>
              </div>
              <div class="detail-item">
                <span class="detail-label">{{ t('settings.quota.sysPaid.totalConsume') }}</span>
                <span class="detail-value">{{ formatTokens(creditStatus?.credit_total_used || 0) }}</span>
              </div>
              <div class="detail-item">
                <span class="detail-label">{{ t('settings.quota.sysPaid.systemRequests') }}</span>
                <span class="detail-value">{{ creditStatus?.requests || 0 }}</span>
              </div>
            </div>
            <SparkTag :type="(creditStatus?.credit_balance || 0) > 0 ? 'success' : 'danger'" size="small" style="margin-top: 10px;">
              {{ (creditStatus?.credit_balance || 0) > 0 ? t('settings.quota.sysPaid.available') : t('settings.quota.sysPaid.insufficient') }}
            </SparkTag>
          </n-card>
        </template>

        <template v-else>
          <div class="stats-grid stats-grid--main">
            <n-card size="small">
              <n-statistic :label="t('settings.quota.selfPaid.totalTokens')">{{ formatTokens(quotaStatus.self_paid?.total?.usage?.tokens || 0) }}</n-statistic>
            </n-card>
            <n-card size="small">
              <n-statistic :label="t('settings.quota.selfPaid.totalRequests')">{{ quotaStatus.self_paid?.total?.usage?.requests || 0 }}</n-statistic>
            </n-card>
            <n-card size="small">
              <n-statistic :label="t('settings.quota.selfPaid.errorCount')">{{ quotaStatus.self_paid?.total?.usage?.errors || 0 }}</n-statistic>
            </n-card>
          </div>

          <n-card size="small" :title="t('settings.quota.selfPaid.descriptionTitle')" style="margin-top: 12px;">
            <div class="detail-grid">
              <div class="detail-item">
                <span class="detail-label">{{ t('settings.quota.selfPaid.limitLabel') }}</span>
                <span class="detail-value">{{ t('settings.quota.selfPaid.noLimit') }}</span>
              </div>
              <div class="detail-item">
                <span class="detail-label">{{ t('settings.quota.selfPaid.billingOwnerLabel') }}</span>
                <span class="detail-value">{{ t('settings.quota.selfPaid.userPaid') }}</span>
              </div>
              <div class="detail-item">
                <span class="detail-label">{{ t('settings.quota.selfPaid.totalTokens') }}</span>
                <span class="detail-value">{{ formatTokens(quotaStatus.self_paid?.total?.usage?.tokens || 0) }}</span>
              </div>
              <div class="detail-item">
                <span class="detail-label">{{ t('settings.quota.selfPaid.totalRequests') }}</span>
                <span class="detail-value">{{ quotaStatus.self_paid?.total?.usage?.requests || 0 }}</span>
              </div>
            </div>
          </n-card>
        </template>
      </template>
    </n-spin>

    <!-- 兑换码兑换 -->
    <div class="redeem-section">
      <div class="redeem-row">
        <n-input
          v-model:value="redeemCodeInput"
          :placeholder="t('settings.quota.redeem.placeholder')"
          size="small"
          clearable
          @keyup.enter="handleRedeem"
        />
        <n-button
          type="primary"
          size="small"
          :loading="redeeming"
          @click="handleRedeem"
        >{{ t('settings.quota.redeem.button') }}</n-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { NButton, NCard, NIcon, NInput, NSpin, NStatistic, useMessage } from 'naive-ui';
import { useI18n } from 'vue-i18n';
import SparkTag from '../share/SparkTag.vue';
import SparkAlert from '../share/SparkAlert.vue';
import SparkSegment from '../share/SparkSegment.vue';
import { RefreshCw } from '@lucide/vue';
import SparkIcon from '@/components/share/CreditIcon.vue';
import { getMyQuotaStatus, getMyCreditStatus, formatTokens, redeemCode } from '../../services/adminService';

const message = useMessage();
const { t } = useI18n();
const loading = ref(false);
const quotaStatus = ref(null);
const creditStatus = ref(null);
const selectedScope = ref('total');

const scopeOptions = computed(() => [
  { value: 'total', label: t('settings.quota.scope.overview') },
  { value: 'sys_paid', label: t('settings.quota.scope.sysPaid') },
  { value: 'self_paid', label: t('settings.quota.scope.selfPaid') },
]);

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
      const errorMessage = error instanceof Error ? error.message : String(error || t('app.systemInit.unknownError'));
      message.error(errorMessage || t('settings.quota.loadFailed'));
  } finally {
    loading.value = false;
  }
}

const redeemCodeInput = ref('');
const redeeming = ref(false);

async function handleRedeem() {
  const code = redeemCodeInput.value.trim();
  if (!code) {
    message.warning(t('settings.quota.redeem.emptyCode'));
    return;
  }
  redeeming.value = true;
  try {
    const result = await redeemCode(code);
    message.success(t('settings.quota.redeem.success', { amount: result.credit_amount }));
    redeemCodeInput.value = '';
    loadStatus();
  } catch (e: any) {
    message.error(e.message || t('settings.quota.redeem.failed'));
  } finally {
    redeeming.value = false;
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
  font-size: var(--spark-fs-h3);
}

.section-desc {
  margin: 6px 0 0;
  color: var(--spark-text-muted);
  font-size: var(--spark-fs-sm);
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
  font-size: var(--spark-fs-sm);
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
  font-size: var(--spark-fs-sm);
}

.detail-label {
  color: var(--spark-text-muted);
}

.detail-value {
  font-weight: 600;
}

.redeem-section {
  margin-top: 16px;
  padding-top: 12px;
  border-top: 1px solid var(--spark-border);
}

.redeem-row {
  display: flex;
  gap: 8px;
  align-items: center;
}
</style>
