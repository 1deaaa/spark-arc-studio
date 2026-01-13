<template>
  <transition name="fade">
    <div v-if="visible" class="loading-overlay">
      <!-- 背景漂浮粒子层 -->
      <div class="particle-field">
        <div v-for="i in 20" :key="'p'+i" class="floating-particle" :style="getParticleStyle(i)"></div>
      </div>
      
      <div class="loading-content">
        <div class="spark-loader">
          <!-- 脉冲涟漪效果 -->
          <div class="pulse-rings">
            <div class="pulse-ring ring-1"></div>
            <div class="pulse-ring ring-2"></div>
            <div class="pulse-ring ring-3"></div>
          </div>
          
          <svg class="spark-svg" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
            <defs>
              <!-- 发光滤镜 -->
              <filter id="glow" x="-50%" y="-50%" width="200%" height="200%">
                <feGaussianBlur stdDeviation="2" result="coloredBlur"/>
                <feMerge>
                  <feMergeNode in="coloredBlur"/>
                  <feMergeNode in="SourceGraphic"/>
                </feMerge>
              </filter>
              <!-- 强发光滤镜 -->
              <filter id="strongGlow" x="-100%" y="-100%" width="300%" height="300%">
                <feGaussianBlur stdDeviation="3" result="coloredBlur"/>
                <feMerge>
                  <feMergeNode in="coloredBlur"/>
                  <feMergeNode in="coloredBlur"/>
                  <feMergeNode in="SourceGraphic"/>
                </feMerge>
              </filter>
              <!-- 渐变定义 -->
              <radialGradient id="coreGradient" cx="50%" cy="50%" r="50%">
                <stop offset="0%" style="stop-color: var(--loader-primary); stop-opacity: 1" />
                <stop offset="100%" style="stop-color: var(--loader-primary); stop-opacity: 0.6" />
              </radialGradient>
            </defs>
            
            <!-- 能量流粒子 - 外圈 -->
            <g class="energy-particles outer-particles">
              <circle cx="96" cy="50" r="1.5" class="energy-dot e1" filter="url(#glow)" />
              <circle cx="4" cy="50" r="1.2" class="energy-dot e2" filter="url(#glow)" />
              <circle cx="50" cy="96" r="1.3" class="energy-dot e3" filter="url(#glow)" />
              <circle cx="50" cy="4" r="1" class="energy-dot e4" filter="url(#glow)" />
              <circle cx="82" cy="82" r="1.1" class="energy-dot e5" filter="url(#glow)" />
              <circle cx="18" cy="18" r="1.4" class="energy-dot e6" filter="url(#glow)" />
            </g>
            
            <!-- 能量流粒子 - 内圈 -->
            <g class="energy-particles inner-particles">
              <circle cx="88" cy="50" r="1.2" class="energy-dot e7" filter="url(#glow)" />
              <circle cx="12" cy="50" r="1" class="energy-dot e8" filter="url(#glow)" />
              <circle cx="50" cy="88" r="1.1" class="energy-dot e9" filter="url(#glow)" />
              <circle cx="50" cy="12" r="1.3" class="energy-dot e10" filter="url(#glow)" />
            </g>
            
            <!-- 核心：四角星 -->
            <g class="core-star-group">
              <path class="core-star" d="M50 20 L58 42 L80 50 L58 58 L50 80 L42 58 L20 50 L42 42 Z" fill="url(#coreGradient)" filter="url(#strongGlow)" />
              <circle cx="50" cy="50" r="4" class="core-center" />
              <!-- 中心光晕 -->
              <circle cx="50" cy="50" r="8" class="core-halo" />
            </g>

            <!-- 内圈：虚线轨道 -->
            <circle cx="50" cy="50" r="32" class="orbit-dashed" />

            <!-- 外圈：双重行星轨道 -->
            <circle cx="50" cy="50" r="46" class="orbit-solid outer" />
            <circle cx="50" cy="50" r="38" class="orbit-solid inner" />

            <!-- 环绕卫星 -->
            <g class="satellite-group">
              <!-- 卫星尾迹 -->
              <g class="satellite-trail t1">
                <circle cx="50" cy="8" r="2" class="trail-dot td1" />
                <circle cx="50" cy="12" r="1.5" class="trail-dot td2" />
                <circle cx="50" cy="16" r="1" class="trail-dot td3" />
              </g>
              <circle cx="50" cy="4" r="5" class="satellite s1" filter="url(#strongGlow)" />
              
              <!-- 第二卫星尾迹 -->
              <g class="satellite-trail t2">
                <circle cx="50" cy="84" r="1.5" class="trail-dot td1" />
                <circle cx="50" cy="80" r="1" class="trail-dot td2" />
                <circle cx="50" cy="76" r="0.7" class="trail-dot td3" />
              </g>
              <circle cx="50" cy="88" r="4" class="satellite s2" filter="url(#glow)" />
            </g>

            <!-- 背景星尘 - 增强版 -->
            <g class="stardust-group">
              <path d="M20 20 L22 22 M80 80 L82 82 M20 80 L22 78 M80 20 L78 22" class="stardust" />
              <circle cx="15" cy="50" r="1" class="dust d1" />
              <circle cx="85" cy="50" r="1" class="dust d2" />
              <circle cx="50" cy="15" r="1" class="dust d3" />
              <circle cx="50" cy="85" r="1" class="dust d4" />
              <!-- 额外闪烁星点 -->
              <circle cx="25" cy="30" r="0.8" class="sparkle sp1" filter="url(#glow)" />
              <circle cx="75" cy="25" r="0.6" class="sparkle sp2" filter="url(#glow)" />
              <circle cx="70" cy="70" r="0.7" class="sparkle sp3" filter="url(#glow)" />
              <circle cx="30" cy="75" r="0.9" class="sparkle sp4" filter="url(#glow)" />
              <circle cx="35" cy="45" r="0.5" class="sparkle sp5" filter="url(#glow)" />
              <circle cx="65" cy="55" r="0.6" class="sparkle sp6" filter="url(#glow)" />
            </g>
            
            <!-- 光芒射线 -->
            <g class="ray-group">
              <line x1="50" y1="50" x2="50" y2="15" class="ray r1" />
              <line x1="50" y1="50" x2="85" y2="50" class="ray r2" />
              <line x1="50" y1="50" x2="50" y2="85" class="ray r3" />
              <line x1="50" y1="50" x2="15" y2="50" class="ray r4" />
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
import { ref, computed, onMounted, onBeforeUnmount } from 'vue';
import { NButton } from 'naive-ui';
import bus from '@/eventBus';

const visible = ref(false);

// 生成随机粒子样式
function getParticleStyle(index) {
  const size = 2 + Math.random() * 4;
  const left = Math.random() * 100;
  const top = Math.random() * 100;
  const delay = Math.random() * 8;
  const duration = 6 + Math.random() * 8;
  const opacity = 0.2 + Math.random() * 0.4;
  
  return {
    width: `${size}px`,
    height: `${size}px`,
    left: `${left}%`,
    top: `${top}%`,
    animationDelay: `${delay}s`,
    animationDuration: `${duration}s`,
    '--particle-opacity': opacity
  };
}
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
  --loader-primary: var(--spark-primary);
  /* 使用新的和谐色变体 (Harmonious Colors) */
  --loader-orbit-1: var(--spark-harmonious-a);
  --loader-orbit-2: var(--spark-harmonious-b);
  --loader-bg: color-mix(in srgb, var(--spark-bg), transparent 8%);
  --loader-text: var(--spark-text);
  --loader-particle: var(--spark-primary);
}

/* 亮色模式适配 */
:root[data-theme="light"] .loading-overlay,
.light .loading-overlay {
  --loader-bg: color-mix(in srgb, var(--spark-bg), transparent 5%);
  --loader-text: var(--spark-text);
  /* 亮色模式下使用稍深的变体以保证可见度 */
  --loader-orbit-1: var(--spark-harmonious-a);
  --loader-orbit-2: var(--spark-harmonious-b);
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
  overflow: hidden;
}

/* 背景漂浮粒子层 */
.particle-field {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
  overflow: hidden;
}

.floating-particle {
  position: absolute;
  background: radial-gradient(circle, var(--loader-particle) 0%, transparent 70%);
  border-radius: 50%;
  opacity: var(--particle-opacity, 0.3);
  animation: float-particle linear infinite;
}

@keyframes float-particle {
  0% {
    transform: translateY(0) translateX(0) scale(1);
    opacity: 0;
  }
  10% {
    opacity: var(--particle-opacity, 0.3);
  }
  90% {
    opacity: var(--particle-opacity, 0.3);
  }
  100% {
    transform: translateY(-100px) translateX(20px) scale(0.5);
    opacity: 0;
  }
}

.loading-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  color: var(--loader-text);
  position: relative;
  z-index: 1;
}

/* 创意加载器容器 */
.spark-loader {
  position: relative;
  width: 120px;
  height: 120px;
  margin-bottom: 32px;
}

/* 脉冲涟漪效果 */
.pulse-rings {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 100%;
  height: 100%;
  pointer-events: none;
}

.pulse-ring {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  border: 1px solid var(--loader-primary);
  border-radius: 50%;
  opacity: 0;
  animation: pulse-expand 3s ease-out infinite;
}

.pulse-ring.ring-1 {
  animation-delay: 0s;
}

.pulse-ring.ring-2 {
  animation-delay: 1s;
}

.pulse-ring.ring-3 {
  animation-delay: 2s;
}

@keyframes pulse-expand {
  0% {
    width: 30px;
    height: 30px;
    opacity: 0.6;
  }
  100% {
    width: 160px;
    height: 160px;
    opacity: 0;
  }
}

.spark-svg {
  width: 100%;
  height: 100%;
  overflow: visible;
  position: relative;
  z-index: 2;
}

/* 核心星星 */
.core-star-group {
  transform-origin: 50px 50px;
  animation: pulse-rotate 6s ease-in-out infinite;
}

.core-star {
  fill: var(--loader-primary);
  opacity: 0.9;
}

.core-center {
  fill: var(--spark-text-inverse);
  opacity: 0.95;
}

.core-halo {
  fill: var(--loader-primary);
  opacity: 0;
  animation: halo-pulse 2s ease-in-out infinite;
}

@keyframes halo-pulse {
  0%, 100% {
    opacity: 0;
    r: 6;
  }
  50% {
    opacity: 0.3;
    r: 12;
  }
}

/* 能量流粒子 */
.energy-particles {
  transform-origin: 50px 50px;
}

.outer-particles {
  animation: spin 15s linear infinite;
}

.inner-particles {
  animation: spin-rev 12s linear infinite;
}

.energy-dot {
  fill: var(--loader-orbit-1);
  opacity: 0;
  animation: energy-flow 2s ease-in-out infinite;
}

.energy-dot.e1 { animation-delay: 0s; }
.energy-dot.e2 { animation-delay: 0.3s; }
.energy-dot.e3 { animation-delay: 0.6s; }
.energy-dot.e4 { animation-delay: 0.9s; }
.energy-dot.e5 { animation-delay: 1.2s; }
.energy-dot.e6 { animation-delay: 1.5s; }
.energy-dot.e7 { animation-delay: 0.15s; }
.energy-dot.e8 { animation-delay: 0.45s; }
.energy-dot.e9 { animation-delay: 0.75s; }
.energy-dot.e10 { animation-delay: 1.05s; }

@keyframes energy-flow {
  0%, 100% {
    opacity: 0;
    transform: scale(0.5);
  }
  50% {
    opacity: 0.8;
    transform: scale(1.2);
  }
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
  stroke-width: 1.2;
  opacity: 0.8;
}

.orbit-solid.outer {
  stroke: var(--loader-orbit-1);
  filter: drop-shadow(0 0 3px var(--loader-orbit-1));
}

.orbit-solid.inner {
  stroke: var(--loader-orbit-1);
  opacity: 0.4;
  stroke-dasharray: 4 8;
}

/* 卫星 */
.satellite-group {
  transform-origin: 50px 50px;
  animation: spin 10s linear infinite;
}

.satellite {
  fill: var(--loader-orbit-2);
}

.satellite.s1 {
  opacity: 1;
}

.satellite.s2 {
  opacity: 0.8;
}

/* 卫星尾迹 */
.satellite-trail {
  opacity: 1;
}

.trail-dot {
  fill: var(--loader-orbit-2);
}

.satellite-trail.t1 .td1 { opacity: 0.5; animation: trail-fade 10s linear infinite; }
.satellite-trail.t1 .td2 { opacity: 0.3; animation: trail-fade 10s linear infinite 0.1s; }
.satellite-trail.t1 .td3 { opacity: 0.15; animation: trail-fade 10s linear infinite 0.2s; }

.satellite-trail.t2 .td1 { opacity: 0.4; animation: trail-fade 10s linear infinite; }
.satellite-trail.t2 .td2 { opacity: 0.25; animation: trail-fade 10s linear infinite 0.1s; }
.satellite-trail.t2 .td3 { opacity: 0.1; animation: trail-fade 10s linear infinite 0.2s; }

@keyframes trail-fade {
  0%, 100% {
    opacity: var(--base-opacity, 0.3);
  }
  50% {
    opacity: calc(var(--base-opacity, 0.3) * 1.5);
  }
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

/* 闪烁星点 */
.sparkle {
  fill: var(--loader-orbit-1);
  opacity: 0;
}

.sparkle.sp1 { animation: sparkle-burst 2.5s ease-in-out infinite 0s; }
.sparkle.sp2 { animation: sparkle-burst 2.8s ease-in-out infinite 0.4s; }
.sparkle.sp3 { animation: sparkle-burst 2.3s ease-in-out infinite 0.8s; }
.sparkle.sp4 { animation: sparkle-burst 2.6s ease-in-out infinite 1.2s; }
.sparkle.sp5 { animation: sparkle-burst 2.4s ease-in-out infinite 1.6s; }
.sparkle.sp6 { animation: sparkle-burst 2.7s ease-in-out infinite 2s; }

@keyframes sparkle-burst {
  0%, 100% {
    opacity: 0;
    transform: scale(0.5);
  }
  50% {
    opacity: 0.9;
    transform: scale(1.5);
  }
}

/* 光芒射线 */
.ray-group {
  transform-origin: 50px 50px;
  animation: ray-rotate 8s linear infinite;
}

.ray {
  stroke: var(--loader-primary);
  stroke-width: 0.5;
  stroke-linecap: round;
  opacity: 0;
  animation: ray-pulse 2s ease-in-out infinite;
}

.ray.r1 { animation-delay: 0s; }
.ray.r2 { animation-delay: 0.5s; }
.ray.r3 { animation-delay: 1s; }
.ray.r4 { animation-delay: 1.5s; }

@keyframes ray-rotate {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

@keyframes ray-pulse {
  0%, 100% {
    opacity: 0;
    stroke-dasharray: 0 35;
    stroke-dashoffset: 0;
  }
  50% {
    opacity: 0.4;
    stroke-dasharray: 15 20;
    stroke-dashoffset: -10;
  }
}

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
  margin-top: 16px;
  opacity: 1;
  transition: all 0.3s ease;
  /* 使用半透明背景增强对比度 */
  background: color-mix(in srgb, var(--loader-text), transparent 90%);
  border: 1px solid var(--loader-text);
  color: var(--loader-text);
  padding: 8px 20px;
  height: auto;
}

.cancel-btn:hover {
  background: var(--loader-text);
  color: var(--loader-bg);
  transform: translateY(-2px);
  box-shadow: 0 4px 12px color-mix(in srgb, black, transparent 70%);
}

/* 淡入淡出 */
.fade-enter-active, .fade-leave-active {
  transition: opacity 0.4s ease;
}
.fade-enter-from, .fade-leave-to {
  opacity: 0;
}
</style>