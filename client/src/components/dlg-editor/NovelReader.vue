<template>
  <div class="novel-reader" :class="themeClass" :style="{ fontSize: fontSize + 'px' }">
    <div class="reader-toolbar">
      <div class="toolbar-left">
        <span class="toolbar-title">阅读模式</span>
      </div>
      <div class="toolbar-right">
        <n-button-group size="small">
          <n-button @click="decreaseFontSize" :disabled="fontSize <= 12">A-</n-button>
          <n-button @click="increaseFontSize" :disabled="fontSize >= 32">A+</n-button>
        </n-button-group>
        <n-select
          v-model:value="theme"
          :options="themeOptions"
          size="small"
          style="width: 100px; margin-left: 8px;"
        />
      </div>
    </div>
    
    <div class="reader-content-wrapper">
      <div class="reader-content">
        {{ content }}
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue';
import { NButtonGroup, NButton, NSelect } from 'naive-ui';

const props = defineProps({
  content: {
    type: String,
    default: ''
  }
});

const fontSize = ref(16);
const theme = ref('parchment');

const themeOptions = [
  { label: '羊皮纸', value: 'parchment' },
  { label: '白纸', value: 'light' },
  { label: '夜间', value: 'dark' }
];

const themeClass = computed(() => `theme-${theme.value}`);

function increaseFontSize() {
  if (fontSize.value < 32) fontSize.value += 2;
}

function decreaseFontSize() {
  if (fontSize.value > 12) fontSize.value -= 2;
}
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

.reader-content {
  max-width: 800px;
  width: 100%;
  white-space: pre-wrap;
  word-wrap: break-word;
  line-height: 1.8;
  font-family: inherit; /* user can configure their system reader font */
  padding-bottom: 50px;
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
