<template>
  <transition name="fade">
    <div v-if="visible" class="loading-overlay">
      <div class="loading-content">
        <!-- 华丽的灵感/创作主题 SVG 动画 -->
        <div class="creative-loader">
          <!-- 背景光晕 -->
          <div class="glow-ring"></div>
          <div class="glow-ring delay-1"></div>
          <div class="glow-ring delay-2"></div>
          
          <svg class="creative-svg" viewBox="0 0 120 120" xmlns="http://www.w3.org/2000/svg">
            <defs>
              <!-- 渐变定义 -->
              <linearGradient id="sparkGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stop-color="var(--loader-primary)" />
                <stop offset="50%" stop-color="var(--loader-accent)" />
                <stop offset="100%" stop-color="var(--loader-secondary)" />
              </linearGradient>
              <linearGradient id="trailGrad" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" stop-color="var(--loader-primary)" stop-opacity="0" />
                <stop offset="50%" stop-color="var(--loader-accent)" stop-opacity="0.8" />
                <stop offset="100%" stop-color="var(--loader-secondary)" stop-opacity="1" />
              </linearGradient>
              <filter id="glowFilter" x="-50%" y="-50%" width="200%" height="200%">
                <feGaussianBlur stdDeviation="3" result="blur"/>
                <feMerge>
                  <feMergeNode in="blur"/>
                  <feMergeNode in="blur"/>
                  <feMergeNode in="SourceGraphic"/>
                </feMerge>
              </filter>
            </defs>
            
            <!-- 外圈：星轨 -->
            <circle cx="60" cy="60" r="50" class="orbit-ring" />
            
            <!-- 旋转的灵感火花轨迹 -->
            <g class="spark-trail">
              <path d="M60 10 A50 50 0 0 1 110 60" 
                    stroke="url(#trailGrad)" 
                    stroke-width="3" 
                    fill="none" 
                    stroke-linecap="round"
                    filter="url(#glowFilter)" />
            </g>
            
            <!-- 反向内圈轨迹 -->
            <g class="inner-trail">
              <path d="M60 25 A35 35 0 0 0 25 60" 
                    stroke="url(#trailGrad)" 
                    stroke-width="2" 
                    fill="none" 
                    stroke-linecap="round"
                    opacity="0.7" />
            </g>
            
            <!-- 中心：灵感之核 -->
            <g class="core-group">
              <!-- 呼吸光环 -->
              <circle cx="60" cy="60" r="12" class="core-glow" />
              <!-- 实心核心 -->
              <circle cx="60" cy="60" r="6" class="core-solid" />
            </g>
            
            <!-- 漂浮的灵感粒子 -->
            <g class="particles">
              <circle cx="60" cy="18" r="2.5" class="particle p1" />
              <circle cx="95" cy="45" r="2" class="particle p2" />
              <circle cx="85" cy="90" r="1.5" class="particle p3" />
              <circle cx="35" cy="85" r="2" class="particle p4" />
              <circle cx="25" cy="40" r="1.5" class="particle p5" />
            </g>
            
            <!-- 星星闪烁 -->
            <g class="stars">
              <polygon points="60,5 61,8 64,8 62,10 63,13 60,11 57,13 58,10 56,8 59,8" class="star s1" />
              <polygon points="105,60 106,62 108,62 107,64 108,66 105,65 102,66 103,64 102,62 104,62" class="star s2" />
              <polygon points="60,105 61,107 63,107 62,109 63,111 60,110 57,111 58,109 57,107 59,107" class="star s3" />
            </g>
          </svg>
        </div>
        
        <div class="loading-text">{{ text }}</div>
        
        <!-- 进度指示（可选） -->
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
  --loader-primary: var(--spark-primary, #f0b429);
  --loader-secondary: var(--spark-secondary, #ff6b6b);
  --loader-accent: #a78bfa;
  --loader-bg: rgba(13, 17, 23, 0.85);
  --loader-text: var(--spark-text, #e6edf3);
}

/* 亮色模式适配 */
:root[data-theme="light"] .loading-overlay,
.light .loading-overlay {
  --loader-bg: rgba(255, 255, 255, 0.9);
  --loader-text: #24292f;
}

.loading-overlay {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: var(--loader-bg);
  backdrop-filter: blur(8px);
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
.creative-loader {
  position: relative;
  width: 140px;
  height: 140px;
  margin-bottom: 24px;
}

/* 背景光晕 */
.glow-ring {
  position: absolute;
  top: 50%;
  left: 50%;
  width: 100px;
  height: 100px;
  margin: -50px 0 0 -50px;
  border-radius: 50%;
  background: radial-gradient(circle, var(--loader-primary) 0%, transparent 70%);
  opacity: 0.3;
  animation: pulse 3s ease-in-out infinite;
}

.glow-ring.delay-1 {
  width: 120px;
  height: 120px;
  margin: -60px 0 0 -60px;
  background: radial-gradient(circle, var(--loader-accent) 0%, transparent 70%);
  opacity: 0.2;
  animation-delay: 1s;
}

.glow-ring.delay-2 {
  width: 140px;
  height: 140px;
  margin: -70px 0 0 -70px;
  background: radial-gradient(circle, var(--loader-secondary) 0%, transparent 70%);
  opacity: 0.15;
  animation-delay: 2s;
}

@keyframes pulse {
  0%, 100% { transform: scale(1); opacity: 0.3; }
  50% { transform: scale(1.1); opacity: 0.5; }
}

/* SVG 动画 */
.creative-svg {
  width: 100%;
  height: 100%;
  position: relative;
  z-index: 1;
}

/* 轨道环 */
.orbit-ring {
  fill: none;
  stroke: var(--loader-text);
  stroke-width: 0.5;
  opacity: 0.15;
}

/* 火花轨迹旋转 */
.spark-trail {
  transform-origin: 60px 60px;
  animation: spinClockwise 2.5s linear infinite;
}

.inner-trail {
  transform-origin: 60px 60px;
  animation: spinCounterClockwise 3.5s linear infinite;
}

@keyframes spinClockwise {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

@keyframes spinCounterClockwise {
  from { transform: rotate(360deg); }
  to { transform: rotate(0deg); }
}

/* 核心呼吸效果 */
.core-glow {
  fill: var(--loader-primary);
  opacity: 0.3;
  animation: coreBreath 2s ease-in-out infinite;
}

.core-solid {
  fill: var(--loader-primary);
  filter: url(#glowFilter);
}

@keyframes coreBreath {
  0%, 100% { r: 12; opacity: 0.3; }
  50% { r: 16; opacity: 0.5; }
}

/* 粒子动画 */
.particle {
  fill: var(--loader-accent);
  filter: url(#glowFilter);
}

.particles {
  transform-origin: 60px 60px;
  animation: spinClockwise 8s linear infinite;
}

.particle.p1 { animation: twinkle 1.5s ease-in-out infinite; }
.particle.p2 { animation: twinkle 1.8s ease-in-out infinite 0.3s; }
.particle.p3 { animation: twinkle 1.6s ease-in-out infinite 0.6s; }
.particle.p4 { animation: twinkle 2s ease-in-out infinite 0.9s; }
.particle.p5 { animation: twinkle 1.7s ease-in-out infinite 1.2s; }

@keyframes twinkle {
  0%, 100% { opacity: 0.4; r: 1.5; }
  50% { opacity: 1; r: 3; }
}

/* 星星闪烁 */
.star {
  fill: var(--loader-secondary);
  opacity: 0;
  animation: starFlash 3s ease-in-out infinite;
}

.star.s1 { animation-delay: 0s; }
.star.s2 { animation-delay: 1s; }
.star.s3 { animation-delay: 2s; }

@keyframes starFlash {
  0%, 40%, 100% { opacity: 0; transform: scale(0.5); }
  20% { opacity: 1; transform: scale(1.2); }
  30% { opacity: 0.8; transform: scale(1); }
}

/* 文字样式 */
.loading-text {
  font-size: 1.15rem;
  font-weight: 500;
  letter-spacing: 2px;
  font-family: var(--spark-font);
  margin-bottom: 8px;
  background: linear-gradient(90deg, var(--loader-primary), var(--loader-accent), var(--loader-secondary));
  background-size: 200% auto;
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  animation: shimmerText 3s linear infinite;
}

@keyframes shimmerText {
  0% { background-position: 0% center; }
  100% { background-position: 200% center; }
}

.progress-info {
  font-size: 0.9rem;
  color: var(--loader-text);
  opacity: 0.7;
  margin-bottom: 16px;
}

.cancel-btn {
  margin-top: 12px;
  opacity: 0.85;
  transition: all 0.3s ease;
  border-color: var(--loader-text);
  color: var(--loader-text);
}

.cancel-btn:hover {
  opacity: 1;
  background: rgba(255, 255, 255, 0.1);
}

/* 淡入淡出 */
.fade-enter-active, .fade-leave-active {
  transition: opacity 0.4s ease;
}
.fade-enter-from, .fade-leave-to {
  opacity: 0;
}
</style>