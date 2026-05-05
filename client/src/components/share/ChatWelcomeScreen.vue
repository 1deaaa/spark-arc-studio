<template>
  <div class="chat-welcome">
    <!-- 中心火花动画 -->
    <div class="welcome-spark-anim">
      <svg viewBox="0 0 120 120" fill="none" xmlns="http://www.w3.org/2000/svg" class="spark-anim-svg">
        <defs>
          <filter id="wc-glow" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="2.5" result="blur" />
            <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>
          <radialGradient id="wc-core-grad" cx="50%" cy="50%" r="50%">
            <stop offset="0%" style="stop-color: var(--spark-primary-light); stop-opacity: 1" />
            <stop offset="60%" style="stop-color: var(--spark-primary); stop-opacity: 0.8" />
            <stop offset="100%" style="stop-color: var(--spark-primary); stop-opacity: 0.3" />
          </radialGradient>
        </defs>

        <!-- 脉冲涟漪 -->
        <circle cx="60" cy="60" r="20" class="wc-pulse-ring pr1" />
        <circle cx="60" cy="60" r="20" class="wc-pulse-ring pr2" />
        <circle cx="60" cy="60" r="20" class="wc-pulse-ring pr3" />

        <!-- 轨道弧 -->
        <circle cx="60" cy="60" r="48" class="wc-orbit wc-orbit-outer" />
        <circle cx="60" cy="60" r="36" class="wc-orbit wc-orbit-inner" />

        <!-- 轨道能量流光 -->
        <g class="wc-flow wc-flow-outer">
          <circle cx="108" cy="48" r="1.4" class="wc-fdot fd1" filter="url(#wc-glow)" />
          <circle cx="96" cy="22" r="1.1" class="wc-fdot fd2" filter="url(#wc-glow)" />
          <circle cx="60" cy="12" r="1.2" class="wc-fdot fd3" filter="url(#wc-glow)" />
          <circle cx="24" cy="22" r="1" class="wc-fdot fd4" filter="url(#wc-glow)" />
        </g>
        <g class="wc-flow wc-flow-inner">
          <circle cx="96" cy="60" r="1.1" class="wc-fdot fd5" filter="url(#wc-glow)" />
          <circle cx="78" cy="88" r="0.9" class="wc-fdot fd6" filter="url(#wc-glow)" />
          <circle cx="42" cy="88" r="1" class="wc-fdot fd7" filter="url(#wc-glow)" />
        </g>

        <!-- 微尘 -->
        <g class="wc-stardust">
          <circle cx="30" cy="34" r="0.6" class="wc-dust dd1" />
          <circle cx="90" cy="36" r="0.5" class="wc-dust dd2" />
          <circle cx="92" cy="86" r="0.5" class="wc-dust dd3" />
          <circle cx="28" cy="84" r="0.4" class="wc-dust dd4" />
          <circle cx="60" cy="30" r="0.3" class="wc-dust dd5" />
        </g>

        <!-- 汇聚节点 -->
        <g class="wc-convergence">
          <circle cx="42" cy="42" r="1.4" class="wc-cdot cv1" filter="url(#wc-glow)" />
          <circle cx="78" cy="42" r="1.1" class="wc-cdot cv2" filter="url(#wc-glow)" />
          <circle cx="78" cy="78" r="1.4" class="wc-cdot cv3" filter="url(#wc-glow)" />
          <circle cx="42" cy="78" r="1.1" class="wc-cdot cv4" filter="url(#wc-glow)" />
        </g>

        <!-- 卫星 -->
        <g class="wc-sat-group wc-sat-1">
          <circle cx="60" cy="12" r="3" class="wc-sat wc-sat-primary" filter="url(#wc-glow)" />
          <circle cx="57" cy="16" r="1.6" class="wc-sat-trail st1" />
          <circle cx="54.5" cy="20" r="0.8" class="wc-sat-trail st2" />
        </g>
        <g class="wc-sat-group wc-sat-2">
          <circle cx="60" cy="96" r="2.2" class="wc-sat wc-sat-secondary" filter="url(#wc-glow)" />
          <circle cx="63" cy="92" r="1.1" class="wc-sat-trail st1" />
        </g>

        <!-- 辐射光芒 -->
        <g class="wc-ray-group">
          <line x1="60" y1="60" x2="60" y2="22" class="wc-ray r1" />
          <line x1="60" y1="60" x2="98" y2="60" class="wc-ray r2" />
          <line x1="60" y1="60" x2="60" y2="98" class="wc-ray r3" />
          <line x1="60" y1="60" x2="22" y2="60" class="wc-ray r4" />
        </g>

        <!-- 核心：四角星 -->
        <g class="wc-core-group">
          <circle cx="60" cy="60" r="14" class="wc-core-halo" />
          <path
            class="wc-core-star"
            d="M60 28 L68 52 L92 60 L68 68 L60 92 L52 68 L28 60 L52 52 Z"
            fill="url(#wc-core-grad)"
            filter="url(#wc-glow)"
          />
          <circle cx="60" cy="60" r="4.5" class="wc-core-center" />
        </g>
      </svg>
    </div>

    <!-- 欢迎标题 -->
    <h2 class="welcome-title">{{ t('components.chatWelcome.title') }}</h2>
    <p class="welcome-subtitle">{{ t('components.chatWelcome.subtitle') }}</p>

    <!-- 快速开始提示 -->
    <div class="welcome-tips">
      <div class="tip-section">
        <div class="tip-section-header">
          <svg viewBox="0 0 20 20" fill="none" class="tip-icon tip-icon-rocket">
            <path d="M10 2C10 2 14 6 14 10C14 12 12.5 14 10 14C7.5 14 6 12 6 10C6 6 10 2 10 2Z" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" />
            <path d="M10 14V18" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
            <path d="M7 18H13" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
          </svg>
          <span class="tip-section-title">{{ t('components.chatWelcome.quickStart') }}</span>
        </div>
        <ul class="tip-list">
          <li v-for="(tip, i) in quickStartTips" :key="i" class="tip-item">
            <span class="tip-num">{{ i + 1 }}</span>
            <span class="tip-text">{{ tip }}</span>
          </li>
        </ul>
      </div>

      <div class="tip-divider"></div>

      <div class="tip-section">
        <div class="tip-section-header">
          <svg viewBox="0 0 20 20" fill="none" class="tip-icon tip-icon-studio">
            <rect x="2" y="4" width="16" height="12" rx="2" stroke="currentColor" stroke-width="1.5" />
            <path d="M6 8H10M6 11H14" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" />
            <circle cx="15" cy="7" r="1.2" fill="currentColor" />
          </svg>
          <span class="tip-section-title">{{ t('components.chatWelcome.proWorkflow') }}</span>
        </div>
        <p class="tip-section-hint">{{ t('components.chatWelcome.proWorkflowHint') }}</p>
        <ul class="tip-list">
          <li v-for="(tip, i) in proTips" :key="i" class="tip-item">
            <span class="tip-num">{{ i + 1 }}</span>
            <span class="tip-text">{{ tip.text }}</span>
            <n-tooltip trigger="hover">
              <template #trigger>
                <button class="tip-goto" @click.stop="goToView(tip.view)">
                  <svg viewBox="0 0 18 18" fill="none" class="tip-goto-svg">
                    <circle cx="9" cy="9" r="7.5" stroke="currentColor" stroke-width="0.8"/>
                    <path d="M7.5 5.5L11.5 9L7.5 12.5" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/>
                  </svg>
                </button>
              </template>
              {{ t('components.chatWelcome.goToPage') }}
            </n-tooltip>
          </li>
        </ul>
      </div>
    </div>

    <!-- 底部快捷提示 -->
    <div class="welcome-footer">
      <span class="footer-hint">{{ t('components.chatWelcome.footerHint') }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { NTooltip } from 'naive-ui';
import { useI18n } from 'vue-i18n';
import { useViewStore, type AppViewKey } from '@/components/stores/viewStore';

const { t } = useI18n();
const viewStore = useViewStore();

const quickStartTips = computed(() => [
  t('components.chatWelcome.quickTip1'),
  t('components.chatWelcome.quickTip2'),
  t('components.chatWelcome.quickTip3'),
  t('components.chatWelcome.quickTip4'),
]);

const proTips = computed(() => [
  { text: t('components.chatWelcome.proTip1'), view: 'world' as AppViewKey },
  { text: t('components.chatWelcome.proTip2'), view: 'synopsis' as AppViewKey },
  { text: t('components.chatWelcome.proTip3'), view: 'structure' as AppViewKey },
  { text: t('components.chatWelcome.proTip4'), view: 'blueprint' as AppViewKey },
  { text: t('components.chatWelcome.proTip5'), view: 'engine' as AppViewKey },
]);

function goToView(view: AppViewKey) {
  viewStore.setView(view);
}
</script>

<style scoped>
.chat-welcome {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: clamp(20px, 5vh, 40px) clamp(16px, 5%, 28px) clamp(16px, 3vh, 28px);
  gap: clamp(10px, 1.8vh, 18px);
  min-height: 100%;
  overflow-y: auto;
  user-select: none;
  -webkit-user-select: none;
}

/* ===== 火花动画 ===== */
.welcome-spark-anim {
  position: relative;
  width: clamp(110px, 18vh, 160px);
  height: clamp(110px, 18vh, 160px);
  flex-shrink: 0;
}

.spark-anim-svg {
  width: 100%;
  height: 100%;
  overflow: visible;
}

/* 脉冲涟漪 */
.wc-pulse-ring {
  fill: none;
  stroke: var(--spark-primary-glow);
  stroke-width: 1;
  opacity: 0;
  animation: wc-heartbeat 4s ease-out infinite;
}
.wc-pulse-ring.pr1 { animation-delay: 0s; }
.wc-pulse-ring.pr2 { animation-delay: 1.33s; }
.wc-pulse-ring.pr3 { animation-delay: 2.66s; }

@keyframes wc-heartbeat {
  0% { r: 14; opacity: 0.4; }
  100% { r: 55; opacity: 0; }
}

/* 轨道弧 */
.wc-orbit {
  fill: none;
  stroke-width: 1;
  stroke-linecap: round;
}
.wc-orbit-outer {
  stroke: var(--spark-primary);
  stroke-dasharray: 180 120;
  opacity: 0.3;
  transform-origin: 60px 60px;
  animation: wc-orbit-cw 20s linear infinite;
  filter: drop-shadow(0 0 3px var(--spark-primary-glow));
}
.wc-orbit-inner {
  stroke: var(--spark-harmonious-a);
  stroke-dasharray: 100 126;
  opacity: 0.2;
  transform-origin: 60px 60px;
  animation: wc-orbit-ccw 16s linear infinite;
}

@keyframes wc-orbit-cw { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
@keyframes wc-orbit-ccw { from { transform: rotate(360deg); } to { transform: rotate(0deg); } }

/* 能量流光 */
.wc-flow { transform-origin: 60px 60px; }
.wc-flow-outer { animation: wc-orbit-cw 20s linear infinite; }
.wc-flow-inner { animation: wc-orbit-ccw 16s linear infinite; }

.wc-fdot {
  fill: var(--spark-primary);
  opacity: 0;
  animation: wc-flow-pulse 2.5s ease-in-out infinite;
}
.wc-fdot.fd1 { animation-delay: 0s; }
.wc-fdot.fd2 { animation-delay: 0.5s; }
.wc-fdot.fd3 { animation-delay: 1s; }
.wc-fdot.fd4 { animation-delay: 1.5s; }
.wc-fdot.fd5 { animation-delay: 0.3s; }
.wc-fdot.fd6 { animation-delay: 0.9s; }
.wc-fdot.fd7 { animation-delay: 1.5s; }

@keyframes wc-flow-pulse {
  0%, 100% { opacity: 0; transform: scale(0.6); }
  50% { opacity: 0.55; transform: scale(1.3); }
}

/* 微尘 */
.wc-dust {
  fill: var(--spark-text-muted);
  opacity: 0;
  animation: wc-twinkle 4s ease-in-out infinite;
}
.wc-dust.dd1 { animation-delay: 0s; }
.wc-dust.dd2 { animation-delay: 0.8s; }
.wc-dust.dd3 { animation-delay: 1.6s; }
.wc-dust.dd4 { animation-delay: 2.4s; }
.wc-dust.dd5 { animation-delay: 3.2s; }

@keyframes wc-twinkle {
  0%, 100% { opacity: 0; transform: scale(0.7); }
  50% { opacity: 0.35; transform: scale(1.2); }
}

/* 汇聚节点 */
.wc-cdot {
  fill: var(--spark-primary);
  opacity: 0;
  animation: wc-conv-pulse 3s ease-in-out infinite;
}
.wc-cdot.cv1 { animation-delay: 0s; }
.wc-cdot.cv2 { animation-delay: 0.75s; }
.wc-cdot.cv3 { animation-delay: 1.5s; }
.wc-cdot.cv4 { animation-delay: 2.25s; }

@keyframes wc-conv-pulse {
  0%, 100% { opacity: 0; transform: scale(0.5); }
  50% { opacity: 0.6; transform: scale(1.4); }
}

/* 卫星 */
.wc-sat-group { transform-origin: 60px 60px; }
.wc-sat-1 { animation: wc-orbit-cw 10s linear infinite; }
.wc-sat-2 { animation: wc-orbit-ccw 14s linear infinite; }

.wc-sat { opacity: 0.9; }
.wc-sat-primary { fill: var(--spark-primary); }
.wc-sat-secondary { fill: var(--spark-harmonious-a); }
.wc-sat-trail { fill: var(--spark-primary); }
.wc-sat-trail.st1 { opacity: 0.35; }
.wc-sat-trail.st2 { opacity: 0.12; }

/* 辐射光芒 */
.wc-ray-group {
  transform-origin: 60px 60px;
  animation: wc-ray-rotate 12s linear infinite;
}
.wc-ray {
  stroke: var(--spark-primary);
  stroke-width: 0.4;
  stroke-linecap: round;
  opacity: 0;
  animation: wc-ray-breathe 3s ease-in-out infinite;
}
.wc-ray.r1 { animation-delay: 0s; }
.wc-ray.r2 { animation-delay: 0.75s; }
.wc-ray.r3 { animation-delay: 1.5s; }
.wc-ray.r4 { animation-delay: 2.25s; }

@keyframes wc-ray-rotate { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
@keyframes wc-ray-breathe {
  0%, 100% { opacity: 0; stroke-dasharray: 0 38; stroke-dashoffset: 0; }
  50% { opacity: 0.25; stroke-dasharray: 18 20; stroke-dashoffset: -9; }
}

/* 核心四角星 */
.wc-core-group {
  transform-origin: 60px 60px;
  animation: wc-core-breathe 6s ease-in-out infinite;
}
.wc-core-star { opacity: 0.85; }
.wc-core-center { fill: var(--spark-text-inverse); opacity: 0.85; }
.wc-core-halo { fill: var(--spark-primary-glow); opacity: 0; animation: wc-halo 3s ease-in-out infinite; }

@keyframes wc-core-breathe {
  0% { transform: scale(0.9) rotate(0deg); opacity: 0.75; }
  50% { transform: scale(1.06) rotate(180deg); opacity: 1; }
  100% { transform: scale(0.9) rotate(360deg); opacity: 0.75; }
}
@keyframes wc-halo {
  0%, 100% { opacity: 0; r: 10; }
  50% { opacity: 0.25; r: 18; }
}

/* ===== 文字区域 ===== */
.welcome-title {
  font-size: var(--spark-fs-h2);
  font-weight: 800;
  color: var(--spark-text);
  margin: 0;
  text-align: center;
  letter-spacing: -0.3px;
}

.welcome-subtitle {
  font-size: var(--spark-fs-sm);
  color: var(--spark-primary);
  margin: 0;
  text-align: center;
  max-width: min(88%, 340px);
  line-height: 1.5;
}

/* ===== 提示区域 ===== */
.welcome-tips {
  display: flex;
  flex-direction: column;
  gap: clamp(8px, 1.2vh, 14px);
  width: 100%;
  max-width: min(100%, 560px);
  margin-top: 4px;
}

.tip-section {
  background: color-mix(in srgb, var(--spark-primary), transparent 92%);
  border: 1px solid var(--spark-border);
  border-radius: var(--spark-radius-sm);
  padding: clamp(10px, 1.8vh, 16px) clamp(12px, 3%, 18px);
}

.tip-section-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.tip-icon {
  width: 18px;
  height: 18px;
  flex-shrink: 0;
  color: var(--spark-primary);
}

.tip-section-title {
  font-size: var(--spark-fs-lg);
  font-weight: 700;
  color: var(--spark-text);
}

.tip-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.tip-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  font-size: var(--spark-fs-sm);
  color: var(--spark-text-muted);
  line-height: 1.55;
}

.tip-section-hint {
  font-size: var(--spark-fs-xs);
  color: var(--spark-text-muted);
  margin: 0 0 8px 0;
  line-height: 1.5;
  opacity: 0.85;
}

.tip-num {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  flex-shrink: 0;
  border-radius: 50%;
  background: var(--spark-primary-container);
  color: var(--spark-primary);
  font-size: var(--spark-fs-3xs);
  font-weight: 700;
  line-height: 1;
}

.tip-text {
  flex: 1;
}

.tip-goto {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  align-self: center;
  flex-shrink: 0;
  width: 26px;
  height: 26px;
  padding: 0;
  border: none;
  background: color-mix(in srgb, var(--spark-primary), transparent 92%);
  color: var(--spark-primary);
  opacity: 0.55;
  cursor: pointer;
  transition: opacity 0.2s ease, transform 0.2s ease, background 0.2s ease;
  border-radius: 50%;
}

.tip-goto:hover {
  opacity: 1;
  transform: scale(1.12);
  background: color-mix(in srgb, var(--spark-primary), transparent 82%);
}

.tip-goto:active {
  transform: scale(0.92);
  opacity: 1;
}

.tip-goto-svg {
  width: 18px;
  height: 18px;
}

.tip-divider {
  width: 40px;
  height: 1px;
  background: var(--spark-border);
  align-self: center;
}

/* ===== 底部 ===== */
.welcome-footer {
  margin-top: 4px;
}

.footer-hint {
  font-size: var(--spark-fs-2xs);
  color: var(--spark-text-muted);
  opacity: 0.7;
}
</style>
