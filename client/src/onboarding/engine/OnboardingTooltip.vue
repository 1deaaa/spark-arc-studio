<template>
  <transition name="onboarding-tooltip">
    <div
      v-if="engine.isActive.value && currentStep && !engine.isTransitioning.value"
      ref="tooltipEl"
      class="onboarding-tooltip"
      :class="[`placement-${currentStep.placement}`]"
      :style="tooltipStyle"
    >
      <!-- 进度指示 -->
      <div class="tooltip-progress">
        <div
          v-for="i in engine.totalSteps.value"
          :key="i"
          class="progress-dot"
          :class="{ active: i - 1 === engine.currentStepIndex.value, done: i - 1 < engine.currentStepIndex.value }"
        />
      </div>

      <!-- 内容区 -->
      <div class="tooltip-body">
        <h4 class="tooltip-title">{{ t(currentStep.titleKey) }}</h4>
        <p class="tooltip-desc">{{ t(currentStep.descKey) }}</p>
        <!-- 桌面端引导提示行（仅完成步骤有 hintKey 时显示） -->
        <div v-if="currentStep.hintKey" class="tooltip-hint">
          <svg class="hint-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
            <rect x="2" y="3" width="20" height="14" rx="2" />
            <path d="M8 21h8" />
            <path d="M12 17v4" />
          </svg>
          <span class="hint-text">{{ t(currentStep.hintKey) }}</span>
        </div>
      </div>

      <!-- 动作按钮 -->
      <div class="tooltip-actions">
        <button v-if="engine.currentStepIndex.value > 0" class="tooltip-btn secondary" @click="onPrev">
          {{ t('onboarding.common.prev') }}
        </button>
        <button class="tooltip-btn skip" @click="onSkip">
          {{ t('onboarding.common.skip') }}
        </button>
        <button class="tooltip-btn primary" @click="onNext">
          {{ isLastStep ? t('onboarding.common.done') : t('onboarding.common.next') }}
        </button>
      </div>
    </div>
  </transition>
</template>

<script setup lang="ts">
import { computed, ref, watch, nextTick, onMounted, onUpdated, type StyleValue } from 'vue';
import { useI18n } from 'vue-i18n';
import { getOnboardingEngine } from './OnboardingEngine';

const engine = getOnboardingEngine();
const { t } = useI18n();
const tooltipEl = ref<HTMLElement | null>(null);
// 用于触发 tooltipStyle 重算的尺寸响应式代理
const tooltipSize = ref({ w: 280, h: 200 });

function measureTooltip() {
  if (tooltipEl.value) {
    tooltipSize.value = { w: tooltipEl.value.offsetWidth, h: tooltipEl.value.offsetHeight };
  }
}
onMounted(() => nextTick(measureTooltip));
onUpdated(() => nextTick(measureTooltip));

const currentStep = computed(() => engine.getCurrentStep());
const isLastStep = computed(() => {
  if (!engine.currentSceneId.value) return false;
  return engine.currentStepIndex.value >= engine.totalSteps.value - 1;
});

const tooltipStyle = computed<StyleValue>(() => {
  const step = currentStep.value;
  const rect = engine.targetRect.value;
  if (!step || step.placement === 'center') {
    return {
      position: 'fixed',
      top: '50%',
      left: '50%',
      transform: 'translate(-50%, -50%)',
      maxWidth: 'calc(100vw - 32px)',
    };
  }
  if (!rect) {
    return {
      position: 'fixed',
      top: '50%',
      left: '50%',
      transform: 'translate(-50%, -50%)',
      maxWidth: 'calc(100vw - 32px)',
    };
  }

  const vw = window.innerWidth;
  const vh = window.innerHeight;
  const margin = 12; // 屏幕边缘安全距离
  const gap = 12;

  // 使用响应式尺寸，挂载后自动更新
  const tw = tooltipSize.value.w;
  const th = tooltipSize.value.h;

  // 计算各方向理想位置
  const idealBottom = rect.bottom + gap;
  const idealTop = rect.top - gap;
  const idealRight = rect.right + gap;
  const idealLeft = rect.left - gap;

  // 空间不足时自动翻转（可能回退到 center）
  let placement: string = step.placement;
  if (placement === 'bottom' && idealBottom + th > vh - margin) {
    if (idealTop - th > margin) placement = 'top';
  }
  if (placement === 'top' && idealTop - th < margin) {
    if (idealBottom + th < vh - margin) placement = 'bottom';
  }
  if (placement === 'right' && idealRight + tw > vw - margin) {
    if (idealLeft - tw > margin) placement = 'left';
  }
  if (placement === 'left' && idealLeft - tw < margin) {
    // 移动端左侧放不下时回退到 bottom
    if (idealBottom + th < vh - margin) placement = 'bottom';
    else placement = 'center';
  }

  if (placement === 'center') {
    return {
      position: 'fixed',
      top: '50%',
      left: '50%',
      transform: 'translate(-50%, -50%)',
      maxWidth: `calc(${vw}px - 32px)`,
    };
  }

  const style: Record<string, string> = {
    position: 'fixed',
    maxWidth: `calc(${vw}px - ${margin * 2}px)`,
  };

  if (placement === 'top' || placement === 'bottom') {
    const centerX = rect.left + rect.width / 2;
    style.left = `${Math.max(margin, Math.min(centerX, vw - margin))}px`;
    style.transform = 'translateX(-50%)';
    if (placement === 'bottom') {
      style.top = `${Math.min(idealBottom, vh - th - margin)}px`;
    } else {
      style.bottom = `${Math.max(margin, vh - idealTop)}px`;
    }
  } else {
    const centerY = rect.top + rect.height / 2;
    const clampedTop = Math.max(margin, Math.min(centerY - th / 2, vh - th - margin));
    style.top = `${clampedTop}px`;
    style.transform = 'translateY(0)';
    if (placement === 'right') {
      style.left = `${Math.min(idealRight, vw - tw - margin)}px`;
    } else {
      style.right = `${Math.max(margin, vw - idealLeft)}px`;
    }
  }

  return style as StyleValue;
});

function onNext() {
  if (isLastStep.value) {
    engine.complete();
  } else {
    engine.next();
  }
}

function onPrev() {
  engine.prev();
}

function onSkip() {
  engine.skip();
}

// targetRect 就绪时播放入场动画（确保位置已计算完毕再淡入）
watch(() => engine.targetRect.value, async (rect) => {
  if (!rect || !tooltipEl.value) return;
  // 先设为不可见，等 GSAP 淡入
  tooltipEl.value.style.visibility = 'hidden';
  await nextTick();
  if (tooltipEl.value) {
    const { gsapFadeIn } = await import('../animations/gsapPresets');
    gsapFadeIn(tooltipEl.value, 0.3);
    // GSAP 会设置 opacity，确保 visibility 也恢复
    tooltipEl.value.style.visibility = '';
  }
});
</script>

<style scoped>
.onboarding-tooltip {
  position: fixed;
  z-index: 10002;
  min-width: 200px;
  max-width: 360px;
  background: var(--spark-panel-bg, var(--n-color-modal, #1e1e1e));
  border: 1px solid var(--spark-border);
  border-radius: 12px;
  box-shadow: var(--spark-shadow), 0 0 0 1px var(--spark-primary) inset;
  padding: 16px;
  pointer-events: auto;
}

/* 移动端紧凑布局 */
@media (max-width: 480px) {
  .onboarding-tooltip {
    min-width: unset;
    padding: 14px;
  }
  .tooltip-actions {
    gap: 6px;
  }
  .tooltip-btn {
    padding: 5px 10px;
    font-size: var(--spark-fs-xs, 12px);
  }
  .tooltip-hint {
    padding: 8px 10px;
    gap: 8px;
  }
  .hint-icon {
    width: 18px;
    height: 18px;
  }
  .hint-text {
    font-size: var(--spark-fs-xs, 12px);
  }
}

.tooltip-progress {
  display: flex;
  gap: 6px;
  margin-bottom: 12px;
}

.progress-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--spark-border);
  transition: all 0.3s ease;
}

.progress-dot.active {
  background: var(--spark-primary);
  box-shadow: 0 0 6px var(--spark-primary);
  transform: scale(1.3);
}

.progress-dot.done {
  background: var(--spark-success);
}

.tooltip-body {
  margin-bottom: 16px;
}

.tooltip-title {
  font-size: var(--spark-fs-lg);
  font-weight: 700;
  color: var(--spark-text);
  margin: 0 0 8px;
}

.tooltip-desc {
  font-size: var(--spark-fs-sm);
  color: var(--spark-text-muted);
  line-height: 1.5;
  margin: 0;
}

/* 桌面端引导提示行 */
.tooltip-hint {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  margin-top: 12px;
  padding: 10px 12px;
  border-radius: 8px;
  background: color-mix(in srgb, var(--spark-primary), transparent 88%);
  border: 1px solid color-mix(in srgb, var(--spark-primary), transparent 50%);
}

.hint-icon {
  flex-shrink: 0;
  width: 20px;
  height: 20px;
  color: var(--spark-primary);
  margin-top: 1px;
}

.hint-text {
  font-size: var(--spark-fs-sm);
  font-weight: 600;
  color: var(--spark-primary);
  line-height: 1.5;
}

.tooltip-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
  align-items: center;
  flex-wrap: nowrap;
}

.tooltip-btn {
  padding: 6px 14px;
  border-radius: 6px;
  font-size: var(--spark-fs-sm);
  font-weight: 500;
  cursor: pointer;
  border: none;
  transition: all 0.2s ease;
  white-space: nowrap;
  flex-shrink: 0;
}

.tooltip-btn.primary {
  background: var(--spark-primary);
  color: var(--spark-text-inverse);
}

.tooltip-btn.primary:hover {
  box-shadow: 0 0 12px color-mix(in srgb, var(--spark-primary), transparent 50%);
  transform: translateY(-1px);
}

.tooltip-btn.secondary {
  background: transparent;
  color: var(--spark-text-muted);
  border: 1px solid var(--spark-border);
}

.tooltip-btn.secondary:hover {
  color: var(--spark-text);
  border-color: var(--spark-text-muted);
}

.tooltip-btn.skip {
  background: transparent;
  color: var(--spark-text-muted);
  margin-right: auto;
}

.tooltip-btn.skip:hover {
  color: var(--spark-text);
}

/* 过渡动画 */
.onboarding-tooltip-enter-active {
  transition: opacity 0.3s ease, transform 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.onboarding-tooltip-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.onboarding-tooltip-enter-from {
  opacity: 0;
  transform: translateX(-50%) translateY(8px) scale(0.95);
}

.onboarding-tooltip-leave-to {
  opacity: 0;
  transform: translateX(-50%) translateY(-4px) scale(0.98);
}

/* center 模式的过渡 */
.placement-center.onboarding-tooltip-enter-from {
  transform: translate(-50%, -50%) scale(0.9);
}

.placement-center.onboarding-tooltip-leave-to {
  transform: translate(-50%, -50%) scale(0.95);
}

/* left/right 模式的过渡 */
.placement-left.onboarding-tooltip-enter-from,
.placement-right.onboarding-tooltip-enter-from {
  opacity: 0;
  transform: translateY(0) scale(0.95);
}

.placement-left.onboarding-tooltip-leave-to,
.placement-right.onboarding-tooltip-leave-to {
  opacity: 0;
  transform: translateY(0) scale(0.98);
}
</style>
