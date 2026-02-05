<template>
  <transition name="fade">
    <div v-if="visible" class="tool-loading-overlay">
      <!-- 简化版粒子效果 -->
      <div class="particle-field">
        <div v-for="i in 8" :key="'p'+i" class="floating-particle" :style="getParticleStyle(i)"></div>
      </div>
      
      <div class="loading-content">
        <div class="spark-loader">
          <!-- 脉冲涟漪 -->
          <div class="pulse-rings">
            <div class="pulse-ring ring-1"></div>
            <div class="pulse-ring ring-2"></div>
          </div>
          
          <svg class="spark-svg" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
            <defs>
              <filter id="tool-glow" x="-50%" y="-50%" width="200%" height="200%">
                <feGaussianBlur stdDeviation="2" result="coloredBlur"/>
                <feMerge>
                  <feMergeNode in="coloredBlur"/>
                  <feMergeNode in="SourceGraphic"/>
                </feMerge>
              </filter>
              <radialGradient id="toolCoreGradient" cx="50%" cy="50%" r="50%">
                <stop offset="0%" style="stop-color: var(--loader-primary); stop-opacity: 1" />
                <stop offset="100%" style="stop-color: var(--loader-primary); stop-opacity: 0.6" />
              </radialGradient>
            </defs>
            
            <!-- 核心：四角星 -->
            <g class="core-star-group">
              <path class="core-star" d="M50 25 L56 44 L75 50 L56 56 L50 75 L44 56 L25 50 L44 44 Z" fill="url(#toolCoreGradient)" filter="url(#tool-glow)" />
              <circle cx="50" cy="50" r="3" class="core-center" />
            </g>

            <!-- 轨道 -->
            <circle cx="50" cy="50" r="38" class="orbit-solid" />
            
            <!-- 环绕卫星 -->
            <g class="satellite-group">
              <circle cx="50" cy="12" r="4" class="satellite" filter="url(#tool-glow)" />
            </g>
          </svg>
        </div>
        
        <div class="loading-text">{{ text }}</div>
        <div v-if="toolName" class="tool-name">工具: {{ toolName }}</div>
      </div>
    </div>
  </transition>
</template>

<script setup>
import { ref, computed } from 'vue';

const props = defineProps({
  visible: { type: Boolean, default: false },
  text: { type: String, default: '正在执行工具...' },
  toolName: { type: String, default: '' }
});

function getParticleStyle(index) {
  const size = 2 + Math.random() * 3;
  const left = Math.random() * 100;
  const top = Math.random() * 100;
  const delay = Math.random() * 5;
  const duration = 4 + Math.random() * 4;
  const opacity = 0.2 + Math.random() * 0.3;
  
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
</script>

<style scoped>
.tool-loading-overlay {
  --loader-primary: var(--spark-primary);
  --loader-orbit-1: var(--spark-harmonious-a);
  --loader-bg: color-mix(in srgb, var(--spark-bg), transparent 8%);
  --loader-text: var(--spark-text);
  --loader-particle: var(--spark-primary);
  
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  background: var(--loader-bg);
  pointer-events: none;
  backdrop-filter: blur(8px);
  z-index: 50;
  display: flex;
  justify-content: center;
  align-items: center;
  border-radius: inherit;
  overflow: hidden;
}

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
    transform: translateY(-60px) translateX(15px) scale(0.5);
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

.spark-loader {
  position: relative;
  width: 80px;
  height: 80px;
  margin-bottom: 16px;
}

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
  animation: pulse-expand 2.5s ease-out infinite;
}

.pulse-ring.ring-1 { animation-delay: 0s; }
.pulse-ring.ring-2 { animation-delay: 1.25s; }

@keyframes pulse-expand {
  0% {
    width: 20px;
    height: 20px;
    opacity: 0.5;
  }
  100% {
    width: 100px;
    height: 100px;
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

.core-star-group {
  transform-origin: 50px 50px;
  animation: pulse-rotate 5s ease-in-out infinite;
}

.core-star {
  fill: var(--loader-primary);
  opacity: 0.9;
}

.core-center {
  fill: var(--spark-text-inverse);
  opacity: 0.95;
}

.orbit-solid {
  fill: none;
  stroke: var(--loader-orbit-1);
  stroke-width: 1.2;
  opacity: 0.6;
  filter: drop-shadow(0 0 2px var(--loader-orbit-1));
}

.satellite-group {
  transform-origin: 50px 50px;
  animation: spin 8s linear infinite;
}

.satellite {
  fill: var(--loader-orbit-1);
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

@keyframes pulse-rotate {
  0% { transform: scale(0.9) rotate(0deg); opacity: 0.8; }
  50% { transform: scale(1.1) rotate(180deg); opacity: 1; }
  100% { transform: scale(0.9) rotate(360deg); opacity: 0.8; }
}

.loading-text {
  font-size: 0.9rem;
  font-weight: 500;
  letter-spacing: 0.5px;
  font-family: var(--spark-font);
  margin-bottom: 4px;
  color: var(--loader-text);
  opacity: 0.9;
}

.tool-name {
  font-size: 0.75rem;
  color: var(--loader-text);
  opacity: 0.5;
  font-family: var(--spark-mono);
}

.fade-enter-active, .fade-leave-active {
  transition: opacity 0.3s ease;
}
.fade-enter-from, .fade-leave-to {
  opacity: 0;
}
</style>
