<template>
  <div class="mobile-expandable-textarea">
    <div class="relative-input-container">
      <n-input
        :value="inputValue"
        type="textarea"
        :autosize="autosize"
        :placeholder="placeholder"
        :class="['custom-textarea', customClass]"
        :maxlength="maxlength"
        :show-count="showCount"
        @update:value="handleInputChange"
      />
      
      <n-button 
        class="expand-btn" 
        quaternary 
        circle 
        size="small" 
        @click="openEditor"
      >
        <n-icon :component="ExpandOutline" />
      </n-button>
    </div>

    <!-- 弹窗部分 -->
    <MobileTextEditor 
      v-model:show="showEditor"
      :title="title"
      :placeholder="placeholder"
      v-model:value="editorValue"
      @confirm="onEditorConfirm"
    />
  </div>
</template>

<script setup>
import { ref, watch } from 'vue';
import { NInput, NButton, NIcon } from 'naive-ui';
import { ExpandOutline } from '@vicons/ionicons5';
import MobileTextEditor from './MobileTextEditor.vue';

const props = defineProps({
  value: { type: String, default: '' },
  title: { type: String, default: '大文本编辑' }, // 抽屉头部标题
  placeholder: { type: String, default: '请输入内容...' },
  autosize: { type: [Boolean, Object], default: () => ({ minRows: 2, maxRows: 6 }) },
  customClass: { type: String, default: '' }, // 供外部挂自定义类名如 desc-input
  maxlength: { type: Number, default: undefined },
  showCount: { type: Boolean, default: false }
});

const emit = defineEmits(['update:value']);

// 本地数据绑定层
const inputValue = ref(props.value);
watch(() => props.value, (newVal) => {
  if (inputValue.value !== newVal) {
    inputValue.value = newVal;
  }
});

function handleInputChange(val) {
  inputValue.value = val;
  emit('update:value', val);
}

// 抽屉管理
const showEditor = ref(false);
const editorValue = ref('');

function openEditor() {
  editorValue.value = inputValue.value;
  showEditor.value = true;
}

function onEditorConfirm(val) {
  inputValue.value = val;
  // 此处已通过 watch inputValue 传递到外部 update:value
}
</script>

<style scoped>
.mobile-expandable-textarea {
  width: 100%;
}

.relative-input-container {
  position: relative;
  width: 100%;
}

.expand-btn {
  position: absolute;
  right: 8px;
  bottom: 8px;
  z-index: 2;
  color: var(--spark-primary);
  background: var(--spark-panel-bg);
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
  transition: all 0.2s ease;
}

.expand-btn:active {
  transform: scale(0.9);
}

:deep(.n-input-wrapper),
:deep(.n-input__state-border),
:deep(.n-input__border) {
  height: 100% !important;
}

:deep(.n-input__textarea-el) {
  height: 100% !important;
  overflow-y: auto !important;
}
</style>
