<template>
  <!-- 移动端欢迎场景：竖屏品牌动画 -->
  <Teleport to="body">
    <transition name="mobile-welcome">
      <div v-if="visible" ref="sceneRoot" class="mobile-welcome-scene">
        <!-- 背景 -->
        <div class="welcome-bg" />

        <!-- 中心内容 -->
        <div class="welcome-content">
          <!-- Logo 火花 -->
          <div ref="logoEl" class="welcome-logo">
            <svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg" class="logo-svg">
              <path
                ref="sparkMain"
                d="M32 4L38 24L58 32L38 40L32 60L26 40L6 32L26 24L32 4Z"
                stroke="currentColor"
                stroke-width="2.5"
                stroke-linecap="round"
                stroke-linejoin="round"
                class="spark-main-path"
              />
              <path
                ref="sparkSub1"
                d="M50 4L53 13L62 16L53 19L50 28L47 19L38 16L47 13L50 4Z"
                stroke="currentColor"
                stroke-width="1.5"
                stroke-linecap="round"
                class="spark-sub-path"
              />
            </svg>
          </div>

          <!-- 品牌名 -->
          <h1 ref="titleEl" class="welcome-title">{{ t('onboarding.mobile.welcome.title') }}</h1>

          <!-- 副标题 -->
          <p ref="subtitleEl" class="welcome-subtitle">{{ t('onboarding.mobile.welcome.subtitle') }}</p>

          <!-- 向下刷手势暗示 -->
          <div ref="swipeHintEl" class="swipe-hint">
            <div class="swipe-hand">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round">
                <path d="M12 4v16m0 0l-4-4m4 4l4-4" />
              </svg>
            </div>
            <span class="swipe-text">{{ t('onboarding.mobile.welcome.swipeHint') }}</span>
          </div>
        </div>
      </div>
    </transition>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, onUnmounted } from 'vue';
import { useI18n } from 'vue-i18n';
import gsap from 'gsap';
import { gsapStrokeDraw, gsapSlideUp, gsapFadeIn, gsapParticleBurst } from '../../animations/gsapPresets';

const { t } = useI18n();

const visible = ref(false);
const sceneRoot = ref<HTMLElement | null>(null);
const logoEl = ref<HTMLElement | null>(null);
const sparkMain = ref<SVGPathElement | null>(null);
const sparkSub1 = ref<SVGPathElement | null>(null);
const titleEl = ref<HTMLElement | null>(null);
const subtitleEl = ref<HTMLElement | null>(null);
const swipeHintEl = ref<HTMLElement | null>(null);

const emit = defineEmits<{
  (e: 'complete'): void;
}>();

let mainTimeline: gsap.core.Timeline | null = null;

function playAnimation(): void {
  if (!logoEl.value || !titleEl.value || !subtitleEl.value || !swipeHintEl.value) return;

  mainTimeline = gsap.timeline();

  // 1. Logo 描边 + 填充
  if (sparkMain.value) {
    mainTimeline.add(gsapStrokeDraw(sparkMain.value, 1, 0), 0);
  }
  if (sparkSub1.value) {
    mainTimeline.add(gsapStrokeDraw(sparkSub1.value, 0.5, 0.3), 0);
  }

  // 读取 CSS 变量获取主题色
  const primaryColor = getComputedStyle(document.body).getPropertyValue('--spark-primary').trim() || '#7aa2f7';
  mainTimeline.to(logoEl.value, { color: primaryColor, duration: 0.4 }, 0.8);

  // 粒子
  mainTimeline.call(() => {
    if (logoEl.value) gsapParticleBurst(logoEl.value, 10, primaryColor, 0.6);
  }, [], 1);

  // 2. 标题
  mainTimeline.add(gsapSlideUp(titleEl.value, 16, 0.5, 1.2), 1.2);

  // 3. 副标题
  mainTimeline.add(gsapFadeIn(subtitleEl.value, 0.4, 1.6), 1.6);

  // 4. 手势暗示（循环动画）
  mainTimeline.add(gsapFadeIn(swipeHintEl.value, 0.4, 2), 2);
  // 手指上下循环
  const hand = swipeHintEl.value.querySelector('.swipe-hand');
  if (hand) {
    mainTimeline.to(hand, {
      y: 12,
      duration: 0.8,
      ease: 'sine.inOut',
      repeat: -1,
      yoyo: true,
    }, 2.4);
  }
}

function show(): void {
  visible.value = true;
  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      playAnimation();
    });
  });
}

function hide(): void {
  if (sceneRoot.value) {
    gsap.to(sceneRoot.value, {
      opacity: 0,
      duration: 0.3,
      ease: 'power2.in',
      onComplete: () => {
        visible.value = false;
        emit('complete');
      },
    });
  } else {
    visible.value = false;
  }
  mainTimeline?.kill();
}

defineExpose({ show, hide });

onUnmounted(() => {
  mainTimeline?.kill();
});
</script>

<style scoped>
.mobile-welcome-scene {
  position: fixed;
  inset: 0;
  z-index: 20000;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

.welcome-bg {
  position: absolute;
  inset: 0;
  background: radial-gradient(ellipse at center, color-mix(in srgb, var(--spark-primary), transparent 94%) 0%, var(--spark-bg) 70%);
}

.welcome-content {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  padding: 32px 24px;
  text-align: center;
}

.welcome-logo {
  color: transparent;
  position: relative;
}

.logo-svg {
  width: 64px;
  height: 64px;
}

.spark-main-path,
.spark-sub-path {
  fill: none;
}

.welcome-title {
  font-size: 2rem;
  font-weight: 800;
  color: var(--spark-text);
  margin: 0;
  letter-spacing: 2px;
  font-family: 'Outfit', 'Microsoft YaHei', 'PingFang SC', sans-serif;
}

.welcome-subtitle {
  font-size: 1rem;
  color: var(--spark-primary);
  margin: 0;
}

.swipe-hint {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  margin-top: 24px;
}

.swipe-hand {
  color: var(--spark-primary);
  width: 32px;
  height: 32px;
}

.swipe-hand svg {
  width: 100%;
  height: 100%;
}

.swipe-text {
  font-size: var(--spark-fs-sm);
  color: var(--spark-text-muted);
}

/* 过渡 */
.mobile-welcome-enter-active {
  transition: opacity 0.4s ease;
}

.mobile-welcome-leave-active {
  transition: opacity 0.3s ease;
}

.mobile-welcome-enter-from,
.mobile-welcome-leave-to {
  opacity: 0;
}
</style>
