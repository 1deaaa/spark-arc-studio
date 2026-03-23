<template>
  <div class="novel-reader" :style="{ '--novel-editor-font-size': fontSize + 'px' }">
    <div class="reader-toolbar">
      <div class="toolbar-left">
        <span class="toolbar-title">小说编辑</span>
        <span class="toolbar-meta">{{ wordCount }} 字</span>
      </div>
      <div class="toolbar-right">
        <n-button-group size="small">
          <n-button @click="decreaseFontSize" :disabled="fontSize <= 12">A-</n-button>
          <n-button @click="increaseFontSize" :disabled="fontSize >= 32">A+</n-button>
        </n-button-group>
        <n-button size="small" secondary style="margin-left: 8px;" @click="saveNow">保存</n-button>
      </div>
    </div>
    
    <div class="reader-content-wrapper">
      <n-input
        v-model:value="localContent"
        type="textarea"
        class="reader-editor"
        :style="{ '--novel-editor-font-size': fontSize + 'px' }"
        :autosize="{ minRows: 18 }"
        placeholder="在这里开始你的小说创作……"
        @update:value="handleInput"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onBeforeUnmount } from 'vue';
import { NButtonGroup, NButton, NInput } from 'naive-ui';
import { useSceneStore } from '@/components/stores/sceneStore';

const props = defineProps({
  content: {
    type: String,
    default: ''
  }
});

const sceneStore = useSceneStore();

const fontSize = ref(16);
function normalizeContent(value) {
  if (typeof value === 'string') return value;
  if (Array.isArray(value)) return '';
  if (value == null) return '';
  return String(value);
}

const localContent = ref(normalizeContent(props.content));
let saveTimer = null;
const wordCount = computed(() => normalizeContent(localContent.value).replace(/\s+/g, '').length);

watch(() => props.content, (value) => {
  const next = normalizeContent(value);
  if (next !== localContent.value) {
    localContent.value = next;
  }
});

function scheduleSave() {
  if (saveTimer) clearTimeout(saveTimer);
  saveTimer = setTimeout(async () => {
    saveTimer = null;
    await sceneStore._saveStory();
  }, 600);
}

function handleInput(value) {
  sceneStore.scriptData = normalizeContent(value);
  sceneStore.selectionType = 'novel';
  scheduleSave();
}

async function saveNow() {
  if (saveTimer) {
    clearTimeout(saveTimer);
    saveTimer = null;
  }
  sceneStore.scriptData = normalizeContent(localContent.value);
  sceneStore.selectionType = 'novel';
  await sceneStore._saveStory();
}

function increaseFontSize() {
  if (fontSize.value < 32) fontSize.value += 2;
}

function decreaseFontSize() {
  if (fontSize.value > 12) fontSize.value -= 2;
}

onBeforeUnmount(() => {
  if (saveTimer) clearTimeout(saveTimer);
});
</script>

<style scoped>
.novel-reader {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: transparent;
  color: var(--n-text-color);
  --novel-editor-font-size: 16px;
}

.reader-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 16px;
  border-bottom: 1px solid var(--n-border-color);
  flex-shrink: 0;
  background: color-mix(in srgb, var(--n-color) 72%, transparent);
  backdrop-filter: blur(8px);
}

.toolbar-title {
  font-weight: bold;
  opacity: 0.8;
  font-size: 14px;
}

.toolbar-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.toolbar-meta {
  opacity: 0.65;
  font-size: 12px;
}

.toolbar-right {
  display: flex;
  align-items: center;
}

.reader-content-wrapper {
  flex: 1;
  overflow-y: auto;
  padding: 0;
  display: flex;
}

.reader-editor {
  width: 100%;
  height: 100%;
}

:deep(.reader-editor .n-input-wrapper) {
  padding: 0;
  background: transparent;
  box-shadow: none !important;
  height: 100%;
}

:deep(.reader-editor textarea) {
  min-height: 100%;
  height: 100%;
  padding: 20px 24px 40px;
  border: none;
  outline: none;
  resize: none;
  background: color-mix(in srgb, var(--n-color-modal) 82%, transparent);
  color: inherit;
  line-height: 1.9;
  font-size: var(--novel-editor-font-size) !important;
  font-family: inherit;
  white-space: pre-wrap;
  word-wrap: break-word;
  box-sizing: border-box;
}
</style>
