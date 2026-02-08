<template>
  <div v-if="isTauriDesktop" class="win-controls" :class="variant">
    <button 
      class="win-btn win-btn--minimize" 
      @click="minimize" 
      @mouseenter="onHover('minimize')"
      @mouseleave="onLeave('minimize')"
      @mousedown="onPress('minimize')"
      @mouseup="onRelease('minimize')"
      title="最小化"
    >
      <svg class="win-icon" viewBox="0 0 24 24" fill="none">
        <rect 
          class="icon-shape" 
          x="5" y="11" width="14" height="2" rx="1" 
          fill="currentColor"
        />
      </svg>
    </button>
    <button 
      class="win-btn win-btn--maximize" 
      @click="toggleMaximize" 
      @mouseenter="onHover('maximize')"
      @mouseleave="onLeave('maximize')"
      @mousedown="onPress('maximize')"
      @mouseup="onRelease('maximize')"
      :title="isMaximized ? '还原' : '最大化'"
    >
      <svg v-if="!isMaximized" class="win-icon" viewBox="0 0 24 24" fill="none">
        <rect 
          class="icon-shape" 
          x="5" y="5" width="14" height="14" rx="2" 
          stroke="currentColor" stroke-width="2" fill="none"
        />
      </svg>
      <svg v-else class="win-icon" viewBox="0 0 24 24" fill="none">
        <rect 
          class="icon-shape icon-back" 
          x="8" y="4" width="12" height="12" rx="1.5" 
          stroke="currentColor" stroke-width="1.5" fill="none"
        />
        <rect 
          class="icon-shape icon-front" 
          x="4" y="8" width="12" height="12" rx="1.5" 
          stroke="currentColor" stroke-width="1.5" 
          :fill="fillBg"
        />
      </svg>
    </button>
    <button 
      class="win-btn win-btn--close" 
      @click="close" 
      @mouseenter="onHover('close')"
      @mouseleave="onLeave('close')"
      @mousedown="onPress('close')"
      @mouseup="onRelease('close')"
      title="关闭"
    >
      <svg class="win-icon" viewBox="0 0 24 24" fill="none">
        <path 
          class="icon-shape" 
          d="M6 6L18 18M18 6L6 18" 
          stroke="currentColor" stroke-width="2" stroke-linecap="round"
        />
      </svg>
    </button>
  </div>
</template>

<script setup>
import { computed, reactive } from 'vue';
import { useWindowControls } from '@/composables/useWindowControls';

const props = defineProps({
  /** 'titlebar' = 独立标题栏样式, 'header' = 嵌入 HeaderToolbar 样式 */
  variant: { type: String, default: 'titlebar' }
});

const { isMaximized, minimize, toggleMaximize, close, isTauriDesktop } = useWindowControls();

// 按钮交互状态管理
const btnStates = reactive({
  minimize: { hover: false, pressed: false },
  maximize: { hover: false, pressed: false },
  close: { hover: false, pressed: false }
});

function onHover(btn) {
  btnStates[btn].hover = true;
}

function onLeave(btn) {
  btnStates[btn].hover = false;
  btnStates[btn].pressed = false;
}

function onPress(btn) {
  btnStates[btn].pressed = true;
}

function onRelease(btn) {
  btnStates[btn].pressed = false;
}

// 还原按钮的填充色随变体自适应
const fillBg = computed(() =>
  props.variant === 'header'
    ? 'var(--spark-header-bg, var(--spark-panel-bg))'
    : 'var(--spark-bg)'
);
</script>

<style scoped>
/* ============================================================
   窗口控制按钮 — 现代简约风格
   增大尺寸、SVG动画交互、自适应亮暗色模式
   ============================================================ */

.win-controls {
  display: flex;
  align-items: center;
  gap: 8px;
  padding-left: 10px;
  padding-right: 6px;
  margin-right: 0;
}

.win-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 8px;
  border: none;
  cursor: pointer;
  padding: 0;
  outline: none;
  position: relative;
  background: transparent;
  /* 自适应亮暗色模式的前景色 */
  color: var(--win-btn-color, var(--spark-text-secondary, #6b7280));
  transition: 
    background 0.2s ease,
    color 0.2s ease,
    transform 0.15s cubic-bezier(0.34, 1.56, 0.64, 1),
    box-shadow 0.2s ease;
}

/* ---- 亮色模式默认色 ---- */
:root {
  --win-btn-color: #6b7280;
  --win-btn-hover-bg: rgba(0, 0, 0, 0.06);
  --win-btn-close-hover-bg: rgba(239, 68, 68, 0.12);
  --win-btn-close-hover-color: #dc2626;
}

/* ---- 暗色模式颜色 ---- */
:root[data-theme="dark"],
.dark {
  --win-btn-color: rgba(255, 255, 255, 0.85);
  --win-btn-hover-bg: rgba(255, 255, 255, 0.08);
  --win-btn-close-hover-bg: rgba(239, 68, 68, 0.2);
  --win-btn-close-hover-color: #f87171;
}

/* ---- 图标样式 ---- */
.win-icon {
  width: 18px;
  height: 18px;
  transition: transform 0.2s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.icon-shape {
  transition: 
    transform 0.2s ease,
    stroke-dashoffset 0.3s ease,
    opacity 0.2s ease;
  transform-origin: center;
}

/* ---- Hover 效果 ---- */
.win-btn:hover {
  background: var(--win-btn-hover-bg);
}

.win-btn:hover .win-icon {
  transform: scale(1.1);
}

/* 最小化按钮 hover 动画 - 向下弹跳 */
.win-btn--minimize:hover .icon-shape {
  animation: minimizeBounce 0.4s ease;
}

@keyframes minimizeBounce {
  0% { transform: translateY(0); }
  40% { transform: translateY(3px); }
  60% { transform: translateY(-1px); }
  80% { transform: translateY(1px); }
  100% { transform: translateY(0); }
}

/* 最大化按钮 hover 动画 - 缩放脉冲 */
.win-btn--maximize:hover .icon-shape {
  animation: maximizePulse 0.4s ease;
}

@keyframes maximizePulse {
  0% { transform: scale(1); }
  50% { transform: scale(1.15); }
  100% { transform: scale(1); }
}

/* 关闭按钮样式 */
.win-btn--close:hover {
  background: var(--win-btn-close-hover-bg);
  color: var(--win-btn-close-hover-color);
}

/* 关闭按钮 hover 动画 - 旋转 */
.win-btn--close:hover .icon-shape {
  animation: closeRotate 0.3s ease;
}

@keyframes closeRotate {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(90deg); }
}

/* ---- 点击/按下效果 ---- */
.win-btn:active {
  transform: scale(0.9);
}

.win-btn:active .win-icon {
  transform: scale(0.95);
}

/* ---- Focus 效果 ---- */
.win-btn:focus-visible {
  outline: 2px solid var(--spark-primary, #3b82f6);
  outline-offset: 2px;
}

.win-btn:focus-visible .icon-shape {
  animation: focusPulse 0.5s ease;
}

@keyframes focusPulse {
  0% { opacity: 0.7; }
  50% { opacity: 1; }
  100% { opacity: 0.7; }
}

/* ---- titlebar 变体（登录页透明标题栏）---- */
.titlebar .win-btn {
  opacity: 0.9;
}

.titlebar .win-btn:hover {
  opacity: 1;
}

/* ---- header 变体（嵌入工具栏）---- */
.header .win-btn {
  width: 30px;
  height: 30px;
}

.header .win-icon {
  width: 16px;
  height: 16px;
}

/* 还原按钮的堆叠矩形动画 */
.win-btn--maximize:hover .icon-back {
  animation: restoreBack 0.4s ease;
}

.win-btn--maximize:hover .icon-front {
  animation: restoreFront 0.4s ease;
}

@keyframes restoreBack {
  0% { transform: translate(0, 0); }
  50% { transform: translate(2px, -2px); }
  100% { transform: translate(0, 0); }
}

@keyframes restoreFront {
  0% { transform: translate(0, 0); }
  50% { transform: translate(-2px, 2px); }
  100% { transform: translate(0, 0); }
}
</style>
