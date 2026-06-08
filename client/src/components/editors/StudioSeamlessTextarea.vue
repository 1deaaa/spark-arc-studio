<template>
  <div class="studio-seamless-textarea" :class="{ 'is-disabled': disabled }">
    <n-input
      :value="value"
      type="textarea"
      :autosize="autosize"
      :placeholder="placeholder"
      :disabled="disabled"
      :maxlength="maxlength"
      :show-count="showCount"
      :input-props="{ spellcheck: false }"
      class="studio-seamless-textarea__input"
      @update:value="handleUpdateValue"
      @focus="(event) => emit('focus', event)"
      @blur="(event) => emit('blur', event)"
    />
  </div>
</template>

<script setup lang="ts">
import { NInput } from 'naive-ui';

const props = defineProps({
  value: { type: String, default: '' },
  autosize: { type: [Boolean, Object], default: () => ({ minRows: 4, maxRows: 10 }) },
  placeholder: { type: String, default: '' },
  disabled: { type: Boolean, default: false },
  maxlength: { type: Number, default: undefined },
  showCount: { type: Boolean, default: false },
});

const emit = defineEmits(['update:value', 'input', 'focus', 'blur']);

function handleUpdateValue(value: string) {
  emit('update:value', value);
  emit('input', value);
}
</script>

<style scoped>
.studio-seamless-textarea {
  width: 100%;
}

.studio-seamless-textarea.is-disabled {
  opacity: 0.7;
}

.studio-seamless-textarea :deep(.n-input),
.studio-seamless-textarea :deep(.n-input-wrapper),
.studio-seamless-textarea :deep(.n-input__textarea),
.studio-seamless-textarea :deep(.n-input__state-border),
.studio-seamless-textarea :deep(.n-input__border) {
  width: 100% !important;
  background: transparent !important;
  box-shadow: none !important;
}

.studio-seamless-textarea :deep(.n-input) {
  display: block;
  width: 100%;
  margin: 0 !important;
  border-radius: 0 !important;
  background: var(--n-color, var(--spark-editor-surface)) !important;
  transition: box-shadow 0.18s ease, background-color 0.18s ease;
}

.studio-seamless-textarea :deep(.n-input.n-input--focus) {
  box-shadow:
    var(--n-box-shadow-focus, inset 0 0 0 1px var(--spark-primary)),
    0 0 0 1px color-mix(in srgb, var(--spark-primary), transparent 38%) !important;
  background: var(--n-color, var(--spark-editor-surface)) !important;
}

.studio-seamless-textarea :deep(.n-input-wrapper),
.studio-seamless-textarea :deep(.n-input__state-border),
.studio-seamless-textarea :deep(.n-input__border) {
  border: none !important;
  border-radius: 0 !important;
  padding: 0 !important;
}

.studio-seamless-textarea :deep(.n-input__textarea-el),
.studio-seamless-textarea :deep(.n-input__textarea-mirror) {
  padding: 10px 8px !important;
  margin: 0 !important;
  border: 0 !important;
  box-sizing: border-box !important;
  background: transparent !important;
  color: var(--spark-text);
  font-family: inherit;
  font-size: var(--spark-fs-base);
  font-weight: 400;
  line-height: 1.75;
  letter-spacing: normal;
  white-space: pre-wrap;
  word-break: break-word;
}

.studio-seamless-textarea :deep(.n-input__textarea-el) {
  caret-color: var(--spark-primary);
}

.studio-seamless-textarea :deep(.n-input__textarea-el::placeholder) {
  color: transparent;
}

.studio-seamless-textarea :deep(.n-input__placeholder) {
  padding: 10px 8px !important;
  font-family: inherit;
  font-size: var(--spark-fs-base);
  font-weight: 400;
  line-height: 1.75;
  color: var(--spark-text-muted);
  opacity: 0.82;
  box-sizing: border-box !important;
  white-space: pre-wrap;
  word-break: break-word;
}
</style>
