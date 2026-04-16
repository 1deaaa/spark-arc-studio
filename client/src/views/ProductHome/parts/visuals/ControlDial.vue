<!--
  ControlDial · 三档介入旋钮
  - 点击档位切换模式
  - 旋钮指针随当前档旋转
-->
<template>
  <div class="control-dial">
    <!-- 旋钮本体 -->
    <div class="dial-wrap">
      <svg viewBox="0 0 260 260" width="260" height="260" class="dial-svg">
        <defs>
          <radialGradient id="dial-grad" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stop-color="#C89762" />
            <stop offset="60%" stop-color="#A67441" />
            <stop offset="100%" stop-color="#6E4626" />
          </radialGradient>
          <linearGradient id="dial-top" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stop-color="#D9AE7C" />
            <stop offset="100%" stop-color="#A67441" />
          </linearGradient>
        </defs>

        <!-- 外圈刻度 -->
        <circle cx="130" cy="130" r="118" fill="none" stroke="var(--ink)" stroke-width="1" opacity="0.4" />
        <g v-for="i in 21" :key="i" :transform="`rotate(${-120 + (i - 1) * 12} 130 130)`">
          <line
            x1="130" :y1="i % 5 === 1 ? 16 : 20"
            x2="130" y2="24"
            :stroke="i % 5 === 1 ? 'var(--ember-deep)' : 'var(--ink)'"
            :stroke-width="i % 5 === 1 ? 2 : 1"
            opacity="0.7"
          />
        </g>

        <!-- 档位标签 -->
        <text
          v-for="(m, i) in modes"
          :key="m.key"
          :x="labelPos(i).x"
          :y="labelPos(i).y"
          text-anchor="middle"
          class="dial-label"
          :class="{ 'is-active': active === i }"
          @click="setActive(i)"
        >{{ m.label }}</text>

        <!-- 旋钮本体 -->
        <circle cx="130" cy="130" r="84" fill="url(#dial-grad)" stroke="#4A2E1A" stroke-width="2" />
        <circle cx="130" cy="130" r="70" fill="url(#dial-top)" stroke="#8B5A2B" stroke-width="1.5" />
        <!-- 纹理环 -->
        <circle cx="130" cy="130" r="60" fill="none" stroke="#6E4626" stroke-width="0.8" stroke-dasharray="1 3" opacity="0.5" />

        <!-- 指针 -->
        <g :transform="`rotate(${pointerAngle} 130 130)`" class="dial-pointer">
          <polygon points="130,54 126,70 134,70" fill="var(--ember)" stroke="var(--ember-deep)" stroke-width="1" />
          <circle cx="130" cy="62" r="3" fill="var(--gold)" />
        </g>

        <!-- 中心轴 -->
        <circle cx="130" cy="130" r="10" fill="#3E2416" stroke="#8B5A2B" stroke-width="1" />
        <circle cx="130" cy="130" r="3" fill="var(--gold)" />
      </svg>
    </div>

    <!-- 档位说明 -->
    <div class="mode-info">
      <div class="mode-badge" :class="{ 'is-recommended': modes[active].recommended }">
        <span class="mode-label">{{ modes[active].label }}</span>
        <span v-if="modes[active].recommended" class="mode-recommend">推荐</span>
      </div>
      <p class="mode-desc">{{ modes[active].desc }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';
import { control } from '../../homeContent';

const modes = control.modes;

/** 默认半自动 */
const active = ref(1);

function setActive(i: number) {
  active.value = i;
}

/** 指针角度：左 = -40°, 中 = 0°, 右 = 40° */
const pointerAngle = computed(() => -40 + active.value * 40);

/** 档位标签位置（以旋钮中心 130,130 为参考） */
function labelPos(i: number) {
  const positions = [
    { x: 60, y: 220 },
    { x: 130, y: 246 },
    { x: 200, y: 220 },
  ];
  return positions[i];
}
</script>

<style scoped>
.control-dial {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2rem;
}
.dial-wrap {
  width: 260px;
  height: 260px;
  filter: drop-shadow(0 14px 24px rgba(42, 36, 32, 0.28));
}
.dial-svg {
  display: block;
  width: 100%;
  height: 100%;
}
.dial-pointer {
  transition: transform 520ms cubic-bezier(0.68, -0.2, 0.265, 1.55);
  transform-origin: center;
}
.dial-label {
  font-family: var(--font-display);
  font-size: 14px;
  fill: var(--ink-soft);
  letter-spacing: 0.1em;
  cursor: pointer;
  transition: fill 200ms ease;
}
.dial-label:hover { fill: var(--ink); }
.dial-label.is-active { fill: var(--ember-deep); }

/* 档位信息卡 */
.mode-info {
  text-align: center;
  max-width: 440px;
}
.mode-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.4rem 1.1rem;
  background: var(--ink);
  color: var(--paper);
  border-radius: 2px;
  margin-bottom: 0.8rem;
  font-family: var(--font-display);
}
.mode-badge.is-recommended {
  background: var(--ember);
}
.mode-label {
  font-size: 1.05rem;
  letter-spacing: 0.15em;
}
.mode-recommend {
  font-family: var(--font-hand);
  font-size: 0.85rem;
  padding: 1px 8px;
  background: rgba(255, 255, 255, 0.2);
  border-radius: 2px;
}
.mode-desc {
  font-family: var(--font-hand);
  font-size: 1.05rem;
  color: var(--ink);
  margin: 0;
  line-height: 1.8;
  min-height: 3.2em;
}
</style>
