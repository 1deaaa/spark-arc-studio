<template>
  <n-config-provider
    :theme="theme"
    :theme-overrides="themeOverrides"
    :hljs="hljs"
    :locale="naiveLocale"
    :date-locale="naiveDateLocale"
  >
    <n-global-style />
    <TitleBar />
    <n-message-provider>
      <n-dialog-provider>
        <n-notification-provider>
          <router-view />
          <DirectorAutoWriteOverlay />
          <OnboardingOverlay />
          <Toast ref="toastRef" />

          <ModalHost ref="modalRef" />

          <!-- 公告弹窗 -->
          <AnnouncementModal ref="announcementRef" @read="onAnnouncementRead" />

          <!-- 强制同意条款弹窗 -->
          <TermsModal
            v-model:visible="showTosModal"
            mode="accept"
            @accepted="handleTosAccepted"
          />

          <!-- 通用输入/确认弹窗 -->
          <n-modal 
            v-model:show="promptModal.show" 
            preset="dialog"
            :title="promptModal.title"
            :positive-text="promptModal.okText"
            :negative-text="promptModal.cancelText"
            :style="promptModal.hasPosition ? promptModalStyle : {}"
            :transform-origin="promptModal.hasPosition ? 'center' : undefined"
            :closable="promptModal.maskClosable !== false"
            :mask-closable="promptModal.maskClosable !== false"
            :close-on-esc="promptModal.maskClosable !== false"
            @positive-click="handlePromptConfirm"
            @negative-click="handlePromptCancel"
            @mask-click="promptModal.maskClosable !== false ? handlePromptCancel() : undefined"
          >
            <div v-if="promptModal.message" style="margin-bottom: 12px; color: var(--n-text-color); white-space: pre-wrap;">
              {{ promptModal.message }}
            </div>
            <n-input
              v-if="promptModal.mode === 'prompt'"
              v-model:value="promptModal.input"
              :placeholder="promptModal.placeholder || t('common.pleaseInput')"
              :input-props="{ spellcheck: false, autocorrect: 'off', autocapitalize: 'off', autocomplete: 'off' }"
              @keydown.enter="handlePromptConfirm"
              autofocus
            />
          </n-modal>

          <!-- 全局 Loading 遮罩已移至 MainView.vue 的 GlobalLoading 组件 -->

        </n-notification-provider>
      </n-dialog-provider>
    </n-message-provider>
  </n-config-provider>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, onBeforeUnmount, computed, watch, nextTick } from 'vue';
import {
  NConfigProvider,
  NGlobalStyle,
  NModal,
  NInput,
  NMessageProvider,
  NDialogProvider,
  NNotificationProvider,
  zhCN,
  enUS,
  jaJP,
  dateZhCN,
  dateEnUS,
  dateJaJP,
} from 'naive-ui';
import hljs from 'highlight.js/lib/core';
import Toast from './components/share/Toast.vue';
import ModalHost from './components/share/ModalHost.vue';
import TitleBar from './components/layouts/desktop/TitleBar.vue';
import DirectorAutoWriteOverlay from './components/share/DirectorAutoWriteOverlay.vue';
import { OnboardingOverlay, getOnboardingEngine, setupOnboarding } from './onboarding';
import bus from './eventBus';

import TermsModal from './components/user/TermsModal.vue';
import AnnouncementModal from './components/share/AnnouncementModal.vue';
import { fetchWithAuth, getSessionToken, isAuthError } from './services/apiClient';
import { useThemeStore } from './components/stores/themeStore';
import { useLocaleStore } from './components/stores/localeStore';
import { useNaiveTheme } from './styles/themeConfig';
import { isLocalTauriShell, isTauriDesktop } from './composables/usePlatform';
import { useI18n } from 'vue-i18n';
import router from './router';

const themeStore = useThemeStore();
const { theme, themeOverrides } = useNaiveTheme(themeStore);
const localeStore = useLocaleStore();
const { t } = useI18n();

const naiveLocale = computed(() => {
  switch (localeStore.locale) {
    case 'en-US':
      return enUS;
    case 'ja-JP':
      return jaJP;
    case 'zh-CN':
    default:
      return zhCN;
  }
});

const naiveDateLocale = computed(() => {
  switch (localeStore.locale) {
    case 'en-US':
      return dateEnUS;
    case 'ja-JP':
      return dateJaJP;
    case 'zh-CN':
    default:
      return dateZhCN;
  }
});

const showTosModal = ref(false); // 强制同意条款弹窗
const llmKeyPromptShown = ref(false);
let editorProofingObserver: MutationObserver | null = null;

function disableEditorProofing(root: ParentNode = document) {
  const nodes = root.querySelectorAll('textarea, [contenteditable="true"]');
  nodes.forEach((node) => {
    if (node instanceof HTMLElement) {
      node.setAttribute('spellcheck', 'false');
      node.setAttribute('autocorrect', 'off');
      node.setAttribute('autocapitalize', 'off');
      if (node instanceof HTMLTextAreaElement) {
        node.setAttribute('autocomplete', 'off');
      }
    }
  });
}

function setupGlobalEditorProofing() {
  if (typeof document === 'undefined') return;
  disableEditorProofing(document);
  editorProofingObserver?.disconnect();
  editorProofingObserver = new MutationObserver((mutations) => {
    for (const mutation of mutations) {
      mutation.addedNodes.forEach((node) => {
        if (!(node instanceof HTMLElement)) return;
        if (node.matches('textarea, [contenteditable="true"]')) {
          disableEditorProofing((node.parentNode as ParentNode) || document);
        } else {
          disableEditorProofing(node);
        }
      });
    }
  });
  editorProofingObserver.observe(document.body, { childList: true, subtree: true });
}

// 初始化引导引擎
setupOnboarding();

onMounted(() => {
  const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
  
  const updateTheme = (e) => themeStore.setPrefersDark(e.matches);
  
  // Initial check
  updateTheme(mediaQuery);
  
  // Listen for changes
  mediaQuery.addEventListener('change', updateTheme);
  
  // 桌面端 Tauri：为 body 添加标题栏占位
  if (isTauriDesktop.value) {
    document.body.classList.add('tauri-desktop');
  }

  setupGlobalEditorProofing();
  
  // 监听登录成功事件，触发检查
  bus.on('login-success', runPostLoginGuards);

  // 监听 session 过期事件，提示用户并跳转登录页
  const onSessionExpired = () => {
    // 已在登录页则不重复提示和跳转
    if (router.currentRoute.value.name === 'Login') return;
    bus.emit('toast', { message: t('login.errors.sessionExpired'), type: 'warning' });
    router.push('/login');
  };
  bus.on('auth-session-expired', onSessionExpired);

  // 初始检查 (如果已登录)
  runPostLoginGuards();
  
  onBeforeUnmount(() => {
    mediaQuery.removeEventListener('change', updateTheme);
    bus.off('login-success', runPostLoginGuards);
    bus.off('auth-session-expired', onSessionExpired);
  });
});

onBeforeUnmount(() => {
  editorProofingObserver?.disconnect();
  editorProofingObserver = null;
});

// 标记 post-login-ready 是否已发射，供子组件 mount 时检查
let postLoginReadySent = false;

function resetPostLoginReady() {
  postLoginReadySent = false;
  (bus as any).postLoginReadySent = false;
}

function emitPostLoginReady() {
  postLoginReadySent = true;
  (bus as any).postLoginReadySent = true;
  bus.emit('post-login-ready');
}

function stopOnboarding() {
  const onboardingEngine = getOnboardingEngine();
  if (onboardingEngine.isActive.value) {
    onboardingEngine.destroy();
  }
}

async function runPostLoginGuards() {
  resetPostLoginReady();
  stopOnboarding();
  if (isLocalTauriShell.value) return;
  // 未登录时不应触发任何登录后逻辑（包括 onboarding）
  if (!getSessionToken()) return;
  const needAccept = await checkTosStatus();
  if (needAccept) {
    // 需要接受条款时，不触发 post-login-ready，等用户同意后在 handleTosAccepted 中触发
    return;
  }
  await checkSystemConfig();
  // 所有登录后检查完成，通知子组件可以安全触发 onboarding
  emitPostLoginReady();
  // onboarding 触发后再检查公告弹窗（避免多层弹窗叠加）
  checkAnnouncement();
}

async function checkTosStatus() {
  try {
    const res = await fetchWithAuth('/api/user/tos-status');
    const data = await res.json();
    const needAccept = Boolean(data.success && data.need_accept);
    if (needAccept) {
      stopOnboarding();
      resetPostLoginReady();
    }
    showTosModal.value = needAccept;
    return needAccept;
  } catch (e: unknown) {
    const errorMessage = e instanceof Error ? e.message : String(e || '');
    showTosModal.value = false;
    if (errorMessage && !isAuthError(e)) {
      console.warn('Check TOS status failed:', e);
    }
    return false;
  }
}

async function handleTosAccepted() {
  showTosModal.value = false;
  await checkSystemConfig();
  // TOS 接受后检查完成，通知子组件可以安全触发 onboarding
  emitPostLoginReady();
  // onboarding 触发后再检查公告弹窗
  checkAnnouncement();
}

async function checkAnnouncement() {
  try {
    const res = await fetchWithAuth('/api/system/notice');
    const data = await res.json();
    if (!data.success || !data.notice) return;
    // 已读则不弹
    if (data.is_read) return;
    // 等待 onboarding 完成后再弹公告（避免弹窗叠加）
    await waitForOnboardingDone();
    // 展示公告弹窗
    announcementRef.value?.show(data.notice);
  } catch (e: unknown) {
    const errorMessage = e instanceof Error ? e.message : String(e || '');
    if (errorMessage && !isAuthError(e)) {
      console.warn('Check announcement failed:', e);
    }
  }
}

/**
 * 等待 onboarding 引擎结束（完成/跳过/销毁）。
 * 如果 onboarding 未在运行则立即返回；
 * 如果正在运行则 watch isActive，变为 false 时 resolve。
 */
function waitForOnboardingDone(): Promise<void> {
  const engine = getOnboardingEngine();
  if (!engine.isActive.value) return Promise.resolve();
  return new Promise<void>((resolve) => {
    const stop = watch(engine.isActive, (active) => {
      if (!active) {
        stop();
        resolve();
      }
    });
  });
}

function onAnnouncementRead() {
  // 公告已读回调（预留扩展点，如刷新侧边栏公告板状态等）
}

const toastRef = ref(null);
const modalRef = ref(null);
const announcementRef = ref<InstanceType<typeof AnnouncementModal> | null>(null);

// 通用输入/确认弹窗状态
type PromptModalState = {
  show: boolean;
  mode: 'prompt' | 'confirm' | string;
  title: string;
  message: string;
  input: string;
  placeholder: string;
  okText: string;
  cancelText: string | undefined;
  hasPosition: boolean;
  maskClosable: boolean;
  x: number;
  y: number;
  _resolve: ((value: unknown) => Promise<boolean | void> | boolean | void) | null;
};

const promptModal = reactive<PromptModalState>({
  show: false,
  mode: 'prompt', // 'prompt' | 'confirm'
  title: '',
  message: '',
  input: '',
  placeholder: '',
  okText: t('common.confirm'),
  cancelText: t('common.cancel'),
  hasPosition: false,
  maskClosable: true,
  x: 0,
  y: 0,
  _resolve: null
});

// 计算弹窗位置样式
const promptModalStyle = computed(() => {
  if (!promptModal.hasPosition) return {};
  
  const pad = 12;
  let left = promptModal.x + pad;
  let top = promptModal.y - 8;
  
  // 简单防溢出
  const vw = window.innerWidth;
  const vh = window.innerHeight;
  const w = 400; // 弹窗宽度估算
  const h = 200; // 弹窗高度估算
  
  if (left + w > vw - 8) left = Math.max(8, vw - w - 8);
  if (top + h > vh - 8) top = Math.max(8, vh - h - 8);
  if (top < 8) top = 8;
  
  return {
    position: 'fixed',
    left: `${left}px`,
    top: `${top}px`,
    margin: '0'
  };
});

let onToast, onConfirm, onPrompt;

onMounted(() => {
  // Setup global event listeners for modals and toasts
  // These are needed here because App.vue is the root component
  // and these services should be available everywhere.
  onToast = (p) => {
    const { message, type = 'info', duration } = p || {};
    toastRef.value?.show?.(message || '', type, duration);
  };
  bus.on('toast', onToast);

  onConfirm = async (p) => {
    const { resolve, x, y } = p || {};
    
    // 如果提供了坐标，使用统一的弹窗在指定位置显示
    if (x != null && y != null) {
      promptModal.mode = 'confirm';
      promptModal.title = p.title || t('app.promptDefaultTitleConfirm');
      promptModal.message = p.message || '';
      promptModal.input = '';
      promptModal.okText = p.okText || t('common.confirm');
      promptModal.cancelText = p.cancelText || t('common.cancel');
      promptModal.hasPosition = true;
      promptModal.x = x;
      promptModal.y = y;
      promptModal._resolve = resolve;
      promptModal.show = true;
    } else {
      // 否则使用 ModalHost 居中显示
      const res = await modalRef.value?.open?.({ mode: 'confirm', ...p });
      if (typeof resolve === 'function') {
        resolve(res === true);
      }
    }
  };
  bus.on('confirm', onConfirm);

  onPrompt = async (p) => {
    // 统一使用 Naive UI Modal
    promptModal.mode = p.type || 'prompt';
    promptModal.title = p.title || (promptModal.mode === 'prompt' ? t('app.promptDefaultTitlePrompt') : t('app.promptDefaultTitleConfirm'));
    promptModal.message = p.message || '';
    promptModal.input = p.defaultValue || p.input || '';
    promptModal.placeholder = p.placeholder || '';
    promptModal.okText = p.okText || t('common.confirm');
    promptModal.cancelText = p.cancelText; // 允许为 undefined 以隐藏
    promptModal.hasPosition = p.x != null && p.y != null;
    promptModal.x = p.x || 0;
    promptModal.y = p.y || 0;
    promptModal.maskClosable = p.maskClosable !== false; // 默认为 true
    promptModal._resolve = p.resolve;
    promptModal.show = true;
  };
  bus.on('prompt', onPrompt);
});

// 检查系统配置状态
async function checkSystemConfig() {
  try {
    if (showTosModal.value || llmKeyPromptShown.value || promptModal.show) {
      return;
    }

    const userRes = await fetchWithAuth('/api/user/info');
    const userData = await userRes.json();
    const user = userData?.user;
    const isInitialAdmin = Boolean(user?.is_initial_admin ?? user?.is_admin);

    if (!userData?.success || !isInitialAdmin) {
      return;
    }

    const res = await fetchWithAuth('/api/admin/config/global');
    if (!res.ok) {
      return;
    }

    const data = await res.json();
    if (data.success && !data.data.llm_key_set) {
      llmKeyPromptShown.value = true;
      setTimeout(() => {
        // 使用 bus.emit('prompt') 触发全局输入弹窗
        bus.emit('prompt', {
          title: t('app.systemInit.title'),
          message: t('app.systemInit.message'),
          placeholder: t('app.systemInit.placeholder'),
          okText: t('app.systemInit.submit'),
          cancelText: undefined, // 隐藏取消按钮
          maskClosable: false,   // 禁止点击遮罩关闭
          resolve: async (input) => {
            if (!input || !input.trim()) return false; // 如果为空，不关闭弹窗
 
            try {
              const setRes = await fetchWithAuth('/api/admin/config/llm-key', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ key: input })
              });
              const setJson = await setRes.json();
              
              if (setJson.success) {
                bus.emit('toast', { message: t('app.systemInit.success'), type: 'success' });
                return true;
              } else {
                bus.emit('toast', {
                  message: t('app.systemInit.setFailedPrefix') + (setJson.detail || setJson.message || t('app.systemInit.unknownError')),
                  type: 'error'
                });
                return false;
              }
            } catch (e) {
              bus.emit('toast', { message: t('app.systemInit.networkFailedPrefix') + e, type: 'error' });
              return false;
            }
          }
        });
      }, 500);
    }
  } catch (error: unknown) {
    const errorMessage = error instanceof Error ? error.message : String(error || '');
    if (errorMessage && !isAuthError(error)) {
      console.warn("系统配置检查失败:", error);
    }
  }
}

async function handlePromptConfirm() {
  const result = promptModal.mode === 'prompt' ? promptModal.input : true;
  
  if (typeof promptModal._resolve === 'function') {
    const success = await promptModal._resolve(result);
    // 如果 resolve 返回 false，则不关闭弹窗（用于强制输入验证）
    if (success === false) return;
  }
  
  promptModal.show = false;
  promptModal._resolve = null;
}

function handlePromptCancel() {
  promptModal.show = false;
  promptModal._resolve?.(promptModal.mode === 'prompt' ? null : false);
  promptModal._resolve = null;
}

onBeforeUnmount(() => {
  // Clean up event listeners
  if (onToast) bus.off('toast', onToast);
  if (onConfirm) bus.off('confirm', onConfirm);
  if (onPrompt) bus.off('prompt', onPrompt);
});
</script>

<style>
/* Minimal styles for the root component */
#app {
  height: 100vh;
  width: 100vw;
  display: flex;
  flex-direction: column;
}


.container {
  display: flex;
  flex-direction: column;
  height: 100vh;
}
main {
  display: flex;
  flex: 1;
  overflow: hidden;
}
.panel {
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.resizer {
  background: #f0f0f0;
  cursor: col-resize;
  width: 4px;
  flex-shrink: 0;
}
.resizer.active {
  background: #ccc;
}
.dark-mode .resizer {
  background: #2c2c2c;
}
.dark-mode .resizer.active {
  background: #4a4a4a;
}
</style>
