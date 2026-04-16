<!--
  第 5 幕 · Ch. 05 · Guard · 反 AI 双保险
  - 左：Style Agent 图灵回测闭环
  - 右：Critic 五维审稿单
  - 下方：GraphRAG 事实约束通栏
-->
<template>
  <section id="act-guard" class="act act-guard">
    <div class="act-head">
      <span class="act-chapter-mark">{{ guard.chapterMark }}</span>
    </div>

    <div class="guard-copy fade-up">
      <h2 class="guard-title act-title">{{ guard.title }}</h2>
      <p class="guard-subtitle">{{ guard.subtitle }}</p>
    </div>

    <div class="guard-grid">
      <!-- 左：StyleLoop -->
      <div class="guard-col fade-up">
        <div class="col-tag">一道关 · 风格克隆</div>
        <h3 class="col-title">{{ guard.styleLoop.title }}</h3>

        <!-- 步骤说明 -->
        <ol class="col-steps">
          <li v-for="(s, i) in guard.styleLoop.steps" :key="i">
            <span class="step-num">{{ String(i + 1).padStart(2, '0') }}</span>
            <span class="step-text">{{ s }}</span>
          </li>
        </ol>

        <!-- 可视化 -->
        <StyleLoop />

        <div class="col-tag-tech">
          <code>{{ guard.styleLoop.tag }}</code>
        </div>
      </div>

      <!-- 右：CriticTicket -->
      <div class="guard-col fade-up" style="transition-delay: 0.1s;">
        <div class="col-tag">二道关 · 审稿把关</div>
        <h3 class="col-title">{{ guard.criticTicket.title }}</h3>
        <p class="col-intro">
          他不替你改稿——他像一个苛刻到让你讨厌又信服的编辑那样，
          指着具体那句话，告诉你<strong>哪里假，为什么假</strong>。
        </p>

        <CriticTicket />
      </div>
    </div>

    <!-- 下方通栏：GraphRAG -->
    <div class="graph-rag fade-up" style="transition-delay: 0.2s;">
      <div class="gr-badge">
        <span>+</span>
      </div>
      <div class="gr-body">
        <h4 class="gr-title">{{ guard.graphRag.title }}</h4>
        <p class="gr-text">{{ guard.graphRag.body }}</p>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, onBeforeUnmount } from 'vue';
import StyleLoop from './visuals/StyleLoop.vue';
import CriticTicket from './visuals/CriticTicket.vue';
import { guard } from '../homeContent';

let observer: IntersectionObserver | null = null;
onMounted(() => {
  observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((e) => {
        if (e.isIntersecting) e.target.classList.add('is-visible');
      });
    },
    { threshold: 0.1 }
  );
  document.querySelectorAll('#act-guard .fade-up').forEach((el) => observer?.observe(el));
});
onBeforeUnmount(() => observer?.disconnect());
</script>

<style scoped>
.act-guard {
  min-height: 110vh;
  padding: 6rem 6vw;
  max-width: 1440px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 3rem;
}
.act-head {
  display: flex;
  justify-content: flex-start;
}
.guard-copy {
  text-align: center;
  max-width: 820px;
  margin: 0 auto;
}
.guard-title {
  font-size: clamp(2rem, 3.6vw, 3rem);
  margin: 0 0 0.8rem;
}
.guard-subtitle {
  font-family: var(--font-hand);
  font-size: 1.2rem;
  color: var(--ember-deep);
  margin: 0;
}

/* 双栏 */
.guard-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 4rem;
  align-items: stretch;
}
.guard-col {
  display: flex;
  flex-direction: column;
  gap: 1.2rem;
}
.col-tag {
  display: inline-block;
  align-self: flex-start;
  padding: 3px 10px;
  background: var(--ember-glow);
  color: var(--ember-deep);
  font-family: var(--font-mono);
  font-size: 0.74rem;
  letter-spacing: 0.22em;
  border-radius: 2px;
}
.col-title {
  font-family: var(--font-display);
  font-size: 1.6rem;
  color: var(--ink);
  letter-spacing: 0.06em;
  margin: 0;
}
.col-intro {
  font-family: var(--font-body);
  font-size: 0.98rem;
  color: var(--ink-soft);
  line-height: 1.85;
  margin: 0 0 0.8rem;
}
.col-intro strong {
  color: var(--ink);
  font-weight: 600;
}
.col-steps {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 0.65rem;
}
.col-steps li {
  display: flex;
  gap: 0.9rem;
  align-items: baseline;
  font-size: 0.93rem;
  line-height: 1.75;
  color: var(--ink);
}
.step-num {
  font-family: var(--font-mono);
  font-size: 0.78rem;
  color: var(--ember-deep);
  letter-spacing: 0.15em;
  flex-shrink: 0;
  padding-top: 2px;
}
.step-text { flex: 1; }

.col-tag-tech {
  margin-top: 0.5rem;
  text-align: center;
}
.col-tag-tech code {
  font-family: var(--font-mono);
  font-size: 0.78rem;
  color: var(--moss);
  background: var(--paper-deep);
  padding: 3px 10px;
  letter-spacing: 0.06em;
  border-radius: 2px;
}

/* 底部 GraphRAG */
.graph-rag {
  margin-top: 2.5rem;
  display: flex;
  align-items: center;
  gap: 1.8rem;
  padding: 1.6rem 2rem;
  background: linear-gradient(to right, var(--paper-deep), transparent);
  border-left: 4px solid var(--moss);
}
.gr-badge {
  width: 48px;
  height: 48px;
  flex-shrink: 0;
  border-radius: 50%;
  background: var(--moss);
  color: var(--paper);
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: var(--font-display);
  font-size: 1.6rem;
  box-shadow: 0 4px 10px rgba(74, 103, 65, 0.3);
}
.gr-body {
  flex: 1;
}
.gr-title {
  font-family: var(--font-display);
  font-size: 1.3rem;
  color: var(--ink);
  margin: 0 0 0.3rem;
  letter-spacing: 0.06em;
}
.gr-text {
  margin: 0;
  font-family: var(--font-body);
  font-size: 1rem;
  color: var(--ink-soft);
  line-height: 1.75;
}

@media (max-width: 960px) {
  .guard-grid { grid-template-columns: 1fr; gap: 3rem; }
}
</style>
