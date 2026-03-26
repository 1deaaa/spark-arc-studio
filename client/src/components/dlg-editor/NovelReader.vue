<template>
  <NovelBackdrop class="novel-reader" mode="panel" framed :data-save-state="saveState">
    <template #overlay>
      <div class="stats-dock">
        <div class="stat-pill">
          <span class="stat-label">字数</span>
          <strong class="stat-value">{{ wordCount }}</strong>
        </div>
        <div class="stat-pill">
          <span class="stat-label">段落</span>
          <strong class="stat-value">{{ paragraphCount }}</strong>
        </div>
        <div class="stat-pill">
          <span class="stat-label">预计阅读</span>
          <strong class="stat-value">{{ readingMinutes }} 分钟</strong>
        </div>
      </div>
    </template>

    <div class="reader-stage">
      <div class="reader-sheet">
        <div class="sheet-edge" aria-hidden="true"></div>
        <div class="editor-frame">
          <div v-if="!localContent" class="editor-placeholder">
            在这里开始你的小说创作……

让场景先动起来，再让人物开口。
          </div>
          <div
            ref="editorRef"
            class="reader-editor"
            contenteditable="true"
            role="textbox"
            aria-multiline="true"
            aria-label="小说正文编辑器"
            spellcheck="false"
            @input="handleInput"
            @paste="handlePaste"
          ></div>
        </div>
      </div>
    </div>
  </NovelBackdrop>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, nextTick, onBeforeUnmount } from 'vue';
import NovelBackdrop from '@/components/share/NovelBackdrop.vue';
import { useSceneStore } from '@/components/stores/sceneStore';

const props = defineProps({
  content: {
    type: String,
    default: ''
  }
});

const sceneStore = useSceneStore();
const editorRef = ref<HTMLDivElement | null>(null);
const saveState = ref<'idle' | 'editing' | 'saving' | 'saved'>('idle');

function normalizeContent(value: unknown): string {
  if (typeof value === 'string') return value;
  if (Array.isArray(value)) return '';
  if (value == null) return '';
  return String(value);
}

const localContent = ref(normalizeContent(props.content));
let saveTimer: ReturnType<typeof setTimeout> | null = null;

const wordCount = computed(() => normalizeContent(localContent.value).replace(/\s+/g, '').length);
const paragraphCount = computed(() => normalizeContent(localContent.value).split(/\n+/).map(item => item.trim()).filter(Boolean).length);
const readingMinutes = computed(() => Math.max(1, Math.ceil(wordCount.value / 500)));

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

async function persistContent() {
  sceneStore.scriptData = normalizeContent(localContent.value);
  sceneStore.selectionType = 'novel';
  saveState.value = 'saving';
  await sceneStore._saveStory();
  saveState.value = 'saved';
}

watch(() => props.content, (value) => {
  const next = normalizeContent(value);
  if (next !== localContent.value) {
    localContent.value = next;
  }
  nextTick(() => syncEditorContent(next));
});

function scheduleSave() {
  if (saveTimer) clearTimeout(saveTimer);
  saveState.value = 'editing';
  saveTimer = setTimeout(async () => {
    saveTimer = null;
    await persistContent();
  }, 700);
}

function handleInput() {
  const nextValue = getEditorText();
  localContent.value = nextValue;
  sceneStore.scriptData = nextValue;
  sceneStore.selectionType = 'novel';
  scheduleSave();
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
  saveState.value = localContent.value ? 'saved' : 'idle';
});

onBeforeUnmount(() => {
  if (saveTimer) clearTimeout(saveTimer);
});
</script>

<style scoped>
.novel-reader {
  height: 100%;
}

.stats-dock {
  position: absolute;
  top: 18px;
  right: 18px;
  z-index: 3;
  display: flex;
  gap: 8px;
  align-items: center;
}

.stat-pill {
  min-width: 88px;
  padding: 8px 12px;
  border-radius: 10px;
  border: 1px solid color-mix(in srgb, var(--spark-primary), transparent 72%);
  background: color-mix(in srgb, var(--spark-panel-bg), transparent 12%);
  box-shadow:
    0 8px 20px color-mix(in srgb, black, transparent 90%),
    inset 0 1px 0 color-mix(in srgb, white, transparent 92%);
  backdrop-filter: blur(14px);
}

.stat-label {
  display: block;
  font-size: 11px;
  line-height: 1.2;
  color: var(--spark-text-muted);
}

.stat-value {
  display: block;
  margin-top: 4px;
  font-size: 15px;
  line-height: 1.2;
  font-weight: 700;
  color: var(--spark-text);
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
  position: relative;
  height: 100%;
  padding: 56px 48px 40px;
  overflow: auto;
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
  font-size: 18px;
  line-height: 1.9;
  letter-spacing: 0.01em;
  font-family: 'Georgia', 'Times New Roman', 'PingFang SC', 'Noto Serif SC', serif;
  caret-color: var(--spark-primary);
}

.editor-placeholder {
  position: absolute;
  inset: 56px 48px 40px;
  color: color-mix(in srgb, var(--spark-text-muted), transparent 8%);
  white-space: pre-wrap;
  pointer-events: none;
  user-select: none;
  font-size: 18px;
  line-height: 1.9;
  font-family: 'Georgia', 'Times New Roman', 'PingFang SC', 'Noto Serif SC', serif;
}

.novel-reader[data-save-state='editing'] .reader-sheet {
  box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--spark-primary), transparent 70%);
}

.novel-reader[data-save-state='saving'] .reader-sheet {
  box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--spark-warning), transparent 68%);
}

.novel-reader[data-save-state='saved'] .reader-sheet {
  box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--spark-success), transparent 78%);
}

@media (max-width: 1024px) {
  .stats-dock {
    top: 14px;
    right: 14px;
  }

  .editor-frame {
    padding: 72px 30px 32px;
  }

  .editor-placeholder {
    inset: 72px 30px 32px;
  }
}

@media (max-width: 768px) {
  .stats-dock {
    flex-wrap: wrap;
    justify-content: flex-end;
    max-width: calc(100% - 24px);
  }

  .stat-pill {
    min-width: 78px;
  }

  .editor-frame {
    padding: 84px 20px 24px;
  }

  .editor-placeholder {
    inset: 84px 20px 24px;
  }

  .reader-editor,
  .editor-placeholder {
    font-size: 16px;
    line-height: 1.9;
  }
}
</style>
