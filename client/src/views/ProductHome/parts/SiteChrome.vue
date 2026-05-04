<!--
  SiteChrome · 顶部导航栏 + 底部页脚
  position='top'    → 顶栏（半透明书页 + 装订底线 + 当前章节高亮）
  position='bottom' → 页脚（品牌 · 两列链接 · 版权 · 法律声明）
-->
<template>
  <!-- ============== 顶部导航 ============== -->
  <header v-if="position === 'top'" class="site-top" :class="{ 'is-scrolled': isScrolled }">
    <div class="top-inner">
      <a :href="SPARKARC_GITHUB_URL" target="_blank" rel="noopener" class="brand">
        <AppBrand class="brand-main" :size="28" />
        <span class="brand-edition">{{ brand.edition }}</span>
      </a>

      <nav class="top-nav" aria-label="产品主页章节">
        <a
          v-for="link in nav.links"
          :key="link.id"
          :href="`#${link.id}`"
          class="nav-link"
          :class="{ 'is-active': activeId === link.id }"
          @click.prevent="scrollToSection(link.id)"
        >
          {{ link.label }}
        </a>
      </nav>

      <a href="#/login" class="top-cta stamp-btn">
        {{ nav.cta }}
        <span class="arrow">→</span>
      </a>
    </div>
  </header>

  <!-- ============== 底部页脚 ============== -->
  <footer v-else class="site-bottom">
    <div class="bottom-inner">
      <div class="foot-brand">
        <a :href="SPARKARC_GITHUB_URL" target="_blank" rel="noopener" class="foot-brand-link">
          <AppBrand class="foot-logo" :size="32" :text="footer.brand.name" />
          <p class="foot-tagline">{{ footer.brand.tagline }}</p>
        </a>
      </div>

      <div class="foot-columns">
        <div class="foot-col" v-for="col in footer.columns" :key="col.title">
          <h4 class="col-title">{{ col.title }}</h4>
          <ul class="col-list">
            <li v-for="l in col.links" :key="l.label">
              <a
                :href="resolveHref(l.to)"
                :target="isExternal(l.to) ? '_blank' : undefined"
                :rel="isExternal(l.to) ? 'noopener' : undefined"
              >{{ l.label }}</a>
            </li>
          </ul>
        </div>
      </div>
    </div>

    <div class="bottom-foot">
      <p class="copyright">
        <a :href="SPARKARC_GITHUB_URL" target="_blank" rel="noopener" class="disclaimer-link">© 2025 SparkArc</a> · All rights reserved.
      </p>
      <p class="disclaimer">
        <a :href="SPARKARC_GITHUB_URL" target="_blank" rel="noopener" class="disclaimer-link">SparkArc</a>{{ footer.disclaimer.replace('SparkArc', '') }}
      </p>
    </div>
  </footer>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue';
import AppBrand from '@/components/share/AppBrand.vue';
import { brand, nav, footer } from '../homeContent';
import { SPARKARC_GITHUB_URL } from '@/config';

defineProps<{
  position: 'top' | 'bottom';
}>();

const isScrolled = ref(false);
const activeId = ref<string>('');

let scrollTarget: HTMLElement | null = null;
let sectionCache: HTMLElement[] = [];

function refreshSections() {
  sectionCache = nav.links
    .map((l) => document.getElementById(l.id))
    .filter((el): el is HTMLElement => !!el);
}

function onScroll() {
  if (!scrollTarget) return;
  const top = scrollTarget.scrollTop;
  isScrolled.value = top > 24;

  // 当前可见章节（离视口顶部 30% 最近的 section）
  const rootRect = scrollTarget.getBoundingClientRect();
  const viewportProbe = scrollTarget.clientHeight * 0.3;
  let current = '';
  for (const sec of sectionCache) {
    const secTop = sec.getBoundingClientRect().top - rootRect.top;
    if (secTop <= viewportProbe) current = sec.id;
    else break;
  }
  activeId.value = current;
}

function scrollToSection(id: string) {
  const el = document.getElementById(id);
  if (!el || !scrollTarget) return;
  const elRect = el.getBoundingClientRect();
  const rootRect = scrollTarget.getBoundingClientRect();
  const topPos = elRect.top - rootRect.top + scrollTarget.scrollTop;
  // 减去 sticky 顶栏高度
  const topbar = document.querySelector<HTMLElement>('.site-top');
  const topbarH = topbar ? topbar.offsetHeight : 72;
  scrollTarget.scrollTo({ top: topPos - topbarH - 4, behavior: 'smooth' });
}

function scrollToTop() {
  scrollTarget?.scrollTo({ top: 0, behavior: 'smooth' });
}

/** 判断链接是否是外部链接 */
function isExternal(to: string): boolean {
  return /^(https?:)?\/\//.test(to) || to.startsWith('mailto:');
}

/** 把 SPA 路由（/login）转成 hash 路由（#/login），其他保持 */
function resolveHref(to: string): string {
  if (isExternal(to) || to.startsWith('#') || to === '#') return to;
  if (to.startsWith('/')) return `#${to}`;
  return to;
}

onMounted(() => {
  scrollTarget = document.querySelector<HTMLElement>('.product-home');
  if (!scrollTarget) return;
  refreshSections();
  scrollTarget.addEventListener('scroll', onScroll, { passive: true });
  // 首次刷新
  setTimeout(() => {
    refreshSections();
    onScroll();
  }, 50);
});

onBeforeUnmount(() => {
  scrollTarget?.removeEventListener('scroll', onScroll);
});
</script>

<style scoped>
/* ============================================================
   顶栏
   ============================================================ */
.site-top {
  position: sticky;
  top: 0;
  left: 0;
  right: 0;
  z-index: 50;
  background: rgba(250, 246, 238, 0.76);
  backdrop-filter: blur(10px) saturate(140%);
  -webkit-backdrop-filter: blur(10px) saturate(140%);
  border-bottom: 1px solid transparent;
  transition: border-color 220ms ease, background 220ms ease;
}
.site-top.is-scrolled {
  background: rgba(250, 246, 238, 0.92);
  border-bottom-color: var(--ink-ghost);
}
.top-inner {
  max-width: 1440px;
  margin: 0 auto;
  padding: 0.9rem 3vw;
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: center;
  gap: 2rem;
}
.brand {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  text-decoration: none;
  color: var(--ink);
  cursor: pointer;
}
.brand-main {
  font-family: var(--font-display);
  font-size: 1.45rem;
  letter-spacing: 0.08em;
}
.brand-edition {
  font-family: var(--font-mono);
  font-size: 0.68rem;
  color: var(--ink-soft);
  letter-spacing: 0.24em;
  margin-left: 0.35rem;
  opacity: 0.7;
}

.top-nav {
  display: flex;
  justify-content: center;
  gap: 2.2rem;
}
.nav-link {
  position: relative;
  padding: 0.3rem 0;
  font-family: var(--font-display);
  font-size: 1rem;
  letter-spacing: 0.12em;
  color: var(--ink-soft);
  text-decoration: none;
  transition: color 180ms ease;
}
.nav-link::after {
  content: '';
  position: absolute;
  left: 50%;
  bottom: -4px;
  width: 0;
  height: 1.5px;
  background: var(--ember);
  transform: translateX(-50%);
  transition: width 220ms ease;
}
.nav-link:hover { color: var(--ink); }
.nav-link.is-active {
  color: var(--ink);
}
.nav-link.is-active::after { width: 100%; }

.top-cta {
  font-size: 0.95rem;
  padding: 0.7rem 1.4rem;
}
.top-cta .arrow {
  font-family: var(--font-mono);
  transition: transform 160ms ease;
}
.top-cta:hover .arrow { transform: translateX(3px); }

/* ============================================================
   页脚
   ============================================================ */
.site-bottom {
  position: relative;
  z-index: 5;
  background: var(--paper-deep);
  border-top: 1px solid var(--ink-ghost);
  margin-top: 6rem;
  padding: 5rem 6vw 3rem;
}
.bottom-inner {
  max-width: 1440px;
  margin: 0 auto;
  display: grid;
  grid-template-columns: 1fr 1.4fr;
  gap: 4rem;
  padding-bottom: 3rem;
  border-bottom: 1px dashed var(--ink-ghost);
}
.foot-brand {
  display: flex;
  flex-direction: column;
  gap: 0.7rem;
}
.foot-logo {
  display: inline-flex;
  align-items: center;
  gap: 0.55rem;
  color: var(--ember);
}
.foot-logo {
  font-family: var(--font-display);
  font-size: 1.6rem;
  color: var(--ink);
  letter-spacing: 0.08em;
}
.foot-tagline {
  font-family: var(--font-hand);
  font-size: 1.15rem;
  color: var(--ink-soft);
  margin: 0;
}

.foot-columns {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 3rem;
}
.col-title {
  font-family: var(--font-display);
  font-size: 1.05rem;
  color: var(--ink);
  letter-spacing: 0.1em;
  margin: 0 0 1rem;
}
.col-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}
.col-list a {
  color: var(--ink-soft);
  font-size: 0.95rem;
  text-decoration: none;
  transition: color 160ms ease;
}
.col-list a:hover { color: var(--ember-deep); }

.bottom-foot {
  max-width: 1440px;
  margin: 2rem auto 0;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}
.copyright {
  font-family: var(--font-mono);
  font-size: 0.82rem;
  color: var(--ink-soft);
  margin: 0;
  letter-spacing: 0.06em;
}
.disclaimer {
  font-size: 0.8rem;
  color: var(--slate);
  margin: 0;
  line-height: 1.7;
  opacity: 0.85;
}
.foot-brand-link {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.6rem;
  text-decoration: none;
  color: inherit;
  transition: opacity 0.2s;
}
.foot-brand-link:hover {
  opacity: 0.8;
}
.disclaimer-link {
  color: var(--ember);
  text-decoration: none;
  font-weight: 600;
  transition: opacity 0.2s;
}
.disclaimer-link:hover {
  opacity: 0.75;
  text-decoration: underline;
}

@media (max-width: 900px) {
  .top-nav { display: none; }
  .top-inner { grid-template-columns: auto auto; }
  .bottom-inner { grid-template-columns: 1fr; gap: 2.4rem; }
}
</style>
