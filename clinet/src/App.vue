<template>
  <n-config-provider :theme="theme" :theme-overrides="themeOverrides">
    <n-global-style />
    <router-view />
    <Toast ref="toastRef" />
    <ModalHost ref="modalRef" />
    <ContextPrompt ref="ctxPromptRef" />
  </n-config-provider>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, computed } from 'vue';
import { NConfigProvider, NGlobalStyle, darkTheme } from 'naive-ui';
import Toast from './components/share/Toast.vue';
import ModalHost from './components/share/ModalHost.vue';
import ContextPrompt from './components/share/ContextPrompt.vue';
import bus from './eventBus';

// 响应式深浅色模式
const prefersDark = ref(false);

// 监听深浅色变化，同步更新 body 类名（用于原生 CSS 组件）
const syncBodyClass = () => {
  if (prefersDark.value) {
    document.body.classList.add('dark-mode');
  } else {
    document.body.classList.remove('dark-mode');
  }
};

// 监听系统主题变化
const updateThemePreference = (e) => {
  prefersDark.value = e.matches;
  syncBodyClass(); // 主题变化时同步更新 body 类名
};

// 根据系统主题切换 Naive UI 主题
const theme = computed(() => prefersDark.value ? darkTheme : null);

onMounted(() => {
  // 检测系统当前主题
  const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
  prefersDark.value = mediaQuery.matches;
  syncBodyClass(); // 初始化时同步 body 类名
  
  // 监听系统主题变化
  mediaQuery.addEventListener('change', updateThemePreference);
});

onBeforeUnmount(() => {
  const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
  mediaQuery.removeEventListener('change', updateThemePreference);
});

// Naive UI 主题配置（对亮色和暗色都生效）
const themeOverrides = computed(() => ({
  common: {
    primaryColor: '#3498db',
    primaryColorHover: '#5dade2',
    primaryColorPressed: '#2980b9',
    primaryColorSuppl: '#5dade2',
    borderRadius: '8px',
    fontFamily: "'Microsoft YaHei', 'PingFang SC', sans-serif",
  },
  Button: {
    borderRadiusMedium: '6px',
    borderRadiusSmall: '4px',
    borderRadiusLarge: '8px',
    fontWeightStrong: '600',
  },
  Card: {
    borderRadius: '8px',
    paddingMedium: '12px',
  },
  Input: {
    borderRadius: '6px',
  },
  Select: {
    borderRadius: '6px',
  },
  Dropdown: {
    borderRadius: '6px',
    padding: '4px 0',
  },
  Tag: {
    borderRadius: '4px',
  }
}));

const toastRef = ref(null);
const modalRef = ref(null);
const ctxPromptRef = ref(null);

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
    const { x, y } = p || {};
    let res;
    if (typeof x === 'number' && typeof y === 'number' && ctxPromptRef.value) {
      res = await ctxPromptRef.value.open({ mode: 'confirm', ...p });
    } else {
      res = await modalRef.value?.open?.({ mode: 'confirm', ...p });
    }
    p?.resolve?.(res === true);
  };
  bus.on('confirm', onConfirm);

  onPrompt = async (p) => {
    const { x, y } = p || {};
    let res;
    if (typeof x === 'number' && typeof y === 'number' && ctxPromptRef.value) {
      res = await ctxPromptRef.value.open({ mode: 'prompt', ...p });
    } else {
      res = await modalRef.value?.open?.({ mode: 'prompt', ...p });
    }
    p?.resolve?.(res ?? null);
  };
  bus.on('prompt', onPrompt);
});

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
</style>