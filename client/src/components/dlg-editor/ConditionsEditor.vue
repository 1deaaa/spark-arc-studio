<template>
  <div class="conditions-editor">
    <!-- 模式切换 -->
    <div class="ce-header">
      <n-button-group size="small" class="spark-segment ce-segment">
        <n-button :type="mode === 'visual' ? 'primary' : 'default'" @click="mode = 'visual'">可视化</n-button>
        <n-button :type="mode === 'json' ? 'primary' : 'default'" @click="mode = 'json'">JSON 源码</n-button>
      </n-button-group>
      <n-tag v-if="parseError" type="error" size="small" style="margin-left:8px">格式错误</n-tag>
    </div>

    <!-- 可视化模式 -->
    <div v-if="mode === 'visual'" class="ce-visual">
      <!-- 逻辑类型 -->
      <div class="ce-logic-row">
        <n-text depth="3" class="ce-logic-label">触发逻辑：</n-text>
        <n-button-group size="small" class="spark-segment ce-segment">
          <n-button :type="logicType === 'all' ? 'primary' : 'default'" @click="logicType = 'all'; emitChange()">全部满足 (AND)</n-button>
          <n-button :type="logicType === 'any' ? 'primary' : 'default'" @click="logicType = 'any'; emitChange()">任一满足 (OR)</n-button>
        </n-button-group>
      </div>

      <!-- 条件为空提示 -->
      <n-text v-if="conditions.length === 0" depth="3" class="ce-hint">
        无条件限制 — 场景始终可见/可触发
      </n-text>

      <!-- 条件行列表 -->
      <div v-else class="ce-rows">
        <div v-for="(cond, idx) in conditions" :key="idx" class="ce-row">
          <n-input
            v-model:value="cond.varName"
            placeholder="变量名 (如 quest.main.step)"
            size="small"
            class="ce-var"
            @input="emitChange"
          />
          <n-select
            v-model:value="cond.op"
            :options="opOptions"
            size="small"
            class="ce-op"
            @update:value="emitChange"
          />
          <n-input
            v-model:value="cond.valueStr"
            placeholder="值"
            size="small"
            class="ce-val"
            @input="emitChange"
          />
          <n-button
            quaternary
            circle
            size="small"
            type="error"
            style="flex-shrink:0"
            @click="removeCondition(idx)"
          >
            <template #icon><n-icon :component="CloseOutline" /></template>
          </n-button>
        </div>
      </div>

      <n-button dashed block size="small" @click="addCondition" style="margin-top:6px">
        <template #icon><n-icon :component="AddOutline" /></template>
        添加条件
      </n-button>
    </div>

    <!-- JSON 源码模式 -->
    <n-input
      v-else
      v-model:value="jsonText"
      type="textarea"
      :autosize="{ minRows: 4, maxRows: 10 }"
      :status="parseError ? 'error' : undefined"
      placeholder='{"all":[{"var":"quest.main.step","op":"==","value":3}]}'
      class="ce-json"
      @blur="onJsonBlur"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, watch } from 'vue';
import {
  NInput, NSelect, NButton, NButtonGroup,
  NIcon, NText, NTag,
} from 'naive-ui';
import { AddOutline, CloseOutline } from '@vicons/ionicons5';

/** 条件行的内部表示（仅在可视化模式使用） */
interface ConditionRow {
  varName: string;
  op: string;
  valueStr: string; // 始终以字符串编辑，emit 时自动推断类型
}

const props = defineProps<{
  /** conditions 可以是 all/any 对象、旧式 KV 对象、数组（旧式格式），或 null */
  modelValue: Record<string, unknown> | Array<unknown> | null | undefined;
}>();

const emit = defineEmits<{
  (e: 'update:modelValue', val: Record<string, unknown> | Array<unknown> | null): void;
}>();

const mode = ref<'visual' | 'json'>('visual');
const logicType = ref<'all' | 'any'>('all');
const conditions = reactive<ConditionRow[]>([]);
const jsonText = ref('');
const parseError = ref(false);

const opOptions = [
  { label: '==', value: '==' },
  { label: '!=', value: '!=' },
  { label: '>', value: '>' },
  { label: '>=', value: '>=' },
  { label: '<', value: '<' },
  { label: '<=', value: '<=' },
];

/** 从外部 modelValue 同步到内部状态 */
function loadFromValue(val: Record<string, unknown> | Array<unknown> | null | undefined) {
  if (!val || typeof val !== 'object') {
    conditions.splice(0, conditions.length);
    jsonText.value = '';
    return;
  }
  jsonText.value = JSON.stringify(val, null, 2);

  // 检测 all / any 格式
  const key = 'all' in val ? 'all' : 'any' in val ? 'any' : null;
  if (key) {
    logicType.value = key as 'all' | 'any';
    const list = (val[key] as unknown[]) ?? [];
    conditions.splice(
      0,
      conditions.length,
      ...list.map(item => {
        const c = item as Record<string, unknown>;
        return {
          varName: String(c.var ?? ''),
          op: String(c.op ?? '=='),
          valueStr: c.value !== undefined ? String(c.value) : '',
        };
      }),
    );
  } else {
    // 旧式 KV 或其他格式 - 无法在可视化模式表示，清空列表
    conditions.splice(0, conditions.length);
  }
}

watch(() => props.modelValue, val => loadFromValue(val), { immediate: true, deep: true });

/** 将条件行转为输出对象 */
function toValue(): Record<string, unknown> | null {
  if (conditions.length === 0) return null;
  const list: Record<string, unknown>[] = conditions.map(c => {
    let value: unknown = c.valueStr;
    if (c.valueStr === 'true') value = true;
    else if (c.valueStr === 'false') value = false;
    else if (c.valueStr !== '' && !isNaN(Number(c.valueStr))) value = Number(c.valueStr);
    return { var: c.varName, op: c.op, value };
  });
  return { [logicType.value]: list };
}

function emitChange() {
  if (mode.value !== 'visual') return;
  const val = toValue();
  emit('update:modelValue', val);
  jsonText.value = val ? JSON.stringify(val, null, 2) : '';
}

function addCondition() {
  conditions.push({ varName: '', op: '==', valueStr: '' });
  emitChange();
}

function removeCondition(idx: number) {
  conditions.splice(idx, 1);
  emitChange();
}

function onJsonBlur() {
  const raw = jsonText.value.trim();
  if (!raw) {
    parseError.value = false;
    emit('update:modelValue', null);
    return;
  }
  try {
    const parsed = JSON.parse(raw) as Record<string, unknown> | Array<unknown>;
    parseError.value = false;
    emit('update:modelValue', parsed);
    loadFromValue(parsed);
  } catch {
    parseError.value = true;
  }
}
</script>

<style scoped>
.conditions-editor {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.ce-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}
.ce-visual {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.ce-logic-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 6px;
}
.ce-logic-label {
  font-size: 12px;
  white-space: nowrap;
}
.ce-segment {
  flex-wrap: wrap;
}
.ce-rows {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.ce-row {
  display: grid;
  grid-template-columns: minmax(0, 2fr) 92px minmax(0, 1.3fr) auto;
  align-items: center;
  gap: 8px;
  padding: 10px;
  border: 1px solid color-mix(in srgb, var(--spark-border), transparent 8%);
  border-radius: 12px;
  background: color-mix(in srgb, var(--spark-panel-bg), var(--spark-primary) 3%);
}
.ce-var { min-width: 0; }
.ce-op { width: 92px; flex-shrink: 0; }
.ce-val { min-width: 0; }
.ce-hint {
  font-size: 12px;
  padding: 2px 0;
}
.ce-json {
  font-family: monospace;
  font-size: 12px;
}

@media (max-width: 720px) {
  .ce-row {
    grid-template-columns: 1fr;
  }

  .ce-op {
    width: 100%;
  }
}
</style>
