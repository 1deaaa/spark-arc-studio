<!--
  AgentRoundTable · 六位 Agent 圆桌
  size='mini'  → 小尺寸微缩预览（用于 Hero）
  size='full'  → 大尺寸完整交互（用于 ActEnsemble）
-->
<template>
  <div class="round-table" :class="[`is-${size}`]">
    <svg
      class="table-svg"
      :viewBox="viewBox"
      width="100%"
      height="100%"
      xmlns="http://www.w3.org/2000/svg"
    >
      <defs>
        <!-- 桌面纹理渐变 -->
        <radialGradient id="tbl-grad" cx="50%" cy="50%" r="55%">
          <stop offset="0%" stop-color="var(--paper)" />
          <stop offset="60%" stop-color="var(--paper-deep)" />
          <stop offset="100%" stop-color="var(--paper-deep)" />
        </radialGradient>
        <!-- 呼吸光晕 -->
        <filter id="rt-glow">
          <feGaussianBlur stdDeviation="4" />
        </filter>
      </defs>

      <!-- 圆桌 -->
      <circle :cx="cx" :cy="cy" :r="tableR" fill="url(#tbl-grad)" stroke="var(--ink-ghost)" stroke-width="1.2" />
      <circle :cx="cx" :cy="cy" :r="tableR - 8" fill="none" stroke="var(--ink-ghost)" stroke-width="0.8" stroke-dasharray="2 3" />

      <!-- 中心徽记 -->
      <g :transform="`translate(${cx},${cy})`" class="table-crest" v-if="size === 'full'">
        <text
          text-anchor="middle"
          dy="0.35em"
          class="crest-text"
          :style="{ fontSize: `${tableR * 0.18}px` }"
        >
          编剧部
        </text>
        <text
          text-anchor="middle"
          :y="tableR * 0.22"
          dy="0.35em"
          class="crest-sub"
          :style="{ fontSize: `${tableR * 0.085}px` }"
        >
          SparkArc Writers' Room
        </text>
      </g>

      <!-- 六把椅子 + Agent -->
      <g
        v-for="(seat, i) in seats"
        :key="seat.agent.key"
        :class="['seat', `seat-${seat.agent.key}`, { 'is-active': activeKey === seat.agent.key, 'is-director': seat.agent.key === 'director' }]"
        :transform="`translate(${seat.x},${seat.y})`"
        @mouseenter="onHover(seat.agent.key)"
        @mouseleave="onLeave"
        @click="onClick(seat.agent.key)"
        :style="{ '--i': i }"
      >
        <!-- 呼吸光 -->
        <circle :r="seatR + 8" class="breath" fill="var(--ember-glow)" filter="url(#rt-glow)" />
        <!-- 椅子底 -->
        <circle :r="seatR" fill="var(--paper)" stroke="var(--ink)" stroke-width="1.4" />
        <!-- Agent 人像抽象符号 -->
        <circle :r="seatR * 0.4" :cy="-seatR * 0.15" fill="var(--ink)" />
        <path
          :d="`M ${-seatR * 0.55} ${seatR * 0.45} Q 0 ${seatR * 0.05} ${seatR * 0.55} ${seatR * 0.45}`"
          fill="none"
          stroke="var(--ink)"
          stroke-width="1.5"
          stroke-linecap="round"
        />
        <!-- 名字（full 尺寸才显示完整） -->
        <text
          v-if="size === 'full'"
          text-anchor="middle"
          :y="seatR + 22"
          class="seat-name"
        >{{ seat.agent.name }}</text>
        <text
          v-if="size === 'full'"
          text-anchor="middle"
          :y="seatR + 38"
          class="seat-zh"
        >{{ seat.agent.zh }}</text>
      </g>
    </svg>

    <!-- 悬停显示的职责卡片（仅 full 尺寸） -->
    <div v-if="size === 'full'" class="info-card" :class="{ 'is-visible': !!currentAgent }">
      <template v-if="currentAgent">
        <div class="info-head">
          <span class="info-name">{{ currentAgent.name }}</span>
          <span class="info-zh">{{ currentAgent.zh }}</span>
        </div>
        <p class="info-role">"{{ currentAgent.role }}"</p>
        <p class="info-work">{{ currentAgent.work }}</p>
        <code class="info-sig">{{ currentAgent.signature }}</code>
      </template>
      <template v-else>
        <p class="info-hint">悬停圆桌上的任意一位——他会告诉你他是谁。</p>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';
import { ensemble } from '../../homeContent';

const props = withDefaults(defineProps<{ size?: 'mini' | 'full' }>(), {
  size: 'full',
});

const activeKey = ref<string>('');

/** 圆桌几何参数（统一 viewBox 420×420） */
const cx = 210;
const cy = 210;
const tableR = computed(() => (props.size === 'mini' ? 140 : 160));
const seatR = computed(() => (props.size === 'mini' ? 22 : 34));
const orbitR = computed(() => (props.size === 'mini' ? 165 : 192));
const viewBox = '0 0 420 420';

/** 6 位 Agent 环形排布：Director 在顶部，其他五位环绕 */
const seats = computed(() => {
  const order = ['director', 'muse', 'lorebook', 'showrunner', 'scriptwriter', 'critic'];
  const ordered = order
    .map((k) => ensemble.agents.find((a) => a.key === k))
    .filter((a): a is NonNullable<typeof a> => !!a);

  return ordered.map((agent, i) => {
    // 顶部起算，顺时针
    const angle = -Math.PI / 2 + (i * Math.PI * 2) / ordered.length;
    return {
      agent,
      x: cx + Math.cos(angle) * orbitR.value,
      y: cy + Math.sin(angle) * orbitR.value,
    };
  });
});

const currentAgent = computed(() =>
  ensemble.agents.find((a) => a.key === activeKey.value) ?? null
);

function onHover(key: string) {
  activeKey.value = key;
}
function onLeave() {
  activeKey.value = '';
}
function onClick(key: string) {
  activeKey.value = activeKey.value === key ? '' : key;
}
</script>

<style scoped>
.round-table {
  position: relative;
  width: 100%;
  height: 100%;
}
.table-svg {
  width: 100%;
  height: 100%;
  display: block;
}

/* 呼吸光：错开六个 Agent 的相位，避免一致闪烁 */
.seat .breath {
  opacity: 0;
  animation: breath 4.2s ease-in-out infinite;
  animation-delay: calc(var(--i) * 0.7s);
  transform-origin: center;
}
.seat.is-director .breath {
  fill: var(--gold);
  opacity: 0.22;
  animation-duration: 3.2s;
}
.seat.is-active .breath {
  opacity: 0.8;
  animation-duration: 1.6s;
}
@keyframes breath {
  0%, 100% { opacity: 0.1; transform: scale(0.9); }
  50%      { opacity: 0.6; transform: scale(1.15); }
}

.seat {
  cursor: pointer;
  transition: transform 240ms ease;
}
.round-table.is-full .seat:hover {
  transform: translate(var(--hx, 0), var(--hy, 0)) scale(1.08);
}

.crest-text {
  font-family: var(--font-display);
  fill: var(--ink);
  letter-spacing: 0.1em;
}
.crest-sub {
  font-family: var(--font-mono);
  fill: var(--ink-soft);
  letter-spacing: 0.2em;
}

.seat-name {
  font-family: var(--font-display);
  font-size: 14px;
  fill: var(--ink);
  letter-spacing: 0.08em;
}
.seat-zh {
  font-family: var(--font-hand);
  font-size: 13px;
  fill: var(--ink-soft);
}

/* 悬停信息卡 */
.info-card {
  position: absolute;
  left: 50%;
  top: 50%;
  transform: translate(-50%, -50%);
  width: 260px;
  min-height: 110px;
  padding: 1rem 1.2rem;
  background: var(--paper);
  border: 1px solid var(--ink);
  box-shadow: 3px 3px 0 var(--ink), 0 12px 32px rgba(42, 36, 32, 0.18);
  pointer-events: none;
  opacity: 0;
  transition: opacity 180ms ease;
  text-align: center;
}
.info-card.is-visible { opacity: 1; }
.info-head {
  display: flex;
  align-items: baseline;
  justify-content: center;
  gap: 0.6rem;
  margin-bottom: 0.6rem;
  border-bottom: 1px dashed var(--ink-ghost);
  padding-bottom: 0.5rem;
}
.info-name {
  font-family: var(--font-display);
  font-size: 1.15rem;
  color: var(--ink);
  letter-spacing: 0.08em;
}
.info-zh {
  font-family: var(--font-hand);
  font-size: 1rem;
  color: var(--ember-deep);
}
.info-role {
  font-family: var(--font-hand);
  font-size: 1rem;
  color: var(--ink);
  margin: 0 0 0.35rem;
}
.info-work {
  font-size: 0.85rem;
  color: var(--ink-soft);
  margin: 0 0 0.5rem;
  line-height: 1.6;
}
.info-sig {
  display: inline-block;
  font-family: var(--font-mono);
  font-size: 0.72rem;
  color: var(--moss);
  background: var(--paper-deep);
  padding: 2px 8px;
  border-radius: 2px;
  letter-spacing: 0.05em;
}
.info-hint {
  font-family: var(--font-hand);
  font-size: 0.95rem;
  color: var(--ink-soft);
  margin: 0;
  opacity: 0.8;
}
</style>
