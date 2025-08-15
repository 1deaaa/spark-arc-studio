<template>
  <div v-if="visible" class="toast" :class="type">{{ message }}</div>
</template>

<script setup>
import { ref } from 'vue';

const visible = ref(false);
const message = ref('');
const type = ref('info');
let t;

function show(msg, tpe = 'info', duration = 1800) {
  clearTimeout(t);
  message.value = msg;
  type.value = tpe;
  visible.value = true;
  t = setTimeout(() => (visible.value = false), duration);
}

defineExpose({ show });
</script>

<style scoped>
.toast { position: fixed; right: 16px; bottom: 16px; padding: 10px 14px; border-radius: 6px; color: #fff; box-shadow: 0 2px 8px rgba(0,0,0,0.15); z-index: 9999; }
.toast.info { background: #3498db; }
.toast.success { background: #27ae60; }
.toast.error { background: #e74c3c; }
</style>
