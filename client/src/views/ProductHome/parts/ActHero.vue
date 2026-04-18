<!--
  第 0 幕 · Ch. 00 · Spark · 一点星火
  - 书页装订线（左右纵向虚线 + 三枚装订眼印章）
  - 顶部章节页码
  - FZYaoTi 大标（墨滴进场动画）
  - 手写体副标
  - 打字机（循环 6 条）
  - 双 CTA 印章按钮
-->
<template>
  <section id="act-hero" class="act act-hero">
    <!-- 书页装订（左右两侧） -->
    <div class="binding binding-left" aria-hidden="true">
      <div class="binding-line"></div>
      <span class="eye" v-for="n in 3" :key="`bl-${n}`" :style="{ top: `${18 + n * 22}%` }"></span>
    </div>
    <div class="binding binding-right" aria-hidden="true">
      <div class="binding-line"></div>
      <span class="eye" v-for="n in 3" :key="`br-${n}`" :style="{ top: `${18 + n * 22}%` }"></span>
    </div>

    <!-- 顶部章节页码 -->
    <div class="hero-chapter">
      <span class="hero-chapter-mark">{{ hero.chapterMark }}</span>
      <span class="hero-chapter-dot">·</span>
      <span class="hero-chapter-edition">{{ brand.name }} · {{ brand.zhName }}</span>
    </div>

    <!-- 主内容 -->
    <div class="hero-content">
      <h1 class="hero-title">
        <span
          v-for="(line, i) in hero.titleLines"
          :key="i"
          class="title-line"
          :style="{ animationDelay: `${0.2 + i * 0.32}s` }"
        >{{ line }}</span>
      </h1>

      <div class="hero-sub-wrap">
        <p class="hero-subtitle">{{ hero.subtitle }}</p>
        <p class="hero-helper">{{ hero.helper }}</p>
      </div>

      <!-- 打字机 -->
      <div class="hero-typing">
        <span class="typing-prefix">我给你的——</span>
        <span class="typing-text">{{ typingText }}<span class="cursor">|</span></span>
      </div>

      <!-- CTA -->
      <div class="hero-cta">
        <a class="stamp-btn" :href="`#${hero.ctaPrimary.to}`" @click.prevent="onPrimary">
          {{ hero.ctaPrimary.label }}
          <span class="arrow">→</span>
        </a>
        <a class="ghost-btn" :href="hero.ctaSecondary.to" @click.prevent="onSecondary">
          {{ hero.ctaSecondary.label }}
          <span class="arrow-down">↓</span>
        </a>
      </div>
    </div>

    <!-- 底部下滚提示 -->
    <div class="scroll-hint" aria-hidden="true">
      <span class="scroll-hint-dot"></span>
      <span class="scroll-hint-line"></span>
      <span class="scroll-hint-text">向下，翻开第一页</span>
    </div>
  </section>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue';
import { useRouter } from 'vue-router';
import { hero, brand } from '../homeContent';

const router = useRouter();

/* ---------- 打字机（6 条循环，逐字显示 + 停留 + 清除） ---------- */
const typingText = ref('');
let typingTimer: ReturnType<typeof setTimeout> | null = null;
let wordIdx = 0;

function typeLoop() {
  const word = hero.typingWords[wordIdx];
  let i = 0;

  function typeChar() {
    if (i <= word.length) {
      typingText.value = word.slice(0, i);
      i++;
      typingTimer = setTimeout(typeChar, 80);
    } else {
      typingTimer = setTimeout(eraseChar, 1800);
    }
  }
  function eraseChar() {
    if (i > 0) {
      i--;
      typingText.value = word.slice(0, i);
      typingTimer = setTimeout(eraseChar, 36);
    } else {
      wordIdx = (wordIdx + 1) % hero.typingWords.length;
      typingTimer = setTimeout(typeLoop, 260);
    }
  }
  typeChar();
}

onMounted(() => {
  typeLoop();
});
onBeforeUnmount(() => {
  if (typingTimer) clearTimeout(typingTimer);
});

/* ---------- CTA ---------- */
function onPrimary() {
  router.push(hero.ctaPrimary.to);
}
function onSecondary() {
  const el = document.getElementById(hero.ctaSecondary.to.replace('#', ''));
  const scrollTarget = document.querySelector<HTMLElement>('.product-home');
  if (!el || !scrollTarget) return;
  const elRect = el.getBoundingClientRect();
  const rootRect = scrollTarget.getBoundingClientRect();
  const topPos = elRect.top - rootRect.top + scrollTarget.scrollTop;
  const topbar = document.querySelector<HTMLElement>('.site-top');
  const topbarH = topbar ? topbar.offsetHeight : 72;
  scrollTarget.scrollTo({ top: topPos - topbarH - 4, behavior: 'smooth' });
}
</script>

<style scoped>
.act-hero {
  position: relative;
  min-height: calc(100vh - 64px);
  padding: 2.5rem 6vw 3.5rem;
  display: flex;
  flex-direction: column;
  justify-content: center;
  box-sizing: border-box;
  overflow: hidden;
}

/* 书页装订线 */
.binding {
  position: absolute;
  top: 0;
  bottom: 0;
  width: 42px;
  display: flex;
  justify-content: center;
  pointer-events: none;
}
.binding-left { left: 1.8vw; }
.binding-right { right: 1.8vw; }
.binding-line {
  width: 1px;
  height: 100%;
  background-image: linear-gradient(to bottom, var(--ink) 50%, transparent 50%);
  background-size: 1px 8px;
  opacity: 0.35;
}
.eye {
  position: absolute;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: var(--ember);
  box-shadow: 0 0 0 3px var(--paper), 0 0 0 4px var(--ember-deep), 0 0 14px var(--ember-glow);
  animation: eye-breath 3.6s ease-in-out infinite;
}
.eye:nth-child(3) { animation-delay: 1.2s; }
.eye:nth-child(4) { animation-delay: 2.4s; }
@keyframes eye-breath {
  0%, 100% { opacity: 0.7; transform: scale(0.92); }
  50% { opacity: 1; transform: scale(1.05); }
}

/* 顶部章节页码 */
.hero-chapter {
  display: flex;
  align-items: baseline;
  gap: 0.6rem;
  margin-bottom: 2rem;
  padding-left: 0.4rem;
  opacity: 0;
  animation: fade-in 800ms ease 200ms forwards;
}
.hero-chapter-mark {
  font-family: var(--font-mono);
  font-size: 0.95rem;
  color: var(--ember-deep);
  letter-spacing: 0.3em;
  padding: 3px 10px;
  border: 1px solid var(--ember-deep);
  border-radius: 2px;
}
.hero-chapter-dot {
  color: var(--ink-ghost);
}
.hero-chapter-edition {
  font-family: var(--font-mono);
  font-size: 0.8rem;
  color: var(--ink-soft);
  letter-spacing: 0.22em;
  opacity: 0.7;
}

/* 主内容 */
.hero-content {
  display: flex;
  flex-direction: column;
  flex: 1;
  justify-content: center;
  max-width: 900px;
  width: 100%;
  margin: 0 auto;
}

/* 标题 */
.hero-title {
  font-family: var(--font-display);
  font-weight: 400;
  font-size: clamp(2.4rem, 5.2vw, 4.8rem);
  line-height: 1.18;
  color: var(--ink);
  letter-spacing: 0.03em;
  margin: 0 0 1.8rem;
  display: flex;
  flex-direction: column;
}
.title-line {
  display: inline-block;
  white-space: nowrap;
  opacity: 0;
  filter: blur(8px);
  transform: translateY(16px);
  animation: ink-bloom 1.3s cubic-bezier(0.22, 0.61, 0.36, 1) forwards;
}
@keyframes ink-bloom {
  0%   { opacity: 0; filter: blur(10px); transform: translateY(20px); }
  60%  { opacity: 0.85; filter: blur(2px); transform: translateY(2px); }
  100% { opacity: 1; filter: blur(0); transform: translateY(0); }
}
@keyframes fade-in {
  from { opacity: 0; transform: translateY(8px); }
  to   { opacity: 1; transform: none; }
}

/* 副标 + 辅文 */
.hero-sub-wrap {
  margin-bottom: 1.4rem;
  opacity: 0;
  animation: fade-in 800ms ease 1.4s forwards;
}
.hero-subtitle {
  font-family: var(--font-hand);
  font-size: clamp(1.2rem, 1.6vw, 1.65rem);
  color: var(--ember-deep);
  margin: 0 0 0.5rem;
  line-height: 1.5;
}
.hero-helper {
  font-size: 0.95rem;
  color: var(--ink-soft);
  letter-spacing: 0.08em;
  margin: 0;
}

/* 打字机 */
.hero-typing {
  display: flex;
  align-items: baseline;
  gap: 0.5rem;
  margin-bottom: 1.8rem;
  padding: 0.85rem 1.1rem;
  background: rgba(250, 246, 238, 0.6);
  border-left: 3px solid var(--ember);
  box-shadow: 4px 4px 0 var(--ink-ghost);
  opacity: 0;
  animation: fade-in 800ms ease 1.7s forwards;
  min-height: 2.8rem;
  max-width: 620px;
}
.typing-prefix {
  font-family: var(--font-display);
  font-size: 1.05rem;
  color: var(--ink-soft);
  letter-spacing: 0.1em;
  white-space: nowrap;
}
.typing-text {
  font-family: var(--font-display);
  font-size: 1.3rem;
  color: var(--ink);
  letter-spacing: 0.06em;
}
.cursor {
  display: inline-block;
  margin-left: 2px;
  color: var(--ember);
  animation: blink 1s steps(1) infinite;
}
@keyframes blink {
  50% { opacity: 0; }
}

/* CTA */
.hero-cta {
  display: flex;
  gap: 1.2rem;
  flex-wrap: wrap;
  opacity: 0;
  animation: fade-in 800ms ease 2s forwards;
}
.hero-cta .arrow,
.hero-cta .arrow-down {
  font-family: var(--font-mono);
  transition: transform 160ms ease;
}
.hero-cta .stamp-btn:hover .arrow { transform: translateX(4px); }
.hero-cta .ghost-btn:hover .arrow-down { transform: translateY(3px); }

/* 底部滚动提示 */
.scroll-hint {
  position: absolute;
  bottom: 2rem;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  color: var(--ink-soft);
  opacity: 0;
  animation: fade-in 900ms ease 2.5s forwards;
}
.scroll-hint-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--ember);
  animation: hop 1.8s ease-in-out infinite;
}
.scroll-hint-line {
  width: 1px;
  height: 28px;
  background: linear-gradient(to bottom, var(--ink-soft), transparent);
}
.scroll-hint-text {
  font-family: var(--font-hand);
  font-size: 0.9rem;
  letter-spacing: 0.15em;
}
@keyframes hop {
  0%, 100% { transform: translateY(0); opacity: 1; }
  50% { transform: translateY(6px); opacity: 0.4; }
}

/* 响应式 */
@media (max-width: 960px) {
  .binding { display: none; }
}
</style>
