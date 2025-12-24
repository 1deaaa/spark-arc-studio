<template>
  <transition name="fade">
    <div v-if="visible" class="loading-overlay">
      <div class="loading-content">
        <div class="spark-loader">
          <svg class="spark-svg" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
            <!-- 核心：四角星 -->
            <g class="core-star-group">
              <path class="core-star" d="M50 20 L58 42 L80 50 L58 58 L50 80 L42 58 L20 50 L42 42 Z" />
              <circle cx="50" cy="50" r="4" class="core-center" />
            </g>

            <!-- 内圈：虚线轨道 -->
            <circle cx="50" cy="50" r="32" class="orbit-dashed" />

            <!-- 外圈：行星轨道 -->
            <circle cx="50" cy="50" r="46" class="orbit-solid" />

            <!-- 环绕卫星 -->
            <g class="satellite-group">
              <circle cx="50" cy="4" r="3" class="satellite s1" />
              <circle cx="50" cy="96" r="2" class="satellite s2" />
            </g>

            <!-- 背景星尘 -->
            <g class="stardust-group">
              <path d="M20 20 L22 22 M80 80 L82 82 M20 80 L22 78 M80 20 L78 22" class="stardust" />
              <circle cx="15" cy="50" r="1" class="dust d1" />
              <circle cx="85" cy="50" r="1" class="dust d2" />
              <circle cx="50" cy="15" r="1" class="dust d3" />
              <circle cx="50" cy="85" r="1" class="dust d4" />
            </g>
          </svg>
        </div>
        
        <div class="loading-text">{{ text }}</div>
        
        <div v-if="progress" class="progress-info">{{ progress }}</div>
        
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
const progress = ref('');
const canCancel = ref(false);

function onGlobalLoading(p) {
  if (typeof p === 'boolean') {
    visible.value = p;
    text.value = '';
    progress.value = '';
    canCancel.value = false;
  } else {
    visible.value = !!p?.show;
    text.value = p?.text || '正在创作中...';
    progress.value = p?.progress || '';
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
/* 动态颜色变量，适配亮暗模式 */
.loading-overlay {
  --loader-primary: var(--spark-primary, #7aa2f7);
  /* 使用主题中定义的和谐色 (Harmony)，用于外圈和装饰 */
  --loader-subtle: var(--spark-harmony, var(--spark-primary-light)); 
  --loader-bg: rgba(9, 11, 16, 0.92);
  --loader-text: var(--spark-text, #eef2f6);
}

/* 亮色模式适配 */
:root[data-theme="light"] .loading-overlay,
.light .loading-overlay {
  --loader-bg: rgba(255, 255, 255, 0.95);
  --loader-text: #24292f;
  /* 亮色模式下使用稍深的变体以保证可见度 */
  --loader-subtle: var(--spark-primary-dim);
}

.loading-overlay {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: var(--loader-bg);
  backdrop-filter: blur(12px);
  z-index: 1000;
  display: flex;
  justify-content: center;
  align-items: center;
  border-radius: inherit;
}

.loading-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  color: var(--loader-text);
}

/* 创意加载器容器 */
.spark-loader {
  position: relative;
  width: 120px;
  height: 120px;
  margin-bottom: 32px;
}

.spark-svg {
  width: 100%;
  height: 100%;
  overflow: visible;
}

/* 核心星星 */
.core-star-group {
  transform-origin: 50px 50px;
  animation: pulse-rotate 6s ease-in-out infinite;
}

.core-star {
  fill: var(--loader-primary);
  opacity: 0.8;
  filter: drop-shadow(0 0 8px color-mix(in srgb, var(--loader-primary), transparent 40%));
}

.core-center {
  fill: #fff;
  opacity: 0.9;
}

/* 轨道 */
.orbit-dashed {
  fill: none;
  stroke: var(--loader-text);
  stroke-width: 1;
  stroke-dasharray: 2 4;
  opacity: 0.2;
  transform-origin: 50px 50px;
  animation: spin-rev 20s linear infinite;
}

.orbit-solid {
  fill: none;
  stroke: var(--loader-subtle);
  stroke-width: 0.5;
  opacity: 0.6;
}

/* 卫星 */
.satellite-group {
  transform-origin: 50px 50px;
  animation: spin 10s linear infinite;
}

.satellite {
  fill: var(--loader-subtle);
}

.satellite.s1 {
  filter: drop-shadow(0 0 4px var(--loader-subtle));
}

.satellite.s2 {
  opacity: 0.6;
}

/* 星尘 */
.stardust-group {
  transform-origin: 50px 50px;
}

.stardust {
  stroke: var(--loader-text);
  stroke-width: 1.5;
  stroke-linecap: round;
  opacity: 0.3;
  animation: twinkle 3s ease-in-out infinite;
}

.dust {
  fill: var(--loader-text);
  opacity: 0;
}

.dust.d1 { animation: twinkle 4s ease-in-out infinite 0s; }
.dust.d2 { animation: twinkle 4s ease-in-out infinite 1s; }
.dust.d3 { animation: twinkle 4s ease-in-out infinite 2s; }
.dust.d4 { animation: twinkle 4s ease-in-out infinite 3s; }

/* 动画定义 */
@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

@keyframes spin-rev {
  from { transform: rotate(360deg); }
  to { transform: rotate(0deg); }
}

@keyframes pulse-rotate {
  0% { transform: scale(0.9) rotate(0deg); opacity: 0.8; }
  50% { transform: scale(1.1) rotate(180deg); opacity: 1; }
  100% { transform: scale(0.9) rotate(360deg); opacity: 0.8; }
}

@keyframes twinkle {
  0%, 100% { opacity: 0.1; transform: scale(0.8); }
  50% { opacity: 0.6; transform: scale(1.2); }
}

/* 文字样式 */
.loading-text {
  font-size: 1rem;
  font-weight: 500;
  letter-spacing: 1px;
  font-family: var(--spark-font);
  margin-bottom: 8px;
  color: var(--loader-text);
  opacity: 0.9;
}

.progress-info {
  font-size: 0.85rem;
  color: var(--loader-text);
  opacity: 0.6;
  margin-bottom: 16px;
  font-family: var(--spark-mono);
}

.cancel-btn {
  margin-top: 8px;
  opacity: 0.7;
  transition: all 0.3s ease;
}

.cancel-btn:hover {
  opacity: 1;
}

/* 淡入淡出 */
.fade-enter-active, .fade-leave-active {
  transition: opacity 0.4s ease;
}
.fade-enter-from, .fade-leave-to {
  opacity: 0;
}
</style>