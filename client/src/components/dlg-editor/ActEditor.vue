<template>
  <div class="act-editor">
    <!-- 顶部说明 -->
    <n-text depth="3" style="font-size: var(--spark-fs-2xs); display: block; margin-bottom: 10px; line-height: 1.6;">
      act 在对话节点执行时调用宿主函数（如播 BGM / 切镜头），不写入剧情状态。<br />
      写剧情状态请使用场景的「状态写入 (effects)」字段。
    </n-text>

    <!-- 模式切换 -->
    <div class="ae-header">
      <SparkSegment
        :model-value="mode"
        :options="[{value:'visual',label:'可视化'},{value:'json',label:'JSON 源码'}]"
        size="small"
        @update:model-value="v => v === 'json' ? switchToJson() : mode = v"
      />
      <n-tag v-if="parseError" type="error" size="small" style="margin-left: 8px;">格式错误</n-tag>
    </div>

    <!-- 可视化模式 -->
    <div v-if="mode === 'visual'" class="ae-visual">
      <!-- 空状态 -->
      <n-text v-if="entries.length === 0" depth="3" class="ae-hint">
        无行为指令 — 节点执行时不触发任何宿主回调
      </n-text>

      <!-- 条目列表 -->
      <div v-else class="ae-rows">
        <div v-for="(entry, idx) in entries" :key="idx" class="ae-row">
          <!-- 行为类型选择（支持自定义 tag） -->
          <n-select
            v-model:value="entry.key"
            :options="keyOptions"
            :consistent-menu-width="false"
            filterable
            tag
            size="small"
            class="ae-key"
            placeholder="行为类型"
            @update:value="emitChange"
          />
          <span class="ae-colon">:</span>
          <!-- 值输入 -->
          <n-input
            v-model:value="entry.value"
            size="small"
            class="ae-val"
            :placeholder="getValuePlaceholder(entry.key)"
            @input="emitChange"
          />
          <!-- 删除按钮 -->
          <n-button
            quaternary
            circle
            size="small"
            type="error"
            style="flex-shrink: 0;"
            @click="removeEntry(idx)"
          >
            <template #icon><n-icon :component="X" /></template>
          </n-button>
        </div>
      </div>

      <!-- 添加按钮 -->
      <n-button dashed block size="small" @click="addEntry" style="margin-top: 8px;">
        <template #icon><n-icon :component="Plus" /></template>
        添加行为指令
      </n-button>
    </div>

    <!-- JSON 源码模式 -->
    <template v-else>
      <n-input
        v-model:value="jsonText"
        type="textarea"
        :autosize="{ minRows: 4, maxRows: 10 }"
        :status="parseError ? 'error' : undefined"
        placeholder='{"bg":"school_road","bgm":"theme_sad","sound":"rain,wind"}'
        class="ae-json"
        @blur="onJsonBlur"
      />
      <n-text v-if="parseError" depth="3" type="error" style="font-size: var(--spark-fs-2xs); margin-top: 4px; display: block;">
        JSON 格式有误，请检查后手动修复
      </n-text>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, watch, computed } from 'vue';
import { NInput, NSelect, NButton, NIcon, NText, NTag } from 'naive-ui';
import SparkSegment from '../share/SparkSegment.vue';
import { Plus, X } from '@lucide/vue';
import { storeToRefs } from 'pinia';
import { useActionBindingStore } from '@/components/stores/actionBindingStore';

// 行为值类型（与解析器保持一致）
type ActValue = string | string[];
type ActDict = Record<string, ActValue>;

const props = defineProps<{
  modelValue: ActDict | null | undefined;
}>();

const emit = defineEmits<{
  'update:modelValue': [val: ActDict | null];
}>();

// 条目结构（内部用扁平字符串，逗号分隔表示数组）
interface ActEntry {
  key: string;
  value: string;
}

const entries = reactive<ActEntry[]>([]);
const mode = ref<'visual' | 'json'>('visual');
const jsonText = ref('');
const parseError = ref(false);

// ──────────────────────────────────────────
// 从 actionBindingStore 动态读取行为类型预设
// ──────────────────────────────────────────
const actionBindingStore = useActionBindingStore();
const { actionBindings } = storeToRefs(actionBindingStore);

/**
 * 下拉选项：从 store 中的 actionBindings 动态构建。
 * store 未加载时返回空数组，n-select 设置了 tag=true，
 * 用户仍可手动输入自定义 act_name 作为 fallback。
 */
const keyOptions = computed(() => {
  return actionBindings.value
    .filter(b => b.act_name.trim())
    .map(b => ({
      label: b.act_description
        ? `${b.act_name} — ${b.act_description}`
        : b.act_name,
      value: b.act_name,
    }));
});

/**
 * 根据 act_name 在 store 中查找对应的参数提示。
 * 若绑定中有 act_args，则将 key 列表作为占位提示；否则回退到通用提示。
 */
function getValuePlaceholder(key: string): string {
  const binding = actionBindingStore.actionBindingMap[key];
  if (binding?.act_args && Object.keys(binding.act_args).length > 0) {
    return '参数：' + Object.keys(binding.act_args).join(', ');
  }
  if (binding?.act_description) {
    return binding.act_description;
  }
  return '参数值（多个用逗号分隔）';
}

/**
 * 根据 act_name 获取行为描述提示文本（用于悬浮说明等扩展场景）。
 */
function getKeyHint(key: string): string {
  return actionBindingStore.actionBindingMap[key]?.act_description ?? '';
}

// ──────────────────────────────────────────
// 工具函数：ActDict ↔ entries
// ──────────────────────────────────────────
function dictToEntries(dict: ActDict | null | undefined): ActEntry[] {
  if (!dict) return [];
  return Object.entries(dict).map(([key, val]) => ({
    key,
    value: Array.isArray(val) ? val.join(', ') : String(val ?? ''),
  }));
}

function entriesToDict(list: ActEntry[]): ActDict | null {
  const result: ActDict = {};
  for (const { key, value } of list) {
    if (!key.trim()) continue;
    const trimmed = value.trim();
    // 含逗号则转为数组（与解析器逻辑一致）
    result[key.trim()] = trimmed.includes(',') ? trimmed.split(',').map(s => s.trim()).filter(Boolean) : trimmed;
  }
  return Object.keys(result).length > 0 ? result : null;
}

function dictToJson(dict: ActDict | null | undefined): string {
  if (!dict || Object.keys(dict).length === 0) return '';
  // 将数组值还原为逗号字符串，方便阅读
  const simplified: Record<string, string> = {};
  for (const [k, v] of Object.entries(dict)) {
    simplified[k] = Array.isArray(v) ? v.join(', ') : String(v ?? '');
  }
  return JSON.stringify(simplified, null, 2);
}

function jsonToDict(text: string): ActDict | null {
  const trimmed = text.trim();
  if (!trimmed || trimmed === '{}') return null;
  const raw = JSON.parse(trimmed) as Record<string, unknown>;
  const result: ActDict = {};
  for (const [k, v] of Object.entries(raw)) {
    if (typeof v === 'string') {
      result[k] = v.includes(',') ? v.split(',').map(s => s.trim()).filter(Boolean) : v;
    } else if (Array.isArray(v)) {
      result[k] = v.map(String);
    } else {
      result[k] = String(v ?? '');
    }
  }
  return Object.keys(result).length > 0 ? result : null;
}

// ──────────────────────────────────────────
// 监听 props，同步到内部状态
// ──────────────────────────────────────────
watch(
  () => props.modelValue,
  (newVal) => {
    // 重建 entries
    entries.splice(0, entries.length, ...dictToEntries(newVal));
    // 仅在 json 模式下同步 jsonText（避免抢占用户编辑中的内容）
    if (mode.value === 'json') {
      jsonText.value = dictToJson(newVal);
    }
    parseError.value = false;
  },
  { immediate: true }
);

// ──────────────────────────────────────────
// 切换到 json 模式时同步当前 entries → jsonText
// ──────────────────────────────────────────
function switchToJson() {
  jsonText.value = dictToJson(entriesToDict(entries));
  mode.value = 'json';
  parseError.value = false;
}

// ──────────────────────────────────────────
// 操作
// ──────────────────────────────────────────
function addEntry() {
  // 默认使用 store 中第一个 act_name，未加载时留空（用户可自行输入）
  const defaultKey = actionBindings.value[0]?.act_name ?? '';
  entries.push({ key: defaultKey, value: '' });
}

function removeEntry(idx: number) {
  entries.splice(idx, 1);
  emitChange();
}

function emitChange() {
  emit('update:modelValue', entriesToDict(entries));
}

function onJsonBlur() {
  try {
    const dict = jsonToDict(jsonText.value);
    parseError.value = false;
    // 同步回 entries（方便切换回可视化时有数据）
    entries.splice(0, entries.length, ...dictToEntries(dict));
    emit('update:modelValue', dict);
  } catch {
    parseError.value = true;
  }
}
</script>

<style scoped>
.act-editor {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.ae-header {
  display: flex;
  align-items: center;
  margin-bottom: 10px;
}

.ae-visual {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.ae-hint {
  font-size: var(--spark-fs-xs);
  display: block;
  padding: 8px 0 4px;
}

.ae-rows {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 2px;
}

.ae-row {
  display: flex;
  align-items: center;
  gap: 6px;
  background: var(--n-color-embedded, rgba(128,128,128,.05));
  border-radius: 6px;
  padding: 6px 8px;
  border: 1px solid var(--n-border-color, rgba(128,128,128,.15));
}

.ae-key {
  width: 170px;
  flex-shrink: 0;
}

.ae-colon {
  color: var(--n-text-color-3, #aaa);
  font-size: var(--spark-fs-base);
  flex-shrink: 0;
  font-weight: 600;
}

.ae-val {
  flex: 1;
  min-width: 0;
}

.ae-json {
  font-family: 'Consolas', 'Courier New', monospace;
  font-size: var(--spark-fs-xs);
}
</style>
