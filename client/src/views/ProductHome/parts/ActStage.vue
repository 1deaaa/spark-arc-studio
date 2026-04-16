<!--
  第 7 幕 · Ch. 07 · Stage · 故事登台演出
-->
<template>
  <section id="act-stage" class="act act-stage">
    <div class="act-head">
      <span class="act-chapter-mark">{{ stage.chapterMark }}</span>
    </div>

    <div class="stage-copy fade-up">
      <h2 class="stage-title act-title">{{ stage.title }}</h2>
      <p class="stage-subtitle">{{ stage.subtitle }}</p>
    </div>

    <div class="stage-cards fade-up" style="transition-delay: 0.15s;">
      <StageQuartet />
    </div>

    <div class="stage-foot fade-up" style="transition-delay: 0.3s;">
      <div class="platforms">
        <span class="platforms-label">容器</span>
        <span class="platforms-list">{{ stage.platforms }}</span>
      </div>
      <p class="stage-tail">{{ stage.tail }}</p>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, onBeforeUnmount } from 'vue';
import StageQuartet from './visuals/StageQuartet.vue';
import { stage } from '../homeContent';

let observer: IntersectionObserver | null = null;
onMounted(() => {
  observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((e) => {
        if (e.isIntersecting) e.target.classList.add('is-visible');
      });
    },
    { threshold: 0.12 }
  );
  document.querySelectorAll('#act-stage .fade-up').forEach((el) => observer?.observe(el));
});
onBeforeUnmount(() => observer?.disconnect());
</script>

<style scoped>
.act-stage {
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
.stage-copy {
  text-align: center;
  max-width: 820px;
  margin: 0 auto;
}
.stage-title {
  font-size: clamp(2rem, 3.6vw, 3rem);
  margin: 0 0 0.8rem;
}
.stage-subtitle {
  font-family: var(--font-hand);
  font-size: 1.2rem;
  color: var(--ember-deep);
  margin: 0;
}

.stage-cards {
  margin-top: 1rem;
}

.stage-foot {
  margin-top: 3rem;
  max-width: 900px;
  margin-left: auto;
  margin-right: auto;
  text-align: center;
}
.platforms {
  display: inline-flex;
  align-items: center;
  gap: 1rem;
  padding: 0.6rem 1.4rem;
  background: var(--paper-deep);
  border: 1px dashed var(--ink-ghost);
  border-radius: 2px;
  margin-bottom: 1.2rem;
}
.platforms-label {
  font-family: var(--font-mono);
  font-size: 0.78rem;
  color: var(--ink-soft);
  letter-spacing: 0.2em;
  border-right: 1px solid var(--ink-ghost);
  padding-right: 0.9rem;
}
.platforms-list {
  font-family: var(--font-mono);
  font-size: 0.92rem;
  color: var(--ink);
  letter-spacing: 0.08em;
}
.stage-tail {
  font-family: var(--font-hand);
  font-size: 1.2rem;
  color: var(--ink-soft);
  margin: 0;
  line-height: 1.85;
}
</style>
