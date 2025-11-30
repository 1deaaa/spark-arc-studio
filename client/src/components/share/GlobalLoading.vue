<template>
  <transition name="fade">
    <div v-if="visible" class="loading-overlay">
      <div class="loading-content">
        <!-- 精致的 SVG 动画：星轨/灵感 -->
        <svg class="spinner-svg" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
          <defs>
            <linearGradient id="grad1" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" style="stop-color:var(--spark-primary);stop-opacity:1" />
              <stop offset="100%" style="stop-color:var(--spark-secondary);stop-opacity:1" />
            </linearGradient>
            <filter id="glow">
              <feGaussianBlur stdDeviation="2.5" result="coloredBlur"/>
              <feMerge>
                <feMergeNode in="coloredBlur"/>
                <feMergeNode in="SourceGraphic"/>
              </feMerge>
            </filter>
          </defs>
          
          <!-- 外圈轨道 -->
          <circle cx="50" cy="50" r="45" stroke="var(--spark-border)" stroke-width="1" fill="none" opacity="0.3" />
          
          <!-- 旋转的弧线 1 -->
          <path d="M50 5 A45 45 0 0 1 95 50" stroke="url(#grad1)" stroke-width="2" fill="none" stroke-linecap="round" filter="url(#glow)">
            <animateTransform attributeName="transform" type="rotate" from="0 50 50" to="360 50 50" dur="2s" repeatCount="indefinite" />
          </path>
          
          <!-- 旋转的弧线 2 (反向) -->
          <path d="M50 85 A35 35 0 0 0 15 50" stroke="var(--spark-secondary)" stroke-width="2" fill="none" stroke-linecap="round" opacity="0.8">
            <animateTransform attributeName="transform" type="rotate" from="360 50 50" to="0 50 50" dur="3s" repeatCount="indefinite" />
          </path>
          
          <!-- 中心呼吸圆 -->
          <circle cx="50" cy="50" r="5" fill="var(--spark-primary)">
            <animate attributeName="r" values="5;8;5" dur="2s" repeatCount="indefinite" />
            <animate attributeName="opacity" values="0.8;0.4;0.8" dur="2s" repeatCount="indefinite" />
          </circle>
          
          <!-- 粒子点缀 -->
          <circle cx="50" cy="15" r="2" fill="var(--spark-text)">
            <animateTransform attributeName="transform" type="rotate" from="0 50 50" to="360 50 50" dur="4s" repeatCount="indefinite" />
          </circle>
        </svg>
        
        <div class="loading-text">{{ text }}</div>
        
        <n-button 
          v-if="canCancel" 
          size="small" 
          secondary 
          round 
          class="cancel-btn"
          @click="handleCancel"
        >
          取消生成
        </n-button>
      </div>
    </div>
  </transition>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue';
import { NButton } from 'naive-ui';
import bus from '@/eventBus';

const visible = ref(false);
const text = ref('');
const canCancel = ref(false);

function onGlobalLoading(p) {
  if (typeof p === 'boolean') {
    visible.value = p;
    text.value = '';
    canCancel.value = false;
  } else {
    visible.value = !!p?.show;
    text.value = p?.text || '正在处理...';
    canCancel.value = !!p?.canCancel;
  }
}

function handleCancel() {
  bus.emit('cancel-loading');
}

onMounted(() => {
  bus.on('global-loading', onGlobalLoading);
});

onBeforeUnmount(() => {
  bus.off('global-loading', onGlobalLoading);
});
</script>

<style scoped>
.loading-overlay {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(0, 0, 0, 0.6); /* 半透明遮罩 */
  backdrop-filter: blur(4px);     /* 磨砂效果 */
  z-index: 1000;                  /* 确保在面板内容之上 */
  display: flex;
  justify-content: center;
  align-items: center;
  border-radius: inherit;         /* 跟随父容器圆角 */
}

.loading-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  color: var(--spark-text);
}

.spinner-svg {
  width: 80px;
  height: 80px;
  margin-bottom: 16px;
}

.loading-text {
  font-size: 1.1rem;
  letter-spacing: 1px;
  font-family: var(--spark-font);
  margin-bottom: 20px;
  text-shadow: 0 2px 4px rgba(0,0,0,0.5);
}

.cancel-btn {
  opacity: 0.8;
  transition: opacity 0.3s;
}
.cancel-btn:hover {
  opacity: 1;
}

.fade-enter-active, .fade-leave-active {
  transition: opacity 0.3s ease;
}
.fade-enter-from, .fade-leave-to {
  opacity: 0;
}
</style>