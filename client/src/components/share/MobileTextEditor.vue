<template>
  <!-- 使用 height="auto" 让抽屉高度完全跟随内容（textarea）高度自适应 -->
  <n-drawer
    v-model:show="isVisible"
    placement="bottom"
    height="auto"
    class="mobile-text-editor-drawer"
    @after-enter="focusEditor"
  >
    <n-drawer-content
      :title="title"
      closable
      :body-style="{
        padding: 0,
        display: 'flex',
        flexDirection: 'column',
        background: 'var(--n-color-embedded, rgba(255,255,255,0.06))',
      }"
    >
      <textarea
        ref="textareaRef"
        v-model="editValue"
        class="native-editor"
        :placeholder="placeholder"
        @input="adjustHeight"
      />
    </n-drawer-content>
  </n-drawer>
</template>

<script setup>
import { ref, watch, nextTick } from 'vue';
import { NDrawer, NDrawerContent } from 'naive-ui';

const props = defineProps({
  show: { type: Boolean, default: false },
  value: { type: String, default: '' },
  title: { type: String, default: '编辑文本' },
  placeholder: { type: String, default: '在这里输入内容...' }
});

const emit = defineEmits(['update:show', 'update:value', 'confirm']);

const isVisible = ref(props.show);
const editValue = ref(props.value);
const textareaRef = ref(null);

watch(() => props.show, (newVal) => {
  isVisible.value = newVal;
  if (newVal) {
    editValue.value = props.value ?? '';
    // 打开时根据已有文字自动重塑高度
    nextTick(() => {
      adjustHeight();
    });
  }
});

watch(editValue, () => {
  nextTick(() => {
    adjustHeight();
  });
});

watch(isVisible, (newVal) => {
  emit('update:show', newVal);
  if (!newVal) {
    // 关闭即保存
    emit('update:value', editValue.value);
    emit('confirm', editValue.value);
  }
});

function focusEditor() {
  textareaRef.value?.focus();
}

// 核心：原生 textarea 自适应撑高引擎
function adjustHeight() {
  const el = textareaRef.value;
  if (!el) return;
  // 先设为 auto 让其可以缩回以获得真实的 scrollHeight
  el.style.height = 'auto';
  // 将其实际样式高度设为其包含所有文字所需的高度
  el.style.height = `${el.scrollHeight}px`;
}

defineExpose({
  open: (val = '') => {
    editValue.value = val;
    isVisible.value = true;
  },
  close: () => { isVisible.value = false; }
});
</script>

<!-- 非 scoped 全局样式块，只覆盖本组件的抽屉内层 -->
<style>
/* 强制限制 auto 模式的抽屉突破屏幕 */
.mobile-text-editor-drawer.n-drawer {
  max-height: 90dvh !important;
}

.mobile-text-editor-drawer .n-drawer-body-content-wrapper {
  padding: 0 !important;
  display: flex !important;
  flex-direction: column !important;
}

.mobile-text-editor-drawer .n-drawer-body {
  flex: 1 !important;
  display: flex !important;
  flex-direction: column !important;
}
</style>

<style scoped>
.native-editor {
  width: 100%;
  min-height: 50dvh;
  /* 预留大约 60px 给抽屉的头部，防止在 90dvh 时被遮挡底部且保证出现原生滚轮 */
  max-height: calc(90dvh - 60px);
  padding: 16px 20px;
  box-sizing: border-box;

  background: transparent;
  border: none;
  outline: none;
  resize: none;

  color: var(--spark-text, inherit);
  font-size: 15px;
  line-height: 1.75;
  font-family: inherit;
  caret-color: var(--spark-primary, #5d9e6c);
  -webkit-overflow-scrolling: touch;
  
  /* 当撑满 90dvh 后允许内部滚动 */
  overflow-y: auto;
}

.native-editor::placeholder {
  color: var(--spark-text-muted, rgba(128, 128, 128, 0.7));
}
</style>
