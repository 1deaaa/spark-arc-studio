<!-- 
  全局加载遮罩 —— 「灵感星河」主题
  视觉叙事：灵感之心呼吸律动，思绪沿弧光轨道汇聚流转，创作火花从中心绽放
  在长时间加载的情景中应该使用此组件覆盖部分面板，防止用户误操作
-->
<template>
  <transition name="fade">
    <div v-if="visible" class="loading-overlay" :class="overlayClass">
      <!-- 背景漂浮粒子层：缓慢上升的灵感微光 -->
      <div class="particle-field">
        <div v-for="i in 12" :key="'p'+i" class="floating-particle" :style="particlesStyles[i-1]"></div>
      </div>
      
      <div class="loading-content">
        <div class="spark-loader">
          <!-- 脉冲涟漪：灵感之心的心跳 -->
          <div class="pulse-rings">
            <div class="pulse-ring ring-1"></div>
            <div class="pulse-ring ring-2"></div>
            <div class="pulse-ring ring-3"></div>
          </div>
          
          <svg class="spark-svg" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
            <defs>
              <!-- 柔和辉光 -->
              <filter id="gl-glow" x="-50%" y="-50%" width="200%" height="200%">
                <feGaussianBlur stdDeviation="2" result="coloredBlur"/>
                <feMerge>
                  <feMergeNode in="coloredBlur"/>
                  <feMergeNode in="SourceGraphic"/>
                </feMerge>
              </filter>
              <!-- 核心强辉光 -->
              <filter id="gl-glow-core" x="-100%" y="-100%" width="300%" height="300%">
                <feGaussianBlur stdDeviation="3" result="coloredBlur"/>
                <feMerge>
                  <feMergeNode in="coloredBlur"/>
                  <feMergeNode in="coloredBlur"/>
                  <feMergeNode in="SourceGraphic"/>
                </feMerge>
              </filter>
              <!-- 核心星星径向渐变 -->
              <radialGradient id="gl-core-grad" cx="50%" cy="50%" r="50%">
                <stop offset="0%" style="stop-color: var(--loader-core-bright); stop-opacity: 1" />
                <stop offset="60%" style="stop-color: var(--loader-primary); stop-opacity: 0.85" />
                <stop offset="100%" style="stop-color: var(--loader-primary); stop-opacity: 0.4" />
              </radialGradient>
            </defs>
            
            <!-- 外圈星河轨道弧 -->
            <circle cx="50" cy="50" r="44" class="orbit orbit-outer" />
            
            <!-- 内圈星河轨道弧 -->
            <circle cx="50" cy="50" r="33" class="orbit orbit-inner" />

            <!-- 外圈轨道能量流光：沿轨道分布的光点依次明灭，让轨道"流动"起来 -->
            <g class="energy-flow flow-outer">
              <circle cx="93" cy="40" r="1.2" class="flow-dot fd1" filter="url(#gl-glow)" />
              <circle cx="80" cy="18" r="1" class="flow-dot fd2" filter="url(#gl-glow)" />
              <circle cx="50" cy="6" r="1.1" class="flow-dot fd3" filter="url(#gl-glow)" />
              <circle cx="20" cy="18" r="0.9" class="flow-dot fd4" filter="url(#gl-glow)" />
              <circle cx="8" cy="42" r="1.2" class="flow-dot fd5" filter="url(#gl-glow)" />
            </g>

            <!-- 内圈轨道能量流光 -->
            <g class="energy-flow flow-inner">
              <circle cx="83" cy="50" r="1" class="flow-dot fd6" filter="url(#gl-glow)" />
              <circle cx="67" cy="73" r="0.9" class="flow-dot fd7" filter="url(#gl-glow)" />
              <circle cx="33" cy="73" r="1" class="flow-dot fd8" filter="url(#gl-glow)" />
              <circle cx="17" cy="50" r="0.8" class="flow-dot fd9" filter="url(#gl-glow)" />
            </g>

            <!-- 星河微尘：散布在轨道间的极小闪烁星点，填充星河气氛 -->
            <g class="stardust">
              <circle cx="25" cy="28" r="0.7" class="dust-dot dd1" />
              <circle cx="76" cy="30" r="0.5" class="dust-dot dd2" />
              <circle cx="78" cy="72" r="0.6" class="dust-dot dd3" />
              <circle cx="22" cy="70" r="0.5" class="dust-dot dd4" />
              <circle cx="50" cy="25" r="0.4" class="dust-dot dd5" />
            </g>

            <!-- 灵感汇聚节点：四个方位的能量点依次脉冲，暗示灵感在汇聚 -->
            <g class="convergence-group">
              <circle cx="35" cy="35" r="1.3" class="conv-dot cv1" filter="url(#gl-glow)" />
              <circle cx="65" cy="35" r="1" class="conv-dot cv2" filter="url(#gl-glow)" />
              <circle cx="65" cy="65" r="1.3" class="conv-dot cv3" filter="url(#gl-glow)" />
              <circle cx="35" cy="65" r="1" class="conv-dot cv4" filter="url(#gl-glow)" />
            </g>
            
            <!-- 外圈卫星 1：主思绪流 -->
            <g class="sat-group sg-outer-1">
              <circle cx="50" cy="6" r="3.5" class="satellite sat-primary" filter="url(#gl-glow-core)" />
              <circle cx="47" cy="9" r="2" class="sat-trail st1" />
              <circle cx="44.5" cy="12.5" r="1.2" class="sat-trail st2" />
              <circle cx="42.5" cy="16.5" r="0.6" class="sat-trail st3" />
            </g>
            
            <!-- 内圈卫星 2：逆向思绪流 -->
            <g class="sat-group sg-inner">
              <circle cx="50" cy="83" r="2.5" class="satellite sat-secondary" filter="url(#gl-glow)" />
              <circle cx="52.5" cy="80.5" r="1.3" class="sat-trail st1" />
              <circle cx="54.5" cy="78" r="0.7" class="sat-trail st2" />
            </g>

            <!-- 外圈卫星 3：灵感碎片 -->
            <g class="sat-group sg-outer-2">
              <circle cx="94" cy="50" r="2" class="satellite sat-accent" filter="url(#gl-glow)" />
              <circle cx="91.5" cy="47.5" r="1" class="sat-trail st1" />
              <circle cx="89" cy="45.5" r="0.5" class="sat-trail st2" />
            </g>

            <!-- 核心辐射光芒：4道极细光线从中心向外延伸，缓慢旋转 -->
            <g class="ray-group">
              <line x1="50" y1="50" x2="50" y2="18" class="core-ray ray1" />
              <line x1="50" y1="50" x2="82" y2="50" class="core-ray ray2" />
              <line x1="50" y1="50" x2="50" y2="82" class="core-ray ray3" />
              <line x1="50" y1="50" x2="18" y2="50" class="core-ray ray4" />
            </g>
            
            <!-- 核心：灵感之心（四角星） -->
            <g class="core-group">
              <!-- 外层光晕呼吸 -->
              <circle cx="50" cy="50" r="12" class="core-halo" />
              <!-- 四角星主体 -->
              <path 
                class="core-star" 
                d="M50 22 L57 43 L78 50 L57 57 L50 78 L43 57 L22 50 L43 43 Z" 
                fill="url(#gl-core-grad)" 
                filter="url(#gl-glow-core)" 
              />
              <!-- 中心高亮点 -->
              <circle cx="50" cy="50" r="4" class="core-center" />
            </g>
          </svg>
        </div>
        
        <div class="loading-text">{{ text }}</div>

        <div v-if="statsEnabled && statsText" class="progress-info">{{ statsText }}</div>
        
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

// 生成随机粒子样式（组件初始化时固定，后续不再重算，避免重渲染闪烁）
function getParticleStyle(index) {
  const size = 2 + Math.random() * 3;
  const left = 5 + Math.random() * 90;
  const top = 5 + Math.random() * 90;
  const delay = Math.random() * 12;
  const duration = 10 + Math.random() * 10;
  const opacity = 0.08 + Math.random() * 0.18;
  
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

const particlesStyles = ref(Array.from({ length: 12 }, (_, i) => getParticleStyle(i)));

const text = ref('');
const progress = ref('');
const canCancel = ref(false);
const statsEnabled = ref(false);
const statsText = ref('');

function onGlobalLoading(p) {
  if (!props.active) return;
  if (typeof p === 'boolean') {
    visible.value = p;
    text.value = '';
    progress.value = '';
    canCancel.value = false;
    statsEnabled.value = false;
    statsText.value = '';
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
    statsEnabled.value = !!p?.statsEnabled;
    statsText.value = p?.statsEnabled
      ? (p?.statsLabel || `已撰写 ${Number(p?.statsChars || 0)} 字 · ${Number(p?.statsSpeed || 0)} 字/秒`)
      : '';
  }
}

function handleCancel() {
  bus.emit('cancel-loading', {
    scope: props.scope,
    target: props.target,
    reason: 'user_cancelled',
  });
}

onMounted(() => {
  bus.on('global-loading', onGlobalLoading);
});

onBeforeUnmount(() => {
  bus.off('global-loading', onGlobalLoading);
});
</script>

<style scoped src="./GlobalLoading.scoped.css"></style>
