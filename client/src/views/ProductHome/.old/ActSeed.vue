<!--
  第 1 幕 · Ch. 01 · Seed · 一个灵感的重量
  - 左侧手写便签（逐行浮现）
  - 右侧灵感信箱 SVG + 四条飞入粒子线
  - 大标 + 说明段
-->
<template>
  <section id="act-seed" class="act act-seed">
    <div class="act-head">
      <span class="act-chapter-mark">{{ seed.chapterMark }}</span>
    </div>

    <div class="seed-grid">
      <!-- 左：手写便签 -->
      <div ref="noteRef" class="seed-note">
        <div class="note-paper">
          <div class="note-clip"></div>
          <p
            v-for="(line, i) in seed.noteLines"
            :key="i"
            class="note-line fade-up"
            :style="{ transitionDelay: `${i * 0.18}s` }"
          >{{ line }}</p>
          <div class="note-folded"></div>
        </div>
      </div>

      <!-- 右：灵感信箱 + 四条飞入线 -->
      <div ref="mailboxRef" class="seed-mailbox">
        <svg viewBox="0 0 420 420" class="mailbox-svg">
          <defs>
            <!-- 飞入粒子 -->
            <radialGradient id="spark-ball" cx="50%" cy="50%" r="50%">
              <stop offset="0%" stop-color="var(--ember)" stop-opacity="1" />
              <stop offset="100%" stop-color="var(--ember)" stop-opacity="0" />
            </radialGradient>
            <filter id="soft-shadow" x="-50%" y="-50%" width="200%" height="200%">
              <feDropShadow dx="0" dy="2" stdDeviation="2" flood-color="rgba(42,36,32,0.2)" />
            </filter>
          </defs>

          <!-- 信箱 -->
          <g transform="translate(210 230)" filter="url(#soft-shadow)" class="mailbox-body">
            <!-- 信箱主体 -->
            <rect x="-80" y="-50" width="160" height="110" rx="6" fill="var(--paper)" stroke="var(--ink)" stroke-width="2" />
            <!-- 投递口 -->
            <rect x="-50" y="-35" width="100" height="10" rx="2" fill="var(--ink)" />
            <!-- 信箱顶棚 -->
            <path d="M -88 -50 L 88 -50 L 72 -70 L -72 -70 Z" fill="var(--ember-deep)" stroke="var(--ink)" stroke-width="2" />
            <!-- 标签牌 -->
            <rect x="-46" y="15" width="92" height="32" rx="2" fill="var(--paper-deep)" stroke="var(--ink)" stroke-width="1.2" />
            <text x="0" y="36" text-anchor="middle" class="mailbox-label">{{ seed.mailboxLabel }}</text>
            <!-- 火漆印 -->
            <circle cx="56" cy="-20" r="10" fill="var(--crimson)" opacity="0.85" />
            <text x="56" y="-16" text-anchor="middle" class="wax-text">S</text>
          </g>

          <!-- 四条飞入线 + 粒子 -->
          <g class="flight-lines">
            <g v-for="(src, i) in seed.sources" :key="src.label" :style="{ '--i': i }" class="flight">
              <path
                :d="flightPath(i)"
                fill="none"
                stroke="var(--ember)"
                stroke-width="1"
                stroke-dasharray="3 5"
                opacity="0.45"
              />
              <circle r="5" fill="url(#spark-ball)" class="flight-ball">
                <animateMotion :dur="`${3.6 + i * 0.4}s`" repeatCount="indefinite" rotate="auto">
                  <mpath :href="`#flight-path-${i}`" />
                </animateMotion>
              </circle>
              <path :id="`flight-path-${i}`" :d="flightPath(i)" fill="none" stroke="none" />
              <text
                :x="sourceLabelPos(i).x"
                :y="sourceLabelPos(i).y"
                :text-anchor="sourceLabelPos(i).anchor"
                class="source-label"
              >{{ src.label }}</text>
              <text
                :x="sourceLabelPos(i).x"
                :y="sourceLabelPos(i).y + 14"
                :text-anchor="sourceLabelPos(i).anchor"
                class="source-detail"
              >{{ src.detail }}</text>
            </g>
          </g>
        </svg>
      </div>
    </div>

    <!-- 主标题 + 说明 -->
    <div class="seed-copy">
      <h2 class="seed-title act-title fade-up">
        {{ seed.title }}
      </h2>
      <p class="seed-subtitle fade-up" style="transition-delay: 0.1s;">
        {{ seed.subtitle }}
      </p>

      <div class="seed-explainer fade-up" style="transition-delay: 0.2s;">
        <p v-for="(line, i) in seed.explainer" :key="i">{{ line }}</p>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue';
import { seed } from '../homeContent';

const noteRef = ref<HTMLElement | null>(null);
const mailboxRef = ref<HTMLElement | null>(null);

/* ---------- 飞入线路径：四条曲线从四象限流向中心信箱(210,230) ---------- */
const entries = [
  { sx: 40, sy: 60 },   // 左上
  { sx: 380, sy: 60 },  // 右上
  { sx: 40, sy: 360 },  // 左下
  { sx: 380, sy: 360 }, // 右下
];
function flightPath(i: number): string {
  const start = entries[i];
  const cx = (start.sx + 210) / 2;
  const cy = (start.sy + 230) / 2 + (i < 2 ? -40 : 40);
  return `M ${start.sx} ${start.sy} Q ${cx} ${cy} 210 215`;
}
function sourceLabelPos(i: number) {
  const pos = entries[i];
  const anchor = pos.sx < 210 ? 'start' : 'end';
  const dx = anchor === 'start' ? 6 : -6;
  return { x: pos.sx + dx, y: pos.sy - 10, anchor };
}

/* ---------- IntersectionObserver 进场 ---------- */
let observer: IntersectionObserver | null = null;
onMounted(() => {
  observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((e) => {
        if (e.isIntersecting) e.target.classList.add('is-visible');
      });
    },
    { threshold: 0.15 }
  );
  document.querySelectorAll('#act-seed .fade-up').forEach((el) => observer?.observe(el));
});
onBeforeUnmount(() => observer?.disconnect());
</script>

<style scoped>
.act-seed {
  min-height: 100vh;
  padding: 6rem 6vw;
  position: relative;
  max-width: 1440px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 4rem;
}
.act-head {
  display: flex;
  justify-content: flex-start;
}

/* 主 grid：左便签 · 右信箱 */
.seed-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 4rem;
  align-items: center;
}

/* 左：手写便签纸 */
.seed-note {
  display: flex;
  justify-content: center;
}
.note-paper {
  position: relative;
  width: min(100%, 460px);
  padding: 3.5rem 2.5rem 3rem;
  background: var(--paper);
  box-shadow: 2px 4px 16px rgba(42, 36, 32, 0.15), 0 0 0 1px var(--ink-ghost);
  transform: rotate(-1.6deg);
  min-height: 360px;
}
.note-paper::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 28px;
  background: repeating-linear-gradient(
    90deg,
    var(--paper-deep) 0 14px,
    transparent 14px 28px
  );
  opacity: 0.5;
}
.note-clip {
  position: absolute;
  top: -18px;
  left: 50%;
  transform: translateX(-50%);
  width: 58px;
  height: 36px;
  background: var(--ink);
  border-radius: 4px 4px 14px 14px;
  box-shadow: 0 4px 8px rgba(42, 36, 32, 0.3);
}
.note-clip::before {
  content: '';
  position: absolute;
  inset: 6px;
  background: var(--paper);
  border-radius: 2px 2px 10px 10px;
}
.note-line {
  font-family: var(--font-hand);
  font-size: 1.18rem;
  color: var(--ink);
  line-height: 1.9;
  margin: 0;
  border-bottom: 1px dashed var(--ink-ghost);
  padding: 0.35rem 0;
}
.note-folded {
  position: absolute;
  bottom: 0;
  right: 0;
  width: 38px;
  height: 38px;
  background: linear-gradient(135deg, transparent 50%, var(--paper-deep) 50%);
  border-left: 1px solid var(--ink-ghost);
  border-top: 1px solid var(--ink-ghost);
}

/* 右：信箱 SVG */
.seed-mailbox {
  width: 100%;
  max-width: 500px;
  aspect-ratio: 1 / 1;
  margin: 0 auto;
}
.mailbox-svg {
  width: 100%;
  height: 100%;
}
.mailbox-body {
  animation: breathe-scale 4.2s ease-in-out infinite;
  transform-origin: center;
}
@keyframes breathe-scale {
  0%, 100% { transform: translate(210px, 230px) scale(1); }
  50% { transform: translate(210px, 230px) scale(1.025); }
}
.mailbox-label {
  font-family: var(--font-display);
  font-size: 16px;
  fill: var(--ink);
  letter-spacing: 0.2em;
}
.wax-text {
  font-family: var(--font-display);
  font-size: 10px;
  fill: var(--paper);
  font-weight: 700;
}
.source-label {
  font-family: var(--font-display);
  font-size: 15px;
  fill: var(--ink);
  letter-spacing: 0.1em;
}
.source-detail {
  font-family: var(--font-hand);
  font-size: 12px;
  fill: var(--ink-soft);
}

/* 主标 + 说明 */
.seed-copy {
  max-width: 900px;
  margin: 0 auto;
  text-align: center;
}
.seed-title {
  font-size: clamp(2rem, 3.6vw, 3.2rem);
  margin: 0 0 1rem;
}
.seed-subtitle {
  font-family: var(--font-hand);
  font-size: 1.25rem;
  color: var(--ember-deep);
  margin: 0 0 2.5rem;
}
.seed-explainer {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  max-width: 640px;
  margin: 0 auto;
  padding: 1.4rem 1.8rem;
  background: rgba(250, 246, 238, 0.7);
  border-left: 2px solid var(--ember);
  text-align: left;
}
.seed-explainer p {
  margin: 0;
  color: var(--ink-soft);
  font-size: 1.02rem;
  line-height: 1.9;
}

@media (max-width: 900px) {
  .seed-grid {
    grid-template-columns: 1fr;
    gap: 2rem;
  }
  .note-paper { transform: none; padding: 2.5rem 2rem; }
}
</style>
