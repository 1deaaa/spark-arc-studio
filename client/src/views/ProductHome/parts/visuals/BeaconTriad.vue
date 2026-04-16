<!--
  BeaconTriad · 信标 · 号角 · 旗帜 · 三盏灯笼交互
  - 点击切换灯的亮灭状态
  - 下方日志行随交互打字机式浮现
-->
<template>
  <div class="beacon-triad">
    <div class="lanterns">
      <div
        v-for="(t, i) in triad"
        :key="t.key"
        class="lantern-wrap"
        :class="{ 'is-lit': lit[i], 'is-hover': hovered === i, 'is-dim': hovered !== null && hovered !== i }"
        @mouseenter="hovered = i"
        @mouseleave="hovered = null"
        @click="toggle(i)"
      >
        <!-- 灯笼 SVG -->
        <svg viewBox="0 0 120 180" width="100%" height="220">
          <!-- 挂绳 -->
          <line x1="60" y1="0" x2="60" y2="25" stroke="var(--ink)" stroke-width="1.5" />
          <!-- 顶盖 -->
          <path d="M 35 25 L 85 25 L 78 35 L 42 35 Z" fill="var(--ink)" />
          <!-- 灯笼主体 -->
          <ellipse cx="60" cy="80" rx="38" ry="48" fill="var(--paper)" stroke="var(--ink)" stroke-width="2" class="lantern-body" />
          <!-- 灯笼纵向褶皱 -->
          <line v-for="n in 5" :key="n" :x1="60 - 30 + (n - 1) * 15" y1="35" :x2="60 - 30 + (n - 1) * 15" y2="125" stroke="var(--ink)" stroke-width="0.8" opacity="0.3" />
          <!-- 灯光核心 -->
          <circle cx="60" cy="80" r="22" class="lantern-light" />
          <!-- 底部穗 -->
          <path d="M 50 128 L 60 128 L 70 128 L 65 155 L 60 165 L 55 155 Z" fill="var(--ink)" />
          <!-- 底部字牌 -->
          <text x="60" y="85" text-anchor="middle" class="lantern-char">{{ t.name.charAt(0) }}</text>
        </svg>

        <!-- 下方名牌 -->
        <div class="lantern-plaque">
          <div class="plaque-cn">{{ t.name }}</div>
          <div class="plaque-en">{{ t.en }}</div>
        </div>

        <!-- 悬停问号 -->
        <div class="lantern-question">{{ t.question }}</div>
      </div>
    </div>

    <!-- 交互说明 -->
    <p class="triad-hint">{{ hint }}</p>

    <!-- 日志终端 -->
    <div class="log-terminal">
      <div class="log-head">
        <span class="log-dot"></span>
        <span class="log-dot"></span>
        <span class="log-dot"></span>
        <span class="log-title">agent_runtime.log</span>
      </div>
      <div class="log-body">
        <div v-for="(line, i) in logLines" :key="`${line.ts}-${i}`" class="log-line" :class="{ 'is-new': i === logLines.length - 1 }">
          <span class="log-ts">{{ line.ts }}</span>
          <span class="log-text" v-html="line.text"></span>
        </div>
        <div v-if="!logLines.length" class="log-empty">点击任意一盏灯笼，看看他们怎么协作。</div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';
import { protocol } from '../../homeContent';

const triad = protocol.triad;

const lit = ref<boolean[]>([true, true, true]);
const hovered = ref<number | null>(null);

interface LogLine { ts: string; text: string; }
const logLines = ref<LogLine[]>([]);

const hint = computed(() => {
  if (hovered.value === null) return '点击灯笼，切换 Agent 的状态——观察他们之间是怎么协作的。';
  return triad[hovered.value].detail;
});

function pad(n: number): string {
  return n < 10 ? `0${n}` : `${n}`;
}
function now(): string {
  const d = new Date();
  return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

function toggle(i: number) {
  lit.value[i] = !lit.value[i];
  const t = triad[i];
  const verb = lit.value[i] ? '开启' : '关闭';
  const text = `<span class="log-tag log-tag-${t.key}">[${t.name}]</span> ${t.log.replace(/^\[[^\]]+\]\s*/, '')} · 状态 ${verb}`;
  logLines.value.push({ ts: now(), text });
  if (logLines.value.length > 8) logLines.value.shift();
}
</script>

<style scoped>
.beacon-triad {
  display: flex;
  flex-direction: column;
  gap: 2.5rem;
  align-items: center;
  max-width: 1080px;
  margin: 0 auto;
}

/* 三盏灯笼 */
.lanterns {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 3rem;
  width: 100%;
}
.lantern-wrap {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1.1rem;
  cursor: pointer;
  transition: transform 240ms ease, opacity 240ms ease;
  padding-top: 0.4rem;
}
.lantern-wrap:hover {
  transform: translateY(-6px);
}
.lantern-wrap.is-dim {
  opacity: 0.4;
}
.lantern-wrap .lantern-body {
  transition: fill 300ms ease;
}
.lantern-wrap.is-lit .lantern-body {
  fill: var(--gold-soft);
}
.lantern-light {
  fill: transparent;
  transition: fill 300ms ease, filter 400ms ease;
  filter: blur(2px);
}
.lantern-wrap.is-lit .lantern-light {
  fill: var(--ember);
  filter: blur(1.2px) drop-shadow(0 0 16px var(--ember-glow));
  animation: flame 2.4s ease-in-out infinite;
}
@keyframes flame {
  0%, 100% { transform: scale(1) translate(0, 0); opacity: 0.9; }
  50% { transform: scale(1.08) translate(0.5px, -0.5px); opacity: 1; }
}
.lantern-char {
  font-family: var(--font-display);
  font-size: 24px;
  fill: var(--ember-deep);
  font-weight: 700;
  opacity: 0;
  transition: opacity 300ms ease;
}
.lantern-wrap.is-lit .lantern-char { opacity: 0.9; }

/* 名牌 */
.lantern-plaque {
  text-align: center;
  padding: 0.5rem 1.2rem;
  background: var(--paper);
  border: 1px solid var(--ink);
  box-shadow: 2px 2px 0 var(--ink);
}
.plaque-cn {
  font-family: var(--font-display);
  font-size: 1.25rem;
  color: var(--ink);
  letter-spacing: 0.2em;
}
.plaque-en {
  font-family: var(--font-mono);
  font-size: 0.75rem;
  color: var(--ink-soft);
  letter-spacing: 0.22em;
  margin-top: 2px;
}
.lantern-question {
  font-family: var(--font-hand);
  font-size: 1.05rem;
  color: var(--ember-deep);
  text-align: center;
  max-width: 260px;
}

/* 交互提示 */
.triad-hint {
  font-family: var(--font-hand);
  font-size: 1.15rem;
  color: var(--ink-soft);
  text-align: center;
  margin: 0;
  min-height: 2rem;
  max-width: 720px;
  line-height: 1.7;
  transition: all 240ms ease;
}

/* 日志终端 */
.log-terminal {
  width: 100%;
  max-width: 780px;
  background: var(--ink);
  border-radius: 4px;
  box-shadow: 0 12px 36px rgba(42, 36, 32, 0.25);
  overflow: hidden;
}
.log-head {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.6rem 1rem;
  background: #3a3230;
}
.log-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--ember);
}
.log-dot:nth-child(2) { background: var(--gold); }
.log-dot:nth-child(3) { background: var(--moss); }
.log-title {
  margin-left: 0.6rem;
  font-family: var(--font-mono);
  font-size: 0.75rem;
  color: var(--paper-deep);
  letter-spacing: 0.12em;
  opacity: 0.7;
}
.log-body {
  padding: 1rem 1.2rem;
  min-height: 140px;
  max-height: 220px;
  overflow-y: auto;
  font-family: var(--font-mono);
  font-size: 0.84rem;
  color: var(--paper);
  line-height: 1.8;
}
.log-line {
  display: flex;
  gap: 0.8rem;
  opacity: 0.85;
}
.log-line.is-new {
  animation: log-in 420ms ease;
}
@keyframes log-in {
  from { opacity: 0; transform: translateX(-8px); }
  to   { opacity: 0.85; transform: none; }
}
.log-ts {
  color: var(--slate);
  flex-shrink: 0;
}
.log-text :deep(.log-tag) {
  display: inline-block;
  padding: 0 6px;
  margin-right: 6px;
  border-radius: 2px;
  color: var(--ink);
  font-weight: 600;
}
.log-text :deep(.log-tag-beacon) { background: var(--gold); }
.log-text :deep(.log-tag-horn) { background: var(--ember); color: #fff; }
.log-text :deep(.log-tag-baton) { background: var(--moss); color: #fff; }
.log-empty {
  font-family: var(--font-mono);
  font-size: 0.8rem;
  color: var(--slate);
  font-style: italic;
}

@media (max-width: 900px) {
  .lanterns { grid-template-columns: 1fr; gap: 2rem; }
}
</style>
