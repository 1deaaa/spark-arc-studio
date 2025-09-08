<template>
  <router-view />
  <Toast ref="toastRef" />
  <ModalHost ref="modalRef" />
  <ContextPrompt ref="ctxPromptRef" />
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue';
import Toast from './components/share/Toast.vue';
import ModalHost from './components/share/ModalHost.vue';
import ContextPrompt from './components/share/ContextPrompt.vue';
import bus from './eventBus';

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