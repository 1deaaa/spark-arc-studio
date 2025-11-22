<template>
  <Transition name="toast-fade">
  <div v-if="visible" class="toast" :class="type">{{ message }}</div>
  </Transition>
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
.toast { 
  position: fixed; 
  right: 16px; 
  bottom: 16px; 
  padding: 10px 14px; 
  border-radius: var(--spark-radius); 
  color: var(--spark-text-inverse); 
  box-shadow: var(--spark-shadow); 
  z-index: 9999; 
  font-weight: 500;
}
.toast.info { background: var(--spark-primary); }
.toast.success { background: var(--spark-success); }
.toast.error { background: var(--spark-danger); }

.toast-fade-enter-active,
.toast-fade-leave-active {
  transition: all 0.3s ease;
}
.toast-fade-enter-from,
.toast-fade-leave-to {
  opacity: 0;
  transform: translate(20px, 20px);
}
</style>
