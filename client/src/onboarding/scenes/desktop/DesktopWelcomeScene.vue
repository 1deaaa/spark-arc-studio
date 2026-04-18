<template>
  <!-- 桌面端欢迎场景：品牌动画 + 产品理念 -->
  <Teleport to="body">
    <transition name="welcome-scene">
      <div v-if="visible" ref="sceneRoot" class="desktop-welcome-scene">
        <!-- 背景渐变 -->
        <div class="welcome-bg" />

        <!-- 中心内容 -->
        <div class="welcome-content">
          <!-- Logo 火花动画 -->
          <div ref="logoEl" class="welcome-logo">
            <svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg" class="logo-svg">
              <path
                ref="sparkMain"
                d="M32 4L38 24L58 32L38 40L32 60L26 40L6 32L26 24L32 4Z"
                stroke="currentColor"
                stroke-width="2"
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
              <path
                ref="sparkSub2"
                d="M14 44L16 50L22 52L16 54L14 60L12 54L6 52L12 50L14 44Z"
                stroke="currentColor"
                stroke-width="1.5"
                stroke-linecap="round"
                class="spark-sub-path"
              />
            </svg>
          </div>

          <!-- 标题 -->
          <h1 ref="titleEl" class="welcome-title">{{ t('onboarding.desktop.welcome.title') }}</h1>

          <!-- 副标题 -->
          <p ref="subtitleEl" class="welcome-subtitle">{{ t('onboarding.desktop.welcome.subtitle') }}</p>

          <!-- Agent 团队图标 -->
          <div ref="agentTeamEl" class="agent-team">
            <div v-for="agent in agents" :key="agent.id" class="agent-badge">
              <n-icon size="28" :color="agent.color">
                <component :is="agent.icon" />
              </n-icon>
              <span class="agent-name">{{ agent.name }}</span>
            </div>
          </div>

          <!-- 流水线 -->
          <div ref="flowLineEl" class="flow-line">
            <span class="flow-text">{{ t('onboarding.desktop.welcome.flowLine') }}</span>
          </div>

          <!-- CTA 按钮 -->
          <button ref="ctaEl" class="welcome-cta" @click="onStart">
            {{ t('onboarding.desktop.welcome.startCta') }}
          </button>
        </div>
      </div>
    </transition>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, markRaw } from 'vue';
import { NIcon } from 'naive-ui';
import { useI18n } from 'vue-i18n';
import gsap from 'gsap';
import {
  BulbOutline,
  PlanetOutline,
  PulseOutline,
  ListOutline,
  CreateOutline,
  EyeOutline,
} from '@vicons/ionicons5';
import { gsapStrokeDraw, gsapFadeIn, gsapSlideUp, gsapStaggerIn, gsapParticleBurst } from '../../animations/gsapPresets';

const { t } = useI18n();

const visible = ref(false);
const sceneRoot = ref<HTMLElement | null>(null);
const logoEl = ref<HTMLElement | null>(null);
const sparkMain = ref<SVGPathElement | null>(null);
const sparkSub1 = ref<SVGPathElement | null>(null);
const sparkSub2 = ref<SVGPathElement | null>(null);
const titleEl = ref<HTMLElement | null>(null);
const subtitleEl = ref<HTMLElement | null>(null);
const agentTeamEl = ref<HTMLElement | null>(null);
const flowLineEl = ref<HTMLElement | null>(null);
const ctaEl = ref<HTMLElement | null>(null);

const emit = defineEmits<{
  (e: 'start'): void;
  (e: 'complete'): void;
}>();

const agents = [
  { id: 'director', name: '导演', icon: markRaw(BulbOutline), color: '#ffaa40' },
  { id: 'muse', name: '灵感', icon: markRaw(BulbOutline), color: '#ff6b6b' },
  { id: 'lorebook', name: '设定', icon: markRaw(PlanetOutline), color: '#40c9ff' },
  { id: 'showrunner', name: '策划', icon: markRaw(PulseOutline), color: '#52c41a' },
  { id: 'scriptwriter', name: '编剧', icon: markRaw(CreateOutline), color: '#b37feb' },
  { id: 'critic', name: '评审', icon: markRaw(EyeOutline), color: '#ffc53d' },
];

let mainTimeline: gsap.core.Timeline | null = null;

function playAnimation(): void {
  if (!logoEl.value || !titleEl.value || !subtitleEl.value || !agentTeamEl.value || !flowLineEl.value || !ctaEl.value) return;

  mainTimeline = gsap.timeline();

  // 1. Logo 火花描边动画
  if (sparkMain.value) {
    mainTimeline.add(gsapStrokeDraw(sparkMain.value, 1, 0), 0);
  }
  if (sparkSub1.value) {
    mainTimeline.add(gsapStrokeDraw(sparkSub1.value, 0.6, 0.3), 0);
  }
  if (sparkSub2.value) {
    mainTimeline.add(gsapStrokeDraw(sparkSub2.value, 0.6, 0.5), 0);
  }

  // Logo 填充色渐变（读取 CSS 变量）
  const primaryColor = getComputedStyle(document.body).getPropertyValue('--spark-primary').trim() || '#7aa2f7';
  mainTimeline.to(logoEl.value, { color: primaryColor, duration: 0.5 }, 1);

  // 粒子扩散
  mainTimeline.call(() => {
    if (logoEl.value) gsapParticleBurst(logoEl.value, 16, primaryColor, 0.8);
  }, [], 1.2);

  // 2. 标题淡入
  mainTimeline.add(gsapSlideUp(titleEl.value, 20, 0.6, 1.4), 1.4);

  // 3. 副标题淡入
  mainTimeline.add(gsapFadeIn(subtitleEl.value, 0.5, 1.8), 1.8);

  // 4. Agent 团队依次入场
  const badges = agentTeamEl.value.querySelectorAll('.agent-badge');
  mainTimeline.add(gsapStaggerIn(Array.from(badges) as HTMLElement[], 0.12, 0.4, 2.2), 2.2);

  // 5. 流水线淡入
  mainTimeline.add(gsapFadeIn(flowLineEl.value, 0.5, 3.2), 3.2);

  // 6. CTA 按钮弹入
  mainTimeline.fromTo(ctaEl.value,
    { opacity: 0, scale: 0.8 },
    { opacity: 1, scale: 1, duration: 0.5, ease: 'back.out(1.7)', delay: 3.6 },
    3.6
  );
}

function onStart(): void {
  if (mainTimeline) {
    mainTimeline.kill();
  }
  // 退场动画
  if (sceneRoot.value) {
    gsap.to(sceneRoot.value, {
      opacity: 0,
      scale: 1.05,
      duration: 0.4,
      ease: 'power2.in',
      onComplete: () => {
        visible.value = false;
        emit('complete');
      },
    });
  } else {
    visible.value = false;
    emit('complete');
  }
}

function show(): void {
  visible.value = true;
  // 等待 DOM 渲染后播放动画
  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      playAnimation();
    });
  });
}

function hide(): void {
  visible.value = false;
  mainTimeline?.kill();
}

defineExpose({ show, hide });

onUnmounted(() => {
  mainTimeline?.kill();
});
</script>

<style scoped>
.desktop-welcome-scene {
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
  background: radial-gradient(ellipse at center, color-mix(in srgb, var(--spark-primary), transparent 92%) 0%, var(--spark-bg) 70%);
}

.welcome-content {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 20px;
  padding: 40px;
  text-align: center;
}

.welcome-logo {
  color: transparent;
  position: relative;
}

.logo-svg {
  width: 80px;
  height: 80px;
}

.spark-main-path,
.spark-sub-path {
  fill: none;
}

.welcome-title {
  font-size: 2.5rem;
  font-weight: 800;
  color: var(--spark-text);
  margin: 0;
  letter-spacing: -0.5px;
  font-family: var(--spark-font), 'Outfit', sans-serif;
}

.welcome-subtitle {
  font-size: 1.2rem;
  color: var(--spark-primary);
  margin: 0;
  max-width: 500px;
}

.agent-team {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
  justify-content: center;
  margin-top: 8px;
}

.agent-badge {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 8px 12px;
  border-radius: 10px;
  background: color-mix(in srgb, var(--spark-text), transparent 95%);
  border: 1px solid var(--spark-border);
}

.agent-name {
  font-size: var(--spark-fs-2xs);
  color: var(--spark-text-muted);
}

.flow-line {
  margin-top: 4px;
}

.flow-text {
  font-size: var(--spark-fs-sm);
  color: var(--spark-text-muted);
  letter-spacing: 1px;
}

.welcome-cta {
  margin-top: 12px;
  padding: 12px 36px;
  background: var(--spark-primary);
  color: var(--spark-text-inverse);
  border: none;
  border-radius: 24px;
  font-size: 1rem;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.3s ease;
  letter-spacing: 1px;
}

.welcome-cta:hover {
  transform: translateY(-2px);
  box-shadow: 0 0 30px color-mix(in srgb, var(--spark-primary), transparent 50%);
}

/* 场景过渡 */
.welcome-scene-enter-active {
  transition: opacity 0.5s ease;
}

.welcome-scene-leave-active {
  transition: opacity 0.3s ease;
}

.welcome-scene-enter-from,
.welcome-scene-leave-to {
  opacity: 0;
}
</style>
