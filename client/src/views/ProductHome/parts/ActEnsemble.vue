<!--
  第 3 幕 · Ch. 03 · Ensemble · 编剧部的六把椅子
  - 标题 + 副标
  - AgentRoundTable 大尺寸完整交互版
  - 三模态彩蛋
-->
<template>
  <section id="act-ensemble" class="act act-ensemble">
    <div class="act-head">
      <span class="act-chapter-mark">{{ ensemble.chapterMark }}</span>
    </div>

    <div class="ensemble-copy fade-up">
      <h2 class="ensemble-title act-title">{{ ensemble.title }}</h2>
      <p class="ensemble-subtitle">{{ ensemble.subtitle }}</p>
    </div>

    <div class="round-holder fade-up" style="transition-delay: 0.15s;">
      <AgentRoundTable size="full" />
    </div>

    <!-- 三模态彩蛋 -->
    <div class="triple-mode fade-up" style="transition-delay: 0.25s;">
      <div class="tm-rule"></div>
      <div class="tm-body">
        <h3 class="tm-title">{{ ensemble.tripleMode.title }}</h3>
        <ul class="tm-list">
          <li v-for="(line, i) in ensemble.tripleMode.lines" :key="i">
            <span class="tm-num">{{ i + 1 }}</span>
            <span class="tm-text">{{ line }}</span>
          </li>
        </ul>
        <p class="tm-tail">{{ ensemble.tripleMode.tail }}</p>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, onBeforeUnmount } from 'vue';
import AgentRoundTable from './visuals/AgentRoundTable.vue';
import { ensemble } from '../homeContent';

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
  document.querySelectorAll('#act-ensemble .fade-up').forEach((el) => observer?.observe(el));
});
onBeforeUnmount(() => observer?.disconnect());
</script>

<style scoped>
.act-ensemble {
  min-height: 100vh;
  padding: 6rem 6vw 8rem;
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

.ensemble-copy {
  text-align: center;
  max-width: 800px;
  margin: 0 auto;
}
.ensemble-title {
  font-size: clamp(2.2rem, 4vw, 3.4rem);
  margin: 0 0 0.8rem;
}
.ensemble-subtitle {
  font-family: var(--font-hand);
  font-size: 1.25rem;
  color: var(--ember-deep);
  margin: 0;
}

.round-holder {
  width: min(100%, 720px);
  aspect-ratio: 1 / 1;
  margin: 0 auto;
}

/* 三模态彩蛋 */
.triple-mode {
  max-width: 900px;
  margin: 2rem auto 0;
  padding: 2.5rem 2.8rem;
  background: rgba(250, 246, 238, 0.6);
  border: 1px solid var(--ink-ghost);
  position: relative;
}
.tm-rule {
  position: absolute;
  left: 2rem;
  top: -1px;
  width: 80px;
  height: 3px;
  background: var(--ember);
}
.tm-title {
  font-family: var(--font-display);
  font-size: 1.4rem;
  color: var(--ink);
  letter-spacing: 0.08em;
  margin: 0 0 1.4rem;
}
.tm-list {
  list-style: none;
  padding: 0;
  margin: 0 0 1.2rem;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}
.tm-list li {
  display: flex;
  gap: 1rem;
  align-items: baseline;
}
.tm-num {
  font-family: var(--font-mono);
  font-size: 0.85rem;
  color: var(--ember-deep);
  letter-spacing: 0.15em;
  flex-shrink: 0;
  padding-top: 2px;
}
.tm-text {
  font-family: var(--font-body);
  color: var(--ink);
  font-size: 1.05rem;
  line-height: 1.8;
}
.tm-tail {
  margin: 1.2rem 0 0;
  padding-top: 1rem;
  border-top: 1px dashed var(--ink-ghost);
  font-family: var(--font-hand);
  font-size: 1.1rem;
  color: var(--ember-deep);
  line-height: 1.75;
}
</style>
