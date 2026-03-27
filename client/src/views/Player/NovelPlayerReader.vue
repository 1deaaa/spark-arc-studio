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
          <div class="compact-group chapter-group">
            <span class="group-label">章节</span>
            <div class="chapter-select-wrap">
              <select v-model.number="activeChapterIndex" class="chapter-select">
                <option
                  v-for="(chapter, idx) in chapters"
                  :key="`chapter-${idx}`"
                  :value="idx"
                >
                  {{ chapterLabel(chapter, idx) }}
                </option>
              </select>
            </div>
          </div>

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
          <div class="compact-group chapter-group">
            <span class="group-label">章节</span>
            <div class="chapter-select-wrap">
              <select v-model.number="activeChapterIndex" class="chapter-select">
                <option
                  v-for="(chapter, idx) in chapters"
                  :key="`chapter-mobile-${idx}`"
                  :value="idx"
                >
                  {{ chapterLabel(chapter, idx) }}
                </option>
              </select>
            </div>
          </div>

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

          <article v-else ref="scrollContainer" class="reading-paper reading-paper-scroll" @scroll="onScrollContent">
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
            <div class="footer-meta">滚动阅读 · {{ activeChapterTitle }}</div>
          </div>
        </template>
      </footer>
    </div>
  </NovelBackdrop>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
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

type NovelChapter = {
  title: string;
  paragraphs: string[];
};

type NovelProgressState = {
  chapterIndex: number;
  page: number;
  mode: 'page' | 'scroll';
  fontSize: number;
  scrollRatio: number;
};

const MIN_FONT_SIZE = 15;
const MAX_FONT_SIZE = 22;
const DEFAULT_FONT_SIZE = 17;

function getErrorMessage(error: unknown): string {
  if (error instanceof Error) return error.message;
  return String(error || '加载失败');
}

function normalizeQueryValue(value: unknown): string | null {
  if (Array.isArray(value)) {
    const first = value[0];
    return typeof first === 'string' ? first : null;
  }
  return typeof value === 'string' ? value : null;
}

function toOneBasedIndex(value: string | null): number | null {
  if (!value) return null;
  const parsed = Number.parseInt(value, 10);
  if (!Number.isFinite(parsed) || parsed < 1) return null;
  return parsed - 1;
}

function toClampedRatio(value: string | null): number | null {
  if (!value) return null;
  const parsed = Number.parseFloat(value);
  if (!Number.isFinite(parsed)) return null;
  if (parsed > 1) return Math.min(1, Math.max(0, parsed / 100));
  return Math.min(1, Math.max(0, parsed));
}

function clampInt(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

function resolveChapterHeading(paragraph: string): string | null {
  const markdownMatch = paragraph.match(/^#{1,3}\s+(.+)$/);
  if (markdownMatch) {
    const title = markdownMatch[1].replace(/\s+#*$/, '').trim();
    return title || null;
  }

  if (/^第[0-9零一二三四五六七八九十百千万两〇]+[章节卷回部篇](?:\s*[：:\-.·]\s*.+)?$/i.test(paragraph)) {
    return paragraph.trim();
  }

  if (/^chapter\s+\d+(?:\s*[：:\-.]\s*.+)?$/i.test(paragraph)) {
    return paragraph.trim();
  }

  return null;
}

function parseProgressState(raw: string | null): NovelProgressState | null {
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as Partial<NovelProgressState>;
    const chapterIndex = Number.isFinite(parsed.chapterIndex) ? Number(parsed.chapterIndex) : 0;
    const page = Number.isFinite(parsed.page) ? Number(parsed.page) : 0;
    const mode = parsed.mode === 'scroll' ? 'scroll' : 'page';
    const fontSize = Number.isFinite(parsed.fontSize) ? Number(parsed.fontSize) : DEFAULT_FONT_SIZE;
    const scrollRatio = Number.isFinite(parsed.scrollRatio) ? Number(parsed.scrollRatio) : 0;
    return {
      chapterIndex,
      page,
      mode,
      fontSize,
      scrollRatio: Math.min(1, Math.max(0, scrollRatio)),
    };
  } catch {
    return null;
  }
}

const route = useRoute();
const router = useRouter();
const { isCompact } = useMobile();

const loading = ref(true);
const error = ref('');
const meta = ref({ title: '', description: '' });
const rawContent = ref('');
const readingMode = ref<'page' | 'scroll'>('page');
const currentPage = ref(0);
const fontSize = ref(DEFAULT_FONT_SIZE);
const showSettings = ref(false);
const activeChapterIndex = ref(0);
const scrollProgressRatio = ref(0);
const applyingProgress = ref(false);
const scrollContainer = ref<HTMLElement | null>(null);

const shareId = computed(() => String(route.params.shareId || ''));
const isVersionPlay = computed(() => route.path.includes('/play/v/'));

const progressStorageKey = computed(() => {
  const linkType = isVersionPlay.value ? 'version' : 'share';
  return `spark_player_progress_v2:novel:${linkType}:${shareId.value}`;
});

const sourceParagraphs = computed(() => {
  return String(rawContent.value || '')
    .split(/\n{2,}/)
    .map(item => item.trim())
    .filter(Boolean);
});

const chapters = computed<NovelChapter[]>(() => {
  const result: NovelChapter[] = [];
  let current: NovelChapter | null = null;

  for (const paragraph of sourceParagraphs.value) {
    const heading = resolveChapterHeading(paragraph);
    if (heading) {
      if (current && current.paragraphs.length > 0) {
        result.push(current);
      }
      current = { title: heading, paragraphs: [] };
      continue;
    }

    if (!current) {
      current = { title: '开篇', paragraphs: [] };
    }
    current.paragraphs.push(paragraph);
  }

  if (current && current.paragraphs.length > 0) {
    result.push(current);
  }

  if (!result.length) {
    const fallbackParagraphs = sourceParagraphs.value.length ? sourceParagraphs.value : [''];
    return [{ title: '正文', paragraphs: fallbackParagraphs }];
  }

  return result;
});

const activeChapter = computed(() => {
  const fallback: NovelChapter = { title: '正文', paragraphs: [''] };
  return chapters.value[activeChapterIndex.value] || chapters.value[0] || fallback;
});

const activeChapterTitle = computed(() => activeChapter.value.title || '正文');

const paragraphs = computed(() => {
  return activeChapter.value.paragraphs;
});

const targetCharsPerPage = computed(() => {
  const base = isCompact.value ? 900 : 1800;
  return Math.round(base * (DEFAULT_FONT_SIZE / fontSize.value));
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
  if (readingMode.value === 'scroll') {
    return Math.round(Math.min(1, Math.max(0, scrollProgressRatio.value)) * 100);
  }
  if (totalPages.value <= 1) return 100;
  return ((currentPage.value + 1) / totalPages.value) * 100;
});
const readingStatus = computed(() => {
  if (readingMode.value === 'scroll') {
    return `第 ${activeChapterIndex.value + 1} 章 · ${Math.round(progressPercent.value)}%`;
  }
  return `第 ${activeChapterIndex.value + 1} 章 · 第 ${currentPage.value + 1} / ${totalPages.value} 页`;
});
const readingHint = computed(() => {
  if (readingMode.value === 'scroll') {
    return `滚动阅读「${activeChapterTitle.value}」`;
  }
  return isCompact.value
    ? `左右切页，当前「${activeChapterTitle.value}」`
    : `以正文为主，当前章节「${activeChapterTitle.value}」`;
});

const panelStyle = computed(() => ({
  '--reader-font-size': `${fontSize.value}px`,
}));

function chapterLabel(chapter: NovelChapter, index: number): string {
  return `第 ${index + 1} 章 · ${chapter.title}`;
}

function saveProgressToStorage(state: NovelProgressState) {
  try {
    localStorage.setItem(progressStorageKey.value, JSON.stringify(state));
  } catch {
    // ignore storage errors
  }
}

function loadProgressFromStorage(): NovelProgressState | null {
  try {
    const raw = localStorage.getItem(progressStorageKey.value);
    return parseProgressState(raw);
  } catch {
    return null;
  }
}

function getProgressFromQuery(): Partial<NovelProgressState> {
  const chapterIndex = toOneBasedIndex(normalizeQueryValue(route.query.ch));
  const page = toOneBasedIndex(normalizeQueryValue(route.query.p));
  const modeText = normalizeQueryValue(route.query.mode);
  const fontSizeText = normalizeQueryValue(route.query.fs);
  const ratioText = normalizeQueryValue(route.query.sr);

  const mode = modeText === 'scroll' ? 'scroll' : modeText === 'page' ? 'page' : undefined;
  const fontSizeCandidate = fontSizeText ? Number.parseInt(fontSizeText, 10) : Number.NaN;
  const scrollRatio = toClampedRatio(ratioText);

  return {
    chapterIndex: chapterIndex ?? undefined,
    page: page ?? undefined,
    mode,
    fontSize: Number.isFinite(fontSizeCandidate) ? fontSizeCandidate : undefined,
    scrollRatio: scrollRatio ?? undefined,
  };
}

function buildCurrentProgress(): NovelProgressState {
  return {
    chapterIndex: activeChapterIndex.value,
    page: currentPage.value,
    mode: readingMode.value,
    fontSize: fontSize.value,
    scrollRatio: scrollProgressRatio.value,
  };
}

function syncProgressToQuery(state: NovelProgressState) {
  const nextQuery: Record<string, string> = {};
  for (const [key, value] of Object.entries(route.query)) {
    const text = normalizeQueryValue(value);
    if (text !== null && key !== 'ch' && key !== 'p' && key !== 'mode' && key !== 'fs' && key !== 'sr') {
      nextQuery[key] = text;
    }
  }

  nextQuery.ch = String(state.chapterIndex + 1);
  nextQuery.p = String(state.page + 1);
  nextQuery.mode = state.mode;
  if (state.fontSize !== DEFAULT_FONT_SIZE) {
    nextQuery.fs = String(state.fontSize);
  }
  if (state.mode === 'scroll') {
    nextQuery.sr = String(Math.round(state.scrollRatio * 100));
  }

  const currentChapter = normalizeQueryValue(route.query.ch);
  const currentPageValue = normalizeQueryValue(route.query.p);
  const currentMode = normalizeQueryValue(route.query.mode);
  const currentFont = normalizeQueryValue(route.query.fs);
  const currentRatio = normalizeQueryValue(route.query.sr);
  const nextFont = nextQuery.fs || null;
  const nextRatio = nextQuery.sr || null;

  if (
    currentChapter === nextQuery.ch
    && currentPageValue === nextQuery.p
    && currentMode === nextQuery.mode
    && currentFont === nextFont
    && currentRatio === nextRatio
  ) {
    return;
  }

  void router.replace({ query: nextQuery }).catch(() => {
    // ignore navigation duplicated and transient errors
  });
}

function persistProgress(updateUrl = true) {
  if (loading.value || error.value) return;
  const state = buildCurrentProgress();
  saveProgressToStorage(state);
  if (updateUrl) {
    syncProgressToQuery(state);
  }
}

function updateScrollProgressRatio() {
  const container = scrollContainer.value;
  if (!container) {
    scrollProgressRatio.value = 0;
    return;
  }

  const maxScroll = container.scrollHeight - container.clientHeight;
  if (maxScroll <= 0) {
    scrollProgressRatio.value = 1;
    return;
  }
  scrollProgressRatio.value = Math.min(1, Math.max(0, container.scrollTop / maxScroll));
}

function onScrollContent() {
  updateScrollProgressRatio();
  persistProgress(false);
}

async function restoreProgressAfterLoad() {
  applyingProgress.value = true;

  const fromStorage = loadProgressFromStorage();
  const fromQuery = getProgressFromQuery();

  const chapterIndex = fromQuery.chapterIndex ?? fromStorage?.chapterIndex ?? 0;
  const nextMode = fromQuery.mode ?? fromStorage?.mode ?? 'page';
  const nextFontSize = fromQuery.fontSize ?? fromStorage?.fontSize ?? DEFAULT_FONT_SIZE;
  const nextPage = fromQuery.page ?? fromStorage?.page ?? 0;
  const nextRatio = fromQuery.scrollRatio ?? fromStorage?.scrollRatio ?? 0;

  activeChapterIndex.value = clampInt(chapterIndex, 0, Math.max(chapters.value.length - 1, 0));
  readingMode.value = nextMode;
  fontSize.value = clampInt(nextFontSize, MIN_FONT_SIZE, MAX_FONT_SIZE);

  await nextTick();

  currentPage.value = clampInt(nextPage, 0, Math.max(totalPages.value - 1, 0));
  scrollProgressRatio.value = Math.min(1, Math.max(0, nextRatio));

  if (scrollContainer.value) {
    if (readingMode.value === 'scroll') {
      const maxScroll = Math.max(0, scrollContainer.value.scrollHeight - scrollContainer.value.clientHeight);
      scrollContainer.value.scrollTop = maxScroll * scrollProgressRatio.value;
      updateScrollProgressRatio();
    } else {
      scrollContainer.value.scrollTop = 0;
      scrollProgressRatio.value = 0;
    }
  }

  applyingProgress.value = false;
  persistProgress(true);
}

function changeFont(delta: number) {
  fontSize.value = clampInt(fontSize.value + delta, MIN_FONT_SIZE, MAX_FONT_SIZE);
}

function goPrevPage() {
  currentPage.value = clampInt(currentPage.value - 1, 0, Math.max(totalPages.value - 1, 0));
}

function goNextPage() {
  currentPage.value = clampInt(currentPage.value + 1, 0, Math.max(totalPages.value - 1, 0));
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
    await nextTick();
    await restoreProgressAfterLoad();
  } catch (err: unknown) {
    error.value = getErrorMessage(err);
  } finally {
    loading.value = false;
  }
}

watch([paragraphs, targetCharsPerPage], () => {
  if (currentPage.value >= totalPages.value) {
    currentPage.value = clampInt(currentPage.value, 0, Math.max(totalPages.value - 1, 0));
  }
});

watch(activeChapterIndex, async () => {
  if (applyingProgress.value) return;
  currentPage.value = 0;
  scrollProgressRatio.value = 0;
  await nextTick();
  if (scrollContainer.value) {
    scrollContainer.value.scrollTop = 0;
  }
  persistProgress(true);
});

watch(currentPage, () => {
  if (applyingProgress.value) return;
  persistProgress(true);
});

watch(fontSize, () => {
  if (applyingProgress.value) return;
  if (currentPage.value >= totalPages.value) {
    currentPage.value = clampInt(currentPage.value, 0, Math.max(totalPages.value - 1, 0));
  }
  persistProgress(true);
});

watch(readingMode, (mode) => {
  if (applyingProgress.value) return;
  if (mode === 'scroll' && scrollContainer.value) {
    const maxScroll = Math.max(0, scrollContainer.value.scrollHeight - scrollContainer.value.clientHeight);
    scrollContainer.value.scrollTop = maxScroll * scrollProgressRatio.value;
    updateScrollProgressRatio();
  }
  if (mode === 'page') {
    scrollProgressRatio.value = 0;
  }
  if (isCompact.value) {
    showSettings.value = false;
  }
  persistProgress(true);
});

watch(() => [route.params.shareId, route.path], (nextVal, prevVal) => {
  const nextKey = `${String(nextVal[0] || '')}|${String(nextVal[1] || '')}`;
  const prevKey = `${String(prevVal?.[0] || '')}|${String(prevVal?.[1] || '')}`;
  if (nextKey !== prevKey) {
    loadNovel();
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

.chapter-group {
  min-width: 220px;
}

.chapter-select-wrap {
  width: clamp(180px, 20vw, 260px);
}

.chapter-select {
  width: 100%;
  border: 1px solid color-mix(in srgb, var(--spark-primary), transparent 78%);
  background: color-mix(in srgb, var(--spark-panel-bg), transparent 10%);
  color: inherit;
  padding: 9px 10px;
  border-radius: 10px;
  font-size: 13px;
}

.chapter-select:focus {
  outline: 1px solid color-mix(in srgb, var(--spark-primary), transparent 56%);
  outline-offset: 1px;
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

  .chapter-select-wrap {
    width: min(64vw, 240px);
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
