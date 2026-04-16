<!--
  PipelineConveyor · 剧本工业流水线传送带
  - 6 个工序站：印章 / 英文 / 好莱坞对应 / 中文说明 / 工作描述
  - 站间虚线传送带 + 流动粒子（CSS keyframes）
  - 第 6 站 Critic 回弹循环（深红色粒子反向）
  - 父组件通过 `progress` prop（0~1）控制各站盖章时机与当前高亮
-->
<template>
  <div class="conveyor" :class="{ 'is-mounted': true }">
    <div class="track">
      <!-- 背景传送带：两条平行线 + 流动粒子 -->
      <div class="rail rail-top"></div>
      <div class="rail rail-bottom"></div>
      <div class="particles">
        <span v-for="n in 18" :key="n" class="particle" :style="{ left: `${(n / 18) * 100}%`, animationDelay: `${-(n * 0.4)}s` }"></span>
      </div>

      <!-- 六个工序站 -->
      <div
        v-for="(s, i) in pipeline.stations"
        :key="s.idx"
        class="station"
        :class="{ 'is-stamped': i < currentStamp, 'is-current': i === currentStamp, 'is-critic': i === 5 }"
      >
        <!-- 好莱坞对应（英文小字，顶端） -->
        <div class="station-hollywood">{{ s.hollywood }}</div>

        <!-- 印章 -->
        <div class="station-stamp">
          <div class="stamp-ring">
            <span class="stamp-idx">{{ s.idx }}</span>
            <span class="stamp-zh">{{ s.zh }}</span>
          </div>
          <div class="stamp-en">{{ s.en }}</div>
          <!-- 印章下落时的墨晕 -->
          <div class="stamp-ink"></div>
        </div>

        <!-- 说明文字 -->
        <div class="station-desc">
          <p class="desc-main">{{ s.desc }}</p>
          <p class="desc-work">{{ s.work }}</p>
        </div>
      </div>

      <!-- Critic 回弹循环指示 -->
      <div class="critic-loop" aria-hidden="true">
        <svg viewBox="0 0 200 80" preserveAspectRatio="none" width="200" height="60">
          <path
            d="M 10 40 C 10 10, 100 10, 100 40 C 100 70, 190 70, 190 40"
            fill="none"
            stroke="var(--crimson)"
            stroke-width="1.5"
            stroke-dasharray="4 4"
          />
          <polygon points="185,36 192,40 185,44" fill="var(--crimson)" />
        </svg>
        <span class="critic-loop-label">B/C/D 带工单 · 回站 05</span>
      </div>
    </div>

    <!-- 悬浮工单纸片（随 progress 切换字段） -->
    <div class="work-card" :class="{ 'is-active': currentStamp >= 2 }">
      <div class="work-card-head">
        <span class="work-card-title">{{ pipeline.workCard.title }}</span>
        <span class="work-card-id">#0132</span>
      </div>
      <ul class="work-card-list">
        <li v-for="(f, i) in visibleFields" :key="f.label">
          <span class="work-label">{{ f.label }}</span>
          <span class="work-value">{{ f.value }}</span>
        </li>
      </ul>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { pipeline } from '../../homeContent';

const props = withDefaults(
  defineProps<{
    /** 进度 0~1，由父 pin 容器驱动 */
    progress?: number;
  }>(),
  { progress: 0 }
);

/** 当前已盖章的站数（0~6） */
const currentStamp = computed(() => Math.floor(props.progress * 6.8));

/** 工单随进度展示字段 */
const visibleFields = computed(() => {
  const n = Math.min(pipeline.workCard.fields.length, Math.max(1, currentStamp.value));
  return pipeline.workCard.fields.slice(0, n);
});
</script>

<style scoped>
.conveyor {
  position: relative;
  width: max-content;
  min-width: 100%;
  padding: 4rem 6vw;
}

/* 传送带总轨道 */
.track {
  position: relative;
  display: grid;
  grid-template-columns: repeat(6, minmax(340px, 1fr));
  gap: 4rem;
  padding: 0 2rem;
}

/* 两条传送带 */
.rail {
  position: absolute;
  left: 0;
  right: 0;
  height: 1px;
  background: var(--ink);
  opacity: 0.25;
}
.rail-top { top: calc(45% - 28px); }
.rail-bottom { top: calc(45% + 28px); }

/* 流动粒子 */
.particles {
  position: absolute;
  left: 0;
  right: 0;
  top: 45%;
  height: 0;
  pointer-events: none;
}
.particle {
  position: absolute;
  top: -3px;
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: var(--ember);
  box-shadow: 0 0 8px var(--ember-glow);
  animation: particle-flow 7s linear infinite;
}
@keyframes particle-flow {
  0%   { transform: translateX(-20vw); opacity: 0; }
  10%  { opacity: 1; }
  90%  { opacity: 1; }
  100% { transform: translateX(20vw); opacity: 0; }
}

/* 每个站 */
.station {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1rem;
  min-height: 460px;
  justify-content: flex-start;
  padding-top: 0.5rem;
  transition: opacity 500ms ease;
}
.station:not(.is-stamped):not(.is-current) .station-stamp,
.station:not(.is-stamped):not(.is-current) .station-desc {
  opacity: 0.35;
}

/* 好莱坞对应（顶部小字） */
.station-hollywood {
  font-family: var(--font-mono);
  font-size: 0.75rem;
  color: var(--slate);
  letter-spacing: 0.3em;
  text-transform: uppercase;
  padding: 3px 10px;
  border: 1px solid var(--slate);
  border-radius: 2px;
  opacity: 0.8;
}

/* 印章 */
.station-stamp {
  position: relative;
  width: 130px;
  height: 130px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.25rem;
  z-index: 2;
}
.stamp-ring {
  position: relative;
  width: 110px;
  height: 110px;
  border-radius: 50%;
  border: 3px solid var(--ember);
  background: var(--paper);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 2px;
  transform: translateY(-40px) rotate(-12deg) scale(0.8);
  opacity: 0;
  transition: transform 560ms cubic-bezier(0.68, -0.2, 0.265, 1.55),
              opacity 400ms ease;
  box-shadow: 0 0 0 5px var(--paper), 0 4px 12px rgba(42, 36, 32, 0.18);
}
.is-stamped .stamp-ring,
.is-current .stamp-ring {
  transform: translateY(0) rotate(-4deg) scale(1);
  opacity: 1;
}
.is-critic.is-stamped .stamp-ring,
.is-critic.is-current .stamp-ring {
  border-color: var(--crimson);
}
.stamp-idx {
  font-family: var(--font-mono);
  font-size: 0.95rem;
  color: var(--ember-deep);
  letter-spacing: 0.15em;
}
.is-critic .stamp-idx { color: var(--crimson); }
.stamp-zh {
  font-family: var(--font-display);
  font-size: 1.5rem;
  color: var(--ink);
  letter-spacing: 0.12em;
}
.stamp-en {
  margin-top: 0.2rem;
  font-family: var(--font-mono);
  font-size: 0.78rem;
  color: var(--ink-soft);
  letter-spacing: 0.22em;
  text-transform: uppercase;
}
.stamp-ink {
  position: absolute;
  width: 150px;
  height: 150px;
  border-radius: 50%;
  background: radial-gradient(circle, var(--ember-glow) 0%, transparent 70%);
  transform: scale(0);
  opacity: 0;
  transition: transform 800ms ease-out, opacity 800ms ease-out;
  z-index: -1;
}
.is-stamped .stamp-ink {
  transform: scale(1);
  opacity: 0.8;
}
.is-critic .stamp-ink {
  background: radial-gradient(circle, rgba(184, 74, 63, 0.28) 0%, transparent 70%);
}

/* 说明文字 */
.station-desc {
  text-align: center;
  max-width: 280px;
  transition: opacity 400ms ease;
}
.desc-main {
  font-family: var(--font-display);
  font-size: 1.1rem;
  color: var(--ink);
  line-height: 1.7;
  letter-spacing: 0.04em;
  margin: 0 0 0.75rem;
}
.desc-work {
  font-family: var(--font-body);
  font-size: 0.88rem;
  color: var(--ink-soft);
  line-height: 1.7;
  margin: 0;
  padding-top: 0.75rem;
  border-top: 1px dashed var(--ink-ghost);
}

/* Critic 回弹循环 */
.critic-loop {
  position: absolute;
  right: -10px;
  top: 40%;
  width: 220px;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
}
.critic-loop-label {
  font-family: var(--font-hand);
  font-size: 0.85rem;
  color: var(--crimson);
  margin-top: 4px;
}

/* 悬浮工单纸片 */
.work-card {
  position: absolute;
  bottom: 2rem;
  right: 4rem;
  width: 320px;
  padding: 1.1rem 1.3rem;
  background: var(--paper);
  border: 1px solid var(--ink);
  box-shadow: 4px 4px 0 var(--ink), 0 10px 24px rgba(42, 36, 32, 0.15);
  transform: rotate(1.8deg) translateY(20px);
  opacity: 0;
  transition: opacity 400ms ease, transform 560ms cubic-bezier(0.68, -0.2, 0.265, 1.55);
  z-index: 10;
}
.work-card.is-active {
  opacity: 1;
  transform: rotate(1.8deg) translateY(0);
}
.work-card-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 0.75rem;
  padding-bottom: 0.5rem;
  border-bottom: 1.5px dashed var(--ink-ghost);
}
.work-card-title {
  font-family: var(--font-display);
  font-size: 1rem;
  color: var(--ink);
  letter-spacing: 0.08em;
}
.work-card-id {
  font-family: var(--font-mono);
  font-size: 0.78rem;
  color: var(--crimson);
  letter-spacing: 0.1em;
}
.work-card-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}
.work-card-list li {
  display: grid;
  grid-template-columns: 72px 1fr;
  gap: 0.6rem;
  font-size: 0.82rem;
}
.work-label {
  font-family: var(--font-hand);
  color: var(--ember-deep);
}
.work-value {
  color: var(--ink);
  font-family: var(--font-body);
}
</style>
