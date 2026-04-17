<!--
  第 4 幕 · Ch. 04 · Freedom · 创作自由
  四支柱：主题配色自由 / 模型自由接入 / 模型用途管理 / 配额团队共享
-->
<template>
  <section id="act-freedom" class="act act-freedom">
    <div class="act-head">
      <span class="act-chapter-mark">{{ freedom.chapterMark }}</span>
    </div>

    <div class="freedom-copy fade-up">
      <h2 class="freedom-title act-title">{{ freedom.title }}</h2>
      <p class="freedom-subtitle">{{ freedom.subtitle }}</p>
    </div>

    <!-- 四支柱卡片 -->
    <div class="pillars fade-up" style="transition-delay: 0.15s;">
      <div
        v-for="(pillar, i) in freedom.pillars"
        :key="pillar.key"
        class="pillar"
        :style="{ '--i': i }"
      >
        <div class="pillar-icon" v-html="pillarIcons[pillar.key]"></div>
        <h3 class="pillar-title">{{ pillar.title }}</h3>
        <p class="pillar-body">{{ pillar.body }}</p>
        <span class="pillar-tag">{{ pillar.tag }}</span>
      </div>
    </div>

    <p class="freedom-tail fade-up" style="transition-delay: 0.3s;">{{ freedom.tail }}</p>
  </section>
</template>

<script setup lang="ts">
import { onMounted, onBeforeUnmount } from 'vue';
import { freedom } from '../homeContent';

/* 四支柱 SVG 图标 */
const pillarIcons: Record<string, string> = {
  theme: `<svg width="44" height="44" viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
    <circle cx="24" cy="24" r="18" stroke="var(--ember)" stroke-width="1.6" stroke-dasharray="4 3"/>
    <circle cx="24" cy="24" r="8" fill="var(--ember-glow)" stroke="var(--ember)" stroke-width="1.2"/>
    <circle cx="24" cy="24" r="3" fill="var(--ember)"/>
    <path d="M24 6v4M24 38v4M6 24h4M38 24h4" stroke="var(--ink-soft)" stroke-width="1" stroke-linecap="round"/>
    <path d="M11.3 11.3l2.8 2.8M33.9 33.9l2.8 2.8M11.3 36.7l2.8-2.8M33.9 14.1l2.8-2.8" stroke="var(--ink-ghost)" stroke-width="0.8" stroke-linecap="round"/>
  </svg>`,

  model: `<svg width="44" height="44" viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
    <rect x="8" y="14" width="32" height="20" rx="3" stroke="var(--ink)" stroke-width="1.5" fill="var(--paper-deep)"/>
    <circle cx="18" cy="24" r="4" stroke="var(--ember)" stroke-width="1.2" fill="var(--ember-glow)"/>
    <circle cx="30" cy="24" r="4" stroke="var(--moss)" stroke-width="1.2" fill="rgba(74,103,65,0.12)"/>
    <path d="M22 24h4" stroke="var(--ink-soft)" stroke-width="1" stroke-linecap="round" stroke-dasharray="2 2"/>
    <path d="M8 20h-2c-1 0-2 1-2 2v4c0 1 1 2 2 2h2M40 20h2c1 0 2 1 2 2v4c0 1-1 2-2 2h-2" stroke="var(--ink-soft)" stroke-width="1" stroke-linecap="round"/>
  </svg>`,

  routing: `<svg width="44" height="44" viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
    <rect x="6" y="8" width="16" height="12" rx="2" stroke="var(--ember)" stroke-width="1.2" fill="var(--ember-glow)"/>
    <text x="14" y="17" text-anchor="middle" font-size="6" fill="var(--ember-deep)" font-family="var(--font-mono)">Muse</text>
    <rect x="26" y="8" width="16" height="12" rx="2" stroke="var(--moss)" stroke-width="1.2" fill="rgba(74,103,65,0.1)"/>
    <text x="34" y="17" text-anchor="middle" font-size="5.5" fill="var(--moss)" font-family="var(--font-mono)">Critic</text>
    <path d="M14 20v6l10 4v6" stroke="var(--ink-soft)" stroke-width="1" stroke-linecap="round" stroke-dasharray="3 2"/>
    <path d="M34 20v6l-10 4v6" stroke="var(--ink-soft)" stroke-width="1" stroke-linecap="round" stroke-dasharray="3 2"/>
    <rect x="14" y="32" width="20" height="8" rx="2" stroke="var(--ink)" stroke-width="1.2" fill="var(--paper-deep)"/>
    <text x="24" y="38.5" text-anchor="middle" font-size="5" fill="var(--ink-soft)" font-family="var(--font-mono)">GPT-4o</text>
  </svg>`,

  quota: `<svg width="44" height="44" viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
    <circle cx="18" cy="18" r="8" stroke="var(--ember)" stroke-width="1.4" fill="var(--ember-glow)"/>
    <circle cx="30" cy="18" r="8" stroke="var(--moss)" stroke-width="1.4" fill="rgba(74,103,65,0.1)"/>
    <path d="M18 26v6c0 2 2 4 6 4s6-2 6-4v-6" stroke="var(--ink-soft)" stroke-width="1" stroke-linecap="round" stroke-dasharray="3 2"/>
    <rect x="12" y="36" width="24" height="6" rx="2" stroke="var(--ink)" stroke-width="1.2" fill="var(--paper-deep)"/>
    <path d="M18 36v6M24 36v6M30 36v6" stroke="var(--ink-ghost)" stroke-width="0.6"/>
  </svg>`,
};

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
  document.querySelectorAll('#act-freedom .fade-up').forEach((el) => observer?.observe(el));
});
onBeforeUnmount(() => observer?.disconnect());
</script>

<style scoped>
.act-freedom {
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
.freedom-copy {
  text-align: center;
  max-width: 820px;
  margin: 0 auto;
}
.freedom-title {
  font-size: clamp(2rem, 3.6vw, 3rem);
  margin: 0 0 0.8rem;
}
.freedom-subtitle {
  font-family: var(--font-hand);
  font-size: 1.2rem;
  color: var(--ember-deep);
  margin: 0;
}

/* 四支柱网格 */
.pillars {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 2rem;
  max-width: 1200px;
  margin: 0 auto;
  width: 100%;
}

.pillar {
  position: relative;
  padding: 2rem 1.6rem 1.8rem;
  background: var(--paper);
  border: 1px solid var(--ink-ghost);
  border-radius: 3px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.9rem;
  text-align: center;
  transition: transform 260ms ease, box-shadow 260ms ease, border-color 260ms ease;
}
.pillar:hover {
  transform: translateY(-4px);
  box-shadow: 0 8px 24px rgba(42, 36, 32, 0.1);
  border-color: var(--ember-glow);
}

.pillar-icon {
  width: 44px;
  height: 44px;
  color: var(--ember);
  flex-shrink: 0;
}

.pillar-title {
  font-family: var(--font-display);
  font-size: 1.15rem;
  font-weight: 400;
  color: var(--ink);
  letter-spacing: 0.08em;
  margin: 0;
}

.pillar-body {
  font-size: 0.92rem;
  color: var(--ink-soft);
  line-height: 1.75;
  margin: 0;
}

.pillar-tag {
  display: inline-block;
  font-family: var(--font-mono);
  font-size: 0.68rem;
  color: var(--moss);
  background: rgba(74, 103, 65, 0.08);
  padding: 2px 10px;
  border-radius: 2px;
  letter-spacing: 0.04em;
  margin-top: auto;
}

.freedom-tail {
  text-align: center;
  font-family: var(--font-hand);
  font-size: 1.18rem;
  color: var(--ink-soft);
  max-width: 720px;
  margin: 1rem auto 0;
  line-height: 1.85;
}

@media (max-width: 960px) {
  .pillars {
    grid-template-columns: repeat(2, 1fr);
  }
}
@media (max-width: 600px) {
  .pillars {
    grid-template-columns: 1fr;
  }
}
</style>
