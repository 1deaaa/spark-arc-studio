<template>
  <NovelBackdrop class="novel-reader" mode="panel" framed>
    <div class="reader-stage">
      <div class="reader-sheet">
        <div class="sheet-edge" aria-hidden="true"></div>
        <div
          ref="frameRef"
          class="editor-frame"
          @scroll="updateCurrentPage"
          @pointerdown="handleSwipeStart"
          @pointerup="handleSwipeEnd"
          @pointercancel="handleSwipeCancel"
        >
          <div class="novel-editor-tools">
            <n-popover trigger="click" placement="bottom-end" :show-arrow="false">
              <template #trigger>
                <n-tooltip trigger="hover">
                  <template #trigger>
                    <n-button quaternary circle size="small" :aria-label="t('components.novelEditor.conception.button')">
                      <template #icon><n-icon :component="NotebookPen" /></template>
                    </n-button>
                  </template>
                  {{ t('components.novelEditor.conception.button') }}
                </n-tooltip>
              </template>
              <div class="conception-editor">
                <label>{{ t('components.novelEditor.conception.title') }}</label>
                <n-input
                  :value="sceneStore.novelConception"
                  type="textarea"
                  :autosize="{ minRows: 6, maxRows: 14 }"
                  :placeholder="t('components.novelEditor.conception.placeholder')"
                  @update:value="sceneStore.updateNovelConception"
                />
                <p>{{ t('components.novelEditor.conception.hint') }}</p>
              </div>
            </n-popover>
          </div>
          <div v-if="!localContent" class="editor-placeholder">
            {{ t('components.novelEditor.placeholderLine1') }}

{{ t('components.novelEditor.placeholderLine2') }}
          </div>
          <div
            ref="editorRef"
            class="reader-editor"
            contenteditable="true"
            role="textbox"
            aria-multiline="true"
            :aria-label="t('components.novelEditor.editorAria')"
            spellcheck="false"
            @input="handleInput"
            @paste="handlePaste"
          ></div>
          <div v-if="pageCount > 1" class="mobile-page-nav" :aria-label="t('components.novelEditor.pagination.aria')">
            <n-button quaternary circle size="small" :disabled="currentPage <= 0" @click="goToPage(currentPage - 1)">
              <template #icon><n-icon :component="ChevronLeft" /></template>
            </n-button>
            <span>{{ currentPage + 1 }} / {{ pageCount }}</span>
            <n-button quaternary circle size="small" :disabled="currentPage >= pageCount - 1" @click="goToPage(currentPage + 1)">
              <template #icon><n-icon :component="ChevronRight" /></template>
            </n-button>
          </div>
        </div>
      </div>
    </div>
  </NovelBackdrop>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, nextTick, onBeforeUnmount } from 'vue';
import { useI18n } from 'vue-i18n';
import { NButton, NIcon, NInput, NPopover, NTooltip } from 'naive-ui';
import { ChevronLeft, ChevronRight, NotebookPen } from '@lucide/vue';
import NovelBackdrop from '@/components/player/shared/NovelBackdrop.vue';
import { useSceneStore } from '@/components/stores/sceneStore';
import { useMobile } from '@/composables/useMobile';

const { t } = useI18n();

const props = defineProps({
  content: {
    type: String,
    default: ''
  }
});

const sceneStore = useSceneStore();
const editorRef = ref<HTMLDivElement | null>(null);
const frameRef = ref<HTMLDivElement | null>(null);
const currentPage = ref(0);
const pageCount = ref(1);
const { isCompact } = useMobile();
let resizeObserver: ResizeObserver | null = null;
let swipeStartX = 0;
let swipeStartY = 0;
let swipePointerId: number | null = null;
const SWIPE_THRESHOLD = 44;

function normalizeContent(value: unknown): string {
  if (typeof value === 'string') return value;
  if (Array.isArray(value)) return '';
  if (value == null) return '';
  return String(value);
}

const localContent = ref(normalizeContent(props.content));

function getEditorText(): string {
  return (editorRef.value?.innerText || '').replace(/\r\n/g, '\n').replace(/\u00A0/g, ' ');
}

function syncEditorContent(value: string) {
  if (!editorRef.value) return;
  const normalized = normalizeContent(value);
  if (getEditorText() !== normalized) {
    editorRef.value.innerText = normalized;
  }
}

function updatePageMetrics() {
  const frame = frameRef.value;
  if (!frame) return;
  const viewportHeight = Math.max(1, frame.clientHeight);
  const maxScrollTop = Math.max(0, frame.scrollHeight - viewportHeight);
  pageCount.value = Math.max(1, Math.ceil(frame.scrollHeight / viewportHeight));
  if (pageCount.value === 1) {
    currentPage.value = 0;
  } else if (maxScrollTop - frame.scrollTop <= 2) {
    currentPage.value = pageCount.value - 1;
  } else {
    currentPage.value = Math.min(pageCount.value - 1, Math.max(0, Math.round(frame.scrollTop / viewportHeight)));
  }
}

function updateCurrentPage() {
  updatePageMetrics();
}

function goToPage(page: number) {
  const frame = frameRef.value;
  if (!frame) return;
  const target = Math.min(pageCount.value - 1, Math.max(0, page));
  const maxScrollTop = Math.max(0, frame.scrollHeight - frame.clientHeight);
  const targetTop = target === pageCount.value - 1
    ? maxScrollTop
    : Math.min(target * frame.clientHeight, maxScrollTop);
  currentPage.value = target;
  frame.scrollTo({ top: targetTop, behavior: 'smooth' });
}

function handleSwipeStart(event: PointerEvent) {
  if (!isCompact.value || event.pointerType === 'mouse') return;
  swipeStartX = event.clientX;
  swipeStartY = event.clientY;
  swipePointerId = event.pointerId;
  frameRef.value?.setPointerCapture?.(event.pointerId);
}

function handleSwipeEnd(event: PointerEvent) {
  if (swipePointerId !== event.pointerId) return;
  frameRef.value?.releasePointerCapture?.(event.pointerId);
  swipePointerId = null;
  const dx = event.clientX - swipeStartX;
  const dy = event.clientY - swipeStartY;
  if (Math.abs(dx) < SWIPE_THRESHOLD || Math.abs(dx) <= Math.abs(dy)) return;
  goToPage(currentPage.value + (dx < 0 ? 1 : -1));
}

function handleSwipeCancel(event: PointerEvent) {
  if (swipePointerId !== event.pointerId) return;
  frameRef.value?.releasePointerCapture?.(event.pointerId);
  swipePointerId = null;
}

watch(() => props.content, (value) => {
  const next = normalizeContent(value);
  if (next !== localContent.value) {
    localContent.value = next;
  }
  nextTick(() => syncEditorContent(next));
});

function handleInput() {
  const nextValue = getEditorText();
  localContent.value = nextValue;
  sceneStore.scriptData = nextValue;
  sceneStore.selectionType = 'novel';
  sceneStore.scheduleStorySave();
  nextTick(updatePageMetrics);
}

function handlePaste(event: ClipboardEvent) {
  event.preventDefault();
  const text = event.clipboardData?.getData('text/plain') ?? '';
  const selection = window.getSelection();

  if (!selection || selection.rangeCount === 0) {
    handleInput();
    return;
  }

  selection.deleteFromDocument();
  const range = selection.getRangeAt(0);
  range.insertNode(document.createTextNode(text));
  selection.collapseToEnd();
  handleInput();
}

onMounted(() => {
  syncEditorContent(localContent.value);
  resizeObserver = new ResizeObserver(updatePageMetrics);
  if (frameRef.value) resizeObserver.observe(frameRef.value);
  if (editorRef.value) resizeObserver.observe(editorRef.value);
  nextTick(updatePageMetrics);
});

onBeforeUnmount(() => {
  resizeObserver?.disconnect();
  void sceneStore.flushStorySave();
});
</script>

<style scoped>
.novel-reader {
  height: 100%;
}

.reader-stage {
  height: 100%;
  padding: 0;
}

.reader-sheet {
  position: relative;
  height: 100%;
  border-radius: 0;
  overflow: hidden;
  background:
    linear-gradient(180deg, color-mix(in srgb, var(--spark-panel-bg), white 2%), color-mix(in srgb, var(--spark-bg), white 1%));
  border: none;
  box-shadow:
    inset 0 1px 0 color-mix(in srgb, white, transparent 96%);
}

.sheet-edge {
  position: absolute;
  inset: 0 auto 0 0;
  width: 1px;
  background: color-mix(in srgb, var(--spark-primary), transparent 68%);
  box-shadow: 20px 0 40px color-mix(in srgb, var(--spark-primary), transparent 97%);
}

.editor-frame {
  --novel-editor-pad-top: 32px;
  --novel-editor-pad-inline: 48px;
  --novel-editor-pad-bottom: 40px;

  position: relative;
  height: 100%;
  padding: var(--novel-editor-pad-top) var(--novel-editor-pad-inline) var(--novel-editor-pad-bottom);
  overflow: auto;
  overscroll-behavior: contain;
  background:
    radial-gradient(circle at 12% 18%, color-mix(in srgb, white, transparent 97%), transparent 18%),
    radial-gradient(circle at 78% 24%, color-mix(in srgb, var(--spark-primary), transparent 98%), transparent 16%),
    radial-gradient(circle at 56% 72%, color-mix(in srgb, var(--spark-accent), transparent 99%), transparent 18%),
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
    linear-gradient(180deg, color-mix(in srgb, var(--spark-panel-bg), white 4%), color-mix(in srgb, var(--spark-bg), white 2%));
}

.reader-editor {
  position: relative;
  z-index: 1;
  min-height: 100%;
  outline: none;
  white-space: pre-wrap;
  word-break: break-word;
  color: var(--spark-text);
  font-size: var(--spark-fs-h3);
  line-height: 1.9;
  letter-spacing: 0;
  font-family: var(--spark-font);
  caret-color: var(--spark-primary);
}

.editor-placeholder {
  position: absolute;
  inset: var(--novel-editor-pad-top) var(--novel-editor-pad-inline) var(--novel-editor-pad-bottom);
  color: color-mix(in srgb, var(--spark-text-muted), transparent 8%);
  white-space: pre-wrap;
  pointer-events: none;
  user-select: none;
  font-size: var(--spark-fs-h3);
  line-height: 1.9;
  font-family: var(--spark-font);
}

:global(html.viewport-tablet-down .novel-reader .editor-frame) {
  --novel-editor-pad-top: 36px;
  --novel-editor-pad-inline: 30px;
  --novel-editor-pad-bottom: 32px;
}

.novel-editor-tools {
  position: absolute;
  z-index: 3;
  top: 8px;
  right: 10px;
}

.conception-editor {
  width: min(360px, calc(100vw - 36px));
}

.conception-editor label {
  display: block;
  margin-bottom: 8px;
  color: var(--spark-text);
  font-size: var(--spark-fs-sm);
  font-weight: 650;
}

.conception-editor p {
  margin: 8px 0 0;
  color: var(--spark-text-muted);
  font-size: var(--spark-fs-xs);
  line-height: 1.45;
}

.mobile-page-nav {
  display: none;
}

:global(html.viewport-mobile .novel-reader .editor-frame) {
  --novel-editor-pad-top: 28px;
  --novel-editor-pad-inline: 20px;
  --novel-editor-pad-bottom: 24px;
  padding-bottom: 62px;
  touch-action: pan-y;
  overscroll-behavior-x: contain;
}

:global(html.viewport-mobile .novel-reader .reader-editor),
:global(html.viewport-mobile .novel-reader .editor-placeholder) {
  font-size: var(--spark-fs-lg);
  line-height: 1.9;
}

:global(html.viewport-mobile .novel-reader .mobile-page-nav) {
  position: sticky;
  z-index: 3;
  bottom: 4px;
  display: flex;
  width: max-content;
  align-items: center;
  gap: 8px;
  margin: 10px auto 0;
  padding: 3px 6px;
  border: 1px solid var(--spark-border);
  border-radius: 6px;
  background: color-mix(in srgb, var(--spark-panel-bg) 94%, transparent);
  color: var(--spark-text-muted);
  font-size: var(--spark-fs-xs);
  font-variant-numeric: tabular-nums;
  backdrop-filter: blur(8px);
}
</style>
