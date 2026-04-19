<template>
  <n-card size="small" class="user-redeem-card">
    <template #header>
      {{ t('views.dashboard.desktop.redeemCode') }} <SparkIcon size="18" />
    </template>
    <div class="redeem-row">
      <n-input
        v-model:value="redeemCodeInput"
        :placeholder="t('views.dashboard.desktop.redeemPlaceholder')"
        size="small"
        clearable
        @keyup.enter="handleRedeem"
      />
      <n-button
        type="primary"
        size="small"
        :loading="redeeming"
        @click="handleRedeem"
      >{{ t('views.dashboard.desktop.redeemButton') }}</n-button>
    </div>
  </n-card>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { useI18n } from 'vue-i18n';
import { NCard, NInput, NButton, useMessage } from 'naive-ui';
import SparkIcon from '@/components/share/CreditIcon.vue';
import { redeemCode } from '../../services/adminService';

const { t } = useI18n();
const message = useMessage();

const redeemCodeInput = ref('');
const redeeming = ref(false);

async function handleRedeem() {
  const code = redeemCodeInput.value.trim();
  if (!code) {
    message.warning(t('views.dashboard.desktop.redeemEmpty'));
    return;
  }
  redeeming.value = true;
  try {
    const result = await redeemCode(code);
    message.success(t('views.dashboard.desktop.redeemSuccess', { amount: result.credit_amount }));
    redeemCodeInput.value = '';
  } catch (e: any) {
    message.error(e.message || t('views.dashboard.desktop.redeemFailed'));
  } finally {
    redeeming.value = false;
  }
}
</script>

<style scoped>
.user-redeem-card {
  border-radius: var(--spark-radius);
}

.redeem-row {
  display: flex;
  gap: 8px;
  align-items: center;
}

.redeem-row .n-input {
  flex: 1;
}
</style>
