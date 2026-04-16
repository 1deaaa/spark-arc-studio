<!--
  StyleLoop · 风格克隆图灵回测闭环
  - 一本书被分块 → 串行分析 → ValidatorAgent 自评 → 循环注入负向约束
-->
<template>
  <div class="style-loop">
    <!-- 顶部：书 → 分块 → 分析器串行 -->
    <div class="stage-chain">
      <div class="chain-book">
        <div class="book-spine"></div>
        <div class="book-pages"></div>
        <div class="book-label">目标作家 · 全集</div>
      </div>
      <div class="chain-arrow">→</div>
      <div class="chain-chunks">
        <div
          v-for="n in 4"
          :key="n"
          class="chunk"
          :class="{ 'is-active': activeChunk === n - 1 }"
        >
          <span class="chunk-num">#{{ n }}</span>
          <span class="chunk-size">30k</span>
        </div>
      </div>
      <div class="chain-arrow">→</div>
      <div class="chain-analyzer">
        <div class="analyzer-icon">
          <svg viewBox="0 0 40 40" width="40" height="40">
            <circle cx="20" cy="20" r="14" fill="none" stroke="var(--ember)" stroke-width="2" />
            <circle cx="20" cy="20" r="4" fill="var(--ember)" />
            <line x1="28" y1="28" x2="34" y2="34" stroke="var(--ember)" stroke-width="2.5" stroke-linecap="round" />
          </svg>
        </div>
        <span class="analyzer-label">UnifiedStyleAnalyzer</span>
      </div>
    </div>

    <!-- 底部：ValidatorAgent 自评循环 -->
    <div class="stage-loop">
      <div class="loop-step">
        <div class="step-icon step-write">✎</div>
        <div class="step-title">写一段</div>
        <div class="step-sub">模仿目标作者</div>
      </div>
      <div class="loop-arrow">→</div>
      <div class="loop-step">
        <div class="step-icon step-judge">?</div>
        <div class="step-title">自评 Tier</div>
        <div class="step-sub tier-b">Tier B · 有 AI 味</div>
      </div>
      <div class="loop-arrow">→</div>
      <div class="loop-step">
        <div class="step-icon step-constraint">!</div>
        <div class="step-title">生成负向约束</div>
        <div class="step-sub">注入档案</div>
      </div>
      <!-- 回弹箭头 -->
      <div class="loop-return">
        <svg viewBox="0 0 200 60" preserveAspectRatio="none" width="100%" height="40">
          <path d="M 190 10 C 190 50, 10 50, 10 10" fill="none" stroke="var(--ember-deep)" stroke-width="1.5" stroke-dasharray="5 4" />
          <polygon points="10,8 15,14 5,14" fill="var(--ember-deep)" />
        </svg>
        <span class="loop-return-label">再写一遍，直到他自己都认不出是 AI</span>
      </div>
    </div>

    <!-- 最终通过印章 -->
    <div class="loop-verdict">
      <div class="verdict-stamp">{{ verdictText }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue';
import { guard } from '../../homeContent';

const activeChunk = ref(0);
const verdictText = guard.styleLoop.verdict;

let timer: ReturnType<typeof setInterval> | null = null;
onMounted(() => {
  timer = setInterval(() => {
    activeChunk.value = (activeChunk.value + 1) % 4;
  }, 900);
});
onBeforeUnmount(() => {
  if (timer) clearInterval(timer);
});
</script>

<style scoped>
.style-loop {
  display: flex;
  flex-direction: column;
  gap: 2rem;
  padding: 1.5rem;
  background: rgba(250, 246, 238, 0.5);
  border: 1px solid var(--ink-ghost);
  border-radius: 2px;
}

/* 顶部链式 */
.stage-chain {
  display: flex;
  align-items: center;
  gap: 1rem;
  justify-content: space-between;
  flex-wrap: wrap;
}
.chain-book {
  position: relative;
  width: 60px;
  height: 80px;
  flex-shrink: 0;
  text-align: center;
}
.book-spine {
  position: absolute;
  left: 4px;
  top: 0;
  width: 8px;
  height: 64px;
  background: var(--ember-deep);
}
.book-pages {
  position: absolute;
  left: 12px;
  top: 2px;
  width: 44px;
  height: 60px;
  background: var(--paper);
  border: 1px solid var(--ink);
  box-shadow: 2px 2px 0 var(--ink-ghost);
}
.book-label {
  position: absolute;
  bottom: -18px;
  left: 50%;
  transform: translateX(-50%);
  font-family: var(--font-hand);
  font-size: 0.75rem;
  color: var(--ink-soft);
  white-space: nowrap;
}
.chain-arrow {
  font-family: var(--font-mono);
  color: var(--ink-soft);
  font-size: 1.4rem;
}
.chain-chunks {
  display: flex;
  gap: 6px;
  flex: 1;
  max-width: 320px;
}
.chunk {
  flex: 1;
  padding: 0.5rem 0.3rem;
  background: var(--paper);
  border: 1px solid var(--ink-ghost);
  border-radius: 2px;
  text-align: center;
  font-family: var(--font-mono);
  transition: all 300ms ease;
  min-width: 52px;
}
.chunk.is-active {
  background: var(--ember-glow);
  border-color: var(--ember);
  transform: translateY(-3px);
}
.chunk-num {
  display: block;
  font-size: 0.78rem;
  color: var(--ember-deep);
  letter-spacing: 0.1em;
}
.chunk-size {
  display: block;
  font-size: 0.7rem;
  color: var(--ink-soft);
  margin-top: 2px;
}
.chain-analyzer {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}
.analyzer-icon {
  padding: 0.4rem;
  background: var(--paper);
  border: 1px solid var(--ember);
  border-radius: 50%;
  box-shadow: 0 0 12px var(--ember-glow);
  animation: scan-spin 4s linear infinite;
}
@keyframes scan-spin {
  from { transform: rotate(0); }
  to   { transform: rotate(360deg); }
}
.analyzer-label {
  font-family: var(--font-mono);
  font-size: 0.72rem;
  color: var(--ember-deep);
  letter-spacing: 0.15em;
  white-space: nowrap;
}

/* 底部循环 */
.stage-loop {
  position: relative;
  display: grid;
  grid-template-columns: 1fr auto 1fr auto 1fr;
  gap: 0.6rem;
  align-items: center;
  padding: 1.2rem 0 3rem;
}
.loop-step {
  text-align: center;
}
.step-icon {
  width: 54px;
  height: 54px;
  margin: 0 auto 0.6rem;
  border-radius: 50%;
  background: var(--paper);
  border: 2px solid var(--ember);
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: var(--font-display);
  font-size: 1.5rem;
  color: var(--ember-deep);
  box-shadow: 0 4px 10px rgba(42, 36, 32, 0.1);
}
.step-judge { border-color: var(--crimson); color: var(--crimson); }
.step-constraint { border-color: var(--moss); color: var(--moss); }
.step-title {
  font-family: var(--font-display);
  font-size: 1rem;
  color: var(--ink);
  letter-spacing: 0.08em;
  margin-bottom: 2px;
}
.step-sub {
  font-family: var(--font-hand);
  font-size: 0.86rem;
  color: var(--ink-soft);
}
.step-sub.tier-b {
  color: var(--crimson);
  font-weight: 600;
}
.loop-arrow {
  font-family: var(--font-mono);
  color: var(--ink-soft);
  font-size: 1.3rem;
}
.loop-return {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  text-align: center;
}
.loop-return-label {
  display: block;
  margin-top: -4px;
  font-family: var(--font-hand);
  font-size: 0.9rem;
  color: var(--ember-deep);
}

/* 最终印章 */
.loop-verdict {
  display: flex;
  justify-content: center;
  margin-top: 0.5rem;
}
.verdict-stamp {
  display: inline-block;
  padding: 0.7rem 1.8rem;
  background: var(--moss);
  color: var(--paper);
  font-family: var(--font-display);
  font-size: 1rem;
  letter-spacing: 0.12em;
  border-radius: 2px;
  transform: rotate(-2deg);
  box-shadow: 2px 2px 0 rgba(42, 36, 32, 0.3);
}
</style>
