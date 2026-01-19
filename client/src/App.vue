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
            :positive-text="promptModal.okText"
            :negative-text="promptModal.cancelText"
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

          <!-- 全局 Loading 遮罩已移至 MainView.vue 的 GlobalLoading 组件 -->

        </n-notification-provider>
      </n-dialog-provider>
    </n-message-provider>
  </n-config-provider>
</template>

<script setup>
import { ref, reactive, onMounted, onBeforeUnmount, computed } from 'vue';
import { NConfigProvider, NGlobalStyle, NModal, NInput, NMessageProvider, NDialogProvider, NNotificationProvider } from 'naive-ui';
import Toast from './components/share/Toast.vue';
import ModalHost from './components/share/ModalHost.vue';
import bus from './eventBus.js';
import * as config from './config.js';
import { useThemeStore } from './components/stores/themeStore';
import { useNaiveTheme } from './styles/themeConfig';

const themeStore = useThemeStore();
const { theme, themeOverrides } = useNaiveTheme(themeStore);

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

  // 初始化检查
  checkSystemConfig();
});

// 检查系统配置状态
async function checkSystemConfig() {
  try {
    const res = await fetch('/api/admin/config/global');
    const data = await res.json();
    
    if (data.success && !data.data.llm_key_set) {
      // 延迟显示，避免和页面加载冲突
      setTimeout(() => {
        promptModal.mode = 'alert'; // 借用 promptModal 的结构，虽然原本没有 alert 模式
        promptModal.title = '⚠️ 系统未初始化';
        promptModal.message = '检测到 LLM_KEY (API密钥主密码) 未设置。\n\n为了安全起见，系统需要一个主密码来加密存储您的 API Key。\n\n请联系管理员运行配置工具 (server/llm/llm_mgr/llm_mgr_cfg_gui.py)，或查看后端控制台的详细指引。';
        promptModal.show = true;
        // 隐藏取消按钮，只有确定
        promptModal.okText = '我知道了';
        promptModal.cancelText = undefined; 
        
        // 临时 hack: 让 handlePromptCancel 不做任何事，或者点击遮罩不关闭（如果需要强制的话）
        // 这里只是提示，允许关闭
        
        // 由于复用了 promptModal，我们需要调整一下它的行为以支持单纯的 alert
        // 不过现有的 handlePromptConfirm 实现会把 input 返回，这里无所谓
      }, 1000);
    }
  } catch (error) {
    console.warn("系统配置检查失败:", error);
  }
}

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