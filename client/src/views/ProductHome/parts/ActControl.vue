<!--
  第 6 幕 · Ch. 06 · White-box · 白盒可控
  - 左：ControlDial
  - 右：三枚印章按钮（打断/重写/指定专家）
  - 底部尾文
-->
<template>
  <section id="act-control" class="act act-control">
    <div class="act-head">
      <span class="act-chapter-mark">{{ control.chapterMark }}</span>
    </div>

    <div class="control-copy fade-up">
      <h2 class="control-title act-title">{{ control.title }}</h2>
      <p class="control-subtitle">{{ control.subtitle }}</p>
    </div>

    <div class="control-grid">
      <!-- 左：旋钮 -->
      <div class="control-left fade-up">
        <ControlDial />
      </div>

      <!-- 右：三印章 -->
      <div class="control-right fade-up" style="transition-delay: 0.1s;">
        <h3 class="stamps-title">随时可用的三枚印章</h3>
        <p class="stamps-sub">创作是你的。过程里任何时候，主动权都可以被你拿回来。</p>

        <div class="stamps-grid">
          <button
            v-for="(s, i) in control.stamps"
            :key="s.key"
            class="stamp-card"
            :class="[`stamp-${s.key}`, { 'is-hover': hovered === i }]"
            @mouseenter="hovered = i"
            @mouseleave="hovered = null"
          >
            <div class="stamp-circle">
              <span class="stamp-char">{{ s.label }}</span>
            </div>
            <span class="stamp-name">{{ s.label }}</span>
            <span class="stamp-desc">{{ s.desc }}</span>
          </button>
        </div>
      </div>
    </div>

    <!-- 尾文 -->
    <div class="control-tail fade-up" style="transition-delay: 0.2s;">
      <p>{{ control.tail }}</p>
    </div>
  </section>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue';
import ControlDial from './visuals/ControlDial.vue';
import { control } from '../homeContent';

const hovered = ref<number | null>(null);

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
  document.querySelectorAll('#act-control .fade-up').forEach((el) => observer?.observe(el));
});
onBeforeUnmount(() => observer?.disconnect());
</script>

<style scoped>
.act-control {
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
.control-copy {
  text-align: center;
  max-width: 820px;
  margin: 0 auto;
}
.control-title {
  font-size: clamp(2rem, 3.6vw, 3rem);
  margin: 0 0 0.8rem;
}
.control-subtitle {
  font-family: var(--font-hand);
  font-size: 1.2rem;
  color: var(--ember-deep);
  margin: 0;
}

/* 双栏 */
.control-grid {
  display: grid;
  grid-template-columns: 1fr 1.3fr;
  gap: 5rem;
  align-items: center;
}
.control-left {
  display: flex;
  justify-content: center;
}
.control-right {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}
.stamps-title {
  font-family: var(--font-display);
  font-size: 1.5rem;
  color: var(--ink);
  margin: 0;
  letter-spacing: 0.08em;
}
.stamps-sub {
  font-family: var(--font-hand);
  font-size: 1.05rem;
  color: var(--ember-deep);
  margin: 0 0 1rem;
}
.stamps-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 1.2rem;
}
.stamp-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.75rem;
  padding: 1.5rem 1rem;
  background: var(--paper);
  border: 1px solid var(--ink);
  box-shadow: 3px 3px 0 var(--ink);
  cursor: pointer;
  transition: transform 200ms ease, box-shadow 200ms ease;
  font-family: inherit;
  text-align: center;
}
.stamp-card:hover {
  transform: translate(2px, 2px);
  box-shadow: 1px 1px 0 var(--ink);
}
.stamp-card:active {
  transform: translate(3px, 3px);
  box-shadow: 0 0 0 var(--ink);
}
.stamp-circle {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  border: 2.5px solid var(--ember);
  background: var(--paper);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: transform 300ms ease;
}
.stamp-card:hover .stamp-circle {
  transform: rotate(-6deg) scale(1.05);
}
.stamp-char {
  font-family: var(--font-display);
  font-size: 1.2rem;
  color: var(--ember-deep);
  letter-spacing: 0.1em;
  font-weight: 600;
}
.stamp-name {
  font-family: var(--font-display);
  font-size: 1.05rem;
  color: var(--ink);
  letter-spacing: 0.12em;
}
.stamp-desc {
  font-size: 0.84rem;
  color: var(--ink-soft);
  line-height: 1.65;
}

.stamp-rewrite .stamp-circle { border-color: var(--moss); }
.stamp-rewrite .stamp-char { color: var(--moss); }
.stamp-delegate .stamp-circle { border-color: var(--slate); }
.stamp-delegate .stamp-char { color: var(--slate); }

/* 尾文 */
.control-tail {
  max-width: 820px;
  margin: 2rem auto 0;
  padding: 1.6rem 2rem;
  background: rgba(250, 246, 238, 0.7);
  border-left: 3px solid var(--ink);
  text-align: center;
}
.control-tail p {
  margin: 0;
  font-family: var(--font-hand);
  font-size: 1.2rem;
  color: var(--ink);
  line-height: 1.85;
}

@media (max-width: 960px) {
  .control-grid { grid-template-columns: 1fr; gap: 3rem; }
  .stamps-grid { grid-template-columns: 1fr; gap: 0.8rem; }
}
</style>
