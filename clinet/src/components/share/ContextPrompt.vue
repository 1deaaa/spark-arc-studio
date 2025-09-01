<template>
  <Transition name="ctx-fade">
  <div v-if="state.visible" class="ctx-wrap" :style="wrapStyle" @click.stop>
    <div class="ctx-box">
      <div class="ctx-title" v-if="state.title">{{ state.title }}</div>
      <div class="ctx-message" v-if="state.message">{{ state.message }}</div>
      <input v-if="state.mode==='prompt'" v-model="state.input" class="ctx-input" @keydown.enter.prevent="confirm" />
      <div class="ctx-actions">
        <button class="btn-primary" @click="confirm">{{ state.okText || '确定' }}</button>
        <button class="btn-secondary" @click="cancel">{{ state.cancelText || '取消' }}</button>
      </div>
    </div>
  </div>
  </Transition>
</template>

<script setup>
import { reactive, computed, onMounted, onBeforeUnmount } from 'vue';

const state = reactive({
  visible: false,
  mode: 'confirm', // 'confirm' | 'prompt'
  title: '',
  message: '',
  input: '',
  okText: '确定',
  cancelText: '取消',
  x: 0,
  y: 0,
  _resolve: null,
});

function open(opts) {
  const { x = 0, y = 0, defaultValue } = opts || {};
  const next = { ...opts, x, y };
  if (typeof defaultValue === 'string') next.input = defaultValue;
  else if (!('input' in next)) next.input = '';
  Object.assign(state, { visible: true, ...next });
  return new Promise((resolve) => (state._resolve = resolve));
}

function confirm() {
  const v = state.mode === 'prompt' ? state.input : true;
  state.visible = false; state._resolve?.(v);
}
function cancel() { state.visible = false; state._resolve?.(state.mode === 'prompt' ? null : false); }

const wrapStyle = computed(() => {
  // 默认在鼠标右侧偏移 12px；同时做简单的边界收敛
  const pad = 12;
  let left = state.x + pad;
  let top = state.y - 8;
  // 简单防溢出（依赖大致宽高，后续可用 ResizeObserver 优化）
  const vw = window.innerWidth, vh = window.innerHeight;
  const w = 320, h = 160;
  if (left + w > vw - 8) left = Math.max(8, vw - w - 8);
  if (top + h > vh - 8) top = Math.max(8, vh - h - 8);
  if (top < 8) top = 8;
  return { left: left + 'px', top: top + 'px' };
});

function onDocClick() { if (state.visible) cancel(); }
onMounted(() => document.addEventListener('click', onDocClick));
onBeforeUnmount(() => document.removeEventListener('click', onDocClick));

defineExpose({ open });
</script>

<style scoped>
.ctx-wrap { position: fixed; z-index: 10000; }
.ctx-box { width: 320px; max-width: calc(100vw - 24px); background:#fff; border:1px solid #e6ecf5; border-radius:10px; box-shadow: 0 10px 24px rgba(0,0,0,0.12); padding:12px; }
.ctx-title { font-weight:700; margin-bottom:8px; }
.ctx-message { color:#555; margin-bottom:10px; white-space: pre-wrap; }
.ctx-input { width:100%; border:1px solid #d9d9d9; border-radius:6px; padding:8px; margin-bottom:10px; }
.ctx-actions { display:flex; gap:8px; justify-content:flex-end; }
.btn-primary { background:#3498db; color:#fff; border:none; border-radius:6px; padding:8px 12px; }
.btn-secondary { background:#eef3fb; color:#1f4c7c; border:none; border-radius:6px; padding:8px 12px; }
.btn-primary:hover { filter:brightness(1.05) }
.btn-secondary:hover { filter:brightness(0.98) }

.ctx-fade-enter-active,
.ctx-fade-leave-active {
  transition: all 0.2s ease;
}
.ctx-fade-enter-from,
.ctx-fade-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}
</style>
