<!--
  CriticTicket · Critic 五维审稿单（仿编辑部纸片）
-->
<template>
  <div class="critic-ticket">
    <div class="ticket-paper">
      <!-- 标头 -->
      <div class="ticket-head">
        <div class="ticket-brand">
          <span class="ticket-mark">审稿单</span>
          <span class="ticket-en">Critic's Report</span>
        </div>
        <div class="ticket-grade grade-b">
          <span class="grade-label">等级</span>
          <span class="grade-letter">B</span>
        </div>
      </div>

      <!-- 元信息 -->
      <ul class="ticket-meta">
        <li v-for="m in meta" :key="m.label">
          <span class="meta-label">{{ m.label }}</span>
          <span class="meta-value">{{ m.value }}</span>
        </li>
      </ul>

      <!-- 证据 -->
      <div class="ticket-evidence">
        <span class="evi-label">证据原文</span>
        <blockquote class="evi-quote">{{ evidence.quote }}</blockquote>
      </div>

      <!-- 问题 + 建议 -->
      <div class="ticket-analysis">
        <div class="ana-row">
          <span class="ana-label ana-issue">问题</span>
          <p class="ana-text">{{ evidence.issue }}</p>
        </div>
        <div class="ana-row">
          <span class="ana-label ana-suggest">建议</span>
          <p class="ana-text">{{ evidence.suggest }}</p>
        </div>
      </div>

      <!-- 工单号 -->
      <div class="ticket-foot">
        <span class="ticket-id">{{ ticketId }}</span>
        <span class="ticket-arrow">已生成 →</span>
      </div>

      <!-- 火漆章 -->
      <div class="wax-seal">
        <span class="wax-letter">C</span>
      </div>
    </div>

    <!-- 尾注 -->
    <p class="ticket-tail">{{ tail }}</p>
  </div>
</template>

<script setup lang="ts">
import { guard } from '../../homeContent';

const { meta, evidence, ticketId, tail } = guard.criticTicket;
</script>

<style scoped>
.critic-ticket {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  align-items: center;
}
.ticket-paper {
  position: relative;
  width: 100%;
  max-width: 480px;
  padding: 1.8rem 2rem 1.6rem;
  background: var(--paper);
  box-shadow: 3px 5px 0 var(--ink), 0 14px 32px rgba(42, 36, 32, 0.18);
  border: 1px solid var(--ink);
  transform: rotate(-1deg);
}
.ticket-paper::before {
  content: '';
  position: absolute;
  inset: 6px;
  border: 1px dashed var(--ink-ghost);
  pointer-events: none;
}

/* 标头 */
.ticket-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding-bottom: 0.9rem;
  border-bottom: 2px solid var(--ink);
  margin-bottom: 1rem;
}
.ticket-brand {
  display: flex;
  flex-direction: column;
}
.ticket-mark {
  font-family: var(--font-display);
  font-size: 1.5rem;
  color: var(--ink);
  letter-spacing: 0.15em;
}
.ticket-en {
  font-family: var(--font-mono);
  font-size: 0.72rem;
  color: var(--ink-soft);
  letter-spacing: 0.25em;
  margin-top: 2px;
}
.ticket-grade {
  text-align: center;
  padding: 0.3rem 0.8rem;
  background: var(--crimson);
  color: var(--paper);
  border-radius: 2px;
}
.grade-label {
  display: block;
  font-family: var(--font-mono);
  font-size: 0.7rem;
  letter-spacing: 0.2em;
}
.grade-letter {
  display: block;
  font-family: var(--font-display);
  font-size: 1.8rem;
  font-weight: 700;
  line-height: 1;
  margin-top: -2px;
}

/* 元信息 */
.ticket-meta {
  list-style: none;
  padding: 0;
  margin: 0 0 1.2rem;
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  font-size: 0.86rem;
  padding-bottom: 1rem;
  border-bottom: 1px dashed var(--ink-ghost);
}
.ticket-meta li {
  display: grid;
  grid-template-columns: 64px 1fr;
  gap: 0.6rem;
}
.meta-label {
  font-family: var(--font-hand);
  color: var(--ember-deep);
}
.meta-value {
  font-family: var(--font-body);
  color: var(--ink);
}

/* 证据 */
.ticket-evidence {
  margin-bottom: 1rem;
  padding: 0.6rem 0.9rem;
  background: var(--paper-deep);
  border-left: 3px solid var(--crimson);
}
.evi-label {
  font-family: var(--font-hand);
  font-size: 0.86rem;
  color: var(--ember-deep);
  display: block;
  margin-bottom: 0.2rem;
}
.evi-quote {
  font-family: var(--font-display);
  font-size: 1rem;
  color: var(--ink);
  line-height: 1.75;
  margin: 0;
  font-style: italic;
}

/* 分析 */
.ticket-analysis {
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
  padding-bottom: 0.9rem;
  border-bottom: 1px dashed var(--ink-ghost);
  margin-bottom: 0.9rem;
}
.ana-row {
  display: grid;
  grid-template-columns: 44px 1fr;
  gap: 0.8rem;
  align-items: flex-start;
}
.ana-label {
  display: inline-block;
  padding: 2px 0;
  font-family: var(--font-display);
  font-size: 0.84rem;
  text-align: center;
  letter-spacing: 0.12em;
}
.ana-issue { color: var(--crimson); border-bottom: 2px solid var(--crimson); }
.ana-suggest { color: var(--moss); border-bottom: 2px solid var(--moss); }
.ana-text {
  margin: 0;
  font-size: 0.92rem;
  color: var(--ink);
  line-height: 1.75;
}

/* 工单号 */
.ticket-foot {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
}
.ticket-id {
  font-family: var(--font-mono);
  font-size: 0.92rem;
  color: var(--crimson);
  letter-spacing: 0.1em;
  font-weight: 700;
}
.ticket-arrow {
  font-family: var(--font-hand);
  font-size: 0.9rem;
  color: var(--ember-deep);
}

/* 火漆章（右下角装饰） */
.wax-seal {
  position: absolute;
  bottom: -18px;
  right: -18px;
  width: 56px;
  height: 56px;
  background: var(--crimson);
  border-radius: 50%;
  box-shadow: 0 2px 8px rgba(184, 74, 63, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  transform: rotate(12deg);
  border: 2px solid rgba(255, 255, 255, 0.3);
}
.wax-letter {
  font-family: var(--font-display);
  font-size: 1.8rem;
  color: var(--paper);
  font-weight: 700;
}

/* 尾注 */
.ticket-tail {
  font-family: var(--font-hand);
  font-size: 1rem;
  color: var(--ink-soft);
  margin: 2rem 0 0;
  text-align: center;
  line-height: 1.75;
  max-width: 420px;
}
</style>
