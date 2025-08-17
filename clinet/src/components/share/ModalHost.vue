<template>
  <div v-if="state.visible" class="modal-mask" @click.self="cancel">
    <div class="modal-box">
      <div class="modal-title">{{ state.title }}</div>
      <div class="modal-message" v-if="state.message">{{ state.message }}</div>
      <input v-if="state.mode==='prompt'" v-model="state.input" class="modal-input" />
      <div class="modal-actions">
        <button @click="confirm" class="btn-primary">{{ state.okText || '确定' }}</button>
        <button @click="cancel" class="btn-secondary">{{ state.cancelText || '取消' }}</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { reactive } from 'vue';

const state = reactive({
  visible: false,
  mode: 'confirm', // 'confirm' | 'prompt'
  title: '',
  message: '',
  input: '',
  okText: '确定',
  cancelText: '取消',
  _resolve: null,
});

function open(opts) {
  Object.assign(state, { visible: true, input: '', ...opts });
  return new Promise((resolve) => (state._resolve = resolve));
}
function confirm() {
  const v = state.mode === 'prompt' ? state.input : true;
  state.visible = false; state._resolve?.(v);
}
function cancel() { state.visible = false; state._resolve?.(state.mode === 'prompt' ? null : false); }

defineExpose({ open });
</script>

<style scoped>
.modal-mask { position: fixed; inset: 0; background: rgba(0,0,0,.35); display:flex; align-items:center; justify-content:center; z-index: 10000; }
.modal-box { width: 360px; max-width: calc(100% - 40px); background:#fff; border-radius:8px; padding:16px; box-shadow: 0 6px 22px rgba(0,0,0,.18); }
.modal-title { font-weight: 700; margin-bottom: 10px; }
.modal-message { color:#555; margin-bottom: 14px; white-space: pre-wrap; }
.modal-input { width: 100%; border:1px solid #ddd; border-radius:6px; padding:8px; margin-bottom: 12px; }
.modal-actions { display:flex; gap:8px; justify-content:flex-end; }
.btn-primary { background:#3498db; color:#fff; border:none; border-radius:6px; padding:8px 14px; }
.btn-secondary { background:#eef3fb; color:#1f4c7c; border:none; border-radius:6px; padding:8px 14px; }
.btn-primary:hover { filter:brightness(1.05) }
.btn-secondary:hover { filter:brightness(0.98) }
</style>
