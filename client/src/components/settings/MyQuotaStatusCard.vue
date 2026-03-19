<template>
  <div class="settings-section">
    <div class="section-header">
      <div>
        <h3>我的额度消耗</h3>
        <p class="section-desc">默认显示总消耗，可切换查看系统付费与自身付费明细。</p>
      </div>
      <n-button quaternary size="small" @click="loadStatus" :loading="loading">
        <template #icon><n-icon><RefreshOutline /></n-icon></template>
        刷新
      </n-button>
    </div>

    <n-alert type="info" :show-icon="false" style="margin-bottom: 12px;">
      系统付费 = 使用站点托管密钥；自身付费 = 使用你自己的 API Key。
    </n-alert>

    <n-spin :show="loading">
      <div class="scope-switch">
        <n-button-group>
          <n-button :type="selectedScope === 'total' ? 'primary' : 'default'" @click="selectedScope = 'total'">总额度</n-button>
          <n-button :type="selectedScope === 'sys_paid' ? 'primary' : 'default'" @click="selectedScope = 'sys_paid'">系统付费</n-button>
          <n-button :type="selectedScope === 'self_paid' ? 'primary' : 'default'" @click="selectedScope = 'self_paid'">自身付费</n-button>
        </n-button-group>
      </div>

      <template v-if="status">
        <template v-if="selectedScope === 'total'">
          <div class="stats-grid stats-grid--main">
            <n-card size="small">
              <n-statistic label="累计 Tokens">{{ formatTokens(status.total?.tokens || 0) }}</n-statistic>
            </n-card>
            <n-card size="small">
              <n-statistic label="累计请求">{{ status.total?.requests || 0 }}</n-statistic>
            </n-card>
            <n-card size="small">
              <n-statistic label="错误次数">{{ status.total?.errors || 0 }}</n-statistic>
            </n-card>
          </div>

          <div class="stats-grid stats-grid--sub">
            <n-card size="small" title="系统付费">
              <div class="sub-line">Tokens：{{ formatTokens(status.sys_paid?.total?.usage?.tokens || 0) }}</div>
              <div class="sub-line">请求：{{ status.sys_paid?.total?.usage?.requests || 0 }}</div>
            </n-card>
            <n-card size="small" title="自身付费">
              <div class="sub-line">Tokens：{{ formatTokens(status.self_paid?.total?.usage?.tokens || 0) }}</div>
              <div class="sub-line">请求：{{ status.self_paid?.total?.usage?.requests || 0 }}</div>
            </n-card>
          </div>
        </template>

        <template v-else>
          <div class="stats-grid stats-grid--main">
            <n-card size="small">
              <n-statistic label="累计 Tokens">{{ formatTokens(activeScopeStatus.total?.usage?.tokens || 0) }}</n-statistic>
            </n-card>
            <n-card size="small">
              <n-statistic label="累计请求">{{ activeScopeStatus.total?.usage?.requests || 0 }}</n-statistic>
            </n-card>
            <n-card size="small">
              <n-statistic label="剩余 Tokens">
                {{ formatLimitValue(activeScopeStatus.total?.token_remaining) }}
              </n-statistic>
            </n-card>
          </div>

          <n-card size="small" :title="activeScopeLabel + ' - 总量策略'" style="margin-top: 12px;">
            <div class="detail-grid">
              <div class="detail-item">
                <span class="detail-label">Token 上限</span>
                <span class="detail-value">{{ formatLimitValue(activeScopeStatus.total?.token_limit) }}</span>
              </div>
              <div class="detail-item">
                <span class="detail-label">请求上限</span>
                <span class="detail-value">{{ formatLimitValue(activeScopeStatus.total?.request_limit) }}</span>
              </div>
              <div class="detail-item">
                <span class="detail-label">已用 Tokens</span>
                <span class="detail-value">{{ formatTokens(activeScopeStatus.total?.usage?.tokens || 0) }}</span>
              </div>
              <div class="detail-item">
                <span class="detail-label">已用请求</span>
                <span class="detail-value">{{ activeScopeStatus.total?.usage?.requests || 0 }}</span>
              </div>
            </div>
            <n-tag v-if="activeScopeExceeded" type="error" size="small" style="margin-top: 10px;">当前额度已触顶</n-tag>
            <n-tag v-else type="success" size="small" style="margin-top: 10px;">当前额度正常</n-tag>
          </n-card>

          <n-card
            v-if="activeScopeStatus.window && hasWindowConfig(activeScopeStatus.window)"
            size="small"
            :title="activeScopeLabel + ' - 时间窗策略'"
            style="margin-top: 12px;"
          >
            <div class="detail-grid">
              <div class="detail-item">
                <span class="detail-label">窗口时长</span>
                <span class="detail-value">{{ activeScopeStatus.window_hours || '-' }} 小时</span>
              </div>
              <div class="detail-item">
                <span class="detail-label">窗口 Token 上限</span>
                <span class="detail-value">{{ formatLimitValue(activeScopeStatus.window?.token_limit) }}</span>
              </div>
              <div class="detail-item">
                <span class="detail-label">窗口请求上限</span>
                <span class="detail-value">{{ formatLimitValue(activeScopeStatus.window?.request_limit) }}</span>
              </div>
              <div class="detail-item">
                <span class="detail-label">窗口已用 Tokens</span>
                <span class="detail-value">{{ formatTokens(activeScopeStatus.window?.usage?.tokens || 0) }}</span>
              </div>
            </div>
          </n-card>
        </template>
      </template>
    </n-spin>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue';
import { NAlert, NButton, NButtonGroup, NCard, NIcon, NSpin, NStatistic, NTag, useMessage } from 'naive-ui';
import { RefreshOutline } from '@vicons/ionicons5';
import { getMyQuotaStatus, formatTokens } from '../../services/adminService';

const message = useMessage();
const loading = ref(false);
const status = ref(null);
const selectedScope = ref('total');

const activeScopeStatus = computed(() => {
  if (!status.value) return {};
  return selectedScope.value === 'self_paid' ? (status.value.self_paid || {}) : (status.value.sys_paid || {});
});

const activeScopeLabel = computed(() => (selectedScope.value === 'self_paid' ? '自身付费' : '系统付费'));

const activeScopeExceeded = computed(() => {
  const scope = activeScopeStatus.value || {};
  return Boolean(
    scope?.total?.token_exceeded ||
    scope?.total?.request_exceeded ||
    scope?.window?.token_exceeded ||
    scope?.window?.request_exceeded
  );
});

function hasWindowConfig(windowStatus) {
  return Boolean(
    windowStatus && (
      windowStatus.token_limit !== null ||
      windowStatus.request_limit !== null ||
      windowStatus.usage
    )
  );
}

function formatLimitValue(value) {
  if (value === null || value === undefined || value === '') return '未限制';
  return typeof value === 'number' ? formatTokens(value) : String(value);
}

async function loadStatus() {
  loading.value = true;
  try {
    status.value = await getMyQuotaStatus();
  } catch (error) {
    message.error(error.message || '获取额度状态失败');
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
  padding: 24px;
  margin-bottom: 24px;
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
  margin-bottom: 12px;
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
