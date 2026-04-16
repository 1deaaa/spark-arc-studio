<!--
  第 8 幕 · Ch. 08 · Finale · 写给未来的创作者
  - 书页翻面：背景渐变到深墨
  - 金色大标 + 三句哲学 + CTA
-->
<template>
  <section id="act-finale" class="act act-finale">
    <!-- 纸页翻面蒙层 -->
    <div class="page-flip" aria-hidden="true"></div>

    <div class="finale-inner">
      <div class="act-head">
        <span class="act-chapter-mark">{{ finale.chapterMark }}</span>
      </div>

      <h2 class="finale-title fade-up">{{ finale.title }}</h2>

      <div class="finale-creed">
        <p
          v-for="(line, i) in finale.creed"
          :key="i"
          class="creed-line fade-up"
          :style="{ transitionDelay: `${0.2 + i * 0.18}s` }"
        >{{ line }}</p>
      </div>

      <div class="finale-cta fade-up" style="transition-delay: 1.2s;">
        <a class="stamp-btn stamp-btn-gold" :href="`#${finale.ctaPrimary.to}`" @click.prevent="onPrimary">
          {{ finale.ctaPrimary.label }}
          <span class="arrow">→</span>
        </a>
        <a class="ghost-btn ghost-btn-gold" :href="finale.ctaSecondary.to" target="_blank" rel="noopener">
          {{ finale.ctaSecondary.label }}
          <span class="arrow">↗</span>
        </a>
      </div>

      <p class="finale-micro fade-up" style="transition-delay: 1.5s;">
        {{ finale.micro }}
      </p>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, onBeforeUnmount } from 'vue';
import { useRouter } from 'vue-router';
import { finale } from '../homeContent';

const router = useRouter();

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
  document.querySelectorAll('#act-finale .fade-up').forEach((el) => observer?.observe(el));
});
onBeforeUnmount(() => observer?.disconnect());

function onPrimary() {
  router.push(finale.ctaPrimary.to);
}
</script>

<style scoped>
.act-finale {
  position: relative;
  min-height: 100vh;
  padding: 8rem 6vw;
  background: var(--paper-night);
  color: var(--gold);
  overflow: hidden;
  isolation: isolate;
}

/* 纸页翻面效果（装饰） */
.page-flip {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 140px;
  background:
    linear-gradient(to bottom, var(--paper) 0%, var(--paper-deep) 40%, var(--paper-night) 100%);
  pointer-events: none;
  clip-path: polygon(0 0, 100% 0, 100% 50%, 70% 70%, 50% 80%, 30% 90%, 10% 100%, 0 100%);
  z-index: 1;
  opacity: 0.4;
}

.finale-inner {
  position: relative;
  z-index: 2;
  max-width: 900px;
  margin: 0 auto;
  text-align: center;
  display: flex;
  flex-direction: column;
  gap: 2.5rem;
}

.act-head {
  display: flex;
  justify-content: center;
}
.act-finale .act-chapter-mark {
  color: var(--gold-soft);
  opacity: 0.7;
}

.finale-title {
  font-family: var(--font-display);
  font-size: clamp(2.6rem, 6vw, 5rem);
  color: var(--gold);
  letter-spacing: 0.08em;
  line-height: 1.25;
  margin: 0;
  text-shadow: 0 0 40px rgba(247, 217, 138, 0.2);
}

.finale-creed {
  display: flex;
  flex-direction: column;
  gap: 1.2rem;
  max-width: 720px;
  margin: 0 auto;
  padding: 2rem 0;
  border-top: 1px solid rgba(247, 217, 138, 0.25);
  border-bottom: 1px solid rgba(247, 217, 138, 0.25);
}
.creed-line {
  font-family: var(--font-hand);
  font-size: clamp(1.15rem, 1.8vw, 1.6rem);
  color: var(--gold-soft);
  line-height: 1.85;
  margin: 0;
  letter-spacing: 0.04em;
}
.creed-line:nth-child(3) {
  color: var(--gold);
  font-weight: 600;
}

.finale-cta {
  display: flex;
  gap: 1.2rem;
  justify-content: center;
  flex-wrap: wrap;
}
.stamp-btn-gold {
  background: var(--gold);
  color: var(--paper-night);
  border-color: var(--gold-soft);
  box-shadow: 0 2px 0 var(--ember-deep), 0 8px 24px rgba(247, 217, 138, 0.35);
}
.stamp-btn-gold:hover {
  background: var(--gold-soft);
  color: var(--paper-night);
}
.ghost-btn-gold {
  border-color: var(--gold);
  color: var(--gold);
}
.ghost-btn-gold:hover {
  background: var(--gold);
  color: var(--paper-night);
}

.finale-micro {
  font-family: var(--font-mono);
  font-size: 0.85rem;
  color: var(--gold-soft);
  opacity: 0.65;
  letter-spacing: 0.08em;
  margin: 0;
  line-height: 1.8;
}

/* fade-up 在深色背景里重新定义（白色幽灵起点） */
.act-finale .fade-up {
  opacity: 0;
  transform: translateY(32px);
  transition: opacity 900ms cubic-bezier(0.22, 0.61, 0.36, 1),
              transform 900ms cubic-bezier(0.22, 0.61, 0.36, 1);
}
.act-finale .fade-up.is-visible {
  opacity: 1;
  transform: translateY(0);
}
</style>
