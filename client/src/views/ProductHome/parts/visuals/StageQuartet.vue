<!--
  StageQuartet · 四张明信片（手机 / MCP / WEB / Unity）
  - 错落排布、鼠标悬停微倾
-->
<template>
  <div class="stage-quartet">
    <article
      v-for="(c, i) in stage.cards"
      :key="c.key"
      class="card"
      :class="[`card-${c.key}`]"
      :style="{ '--i': i }"
    >
      <!-- 邮戳（左上） -->
      <div class="card-stamp">
        <span class="card-stamp-idx">{{ String(i + 1).padStart(2, '0') }}</span>
      </div>

      <!-- 图标 -->
      <div class="card-icon">
        <component :is="iconFor(c.key)" />
      </div>

      <!-- 主标题 + 副标 -->
      <h3 class="card-title">{{ c.title }}</h3>
      <p class="card-head">{{ c.head }}</p>

      <!-- 正文 -->
      <p class="card-body">{{ c.body }}</p>

      <!-- 装饰角 -->
      <div class="card-corner"></div>
    </article>
  </div>
</template>

<script setup lang="ts">
import { h } from 'vue';
import { stage } from '../../homeContent';

/** 四个 key 的内联 SVG 图标（零依赖） */
function iconFor(key: string) {
  const common = { width: '44', height: '44', viewBox: '0 0 48 48', fill: 'none' };
  switch (key) {
    case 'mobile':
      return () =>
        h('svg', common, [
          h('rect', { x: 14, y: 4, width: 20, height: 40, rx: 3, stroke: 'currentColor', 'stroke-width': 2 }),
          h('line', { x1: 20, y1: 38, x2: 28, y2: 38, stroke: 'currentColor', 'stroke-width': 2 }),
          h('line', { x1: 14, y1: 10, x2: 34, y2: 10, stroke: 'currentColor', 'stroke-width': 1.2, 'stroke-dasharray': '2 2' }),
        ]);
    case 'mcp':
      return () =>
        h('svg', common, [
          h('path', { d: 'M 4 24 L 44 24', stroke: 'currentColor', 'stroke-width': 2, 'stroke-linecap': 'round' }),
          h('circle', { cx: 10, cy: 24, r: 3, fill: 'currentColor' }),
          h('circle', { cx: 24, cy: 24, r: 5, stroke: 'currentColor', 'stroke-width': 2 }),
          h('circle', { cx: 38, cy: 24, r: 3, fill: 'currentColor' }),
          h('path', { d: 'M 24 6 L 24 18', stroke: 'currentColor', 'stroke-width': 2, 'stroke-dasharray': '2 2' }),
          h('path', { d: 'M 24 30 L 24 42', stroke: 'currentColor', 'stroke-width': 2, 'stroke-dasharray': '2 2' }),
        ]);
    case 'web':
      return () =>
        h('svg', common, [
          h('rect', { x: 6, y: 8, width: 36, height: 28, rx: 2, stroke: 'currentColor', 'stroke-width': 2 }),
          h('line', { x1: 6, y1: 16, x2: 42, y2: 16, stroke: 'currentColor', 'stroke-width': 1.4 }),
          h('circle', { cx: 10, cy: 12, r: 1, fill: 'currentColor' }),
          h('circle', { cx: 14, cy: 12, r: 1, fill: 'currentColor' }),
          h('circle', { cx: 18, cy: 12, r: 1, fill: 'currentColor' }),
          h('path', { d: 'M 14 24 L 20 28 L 14 32 Z', fill: 'currentColor' }),
          h('line', { x1: 22, y1: 24, x2: 34, y2: 24, stroke: 'currentColor', 'stroke-width': 1.4 }),
          h('line', { x1: 22, y1: 28, x2: 34, y2: 28, stroke: 'currentColor', 'stroke-width': 1.4 }),
          h('line', { x1: 22, y1: 32, x2: 30, y2: 32, stroke: 'currentColor', 'stroke-width': 1.4 }),
        ]);
    case 'unity':
      return () =>
        h('svg', common, [
          h('polygon', { points: '24,4 42,14 42,34 24,44 6,34 6,14', stroke: 'currentColor', 'stroke-width': 2, fill: 'none' }),
          h('polygon', { points: '24,14 34,19 34,29 24,34 14,29 14,19', stroke: 'currentColor', 'stroke-width': 1.5, fill: 'currentColor', 'fill-opacity': 0.2 }),
          h('line', { x1: 24, y1: 4, x2: 24, y2: 14, stroke: 'currentColor', 'stroke-width': 1 }),
        ]);
    default:
      return () => h('svg', common);
  }
}
</script>

<style scoped>
.stage-quartet {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 2.4rem;
  max-width: 1100px;
  margin: 0 auto;
}

/* 每张卡片错落微旋 */
.card {
  position: relative;
  padding: 2.5rem 2.2rem 2.2rem;
  background: var(--paper);
  border: 1px solid var(--ink);
  box-shadow: 4px 5px 0 var(--ink), 0 18px 40px rgba(42, 36, 32, 0.12);
  transition: transform 320ms ease, box-shadow 320ms ease;
  min-height: 240px;
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}
.card:nth-child(1) { transform: rotate(-1.2deg); }
.card:nth-child(2) { transform: rotate(0.8deg) translateY(-12px); }
.card:nth-child(3) { transform: rotate(1deg) translateY(14px); }
.card:nth-child(4) { transform: rotate(-0.8deg); }

.card:hover {
  transform: rotate(0) translateY(-4px);
  box-shadow: 2px 2px 0 var(--ink), 0 22px 48px rgba(42, 36, 32, 0.18);
}

/* 邮戳 */
.card-stamp {
  position: absolute;
  top: -14px;
  left: -14px;
  width: 44px;
  height: 44px;
  background: var(--crimson);
  color: var(--paper);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 10px rgba(184, 74, 63, 0.35);
  transform: rotate(-8deg);
  border: 2px solid rgba(255, 255, 255, 0.3);
}
.card-stamp-idx {
  font-family: var(--font-mono);
  font-size: 0.88rem;
  font-weight: 700;
  letter-spacing: 0.08em;
}

/* 图标 */
.card-icon {
  color: var(--ember);
  margin-bottom: 0.4rem;
  height: 54px;
  display: flex;
  align-items: center;
}

/* 文本 */
.card-title {
  font-family: var(--font-display);
  font-size: 1.4rem;
  color: var(--ink);
  letter-spacing: 0.08em;
  margin: 0;
}
.card-head {
  font-family: var(--font-hand);
  font-size: 1rem;
  color: var(--ember-deep);
  margin: 0 0 0.4rem;
}
.card-body {
  margin: 0;
  font-size: 0.95rem;
  color: var(--ink-soft);
  line-height: 1.85;
  flex: 1;
}

/* 装饰角 */
.card-corner {
  position: absolute;
  bottom: 0;
  right: 0;
  width: 28px;
  height: 28px;
  background: linear-gradient(135deg, transparent 50%, var(--paper-deep) 50%);
  border-top: 1px solid var(--ink-ghost);
  border-left: 1px solid var(--ink-ghost);
}

@media (max-width: 760px) {
  .stage-quartet { grid-template-columns: 1fr; gap: 1.8rem; }
  .card { transform: none !important; }
}
</style>
