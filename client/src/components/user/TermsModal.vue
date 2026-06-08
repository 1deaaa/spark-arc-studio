<template>
  <n-modal
    v-model:show="show"
    :mask-closable="false"
    :close-on-esc="false"
    :show-icon="false"
    :closable="false"
    class="tos-modal"
    preset="dialog"
    :title="t('components.termsModal.title')"
    style="width: 800px; max-width: 90vw;"
  >
    <div class="tos-content-wrapper">
      <n-spin :show="loading">
        <div v-if="error" class="error-state">
          <p>{{ t('components.termsModal.loadFailed') }}: {{ error }}</p>
          <n-button size="small" @click="fetchTos">{{ t('common.retry') }}</n-button>
          <div class="fallback-notice">
            <p>{{ t('components.termsModal.fallbackNotice1') }}</p>
            <p>{{ t('components.termsModal.fallbackNotice2') }}</p>
          </div>
        </div>
        <div v-else class="markdown-container">
          <MarkdownRenderer :content="tosContent" />
        </div>
      </n-spin>
    </div>

    <template #action>
      <div v-if="mode === 'accept'" class="modal-actions">
        <n-button @click="handleDecline" :disabled="loading || submitting" type="error" ghost>
          {{ t('components.termsModal.declineAndExit') }}
        </n-button>
        <n-button
          type="primary"
          @click="handleAccept"
          :loading="submitting"
          :disabled="loading"
        >
          {{ error ? t('components.termsModal.agreeAndContinue') : t('components.termsModal.readAndAgree') }}
        </n-button>
      </div>
      <div v-else class="modal-actions">
        <n-button @click="show = false">{{ t('common.close') }}</n-button>
      </div>
    </template>
  </n-modal>
</template>

<script setup lang="ts">
import { defineAsyncComponent, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { NModal, NButton, NSpin, useMessage } from 'naive-ui';
import { fetchWithAuth } from '@/services/apiClient';
import { logout } from '@/services/authService';
import { useProjectStore } from '@/components/stores/projectStore';
import { useRouter } from 'vue-router';

type TermsModalMode = 'accept' | 'view';

type TermsModalProps = {
  visible?: boolean;
  mode?: TermsModalMode;
};

function getErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof Error && error.message) return error.message;
  if (typeof error === 'string' && error.trim()) return error;
  return fallback;
}

const props = withDefaults(defineProps<TermsModalProps>(), {
  visible: false,
  mode: 'accept',
});

const emit = defineEmits(['update:visible', 'accepted']);

const { t, locale } = useI18n();
const MarkdownRenderer = defineAsyncComponent(() => import('@/components/share/MarkdownRenderer.vue'));

const show = ref(props.visible);
const loading = ref(true);
const submitting = ref(false);
const tosContent = ref('');
const error = ref('');
const message = useMessage();
const router = useRouter();

watch(() => props.visible, (val) => {
  show.value = val;
  if (val && !tosContent.value) {
    fetchTos();
  }
});

watch(show, (val) => {
  emit('update:visible', val);
});

async function fetchTos() {
  loading.value = true;
  error.value = '';
  try {
    const res = await fetchWithAuth(`/api/tos?lang=${encodeURIComponent(locale.value)}`);
    const data = await res.json();
    if (data.success) {
      tosContent.value = data.content;
    } else {
      error.value = data.message || t('components.termsModal.fetchFailed');
    }
  } catch (e: unknown) {
    error.value = getErrorMessage(e, t('components.termsModal.networkError'));
  } finally {
    loading.value = false;
  }
}

async function handleAccept() {
  submitting.value = true;
  try {
    const res = await fetchWithAuth('/api/user/accept-tos', {
      method: 'POST'
    });
    const data = await res.json();
    
    if (data.success) {
      message.success(t('components.termsModal.acceptedSuccess'));
      show.value = false;
      emit('accepted');
    } else {
      message.error(data.message || t('components.termsModal.operationFailed'));
    }
  } catch (e: unknown) {
    message.error(t('components.termsModal.networkError') + ': ' + getErrorMessage(e, t('components.termsModal.requestFailed')));
  } finally {
    submitting.value = false;
  }
}

async function handleDecline() {
  // 拒绝条款则登出并返回登录页
  const projectStore = useProjectStore();
  projectStore.resetForLogout();
  try {
    await logout();
  } catch (e: unknown) {
    console.error('Logout failed:', e);
  } finally {
    show.value = false;
    router.push('/login');
    message.warning(t('components.termsModal.declinedWarning'));
  }
}
</script>

<style scoped>
.tos-content-wrapper {
  height: 60vh;
  overflow-y: auto;
  padding: 16px;
  background: var(--n-color-modal);
  border: 1px solid var(--n-border-color);
  border-radius: 4px;
  margin-bottom: 16px;
}

.markdown-container {
  line-height: 1.6;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}
.error-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  gap: 12px;
  color: var(--n-text-color-error);
}

.fallback-notice {
  margin-top: 16px;
  padding: 12px 16px;
  background: rgba(128, 128, 128, 0.1);
  border-radius: 6px;
  color: var(--n-text-color);
  font-size: var(--spark-fs-sm);
  text-align: center;
  line-height: 1.6;
}

/* 适配暗色模式滚动条 */
.tos-content-wrapper::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}

.tos-content-wrapper::-webkit-scrollbar-thumb {
  background: rgba(128, 128, 128, 0.4);
  border-radius: 3px;
}

.tos-content-wrapper::-webkit-scrollbar-track {
  background: transparent;
}
</style>
