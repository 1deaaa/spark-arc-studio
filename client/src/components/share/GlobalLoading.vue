<template>
  <transition name="fade">
    <div v-if="visible" class="loading-overlay" :class="overlayClass">
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
const props = defineProps({
  scope: { type: String, default: '' },
  active: { type: Boolean, default: true },
  target: { type: String, default: '' },
  variant: { type: String, default: 'full' }
});

const overlayClass = computed(() => ({
  'loading-overlay--card': props.variant === 'card',
}));

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
  if (!props.active) return;
  if (typeof p === 'boolean') {
    visible.value = p;
    text.value = '';
    progress.value = '';
    canCancel.value = false;
  } else {
    if (props.scope && p?.scope && p.scope !== props.scope) return;
    const payloadTarget = (p?.target || '').toString().trim();
    const localTarget = (props.target || '').toString().trim();

    if (payloadTarget) {
      if (!localTarget || payloadTarget !== localTarget) return;
    } else if (localTarget && p?.show) {
      return;
    }

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

<style scoped src="./GlobalLoading.scoped.css"></style>