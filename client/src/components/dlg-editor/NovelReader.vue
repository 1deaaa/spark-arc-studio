<template>
  <NovelBackdrop class="novel-reader" mode="panel" framed :data-save-state="saveState">
    <div class="reader-stage">
      <div class="reader-sheet">
        <div class="sheet-edge" aria-hidden="true"></div>
        <div class="editor-frame">
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
        </div>
      </div>
    </div>
  </NovelBackdrop>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, nextTick, onBeforeUnmount } from 'vue';
import { useI18n } from 'vue-i18n';
import NovelBackdrop from '@/components/player/shared/NovelBackdrop.vue';
import { useSceneStore } from '@/components/stores/sceneStore';

const { t } = useI18n();

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

.novel-reader[data-save-state='editing'] .reader-sheet {
  box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--spark-primary), transparent 70%);
}

.novel-reader[data-save-state='saving'] .reader-sheet {
  box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--spark-warning), transparent 68%);
}

.novel-reader[data-save-state='saved'] .reader-sheet {
  box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--spark-success), transparent 78%);
}

:global(html.viewport-tablet-down .novel-reader .editor-frame) {
  --novel-editor-pad-top: 36px;
  --novel-editor-pad-inline: 30px;
  --novel-editor-pad-bottom: 32px;
}

:global(html.viewport-mobile .novel-reader .editor-frame) {
  --novel-editor-pad-top: 28px;
  --novel-editor-pad-inline: 20px;
  --novel-editor-pad-bottom: 24px;
}

:global(html.viewport-mobile .novel-reader .reader-editor),
:global(html.viewport-mobile .novel-reader .editor-placeholder) {
  font-size: var(--spark-fs-lg);
  line-height: 1.9;
}
</style>
