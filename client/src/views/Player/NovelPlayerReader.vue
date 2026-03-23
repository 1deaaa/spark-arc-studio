<template>
  <div class="novel-player" :class="{ compact: isCompact }">
    <div class="novel-backdrop">
      <div class="novel-backdrop-glow"></div>
      <div class="novel-backdrop-grain"></div>
    </div>

    <div v-if="loading" class="novel-screen state-screen">
      <div class="state-card">
        <h2>正在打开小说</h2>
        <p>请稍候，正在准备阅读内容…</p>
      </div>
    </div>

    <div v-else-if="error" class="novel-screen state-screen">
      <div class="state-card error-card">
        <h2>无法加载小说</h2>
        <p>{{ error }}</p>
        <button class="action-btn" @click="loadNovel">重试</button>
      </div>
    </div>

    <div v-else class="novel-screen reading-screen">
      <header class="novel-header">
        <div class="header-main">
          <span class="eyebrow">公开小说试读</span>
          <h1>{{ meta.title || '未命名小说' }}</h1>
          <p v-if="meta.description" class="description">{{ meta.description }}</p>
        </div>

        <div class="header-tools">
          <div class="tool-group">
            <button class="tool-btn" :disabled="fontSize <= 15" @click="changeFont(-1)">A-</button>
            <button class="tool-btn" :disabled="fontSize >= 22" @click="changeFont(1)">A+</button>
          </div>
          <div class="tool-group mode-group">
            <button class="tool-btn" :class="{ active: readingMode === 'page' }" @click="readingMode = 'page'">翻页</button>
            <button class="tool-btn" :class="{ active: readingMode === 'scroll' }" @click="readingMode = 'scroll'">滚动</button>
          </div>
        </div>
      </header>

      <main class="novel-main" :class="`mode-${readingMode}`">
        <section class="novel-panel" :style="panelStyle">
          <template v-if="readingMode === 'page'">
            <transition name="page-fade" mode="out-in">
              <article :key="`${currentPage}-${isCompact ? 'compact' : 'wide'}`" class="novel-page page-card">
                <div class="page-inner">
                  <p v-for="(paragraph, idx) in currentPageParagraphs" :key="`${currentPage}-${idx}`" class="novel-paragraph">
                    {{ paragraph }}
                  </p>
                </div>
              </article>
            </transition>
          </template>

          <template v-else>
            <article class="novel-scroll page-card" ref="scrollContainer">
              <div class="page-inner">
                <p v-for="(paragraph, idx) in paragraphs" :key="`scroll-${idx}`" class="novel-paragraph">
                  {{ paragraph }}
                </p>
              </div>
            </article>
          </template>
        </section>
      </main>

      <footer class="novel-footer">
        <template v-if="readingMode === 'page'">
          <button class="nav-btn" :disabled="currentPage === 0" @click="goPrevPage">上一页</button>
          <div class="footer-center">
            <div class="progress-line">
              <div class="progress-fill" :style="{ width: progressPercent + '%' }"></div>
            </div>
            <span class="page-indicator">第 {{ currentPage + 1 }} / {{ totalPages }} 页</span>
          </div>
          <button class="nav-btn" :disabled="currentPage >= totalPages - 1" @click="goNextPage">下一页</button>
        </template>
        <template v-else>
          <div class="footer-center single">
            <span class="page-indicator">滚动阅读模式 · 共 {{ paragraphs.length }} 段</span>
          </div>
        </template>
      </footer>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useRoute } from 'vue-router';
import { resolveApiUrl } from '@/services/apiClient';
import { useMobile } from '@/composables/useMobile';

const route = useRoute();
const { isCompact } = useMobile();

const loading = ref(true);
const error = ref('');
const meta = ref({ title: '', description: '' });
const rawContent = ref('');
const readingMode = ref('page');
const currentPage = ref(0);
const fontSize = ref(17);
const scrollContainer = ref(null);

const shareId = computed(() => String(route.params.shareId || ''));
const isVersionPlay = computed(() => route.path.includes('/play/v/'));

const paragraphs = computed(() => {
  return String(rawContent.value || '')
    .split(/\n{2,}/)
    .map(item => item.trim())
    .filter(Boolean);
});

const targetCharsPerPage = computed(() => {
  const base = isCompact.value ? 900 : 1800;
  return Math.round(base * (17 / fontSize.value));
});

const pagedParagraphs = computed(() => {
  const result = [];
  let page = [];
  let count = 0;

  for (const paragraph of paragraphs.value) {
    const weight = Math.max(paragraph.length, 80);
    if (page.length > 0 && count + weight > targetCharsPerPage.value) {
      result.push(page);
      page = [];
      count = 0;
    }
    page.push(paragraph);
    count += weight;
  }

  if (page.length > 0) result.push(page);
  return result.length ? result : [[]];
});

const totalPages = computed(() => pagedParagraphs.value.length);
const currentPageParagraphs = computed(() => pagedParagraphs.value[currentPage.value] || []);
const progressPercent = computed(() => {
  if (totalPages.value <= 1) return 100;
  return ((currentPage.value + 1) / totalPages.value) * 100;
});

const panelStyle = computed(() => ({
  '--reader-font-size': `${fontSize.value}px`,
}));

function changeFont(delta) {
  fontSize.value = Math.min(22, Math.max(15, fontSize.value + delta));
}

function goPrevPage() {
  currentPage.value = Math.max(0, currentPage.value - 1);
}

function goNextPage() {
  currentPage.value = Math.min(totalPages.value - 1, currentPage.value + 1);
}

function onKeydown(event) {
  if (readingMode.value !== 'page') return;
  if (event.key === 'ArrowRight' || event.key === 'PageDown' || event.key === ' ') {
    event.preventDefault();
    goNextPage();
  }
  if (event.key === 'ArrowLeft' || event.key === 'PageUp') {
    event.preventDefault();
    goPrevPage();
  }
}

async function loadNovel() {
  loading.value = true;
  error.value = '';
  try {
    const infoUrl = isVersionPlay.value ? `/api/play/v/${shareId.value}/info` : `/api/play/${shareId.value}/info`;
    const dataUrl = isVersionPlay.value ? `/api/play/v/${shareId.value}/data` : `/api/play/${shareId.value}/data`;

    const [infoRes, dataRes] = await Promise.all([
      fetch(resolveApiUrl(infoUrl)),
      fetch(resolveApiUrl(dataUrl)),
    ]);

    if (!infoRes.ok) throw new Error('无法读取分享元信息');
    if (!dataRes.ok) throw new Error('无法读取小说内容');

    const info = await infoRes.json();
    const data = await dataRes.json();

    if ((data.format || 'script') !== 'novel') {
      throw new Error('当前公开链接不是小说内容');
    }

    meta.value = {
      title: info.title || '未命名小说',
      description: info.description || '',
    };
    rawContent.value = String(data.content || '');
    currentPage.value = 0;
    if (scrollContainer.value) {
      scrollContainer.value.scrollTop = 0;
    }
  } catch (err) {
    error.value = err.message || '加载失败';
  } finally {
    loading.value = false;
  }
}

watch([paragraphs, targetCharsPerPage], () => {
  if (currentPage.value >= totalPages.value) {
    currentPage.value = Math.max(0, totalPages.value - 1);
  }
});

watch(readingMode, (mode) => {
  if (mode === 'scroll' && scrollContainer.value) {
    scrollContainer.value.scrollTop = 0;
  }
});

onMounted(() => {
  loadNovel();
  window.addEventListener('keydown', onKeydown);
});

onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKeydown);
});
</script>

<style scoped>
.novel-player {
  --reader-font-size: 17px;
  min-height: 100vh;
  color: rgba(248, 244, 236, 0.95);
  background:
    radial-gradient(circle at top, rgba(88, 102, 154, 0.18), transparent 35%),
    linear-gradient(180deg, #11141c 0%, #0b0e14 100%);
  position: relative;
  overflow: hidden;
}

.novel-backdrop,
.novel-backdrop-glow,
.novel-backdrop-grain {
  position: absolute;
  inset: 0;
}

.novel-backdrop {
  pointer-events: none;
}

.novel-backdrop-glow {
  background:
    radial-gradient(circle at 20% 20%, rgba(255, 214, 153, 0.08), transparent 28%),
    radial-gradient(circle at 80% 12%, rgba(140, 153, 255, 0.08), transparent 24%),
    radial-gradient(circle at 50% 100%, rgba(255, 255, 255, 0.03), transparent 30%);
}

.novel-backdrop-grain {
  opacity: 0.04;
  background-image:
    linear-gradient(rgba(255,255,255,0.6) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255,255,255,0.6) 1px, transparent 1px);
  background-size: 3px 3px;
  mix-blend-mode: soft-light;
}

.novel-screen {
  position: relative;
  z-index: 1;
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.state-screen {
  align-items: center;
  justify-content: center;
  padding: 24px;
}

.state-card {
  width: min(560px, 100%);
  padding: 32px 28px;
  border-radius: 20px;
  border: 1px solid rgba(255,255,255,0.08);
  background: rgba(17, 21, 30, 0.78);
  box-shadow: 0 18px 50px rgba(0,0,0,0.28);
  text-align: center;
}

.state-card h2 {
  margin: 0 0 10px;
}

.state-card p {
  margin: 0;
  opacity: 0.76;
  line-height: 1.8;
}

.action-btn {
  margin-top: 18px;
  padding: 10px 22px;
  border-radius: 999px;
  border: 1px solid rgba(255,255,255,0.16);
  background: rgba(255,255,255,0.08);
  color: inherit;
  cursor: pointer;
}

.reading-screen {
  padding: 24px 24px 18px;
  gap: 20px;
}

.novel-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
  width: min(1120px, 100%);
  margin: 0 auto;
}

.header-main {
  min-width: 0;
}

.eyebrow {
  display: inline-block;
  margin-bottom: 10px;
  font-size: 12px;
  letter-spacing: 0.2em;
  text-transform: uppercase;
  opacity: 0.62;
}

.header-main h1 {
  margin: 0;
  font-size: clamp(28px, 4vw, 42px);
  line-height: 1.2;
  font-weight: 600;
}

.description {
  margin: 12px 0 0;
  max-width: 760px;
  line-height: 1.75;
  opacity: 0.75;
}

.header-tools {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.tool-group {
  display: flex;
  align-items: center;
  gap: 0;
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: 999px;
  overflow: hidden;
  background: rgba(255,255,255,0.04);
  backdrop-filter: blur(8px);
}

.tool-btn,
.nav-btn {
  border: none;
  background: transparent;
  color: inherit;
  cursor: pointer;
  transition: background .24s ease, transform .24s ease, opacity .24s ease;
}

.tool-btn {
  padding: 10px 14px;
  min-width: 56px;
}

.tool-btn + .tool-btn {
  border-left: 1px solid rgba(255,255,255,0.08);
}

.tool-btn:hover,
.tool-btn.active {
  background: rgba(255,255,255,0.08);
}

.tool-btn:disabled,
.nav-btn:disabled {
  opacity: 0.34;
  cursor: not-allowed;
}

.novel-main {
  flex: 1;
  width: min(1120px, 100%);
  margin: 0 auto;
  display: flex;
}

.novel-panel {
  flex: 1;
  display: flex;
}

.page-card {
  width: 100%;
  min-height: 0;
  border-radius: 26px;
  border: 1px solid rgba(255,255,255,0.08);
  background:
    linear-gradient(180deg, rgba(255,255,255,0.08), rgba(255,255,255,0.03)),
    rgba(15, 19, 28, 0.82);
  box-shadow:
    0 18px 60px rgba(0,0,0,0.26),
    inset 0 1px 0 rgba(255,255,255,0.06);
  backdrop-filter: blur(14px);
}

.novel-page,
.novel-scroll {
  display: flex;
  min-height: 0;
}

.page-inner {
  width: 100%;
  max-width: 820px;
  margin: 0 auto;
  padding: 42px 48px 48px;
  box-sizing: border-box;
}

.novel-scroll {
  overflow-y: auto;
  scroll-behavior: smooth;
}

.novel-scroll::-webkit-scrollbar {
  width: 10px;
}

.novel-scroll::-webkit-scrollbar-thumb {
  background: rgba(255,255,255,0.12);
  border-radius: 999px;
}

.novel-paragraph {
  margin: 0 0 1.35em;
  font-size: var(--reader-font-size);
  line-height: 2.05;
  letter-spacing: 0.02em;
  color: rgba(248, 244, 236, 0.94);
  text-align: justify;
  text-indent: 2em;
}

.novel-footer {
  width: min(1120px, 100%);
  margin: 0 auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.footer-center {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.footer-center.single {
  justify-content: center;
}

.progress-line {
  width: min(380px, 100%);
  height: 4px;
  border-radius: 999px;
  background: rgba(255,255,255,0.08);
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, rgba(255,214,153,0.95), rgba(255,243,214,0.95));
  box-shadow: 0 0 18px rgba(255,214,153,0.28);
  transition: width .34s ease;
}

.page-indicator {
  font-size: 13px;
  opacity: 0.72;
}

.nav-btn {
  min-width: 108px;
  padding: 11px 18px;
  border-radius: 999px;
  background: rgba(255,255,255,0.05);
  border: 1px solid rgba(255,255,255,0.1);
  backdrop-filter: blur(10px);
}

.nav-btn:not(:disabled):hover {
  background: rgba(255,255,255,0.1);
  transform: translateY(-1px);
}

.page-fade-enter-active,
.page-fade-leave-active {
  transition: opacity .38s ease, transform .38s ease, filter .38s ease;
}

.page-fade-enter-from {
  opacity: 0;
  transform: translateX(28px) scale(0.988);
  filter: blur(6px);
}

.page-fade-leave-to {
  opacity: 0;
  transform: translateX(-22px) scale(0.992);
  filter: blur(4px);
}

.compact .reading-screen {
  padding: 14px 12px 14px;
  gap: 14px;
}

.compact .novel-header {
  flex-direction: column;
  align-items: stretch;
}

.compact .header-tools {
  justify-content: flex-start;
}

.compact .page-inner {
  padding: 24px 18px 28px;
}

.compact .novel-paragraph {
  text-align: left;
  text-indent: 1.8em;
  line-height: 1.95;
}

.compact .novel-footer {
  flex-direction: column;
  align-items: stretch;
}

.compact .nav-btn {
  width: 100%;
}

@media (max-width: 1024px) {
  .novel-main,
  .novel-header,
  .novel-footer {
    width: 100%;
  }
}
</style>
