<!--
  第 4 幕 · Ch. 04 · Protocol · 信标 · 号角 · 旗帜
-->
<template>
  <section id="act-protocol" class="act act-protocol">
    <div class="act-head">
      <span class="act-chapter-mark">{{ protocol.chapterMark }}</span>
    </div>

    <div class="protocol-copy fade-up">
      <h2 class="protocol-title act-title">{{ protocol.title }}</h2>
      <p class="protocol-subtitle">{{ protocol.subtitle }}</p>
    </div>

    <div class="protocol-triad fade-up" style="transition-delay: 0.15s;">
      <BeaconTriad />
    </div>

    <p class="protocol-tail fade-up" style="transition-delay: 0.3s;">{{ protocol.tail }}</p>
  </section>
</template>

<script setup lang="ts">
import { onMounted, onBeforeUnmount } from 'vue';
import BeaconTriad from './BeaconTriad.vue';
import { protocol } from '../homeContent';

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
  document.querySelectorAll('#act-protocol .fade-up').forEach((el) => observer?.observe(el));
});
onBeforeUnmount(() => observer?.disconnect());
</script>

<style scoped>
.act-protocol {
  min-height: 100vh;
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
.protocol-copy {
  text-align: center;
  max-width: 820px;
  margin: 0 auto;
}
.protocol-title {
  font-size: clamp(2rem, 3.6vw, 3rem);
  margin: 0 0 0.8rem;
}
.protocol-subtitle {
  font-family: var(--font-hand);
  font-size: 1.2rem;
  color: var(--ember-deep);
  margin: 0;
}
.protocol-tail {
  text-align: center;
  font-family: var(--font-hand);
  font-size: 1.18rem;
  color: var(--ink-soft);
  max-width: 720px;
  margin: 1rem auto 0;
  line-height: 1.85;
}
</style>
