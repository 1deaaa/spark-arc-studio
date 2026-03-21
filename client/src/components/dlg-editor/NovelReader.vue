<template>
  <div class="novel-reader" :class="themeClass" :style="{ fontSize: fontSize + 'px' }">
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
        <n-select
          v-model:value="theme"
          :options="themeOptions"
          size="small"
          style="width: 100px; margin-left: 8px;"
        />
      </div>
    </div>
    
    <div class="reader-content-wrapper">
      <n-input
        v-model:value="localContent"
        type="textarea"
        class="reader-editor"
        :autosize="{ minRows: 18 }"
        placeholder="在这里开始你的小说创作……"
        @update:value="handleInput"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onBeforeUnmount } from 'vue';
import { NButtonGroup, NButton, NSelect, NInput } from 'naive-ui';
import { useSceneStore } from '@/components/stores/sceneStore';

const props = defineProps({
  content: {
    type: String,
    default: ''
  }
});

const sceneStore = useSceneStore();

const fontSize = ref(16);
const theme = ref('parchment');
const localContent = ref(props.content || '');
let saveTimer = null;

const themeOptions = [
  { label: '羊皮纸', value: 'parchment' },
  { label: '白纸', value: 'light' },
  { label: '夜间', value: 'dark' }
];

const themeClass = computed(() => `theme-${theme.value}`);
const wordCount = computed(() => (localContent.value || '').replace(/\s+/g, '').length);

watch(() => props.content, (value) => {
  const next = value || '';
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
  sceneStore.scriptData = value || '';
  sceneStore.selectionType = 'novel';
  scheduleSave();
}

async function saveNow() {
  if (saveTimer) {
    clearTimeout(saveTimer);
    saveTimer = null;
  }
  sceneStore.scriptData = localContent.value || '';
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
  transition: background-color 0.3s, color 0.3s;
}

.reader-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 16px;
  border-bottom: 1px solid rgba(128, 128, 128, 0.2);
  flex-shrink: 0;
  /* background color will be inherited or specified by theme */
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
  padding: 24px;
  display: flex;
  justify-content: center;
}

.reader-editor {
  max-width: 900px;
  width: 100%;
}

:deep(.reader-editor .n-input-wrapper) {
  padding: 0;
  background: transparent;
  box-shadow: none !important;
}

:deep(.reader-editor textarea) {
  min-height: calc(100vh - 220px);
  padding: 0 0 50px 0;
  border: none;
  outline: none;
  resize: none;
  background: transparent;
  color: inherit;
  line-height: 1.9;
  font-size: inherit;
  font-family: inherit;
  white-space: pre-wrap;
  word-wrap: break-word;
}

/* Themes */
.theme-light {
  background-color: #ffffff;
  color: #333333;
}
.theme-light .reader-toolbar {
  background-color: #f5f5f5;
}

.theme-dark {
  background-color: #1a1a1a;
  color: #cccccc;
}
.theme-dark .reader-toolbar {
  background-color: #242424;
  border-bottom-color: #333;
}

.theme-parchment {
  background-color: #fbf0d9;
  color: #5b4636;
}
.theme-parchment .reader-toolbar {
  background-color: #f1e4c3;
  border-bottom-color: #e3d2a7;
}
</style>
