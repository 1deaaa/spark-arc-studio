<template>
  <div class="effects-editor">
    <!-- 模式切换 -->
    <div class="ee-header">
      <SparkSegment
        v-model="mode"
        :options="[{value:'visual',label:'可视化'},{value:'json',label:'JSON 源码'}]"
        size="small"
      />
    </div>

    <!-- 可视化模式 -->
    <div v-if="mode === 'visual'" class="ee-visual">
      <!-- 空状态 -->
      <n-text v-if="effects.length === 0" depth="3" class="ee-hint">
        场景完成后无状态写入 — 不影响任何游戏变量
      </n-text>

      <!-- 效果行列表 -->
      <div v-else class="ee-rows">
        <div v-for="(effect, idx) in effects" :key="idx" class="ee-row">
          <n-select
            v-model:value="effect.op"
            :options="opOptions"
            size="small"
            class="ee-op"
            @update:value="emitChange"
          />
          <n-input
            v-model:value="effect.key"
            placeholder="状态键 (如 npc.venti.met)"
            size="small"
            class="ee-key"
            @input="emitChange"
          />
          <n-input
            v-if="needsValue(effect.op)"
            v-model:value="effect.valueStr"
            placeholder="值"
            size="small"
            class="ee-val"
            @input="emitChange"
          />
          <div v-else class="ee-val-placeholder" />
          <n-button
            quaternary
            circle
            size="small"
            type="error"
            style="flex-shrink:0"
            @click="removeEffect(idx)"
          >
            <template #icon><n-icon :component="CloseOutline" /></template>
          </n-button>
        </div>
      </div>

      <n-button dashed block size="small" @click="addEffect" style="margin-top:6px">
        <template #icon><n-icon :component="AddOutline" /></template>
        添加状态写入
      </n-button>
    </div>

    <!-- JSON 源码模式 -->
    <n-input
      v-else
      v-model:value="jsonText"
      type="textarea"
      :autosize="{ minRows: 4, maxRows: 10 }"
      placeholder='[{"op":"set","key":"npc.venti.met","value":true}]'
      class="ee-json"
      @blur="onJsonBlur"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, watch } from 'vue';
import {
  NInput, NSelect, NButton, NIcon, NText,
} from 'naive-ui';
import SparkSegment from '../share/SparkSegment.vue';
import { AddOutline, CloseOutline } from '@vicons/ionicons5';

/**
 * 效果行的内部表示（场景完成后的状态写入）。
 *
 * op 说明：
 * - set         → 设置变量为指定值
 * - unset       → 删除变量（重置为 null）
 * - add         → 数值累加
 * - mark_played → 标记此键为已播放/true（等价于 set key true）
 * - unlock      → 解锁某个区域/功能（等价于 set key true）
 */
interface EffectRow {
  op: string;
  key: string;
  valueStr: string; // 始终以字符串编辑，emit 时自动推断类型
}

const props = defineProps<{
  /** 对应 SceneData.effects：数组格式（op/key/value 对象列表），或 null */
  modelValue: unknown[] | Record<string, unknown> | null | undefined;
}>();

const emit = defineEmits<{
  (e: 'update:modelValue', val: unknown[] | Record<string, unknown> | null): void;
}>();

const mode = ref<'visual' | 'json'>('visual');
const effects = reactive<EffectRow[]>([]);
const jsonText = ref('');

/** op 下拉选项（带说明） */
const opOptions = [
  { label: 'set — 设置变量', value: 'set' },
  { label: 'unset — 删除变量', value: 'unset' },
  { label: 'add — 数值累加', value: 'add' },
  { label: 'mark_played — 标为已播', value: 'mark_played' },
  { label: 'unlock — 解锁', value: 'unlock' },
];

/** set 和 add 需要 value 字段，其他操作不需要 */
function needsValue(op: string) {
  return op === 'set' || op === 'add';
}

/** 从外部 modelValue 同步到内部状态 */
function loadFromValue(val: unknown[] | Record<string, unknown> | null | undefined) {
  if (!val || !Array.isArray(val)) {
    effects.splice(0, effects.length);
    jsonText.value = '';
    return;
  }
  effects.splice(
    0,
    effects.length,
    ...val.map(item => {
      const e = item as Record<string, unknown>;
      return {
        op: String(e.op ?? 'set'),
        key: String(e.key ?? ''),
        valueStr: e.value !== undefined ? String(e.value) : '',
      };
    }),
  );
  jsonText.value = JSON.stringify(val, null, 2);
}

watch(() => props.modelValue, val => loadFromValue(val), { immediate: true, deep: true });

/** 将效果行转为输出数组 */
function toValue(): unknown[] | null {
  if (effects.length === 0) return null;
  return effects.map(e => {
    const item: Record<string, unknown> = { op: e.op, key: e.key };
    if (needsValue(e.op)) {
      let value: unknown = e.valueStr;
      if (e.valueStr === 'true') value = true;
      else if (e.valueStr === 'false') value = false;
      else if (e.valueStr !== '' && !isNaN(Number(e.valueStr))) value = Number(e.valueStr);
      item.value = value;
    }
    return item;
  });
}

function emitChange() {
  if (mode.value !== 'visual') return;
  const val = toValue();
  emit('update:modelValue', val);
  jsonText.value = val ? JSON.stringify(val, null, 2) : '';
}

function addEffect() {
  effects.push({ op: 'set', key: '', valueStr: '' });
  emitChange();
}

function removeEffect(idx: number) {
  effects.splice(idx, 1);
  emitChange();
}

function onJsonBlur() {
  const raw = jsonText.value.trim();
  if (!raw) {
    emit('update:modelValue', null);
    return;
  }
  try {
    const parsed = JSON.parse(raw) as unknown[];
    emit('update:modelValue', parsed);
    loadFromValue(parsed);
  } catch {
    // 格式错误 - 不清空，等用户修正
  }
}
</script>

<style scoped>
.effects-editor {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.ee-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}
.ee-visual {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.ee-segment {
  flex-wrap: wrap;
}
.ee-rows {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.ee-row {
  display: grid;
  grid-template-columns: 150px minmax(0, 2fr) minmax(0, 1.2fr) auto;
  align-items: center;
  gap: 8px;
  padding: 10px;
  border: 1px solid color-mix(in srgb, var(--spark-border), transparent 8%);
  border-radius: 12px;
  background: color-mix(in srgb, var(--spark-panel-bg), var(--spark-primary) 3%);
}
.ee-op { width: 150px; flex-shrink: 0; }
.ee-key { min-width: 0; }
.ee-val { min-width: 0; }
.ee-val-placeholder { min-width: 0; }
.ee-hint {
  font-size: 12px;
  padding: 2px 0;
}
.ee-json {
  font-family: monospace;
  font-size: 12px;
}

@media (max-width: 720px) {
  .ee-row {
    grid-template-columns: 1fr;
  }

  .ee-op {
    width: 100%;
  }
}
</style>
