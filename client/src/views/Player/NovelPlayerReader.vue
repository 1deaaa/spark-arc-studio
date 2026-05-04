<template>
  <div class="novel-player">
    <div v-if="loading" class="novel-screen state-screen">
      <div class="state-card">
        <h2>{{ t('views.player.novelReader.openingNovel') }}</h2>
        <p>{{ t('views.player.novelReader.preparingContent') }}</p>
      </div>
    </div>

    <div v-else-if="error" class="novel-screen state-screen">
      <div class="state-card error-card">
        <h2>{{ t('views.player.novelReader.loadNovelFailed') }}</h2>
        <p>{{ error }}</p>
        <button class="action-btn" @click="loadNovel">{{ t('views.common.retry') }}</button>
      </div>
    </div>

    <div v-else class="novel-screen reading-screen" :class="{ compact: isCompact }" @mousemove="onReaderPointerMove">
      <!-- 浮动顶栏：鼠标移入顶部区域或点击时显示，闲置自动隐藏 -->
      <header class="floating-topbar" :class="{ visible: topbarVisible }" @mouseenter="onTopbarEnter" @mouseleave="onTopbarLeave">
        <div class="topbar-inner">
          <div class="topbar-left">
            <BookNavButton
              :items="chapterNavItems"
              :current-id="chapterNavCurrentId"
              :panel-title="t('views.player.novelReader.chapter')"
              :empty-hint="t('views.player.novelReader.mainText')"
              @select="handleChapterNavSelect"
            />
            <h1 class="topbar-title">{{ meta.title || t('views.player.novelReader.untitledNovel') }}</h1>
          </div>
          <div class="topbar-center" v-if="readingMode === 'page'">
            <button class="topbar-icon-btn" :disabled="currentPage === 0 && activeChapterIndex === 0" @click.stop="goPrevPage"><n-icon :component="ChevronLeft" :size="18" /></button>
            <span class="topbar-page-info">{{ currentPage + 1 }} / {{ totalPages }}</span>
            <button class="topbar-icon-btn" :disabled="currentPage >= totalPages - 1 && activeChapterIndex >= chapters.length - 1" @click.stop="goNextPage"><n-icon :component="ChevronRight" :size="18" /></button>
          </div>
          <div class="topbar-right">
            <button class="topbar-icon-btn" :title="t('views.player.novelReader.readingSettings')" @click.stop="showSettings = !showSettings"><n-icon :component="Settings" :size="18" /></button>
          </div>
        </div>
      </header>

      <!-- 设置抽屉：从右侧滑出 -->
      <transition name="drawer-slide">
        <aside v-if="showSettings" class="settings-drawer" @click.stop>
          <div class="drawer-header">
            <span class="drawer-title">{{ t('views.player.novelReader.readingSettings') }}</span>
            <button class="topbar-icon-btn" @click="showSettings = false"><n-icon :component="X" :size="18" /></button>
          </div>

          <div class="drawer-body">
            <div class="drawer-section">
              <label class="drawer-label">{{ t('views.player.novelReader.chapter') }}</label>
              <select v-model.number="activeChapterIndex" class="drawer-select">
                <option v-for="(chapter, idx) in chapters" :key="`drawer-ch-${idx}`" :value="idx">
                  {{ chapterLabel(chapter, idx) }}
                </option>
              </select>
            </div>

            <div class="drawer-section">
              <label class="drawer-label">{{ t('views.player.novelReader.fontSize') }}</label>
              <div class="drawer-font-row">
                <button class="drawer-font-btn" :disabled="fontSize <= 15" @click="changeFont(-1)">A−</button>
                <span class="drawer-font-value">{{ fontSize }}</span>
                <button class="drawer-font-btn" :disabled="fontSize >= 22" @click="changeFont(1)">A+</button>
              </div>
            </div>

            <div class="drawer-section">
              <label class="drawer-label">{{ t('views.player.novelReader.mode') }}</label>
              <div class="drawer-mode-row">
                <button class="drawer-mode-btn" :class="{ active: readingMode === 'page' }" @click="readingMode = 'page'">{{ t('views.player.novelReader.pageMode') }}</button>
                <button class="drawer-mode-btn" :class="{ active: readingMode === 'scroll' }" @click="readingMode = 'scroll'">{{ t('views.player.novelReader.scrollMode') }}</button>
              </div>
            </div>

            <p v-if="meta.description" class="drawer-description">{{ meta.description }}</p>
          </div>
        </aside>
      </transition>
      <transition name="drawer-mask">
        <div v-if="showSettings" class="drawer-overlay" @click="showSettings = false"></div>
      </transition>

      <main class="reading-main" :style="panelStyle" @pointerdown="onSwipeStart" @pointerup="onSwipeEnd" @pointercancel="onSwipeCancel">
        <!-- 非阻塞章节通知条 -->
        <transition name="notify-slide">
          <div v-if="chapterNotifyVisible" class="chapter-notify-bar" @click="chapterNotifyVisible = false">
            <span class="chapter-notify-text">{{ chapterNotifyMessage }}</span>
          </div>
        </transition>
        <section class="reading-paper-shell">
          <article v-if="readingMode === 'page'" class="reading-paper">
            <transition :name="pageTransitionName" mode="out-in">
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
    </div>
    <!-- 常驻免责标签（仅简体中文可见）—— 占位式，不遮挡正文 -->
    <ZhOnlyTag v-if="!loading && !error" type="disclaimer" class="persistent-disclaimer"><template v-if="disclaimerParts">{{ disclaimerParts.before }}<a :href="SPARKARC_GITHUB_URL" target="_blank" rel="noopener" class="disclaimer-brand-link">SparkArc</a>{{ disclaimerParts.after }}</template><template v-else>{{ t('views.player.desktop.zhDisclaimer') }}</template></ZhOnlyTag>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import ZhOnlyTag from '@/components/share/ZhOnlyTag.vue';
import BookNavButton from '@/components/share/BookNavButton.vue';
import { NIcon } from 'naive-ui';
import { ChevronLeft, ChevronRight, Settings, X } from 'lucide-vue-next';
import type { NavItem } from '@/components/share/SceneNavPanel.vue';
import { fetchWithAuth } from '@/services/apiClient';
import { useMobile } from '@/composables/useMobile';
import { SPARKARC_GITHUB_URL } from '@/config';

type NovelInfoResponse = {
  title?: string;
  description?: string;
  project_name?: string;
};

/** 过滤预览版本临时名称（如 __preview__20260418023900） */
function cleanTitle(raw: string | undefined | null, fallback: string): string {
  if (!raw) return fallback;
  if (raw.startsWith('__preview__')) return fallback;
  return raw;
}

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
const { t } = useI18n();

function getErrorMessage(error: unknown): string {
  if (error instanceof Error) return error.message;
  return String(error || t('views.player.desktop.loadFailed'));
}

async function readApiError(response: Response, fallback: string): Promise<string> {
  try {
    const data = await response.json() as Record<string, unknown>;
    const detail = data.detail;
    if (typeof data.error === 'string' && data.error) return data.error;
    if (typeof data.message === 'string' && data.message) return data.message;
    if (typeof detail === 'string' && detail) return detail;
    if (detail && typeof detail === 'object' && typeof (detail as { message?: unknown }).message === 'string') {
      return (detail as { message: string }).message;
    }
  } catch {
    // ignore invalid payload
  }
  return fallback;
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

/* --- 章节切换非阻塞通知 --- */
const CHAPTER_NOTIFY_DURATION = 3200;
const chapterNotifyVisible = ref(false);
const chapterNotifyMessage = ref('');
let chapterNotifyTimer: ReturnType<typeof setTimeout> | null = null;

function showChapterNotify() {
  const nextTitle = activeChapter.value.title || t('views.player.novelReader.mainText');
  const isLast = activeChapterIndex.value >= chapters.value.length - 1;
  const isFirst = activeChapterIndex.value <= 0;
  const swipeHint = isCompact.value
    ? t('views.player.novelReader.hintSwipePage')
    : t('views.player.novelReader.hintKeyPage');

  if (isLast) {
    chapterNotifyMessage.value = t('views.player.novelReader.chapterEndLast', { title: nextTitle });
  } else if (isFirst) {
    chapterNotifyMessage.value = t('views.player.novelReader.chapterStartFirst', { title: nextTitle, hint: swipeHint });
  } else {
    chapterNotifyMessage.value = t('views.player.novelReader.chapterSwitch', { title: nextTitle, hint: swipeHint });
  }

  chapterNotifyVisible.value = true;
  if (chapterNotifyTimer) clearTimeout(chapterNotifyTimer);
  chapterNotifyTimer = setTimeout(() => {
    chapterNotifyVisible.value = false;
    chapterNotifyTimer = null;
  }, CHAPTER_NOTIFY_DURATION);
}

/* --- 浮动顶栏自动隐藏 --- */
const TOPBAR_TRIGGER_ZONE = 80;
const TOPBAR_HIDE_DELAY = 2800;
const TOPBAR_SHOW_DELAY = 300;
const topbarVisible = ref(false);
const topbarHovering = ref(false);
let topbarTimer: ReturnType<typeof setTimeout> | null = null;
let showTimer: ReturnType<typeof setTimeout> | null = null;

function cancelTopbarTimer() {
  if (topbarTimer) { clearTimeout(topbarTimer); topbarTimer = null; }
}

function cancelShowTimer() {
  if (showTimer) { clearTimeout(showTimer); showTimer = null; }
}

function scheduleHideTopbar() {
  cancelTopbarTimer();
  topbarTimer = setTimeout(() => {
    if (!showSettings.value && !topbarHovering.value) topbarVisible.value = false;
  }, TOPBAR_HIDE_DELAY);
}

function showTopbar() {
  topbarVisible.value = true;
  cancelTopbarTimer();
  cancelShowTimer();
  scheduleHideTopbar();
}

function onTopbarEnter() {
  topbarHovering.value = true;
  cancelTopbarTimer();
  cancelShowTimer();
}

function onTopbarLeave() {
  topbarHovering.value = false;
  scheduleHideTopbar();
}

function onReaderPointerMove(e: MouseEvent) {
  if (e.clientY < TOPBAR_TRIGGER_ZONE) {
    // 鼠标在顶部区域，延迟呼出（避免翻页时误触发）
    if (!showTimer && !topbarVisible.value) {
      showTimer = setTimeout(() => {
        showTimer = null;
        showTopbar();
      }, TOPBAR_SHOW_DELAY);
    }
  } else {
    // 鼠标离开顶部区域，取消延迟呼出
    cancelShowTimer();
  }
}

/* --- 左右滑动翻页 --- */
const SWIPE_THRESHOLD = 40;
let swipeStartX = 0;
let swipeStartY = 0;
let swipeActive = false;
let swipeTarget: EventTarget | null = null;

function onSwipeStart(e: PointerEvent) {
  if (readingMode.value !== 'page') return;
  swipeStartX = e.clientX;
  swipeStartY = e.clientY;
  swipeActive = true;
  swipeTarget = e.target;
  // 捕获指针，确保移出元素后仍能收到 pointerup
  (e.target as HTMLElement).setPointerCapture?.(e.pointerId);
}

function onSwipeEnd(e: PointerEvent) {
  if (!swipeActive || readingMode.value !== 'page') return;
  swipeActive = false;
  // 释放捕获
  (swipeTarget as HTMLElement)?.releasePointerCapture?.(e.pointerId);
  swipeTarget = null;
  const dx = e.clientX - swipeStartX;
  const dy = e.clientY - swipeStartY;
  // 水平位移必须大于垂直位移且超过阈值
  if (Math.abs(dx) < SWIPE_THRESHOLD || Math.abs(dy) > Math.abs(dx)) return;
  if (dx < 0) goNextPage();
  else goPrevPage();
}

function onSwipeCancel(e: PointerEvent) {
  if (!swipeActive) return;
  swipeActive = false;
  (swipeTarget as HTMLElement)?.releasePointerCapture?.(e.pointerId);
  swipeTarget = null;
}

const shareId = computed(() => String(route.params.shareId || ''));

/** 将免责声明文本在第一个 "SparkArc" 处拆分，用于插入链接 */
const disclaimerParts = computed(() => {
  const text = t('views.player.desktop.zhDisclaimer');
  const idx = text.indexOf('SparkArc');
  if (idx === -1) return null;
  return { before: text.slice(0, idx), after: text.slice(idx + 'SparkArc'.length) };
});
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
      current = { title: t('views.player.novelReader.openingChapter'), paragraphs: [] };
    }
    current.paragraphs.push(paragraph);
  }

  if (current && current.paragraphs.length > 0) {
    result.push(current);
  }

  if (!result.length) {
    const fallbackParagraphs = sourceParagraphs.value.length ? sourceParagraphs.value : [''];
    return [{ title: t('views.player.novelReader.mainText'), paragraphs: fallbackParagraphs }];
  }

  return result;
});

const activeChapter = computed(() => {
  const fallback: NovelChapter = { title: t('views.player.novelReader.mainText'), paragraphs: [''] };
  return chapters.value[activeChapterIndex.value] || chapters.value[0] || fallback;
});

const activeChapterTitle = computed(() => activeChapter.value.title || t('views.player.novelReader.mainText'));

const paragraphs = computed(() => {
  return activeChapter.value.paragraphs;
});

/* --- BookNavButton 导航数据 --- */
const chapterNavItems = computed<NavItem[]>(() =>
  chapters.value.map((ch, idx) => ({
    id: `chapter-${idx}`,
    title: ch.title,
  }))
);

const chapterNavCurrentId = computed(() => `chapter-${activeChapterIndex.value}`);

function handleChapterNavSelect(item: NavItem) {
  const idx = Number(String(item.id).replace('chapter-', ''));
  if (Number.isFinite(idx) && idx >= 0 && idx < chapters.value.length) {
    activeChapterIndex.value = idx;
  }
}

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
    return t('views.player.novelReader.readingStatusScroll', {
      chapter: activeChapterIndex.value + 1,
      progress: Math.round(progressPercent.value),
    });
  }
  return t('views.player.novelReader.readingStatusPage', {
    chapter: activeChapterIndex.value + 1,
    page: currentPage.value + 1,
    totalPages: totalPages.value,
  });
});
const readingHint = computed(() => {
  if (readingMode.value === 'scroll') {
    return t('views.player.novelReader.hintScroll', { title: activeChapterTitle.value });
  }
  return isCompact.value
    ? t('views.player.novelReader.hintCompactPage', { title: activeChapterTitle.value })
    : t('views.player.novelReader.hintDesktopPage', { title: activeChapterTitle.value });
});

const panelStyle = computed(() => ({
  '--reader-font-size': `${fontSize.value}px`,
  // 翻页模式禁止浏览器水平手势拦截，确保 pointer 事件完整触发
  touchAction: readingMode.value === 'page' ? 'pan-y' : 'auto',
}))

function chapterLabel(chapter: NovelChapter, index: number): string {
  return t('views.player.novelReader.chapterLabel', { chapter: index + 1, title: chapter.title });
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

const pageDirection = ref<'next' | 'prev'>('next');
const pageTransitionName = computed(() => pageDirection.value === 'next' ? 'page-next' : 'page-prev');

function goPrevPage() {
  pageDirection.value = 'prev';
  if (currentPage.value > 0) {
    currentPage.value--;
  } else if (activeChapterIndex.value > 0) {
    // 章节首页翻上一页 → 进入上一章末页
    activeChapterIndex.value--;
    // 等 paragraphs 重新计算后再跳到末页
    nextTick(() => {
      currentPage.value = Math.max(totalPages.value - 1, 0);
      showChapterNotify();
    });
    return;
  }
}

function goNextPage() {
  pageDirection.value = 'next';
  if (currentPage.value < totalPages.value - 1) {
    currentPage.value++;
  } else if (activeChapterIndex.value < chapters.value.length - 1) {
    // 章节末页翻下一页 → 进入下一章首页
    activeChapterIndex.value++;
    // paragraphs 变化后 currentPage 由 watch 重置为 0
    nextTick(() => {
      showChapterNotify();
    });
    return;
  }
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

    if (!infoRes.ok) throw new Error(await readApiError(infoRes, t('views.player.novelReader.metaLoadFailed')));
    if (!dataRes.ok) throw new Error(await readApiError(dataRes, t('views.player.novelReader.dataLoadFailed')));

    const info = await infoRes.json() as NovelInfoResponse;
    const data = await dataRes.json() as NovelDataResponse;

    if ((data.format || 'script') !== 'novel') {
      throw new Error(t('views.player.novelReader.notNovelLink'));
    }

    meta.value = {
      title: cleanTitle(info.title, info.project_name || t('views.player.novelReader.untitledNovel')),
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
  if (topbarTimer) clearTimeout(topbarTimer);
  if (showTimer) clearTimeout(showTimer);
  if (chapterNotifyTimer) clearTimeout(chapterNotifyTimer);
});
</script>

<style scoped>
/* ====== 与剧本播放器一致的深海军蓝配色体系 ====== */
.novel-player {
  --bg-color: #0a0e1a;
  --text-color: #d8dce8;
  --accent-color: #7b9ec4;
  --accent-glow: rgba(123, 158, 196, 0.25);
  --accent-secondary: #b8a9d4;
  --accent-warm: #d4a9b8;
  --panel-bg: rgba(12, 16, 28, 0.88);
  --border-dim: rgba(123, 158, 196, 0.12);
  --border-mid: rgba(123, 158, 196, 0.2);
  --text-dim: rgba(216, 220, 232, 0.5);
  --reader-font-size: 17px;
  --font-main: var(--spark-font);

  width: 100vw;
  height: 100vh; /* 旧浏览器回退 */
  height: 100dvh; /* 动态视口高度，移动端浏览器地址栏可见时仍正确 */
  background: var(--bg-color);
  color: var(--text-color);
  font-family: var(--font-main);
  overflow: hidden;
  user-select: none;
  position: relative;
  display: flex;
  flex-direction: column;
}

/* 常驻免责标签——占位式，不遮挡正文 */
.persistent-disclaimer {
  flex-shrink: 0;
  width: 100%;
  text-align: center;
  padding: 4px 8px;
  box-sizing: border-box;
  font-size: var(--spark-fs-3xs, 11px);
  color: var(--text-dim);
  background: var(--bg-color);
  z-index: 10;
}
.disclaimer-brand-link {
  color: var(--text-dim);
  text-decoration: none;
  font-weight: 600;
  transition: opacity 0.2s;
}
.disclaimer-brand-link:hover {
  opacity: 0.7;
  text-decoration: underline;
}

.novel-screen {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  z-index: 1;
}

.state-screen {
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: var(--bg-color);
  z-index: 1000;
}

.state-card {
  width: min(560px, 100%);
  padding: 32px 28px;
  border-radius: 20px;
  border: 1px solid var(--border-mid);
  background: var(--panel-bg);
  box-shadow: 0 18px 50px rgba(0, 0, 0, 0.5);
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
  border: 1px solid var(--accent-color);
  background: transparent;
  color: var(--accent-color);
  cursor: pointer;
  transition: all 0.3s;
}

.action-btn:hover {
  background: var(--accent-color);
  color: var(--bg-color);
  box-shadow: 0 0 15px var(--accent-glow);
}

/* ====== 沉浸式阅读屏幕 ====== */
.reading-screen {
  display: flex;
  flex-direction: column;
  width: 100%;
  height: 100%;
  position: relative;
}

/* ====== 浮动顶栏 ====== */
.floating-topbar {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 100;
  transform: translateY(-100%);
  opacity: 0;
  transition: transform .35s cubic-bezier(.4, 0, .2, 1), opacity .35s ease;
  pointer-events: none;
}

.floating-topbar.visible {
  transform: translateY(0);
  opacity: 1;
  pointer-events: auto;
}

.topbar-inner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 24px;
  padding-top: calc(10px + var(--sat, 0px));
  background: var(--panel-bg);
  backdrop-filter: blur(24px) saturate(1.4);
  border-bottom: 1px solid var(--border-dim);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
}

.topbar-left {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;

  --book-nav-text: var(--text-color);
  --book-nav-text-dim: var(--text-dim);
  --book-nav-accent: var(--accent-color);
  --book-nav-panel-bg: rgba(12, 16, 28, 0.95);
  --book-nav-border: var(--border-dim);
}

.topbar-title {
  margin: 0;
  font-size: var(--spark-fs-sm);
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  opacity: 0.85;
}

.topbar-center {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}

.topbar-page-info {
  font-size: var(--spark-fs-xs);
  color: var(--text-dim);
  min-width: 56px;
  text-align: center;
  white-space: nowrap;
}

.topbar-right {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
}

.topbar-status {
  font-size: var(--spark-fs-xs);
  color: var(--text-dim);
  white-space: nowrap;
}

.topbar-icon-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border: none;
  border-radius: 8px;
  background: rgba(123, 158, 196, 0.15);
  color: #d8dce8;
  cursor: pointer;
  transition: background .2s ease, color .2s ease, opacity .2s ease;
}

.topbar-icon-btn:hover:not(:disabled) {
  background: rgba(123, 158, 196, 0.32);
  color: #fff;
}

.topbar-icon-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

/* ====== 设置抽屉 ====== */
.settings-drawer {
  position: fixed;
  top: 0;
  right: 0;
  bottom: 0;
  width: min(340px, 85vw);
  z-index: 200;
  display: flex;
  flex-direction: column;
  background: #0f1322;
  backdrop-filter: blur(28px) saturate(1.4);
  border-left: 1px solid var(--border-dim);
  box-shadow: -12px 0 48px rgba(0, 0, 0, 0.5);
}

.drawer-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border-dim);
}

.drawer-title {
  font-size: var(--spark-fs-sm);
  font-weight: 600;
  color: var(--accent-color);
}

.drawer-body {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.drawer-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.drawer-label {
  font-size: var(--spark-fs-xs);
  color: var(--text-dim);
  letter-spacing: 0.04em;
}

.drawer-select {
  width: 100%;
  border: 1px solid var(--border-mid);
  background: rgba(12, 16, 28, 0.6);
  color: inherit;
  padding: 9px 12px;
  border-radius: 8px;
  font-size: var(--spark-fs-sm);
}

.drawer-select:focus {
  outline: 1px solid var(--accent-color);
  outline-offset: 1px;
}

.drawer-font-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.drawer-font-btn {
  flex: 1;
  padding: 8px 0;
  border: 1px solid var(--border-mid);
  border-radius: 8px;
  background: rgba(12, 16, 28, 0.6);
  color: inherit;
  cursor: pointer;
  font-size: var(--spark-fs-sm);
  transition: background .2s ease;
}

.drawer-font-btn:hover:not(:disabled) {
  background: rgba(123, 158, 196, 0.18);
}

.drawer-font-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.drawer-font-value {
  min-width: 36px;
  text-align: center;
  font-size: var(--spark-fs-sm);
  color: var(--text-dim);
}

.drawer-mode-row {
  display: flex;
  gap: 8px;
}

.drawer-mode-btn {
  flex: 1;
  padding: 8px 0;
  border: 1px solid var(--border-mid);
  border-radius: 8px;
  background: rgba(12, 16, 28, 0.6);
  color: inherit;
  cursor: pointer;
  font-size: var(--spark-fs-sm);
  transition: background .2s ease, border-color .2s ease;
}

.drawer-mode-btn.active {
  background: rgba(123, 158, 196, 0.32);
  border-color: rgba(123, 158, 196, 0.5);
}

.drawer-mode-btn:hover:not(.active) {
  background: rgba(123, 158, 196, 0.14);
}

.drawer-description {
  margin: 0;
  font-size: var(--spark-fs-xs);
  line-height: 1.7;
  color: var(--text-dim);
}

/* 抽屉遮罩 */
.drawer-overlay {
  position: fixed;
  inset: 0;
  z-index: 190;
  background: rgba(6, 8, 18, 0.65);
  backdrop-filter: blur(2px);
}

/* 抽屉动画 */
.drawer-slide-enter-active,
.drawer-slide-leave-active {
  transition: transform .32s cubic-bezier(.4, 0, .2, 1);
}

.drawer-slide-enter-from,
.drawer-slide-leave-to {
  transform: translateX(100%);
}

.drawer-mask-enter-active,
.drawer-mask-leave-active {
  transition: opacity .28s ease;
}

.drawer-mask-enter-from,
.drawer-mask-leave-to {
  opacity: 0;
}

/* ====== 正文区域（全屏沉浸） ====== */
.reading-main {
  flex: 1 1 auto;
  display: flex;
  padding: 0;
  position: relative;
  cursor: grab;
}

.reading-main:active {
  cursor: grabbing;
}

.reading-paper-shell {
  flex: 1;
  display: flex;
  min-height: 0;
}

.reading-paper {
  width: 100%;
  height: 100%;
  overflow: hidden;
  border: none;
  background: radial-gradient(circle at 50% 30%, #0f1528 0%, #0a0e1a 80%);
  box-shadow: none;
}

.page-inner {
  width: 100%;
  max-width: 920px;
  margin: 0 auto;
  padding: 48px 48px 32px;
  box-sizing: border-box;
}

.reading-paper-scroll {
  overflow-y: auto;
  scroll-behavior: smooth;
}

.reading-paper-scroll::-webkit-scrollbar {
  width: 6px;
}

.reading-paper-scroll::-webkit-scrollbar-track {
  background: transparent;
}

.reading-paper-scroll::-webkit-scrollbar-thumb {
  background: rgba(123, 158, 196, 0.18);
  border-radius: 999px;
}

.novel-paragraph {
  margin: 0 0 1.35em;
  font-size: var(--reader-font-size);
  line-height: 2;
  letter-spacing: 0.02em;
  color: #eee;
  text-align: justify;
  text-indent: 2em;
}

/* ====== 章节切换非阻塞通知条 ====== */
.chapter-notify-bar {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  z-index: 50;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 10px 20px;
  padding-top: calc(10px + var(--sat, 0px));
  background: rgba(12, 16, 28, 0.92);
  backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--border-mid);
  cursor: pointer;
  user-select: none;
}

.chapter-notify-text {
  font-size: var(--spark-fs-xs);
  color: var(--accent-color);
  letter-spacing: 0.02em;
  text-align: center;
  line-height: 1.5;
}

.notify-slide-enter-active,
.notify-slide-leave-active {
  transition: transform .3s cubic-bezier(.4, 0, .2, 1), opacity .3s ease;
}
.notify-slide-enter-from,
.notify-slide-leave-to {
  transform: translateY(-100%);
  opacity: 0;
}

/* ====== 翻页进度条（极细，页面底部） ====== */
.reading-main::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: 10%;
  right: 10%;
  height: 2px;
  border-radius: 999px;
  background: rgba(123, 158, 196, 0.08);
  pointer-events: none;
}

.progress-fill-bar {
  position: absolute;
  bottom: 0;
  left: 10%;
  height: 2px;
  border-radius: 999px;
  background: linear-gradient(90deg, var(--accent-color), var(--accent-secondary));
  pointer-events: none;
  transition: width .34s ease, right .34s ease;
}

/* 翻页动画——翻下一页：新页从右入，旧页向左出 */
.page-next-enter-active,
.page-next-leave-active {
  transition: opacity .22s ease, transform .22s ease;
}
.page-next-enter-from {
  opacity: 0;
  transform: translateX(40px);
}
.page-next-leave-to {
  opacity: 0;
  transform: translateX(-40px);
}

/* 翻页动画——翻上一页：新页从左入，旧页向右出 */
.page-prev-enter-active,
.page-prev-leave-active {
  transition: opacity .22s ease, transform .22s ease;
}
.page-prev-enter-from {
  opacity: 0;
  transform: translateX(-40px);
}
.page-prev-leave-to {
  opacity: 0;
  transform: translateX(40px);
}

/* ====== 响应式 ====== */
@media (max-width: 1024px) {
  .page-inner {
    max-width: none;
    padding: 36px 32px 28px;
  }

  .topbar-inner {
    padding: 8px 16px;
  }
}

@media (max-width: 768px) {
  .page-inner {
    padding: 28px 16px calc(24px + var(--sab, env(safe-area-inset-bottom, 0px)));
  }

  .topbar-inner {
    padding: 8px 12px;
  }

  .topbar-title {
    font-size: var(--spark-fs-xs);
  }

  .topbar-center {
    gap: 4px;
  }

  .topbar-page-info {
    font-size: 10px;
    min-width: 44px;
  }

  .topbar-icon-btn {
    width: 28px;
    height: 28px;
  }

  .novel-paragraph {
    text-align: left;
    text-indent: 1.8em;
    line-height: 1.92;
  }

  .settings-drawer {
    width: min(300px, 90vw);
  }
}
</style>
