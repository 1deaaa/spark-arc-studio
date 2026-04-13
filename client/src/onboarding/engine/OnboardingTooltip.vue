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
import { computed, ref, watch, nextTick, type StyleValue } from 'vue';
import { useI18n } from 'vue-i18n';
import { getOnboardingEngine } from './OnboardingEngine';

const engine = getOnboardingEngine();
const { t } = useI18n();
const tooltipEl = ref<HTMLElement | null>(null);

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
    };
  }
  // 找不到目标元素时回退到 center 模式
  if (!rect) {
    return {
      position: 'fixed',
      top: '50%',
      left: '50%',
      transform: 'translate(-50%, -50%)',
    };
  }

  const gap = 16;
  let top = 0;
  let left = 0;

  switch (step.placement) {
    case 'bottom':
      top = rect.bottom + gap;
      left = rect.left + rect.width / 2;
      break;
    case 'top':
      top = rect.top - gap;
      left = rect.left + rect.width / 2;
      break;
    case 'right':
      top = rect.top + rect.height / 2;
      left = rect.right + gap;
      break;
    case 'left':
      top = rect.top + rect.height / 2;
      left = rect.left - gap;
      break;
  }

  const style: Record<string, string> = { position: 'fixed' };

  if (step.placement === 'top' || step.placement === 'bottom') {
    style.left = `${Math.max(16, Math.min(left, window.innerWidth - 280))}px`;
    style.transform = 'translateX(-50%)';
    style.top = step.placement === 'bottom' ? `${top}px` : 'auto';
    style.bottom = step.placement === 'top' ? `${window.innerHeight - top}px` : 'auto';
  } else {
    // 估算 Tooltip 高度约 200px，约束 top 不超出视口
    const tooltipH = 200;
    const clampedTop = Math.max(16, Math.min(top, window.innerHeight - tooltipH));
    style.top = `${clampedTop}px`;
    style.transform = 'translateY(0)';
    style.left = step.placement === 'right' ? `${left}px` : 'auto';
    style.right = step.placement === 'left' ? `${window.innerWidth - left}px` : 'auto';
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
  min-width: 240px;
  max-width: 360px;
  background: var(--spark-panel-bg, var(--n-color-modal, #1e1e1e));
  border: 1px solid var(--spark-border);
  border-radius: 12px;
  box-shadow: var(--spark-shadow), 0 0 0 1px var(--spark-primary) inset;
  padding: 20px;
  pointer-events: auto;
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
  font-size: 16px;
  font-weight: 700;
  color: var(--spark-text);
  margin: 0 0 8px;
}

.tooltip-desc {
  font-size: 13px;
  color: var(--spark-text-muted);
  line-height: 1.5;
  margin: 0;
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
  font-size: 13px;
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
</style>
