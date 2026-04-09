<!-- 
  全局加载遮罩 —— 「灵感星河」主题
  视觉叙事：灵感之心呼吸律动，思绪沿弧光轨道汇聚流转，创作火花从中心绽放
  在长时间加载的情景中应该使用此组件覆盖部分面板，防止用户误操作
-->
<template>
  <transition name="fade">
    <div
      v-if="visible"
      ref="overlayRef"
      class="loading-overlay"
      :class="overlayClass"
      tabindex="0"
      aria-busy="true"
      aria-live="polite"
    >
      <!-- 背景漂浮粒子层：缓慢上升的灵感微光 -->
      <div class="particle-field">
        <div v-for="i in 12" :key="'p'+i" class="floating-particle" :style="particlesStyles[i-1]"></div>
      </div>
      
      <div class="loading-content">
        <SparkLoaderAnimation />
        
        <div class="loading-text">{{ text }}</div>

        <div v-if="statsEnabled && statsText" class="progress-info">{{ statsText }}</div>
        
        <div v-if="progress && progress !== text && progress !== statsText" class="progress-info">{{ progress }}</div>
        
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

<script setup lang="ts">
import SparkLoaderAnimation from './SparkLoaderAnimation.vue';
import { ref, computed, onMounted, onBeforeUnmount, nextTick } from 'vue';
import { NButton } from 'naive-ui';
import bus from '@/eventBus';

const visible = ref(false);
const overlayRef = ref(null);
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
    const secondaryText = String(p?.secondaryText || p?.statsLabel || '').trim();
    statsEnabled.value = Boolean(p?.secondaryVisible ?? p?.statsEnabled ?? secondaryText);
    statsText.value = statsEnabled.value
      ? (secondaryText || `已撰写 ${Number(p?.statsChars || 0)} 字 · ${Number(p?.statsSpeed || 0)} 字/秒`)
      : '';

    if (visible.value) {
      nextTick(() => {
        const overlayEl = overlayRef.value;
        const hostEl = overlayEl?.parentElement;
        const activeEl = document.activeElement;
        if (
          hostEl
          && activeEl instanceof HTMLElement
          && hostEl.contains(activeEl)
          && !overlayEl?.contains(activeEl)
        ) {
          activeEl.blur?.();
        }
        overlayEl?.focus?.({ preventScroll: true });
      });
    }
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
