<!--
  第 3 幕 · Ch. 03 · Pipeline · 剧本工业流水线
  - pin 钉屏 + scrub 横向推进 · GSAP ScrollTrigger
  - 展开 6 个工序站 · 印章逐站盖下 · 工单随进度更新
-->
<template>
  <section id="act-pipeline" class="act act-pipeline" ref="rootRef">
    <div class="pipeline-pin" ref="pinRef">
      <!-- 标题（固定在顶部） -->
      <div class="pipeline-head">
        <div class="head-left">
          <span class="act-chapter-mark">{{ pipeline.chapterMark }}</span>
          <h2 class="pipeline-title act-title">{{ pipeline.title }}</h2>
          <p class="pipeline-subtitle">{{ pipeline.subtitle }}</p>
        </div>
        <div class="head-right">
          <span class="progress-label">{{ progressLabel }}</span>
          <div class="progress-track">
            <div class="progress-fill" :style="{ width: `${progress * 100}%` }"></div>
          </div>
        </div>
      </div>

      <!-- 传送带（水平推进） -->
      <div class="conveyor-viewport">
        <div class="conveyor-inner" :style="{ transform: `translateX(${-conveyorX}px)` }">
          <PipelineConveyor :progress="progress" />
        </div>
      </div>

      <!-- 底部文案（progress 接近 1 时显示） -->
      <div class="pipeline-tail" :class="{ 'is-visible': progress > 0.85 }">
        <h3 class="tail-title">{{ pipeline.tail.title }}</h3>
        <p class="tail-body">{{ pipeline.tail.body }}</p>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import PipelineConveyor from './visuals/PipelineConveyor.vue';
import { pipeline } from '../homeContent';

gsap.registerPlugin(ScrollTrigger);

const rootRef = ref<HTMLElement | null>(null);
const pinRef = ref<HTMLElement | null>(null);

/** 0~1 · pin 进度 */
const progress = ref(0);
/** 传送带 x 位移（px） */
const conveyorX = ref(0);

const progressLabel = computed(() => {
  const idx = Math.min(pipeline.stations.length - 1, Math.floor(progress.value * pipeline.stations.length));
  const s = pipeline.stations[idx];
  return `当前工序 · ${s.idx} ${s.zh}`;
});

let trigger: ScrollTrigger | null = null;
let reducedMotion = false;

function onProgress(p: number) {
  progress.value = p;
  // 传送带横向移动：首站居中起，最后一站居中止
  // 总宽度估算：6 站 × (340 + 64 gap) ≈ 2424px，viewport ~1200px
  const conveyorEl = pinRef.value?.querySelector<HTMLElement>('.conveyor');
  const viewportEl = pinRef.value?.querySelector<HTMLElement>('.conveyor-viewport');
  if (!conveyorEl || !viewportEl) return;
  const totalW = conveyorEl.scrollWidth;
  const vw = viewportEl.clientWidth;
  const maxShift = Math.max(0, totalW - vw + 80);
  conveyorX.value = p * maxShift;
}

onMounted(() => {
  if (!rootRef.value || !pinRef.value) return;

  const mq = window.matchMedia('(prefers-reduced-motion: reduce)');
  reducedMotion = mq.matches;

  const scroller = document.querySelector<HTMLElement>('.product-home');
  if (!scroller) return;

  // 降级：reduce-motion 时不 pin，静态铺开
  if (reducedMotion) {
    progress.value = 1;
    onProgress(1);
    return;
  }

  trigger = ScrollTrigger.create({
    trigger: rootRef.value,
    scroller,
    pin: pinRef.value,
    start: 'top top',
    end: '+=260%',
    scrub: 0.8,
    onUpdate: (self) => onProgress(self.progress),
    invalidateOnRefresh: true,
  });

  // 首次强制 refresh（父容器是 fixed，ScrollTrigger 有时检测尺寸不准）
  setTimeout(() => ScrollTrigger.refresh(), 60);
});

onBeforeUnmount(() => {
  trigger?.kill();
});
</script>

<style scoped>
.act-pipeline {
  position: relative;
  min-height: 360vh; /* 占位给 pin 用 */
  padding: 0;
}
.pipeline-pin {
  position: relative;
  width: 100%;
  height: 100vh;
  overflow: hidden;
  padding: 6rem 0 4rem;
  display: flex;
  flex-direction: column;
  gap: 2rem;
  box-sizing: border-box;
}

/* 标题区域 */
.pipeline-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  padding: 0 6vw;
  gap: 2rem;
  flex-wrap: wrap;
}
.head-left {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  max-width: 640px;
}
.pipeline-title {
  font-size: clamp(1.8rem, 3.2vw, 2.8rem);
  margin: 0.4rem 0 0.25rem;
}
.pipeline-subtitle {
  font-family: var(--font-hand);
  font-size: 1.1rem;
  color: var(--ember-deep);
  margin: 0;
}

/* 进度条 */
.head-right {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  min-width: 240px;
}
.progress-label {
  font-family: var(--font-mono);
  font-size: 0.75rem;
  color: var(--ink-soft);
  letter-spacing: 0.18em;
  text-align: right;
}
.progress-track {
  position: relative;
  height: 6px;
  background: var(--paper-deep);
  border: 1px solid var(--ink-ghost);
  overflow: hidden;
}
.progress-fill {
  height: 100%;
  background: linear-gradient(to right, var(--ember), var(--gold));
  transition: width 120ms linear;
}

/* 传送带视口 */
.conveyor-viewport {
  flex: 1;
  width: 100%;
  overflow: hidden;
  position: relative;
}
.conveyor-inner {
  display: inline-block;
  height: 100%;
  will-change: transform;
  transition: transform 80ms linear;
}

/* 底部文案 */
.pipeline-tail {
  text-align: center;
  padding: 0 6vw;
  opacity: 0;
  transform: translateY(12px);
  transition: opacity 500ms ease, transform 500ms ease;
}
.pipeline-tail.is-visible {
  opacity: 1;
  transform: none;
}
.tail-title {
  font-family: var(--font-display);
  font-size: 1.6rem;
  color: var(--ink);
  margin: 0 0 0.4rem;
  letter-spacing: 0.1em;
}
.tail-body {
  font-family: var(--font-hand);
  font-size: 1.1rem;
  color: var(--ember-deep);
  margin: 0;
  line-height: 1.75;
  max-width: 720px;
  margin: 0 auto;
}

/* Reduced motion 降级：整个展开 */
@media (prefers-reduced-motion: reduce) {
  .act-pipeline { min-height: auto; }
  .pipeline-pin { height: auto; }
  .conveyor-inner { transform: none !important; }
  .conveyor-viewport { overflow-x: auto; }
}
</style>
