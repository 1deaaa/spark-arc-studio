<template>
  <n-config-provider :theme="theme" :theme-overrides="themeOverrides">
    <n-global-style />
    <n-message-provider>
      <n-dialog-provider>
        <n-notification-provider>
          <router-view />
          <Toast ref="toastRef" />
          <ModalHost ref="modalRef" />
          
          <!-- 通用输入/确认弹窗 -->
          <n-modal 
            v-model:show="promptModal.show" 
            preset="dialog"
            :title="promptModal.title"
            :positive-text="promptModal.okText || '确定'"
            :negative-text="promptModal.cancelText || '取消'"
            :style="promptModal.hasPosition ? promptModalStyle : {}"
            :transform-origin="promptModal.hasPosition ? 'center' : undefined"
            @positive-click="handlePromptConfirm"
            @negative-click="handlePromptCancel"
            @mask-click="handlePromptCancel"
          >
            <div v-if="promptModal.message" style="margin-bottom: 12px; color: var(--n-text-color);">
              {{ promptModal.message }}
            </div>
            <n-input 
              v-if="promptModal.mode === 'prompt'"
              v-model:value="promptModal.input"
              :placeholder="promptModal.placeholder || '请输入'"
              @keydown.enter="handlePromptConfirm"
              autofocus
            />
          </n-modal>
        </n-notification-provider>
      </n-dialog-provider>
    </n-message-provider>
  </n-config-provider>
</template>

<script setup>
import { ref, reactive, onMounted, onBeforeUnmount, computed } from 'vue';
import { NConfigProvider, NModal, NInput, darkTheme, NMessageProvider, NDialogProvider, NNotificationProvider } from 'naive-ui';
import Toast from './components/share/Toast.vue';
import ModalHost from './components/share/ModalHost.vue';
import bus from './eventBus.js';
import * as config from './config.js';
import { useThemeStore } from './components/stores/themeStore';

const themeStore = useThemeStore();

// 根据 themeStore 切换 Naive UI 主题
const theme = computed(() => {
  if (themeStore.themeMode === 'dark') {
    return darkTheme;
  }
  if (themeStore.themeMode === 'system' && themeStore.prefersDark) {
    return darkTheme;
  }
  return null;
});

onMounted(() => {
  const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
  
  const updateTheme = (e) => themeStore.setPrefersDark(e.matches);
  
  // Initial check
  updateTheme(mediaQuery);
  
  // Listen for changes
  mediaQuery.addEventListener('change', updateTheme);
  
  onBeforeUnmount(() => {
    mediaQuery.removeEventListener('change', updateTheme);
  });
});

// Naive UI 主题配置（对亮色和暗色都生效）
const themeOverrides = computed(() => {
  const isDark = themeStore.themeMode === 'dark' || (themeStore.themeMode === 'system' && themeStore.prefersDark);
  
  const colors = isDark ? {
    primary: '#7aa2f7',
    primaryDim: '#6282c6',
    bg: '#090b10',
    panelBg: '#151923',
    text: '#eef2f6',
    textMuted: '#78869b',
    textInverse: '#0b0e14',
    border: '#2a3040',
    radius: '12px',
    radiusSm: '6px',
  } : {
    primary: '#6b9080',
    primaryDim: '#4a6b5d',
    bg: '#f9fcf9',
    panelBg: '#ffffff',
    text: '#5c5c5c',
    textMuted: '#a0a0a0',
    textInverse: '#ffffff',
    border: '#e6eaf0',
    radius: '12px',
    radiusSm: '6px',
  };

  return {
    common: {
      primaryColor: colors.primary,
      primaryColorHover: colors.primaryDim,
      primaryColorPressed: colors.primaryDim,
      primaryColorSuppl: colors.primary,
      textColorBase: colors.text,
      bodyColor: colors.bg,
      cardColor: colors.panelBg,
      modalColor: colors.panelBg,
      popoverColor: colors.panelBg,
      borderRadius: colors.radius,
      fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif",
      fontSize: '13px',
      heightMedium: '32px',
      heightSmall: '26px',
    },
    Button: {
      borderRadiusMedium: colors.radiusSm,
      borderRadiusSmall: colors.radiusSm,
      borderRadiusLarge: colors.radiusSm,
      fontWeightStrong: '600',
      heightMedium: '32px',
      paddingMedium: '0 16px',
    },
    Card: {
      borderRadius: colors.radius,
      paddingMedium: '16px 20px',
      color: colors.panelBg,
      borderColor: colors.border,
      textColor: colors.text,
      titleTextColor: colors.primary,
    },
    Input: {
      borderRadius: colors.radiusSm,
      heightMedium: '32px',
      color: colors.bg,
      textColor: colors.text,
      border: `1px solid ${colors.border}`,
      borderHover: `1px solid ${colors.primary}`,
      borderFocus: `1px solid ${colors.primary}`,
      placeholderColor: colors.textMuted,
    },
    Select: {
      borderRadius: colors.radiusSm,
      heightMedium: '32px',
      peers: {
        InternalSelection: {
          color: colors.bg,
          textColor: colors.text,
          border: `1px solid ${colors.border}`,
          borderHover: `1px solid ${colors.primary}`,
          borderFocus: `1px solid ${colors.primary}`,
          placeholderColor: colors.textMuted,
        },
        InternalSelectMenu: {
          color: colors.panelBg,
          optionTextColor: colors.text,
          optionTextColorActive: colors.primary,
          optionCheckColor: colors.primary,
        }
      }
    },
    Dropdown: {
      borderRadius: colors.radiusSm,
      padding: '4px 0',
      color: colors.panelBg,
      optionTextColor: colors.text,
      optionTextColorHover: colors.text,
      optionColorHover: colors.border,
    },
    Tag: {
      borderRadius: colors.radiusSm,
      heightMedium: '24px',
    },
    Dialog: {
      borderRadius: colors.radius,
      color: colors.panelBg,
      textColor: colors.text,
      titleTextColor: colors.primary,
    },
    Modal: {
      borderRadius: colors.radius,
      color: colors.panelBg,
      textColor: colors.text,
    },
    Alert: {
      borderRadius: colors.radius,
      colorInfo: isDark ? 'rgba(125, 249, 255, 0.1)' : 'rgba(107, 144, 128, 0.1)',
      titleTextColorInfo: colors.primary,
      iconColorInfo: colors.primary,
      contentTextColor: colors.text,
      border: `1px solid ${isDark ? 'rgba(125, 249, 255, 0.2)' : 'rgba(107, 144, 128, 0.2)'}`,
    },
    Form: {
      labelTextColor: colors.textMuted,
    }
  };
});

const toastRef = ref(null);
const modalRef = ref(null);

// 通用输入/确认弹窗状态
const promptModal = reactive({
  show: false,
  mode: 'prompt', // 'prompt' | 'confirm'
  title: '',
  message: '',
  input: '',
  placeholder: '',
  okText: '确定',
  cancelText: '取消',
  hasPosition: false,
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
      promptModal.title = p.title || '确认';
      promptModal.message = p.message || '';
      promptModal.input = '';
      promptModal.okText = p.okText || '确定';
      promptModal.cancelText = p.cancelText || '取消';
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
    promptModal.title = p.title || (promptModal.mode === 'prompt' ? '输入' : '确认');
    promptModal.message = p.message || '';
    promptModal.input = p.defaultValue || p.input || '';
    promptModal.placeholder = p.placeholder || '';
    promptModal.okText = p.okText || '确定';
    promptModal.cancelText = p.cancelText || '取消';
    promptModal.hasPosition = p.x != null && p.y != null;
    promptModal.x = p.x || 0;
    promptModal.y = p.y || 0;
    promptModal._resolve = p.resolve;
    promptModal.show = true;
  };
  bus.on('prompt', onPrompt);
});

function handlePromptConfirm() {
  const result = promptModal.mode === 'prompt' ? promptModal.input : true;
  promptModal.show = false;
  promptModal._resolve?.(result);
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