<template>
  <NovelBackdrop class="novel-player" mode="viewport">
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

    <div v-else class="novel-screen reading-screen" :class="{ compact: isCompact }">
      <header class="reading-header">
        <div class="title-block">
          <span class="eyebrow">公开小说试读</span>
          <div class="title-line">
            <h1>{{ meta.title || '未命名小说' }}</h1>
            <span class="status-chip">{{ readingStatus }}</span>
          </div>
          <p v-if="meta.description" class="description">{{ meta.description }}</p>
        </div>

        <div v-if="!isCompact" class="header-controls">
          <div class="compact-group">
            <span class="group-label">字号</span>
            <div class="tool-group">
              <button class="tool-btn" :disabled="fontSize <= 15" @click="changeFont(-1)">A-</button>
              <button class="tool-btn value-chip" disabled>{{ fontSize }}</button>
              <button class="tool-btn" :disabled="fontSize >= 22" @click="changeFont(1)">A+</button>
            </div>
          </div>

          <div class="compact-group">
            <span class="group-label">方式</span>
            <div class="tool-group mode-group">
              <button class="tool-btn" :class="{ active: readingMode === 'page' }" @click="readingMode = 'page'">翻页</button>
              <button class="tool-btn" :class="{ active: readingMode === 'scroll' }" @click="readingMode = 'scroll'">滚动</button>
            </div>
          </div>
        </div>

        <div v-else class="mobile-header-actions">
          <button class="mobile-settings-toggle" @click="showSettings = !showSettings">
            {{ showSettings ? '收起设置' : '阅读设置' }}
          </button>
        </div>
      </header>

      <transition name="settings-fold">
        <section v-if="isCompact && showSettings" class="mobile-settings-panel">
          <div class="compact-group">
            <span class="group-label">字号</span>
            <div class="tool-group">
              <button class="tool-btn" :disabled="fontSize <= 15" @click="changeFont(-1)">A-</button>
              <button class="tool-btn value-chip" disabled>{{ fontSize }}</button>
              <button class="tool-btn" :disabled="fontSize >= 22" @click="changeFont(1)">A+</button>
            </div>
          </div>

          <div class="compact-group">
            <span class="group-label">方式</span>
            <div class="tool-group mode-group">
              <button class="tool-btn" :class="{ active: readingMode === 'page' }" @click="readingMode = 'page'">翻页</button>
              <button class="tool-btn" :class="{ active: readingMode === 'scroll' }" @click="readingMode = 'scroll'">滚动</button>
            </div>
          </div>
        </section>
      </transition>

      <main class="reading-main" :style="panelStyle">
        <section class="reading-paper-shell">
          <article v-if="readingMode === 'page'" class="reading-paper">
            <transition name="page-fade" mode="out-in">
              <div :key="`${currentPage}-${isCompact ? 'compact' : 'wide'}`" class="page-inner">
                <p v-for="(paragraph, idx) in currentPageParagraphs" :key="`${currentPage}-${idx}`" class="novel-paragraph">
                  {{ paragraph }}
                </p>
              </div>
            </transition>
          </article>

          <article v-else ref="scrollContainer" class="reading-paper reading-paper-scroll">
            <div class="page-inner">
              <p v-for="(paragraph, idx) in paragraphs" :key="`scroll-${idx}`" class="novel-paragraph">
                {{ paragraph }}
              </p>
            </div>
          </article>
        </section>
      </main>

      <footer class="reading-footer" :class="{ single: readingMode !== 'page' }">
        <div class="footer-progress-block">
          <div class="progress-line">
            <div class="progress-fill" :style="{ width: progressPercent + '%' }"></div>
          </div>
          <div class="footer-hint">{{ readingHint }}</div>
        </div>

        <template v-if="readingMode === 'page'">
          <div class="footer-actions">
            <button class="nav-btn" :disabled="currentPage === 0" @click="goPrevPage">上一页</button>
            <div class="footer-meta">{{ readingStatus }}</div>
            <button class="nav-btn" :disabled="currentPage >= totalPages - 1" @click="goNextPage">下一页</button>
          </div>
        </template>
        <template v-else>
          <div class="footer-actions single-actions">
            <div class="footer-meta">滚动阅读 · 共 {{ paragraphs.length }} 段</div>
          </div>
        </template>
      </footer>
    </div>
  </NovelBackdrop>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useRoute } from 'vue-router';
import NovelBackdrop from '@/components/share/NovelBackdrop.vue';
import { fetchWithAuth } from '@/services/apiClient';
import { useMobile } from '@/composables/useMobile';

type NovelInfoResponse = {
  title?: string;
  description?: string;
};

type NovelDataResponse = {
  format?: string;
  content?: string;
};

function getErrorMessage(error: unknown): string {
  if (error instanceof Error) return error.message;
  return String(error || '加载失败');
}

const route = useRoute();
const { isCompact } = useMobile();

const loading = ref(true);
const error = ref('');
const meta = ref({ title: '', description: '' });
const rawContent = ref('');
const readingMode = ref<'page' | 'scroll'>('page');
const currentPage = ref(0);
const fontSize = ref(17);
const showSettings = ref(false);
const scrollContainer = ref<HTMLElement | null>(null);

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
  const result: string[][] = [];
  let page: string[] = [];
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
const readingStatus = computed(() => {
  if (readingMode.value === 'scroll') {
    return `${paragraphs.value.length} 段正文`;
  }
  return `第 ${currentPage.value + 1} / ${totalPages.value} 页`;
});
const readingHint = computed(() => {
  if (readingMode.value === 'scroll') {
    return '连续滚动浏览全部正文';
  }
  return isCompact.value ? '左右切页，保持连续阅读' : '以正文为主，顶部仅保留必要信息与控制';
});

const panelStyle = computed(() => ({
  '--reader-font-size': `${fontSize.value}px`,
}));

function changeFont(delta: number) {
  fontSize.value = Math.min(22, Math.max(15, fontSize.value + delta));
}

function goPrevPage() {
  currentPage.value = Math.max(0, currentPage.value - 1);
}

function goNextPage() {
  currentPage.value = Math.min(totalPages.value - 1, currentPage.value + 1);
}

function onKeydown(event: KeyboardEvent) {
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
      fetchWithAuth(infoUrl),
      fetchWithAuth(dataUrl),
    ]);

    if (!infoRes.ok) throw new Error('无法读取分享元信息');
    if (!dataRes.ok) throw new Error('无法读取小说内容');

    const info = await infoRes.json() as NovelInfoResponse;
    const data = await dataRes.json() as NovelDataResponse;

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
  } catch (err: unknown) {
    error.value = getErrorMessage(err);
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
  if (isCompact.value) {
    showSettings.value = false;
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
  border: 1px solid color-mix(in srgb, var(--spark-primary), transparent 78%);
  background: color-mix(in srgb, var(--spark-panel-bg), transparent 10%);
  box-shadow: 0 18px 50px color-mix(in srgb, black, transparent 72%);
  backdrop-filter: blur(16px);
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
  border: 1px solid color-mix(in srgb, var(--spark-primary), transparent 72%);
  background: color-mix(in srgb, var(--spark-panel-bg), transparent 16%);
  color: inherit;
  cursor: pointer;
}

.reading-screen {
  padding: 14px 18px 16px;
}

.reading-header,
.reading-main,
.reading-footer {
  width: min(1560px, 100%);
  margin: 0 auto;
}

.reading-screen {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.reading-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding: 12px 14px;
  border: 1px solid color-mix(in srgb, var(--spark-primary), transparent 80%);
  background: color-mix(in srgb, var(--spark-panel-bg), transparent 10%);
  box-shadow:
    0 12px 30px color-mix(in srgb, black, transparent 86%),
    inset 0 1px 0 color-mix(in srgb, white, transparent 94%);
  backdrop-filter: blur(16px);
}

.title-block {
  min-width: 0;
  flex: 1;
}

.title-line {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}

.status-chip {
  flex-shrink: 0;
  padding: 4px 10px;
  border: 1px solid color-mix(in srgb, var(--spark-primary), transparent 76%);
  color: var(--spark-text-muted);
  font-size: 12px;
}

.eyebrow {
  display: inline-block;
  margin-bottom: 8px;
  font-size: 12px;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--spark-text-muted);
}

.title-block h1 {
  margin: 0;
  font-size: clamp(24px, 3vw, 32px);
  line-height: 1.2;
  font-weight: 600;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
}

.description {
  margin: 6px 0 0;
  line-height: 1.6;
  color: var(--spark-text-muted);
}

.header-controls {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.compact-group {
  display: flex;
  align-items: center;
  gap: 8px;
}

.mobile-header-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
}

.mobile-settings-toggle {
  border: 1px solid color-mix(in srgb, var(--spark-primary), transparent 76%);
  background: color-mix(in srgb, var(--spark-panel-bg), transparent 8%);
  color: inherit;
  padding: 8px 12px;
  font-size: 12px;
  cursor: pointer;
}

.mobile-settings-panel {
  width: min(1560px, 100%);
  margin: 0 auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 10px 12px;
  border: 1px solid color-mix(in srgb, var(--spark-primary), transparent 84%);
  background: color-mix(in srgb, var(--spark-panel-bg), transparent 10%);
}

.group-label {
  font-size: 12px;
  white-space: nowrap;
  color: var(--spark-text-muted);
}

.tool-group {
  display: inline-flex;
  align-items: center;
  flex-wrap: wrap;
  border: 1px solid color-mix(in srgb, var(--spark-primary), transparent 78%);
  border-radius: 10px;
  overflow: hidden;
  background: color-mix(in srgb, var(--spark-panel-bg), transparent 8%);
}

.tool-btn,
.nav-btn {
  border: 1px solid transparent;
  background: transparent;
  color: inherit;
  cursor: pointer;
  transition: background .24s ease, transform .24s ease, opacity .24s ease;
}

.tool-btn {
  padding: 10px 12px;
  min-width: 50px;
}

.tool-btn + .tool-btn {
  border-left: 1px solid color-mix(in srgb, var(--spark-primary), transparent 84%);
}

.tool-btn:hover,
.tool-btn.active {
  background: color-mix(in srgb, var(--spark-primary), transparent 88%);
}

.value-chip {
  color: var(--spark-text-muted);
  cursor: default;
}

.tool-btn:disabled,
.nav-btn:disabled {
  opacity: 0.42;
}

.tool-btn:disabled:not(.value-chip) {
  cursor: not-allowed;
}

.reading-main {
  flex: 1 1 auto;
  display: flex;
}

.reading-paper-shell {
  flex: 1;
  display: flex;
  min-height: 0;
}

.reading-paper {
  width: 100%;
  min-height: 100%;
  border: 1px solid color-mix(in srgb, var(--spark-primary), transparent 82%);
  background:
    repeating-linear-gradient(
      45deg,
      color-mix(in srgb, var(--spark-primary), transparent 99.15%) 0,
      color-mix(in srgb, var(--spark-primary), transparent 99.15%) 1px,
      transparent 1px,
      transparent 6px
    ),
    repeating-linear-gradient(
      135deg,
      color-mix(in srgb, white, transparent 99.1%) 0,
      color-mix(in srgb, white, transparent 99.1%) 1px,
      transparent 1px,
      transparent 7px
    ),
    linear-gradient(180deg, color-mix(in srgb, var(--spark-panel-bg), white 4%), color-mix(in srgb, var(--spark-bg), white 1%));
  box-shadow:
    0 18px 48px color-mix(in srgb, black, transparent 84%),
    inset 0 1px 0 color-mix(in srgb, white, transparent 95%);
}

.page-inner {
  width: 100%;
  max-width: 1080px;
  margin: 0 auto;
  padding: 28px 34px 34px;
  box-sizing: border-box;
  min-height: 100%;
}

.reading-paper-scroll {
  overflow-y: auto;
  scroll-behavior: smooth;
}

.reading-paper-scroll::-webkit-scrollbar {
  width: 10px;
}

.reading-paper-scroll::-webkit-scrollbar-thumb {
  background: color-mix(in srgb, var(--spark-primary), transparent 78%);
  border-radius: 999px;
}

.novel-paragraph {
  margin: 0 0 1.35em;
  font-size: var(--reader-font-size);
  line-height: 2;
  letter-spacing: 0.02em;
  color: color-mix(in srgb, var(--spark-text), white 4%);
  text-align: justify;
  text-indent: 2em;
}

.reading-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  padding: 0 2px;
}

.reading-footer.single {
  align-items: center;
}

.footer-progress-block {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}

.progress-line {
  width: 100%;
  height: 4px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--spark-border), transparent 34%);
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, var(--spark-primary-light, var(--spark-primary)), color-mix(in srgb, var(--spark-accent), white 18%));
  box-shadow: 0 0 18px color-mix(in srgb, var(--spark-primary), transparent 72%);
  transition: width .34s ease;
}

.footer-hint {
  font-size: 12px;
  color: var(--spark-text-muted);
}

.footer-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
}

.single-actions {
  min-width: 180px;
  justify-content: flex-end;
}

.footer-meta {
  font-size: 13px;
  color: var(--spark-text-muted);
  min-width: 88px;
  text-align: center;
}

.nav-btn {
  min-width: 88px;
  padding: 10px 16px;
  border-radius: 10px;
  background: color-mix(in srgb, var(--spark-panel-bg), transparent 10%);
  border-color: color-mix(in srgb, var(--spark-primary), transparent 76%);
}

.nav-btn:not(:disabled):hover {
  background: color-mix(in srgb, var(--spark-primary), transparent 88%);
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

.settings-fold-enter-active,
.settings-fold-leave-active {
  transition: opacity .2s ease, transform .2s ease;
}

.settings-fold-enter-from,
.settings-fold-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}

@media (max-width: 1024px) {
  .reading-screen {
    padding: 12px;
  }

  .reading-header,
  .reading-main,
  .reading-footer {
    width: 100%;
  }

  .reading-header {
    flex-direction: column;
    align-items: stretch;
    gap: 10px;
  }

  .header-controls {
    justify-content: space-between;
  }

  .mobile-settings-panel {
    width: 100%;
  }

  .page-inner {
    max-width: none;
    padding: 24px 28px 30px;
  }
}

@media (max-width: 768px) {
  .reading-screen {
    padding: 8px;
  }

  .reading-header {
    padding: 10px;
    gap: 8px;
  }

  .title-line {
    gap: 8px;
    align-items: flex-start;
    flex-direction: column;
  }

  .title-block h1 {
    font-size: 22px;
  }

  .description {
    font-size: 13px;
  }

  .header-controls {
    display: none;
  }

  .mobile-settings-panel {
    flex-direction: column;
    align-items: stretch;
    gap: 8px;
    padding: 10px;
  }

  .compact-group {
    min-width: 0;
    justify-content: space-between;
  }

  .tool-btn {
    min-width: 42px;
    padding: 9px 10px;
    font-size: 13px;
  }

  .page-inner {
    padding: 18px 18px 22px;
  }

  .novel-paragraph {
    text-align: left;
    text-indent: 1.8em;
    line-height: 1.92;
  }

  .reading-footer {
    flex-direction: column;
    align-items: stretch;
    gap: 8px;
  }

  .footer-actions {
    width: 100%;
    justify-content: space-between;
  }

  .single-actions {
    justify-content: center;
  }

  .footer-meta {
    min-width: 0;
    flex: 1;
  }
}
</style>
