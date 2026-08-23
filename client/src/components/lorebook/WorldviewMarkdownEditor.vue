<template>
  <div class="worldview-workbench">
    <!-- 顶部工作台状态与主操作栏 -->
    <header class="workbench-toolbar">
      <div class="workbench-summary">
        <div class="workbench-brand-icon">
          <n-icon :component="Sparkles" />
        </div>
        <div class="workbench-title-group">
          <span class="workbench-title">{{ t('components.lorebookEditor.worldviewWorkbench') }}</span>
          <span class="section-count-badge">{{ t('components.lorebookEditor.sectionCount', { count: visibleSections.length }) }}</span>
        </div>
      </div>
      <div class="workbench-actions">
        <div class="save-state-pill" :class="`is-${saveStatus}`">
          <span class="save-state-dot" />
          <span class="save-state-text">{{ saveStatusLabel }}</span>
        </div>
        <n-dropdown :options="templateOptions" trigger="click" @select="addTemplateSection">
          <n-button size="small" type="primary" class="add-module-btn">
            <template #icon><n-icon :component="Plus" /></template>
            {{ t('components.lorebookEditor.addModule') }}
          </n-button>
        </n-dropdown>
      </div>
    </header>

    <div
      class="workbench-main"
      :style="{ gridTemplateColumns: `${railWidth}px 1px minmax(0, 1fr)` }"
    >
      <!-- 左侧世界观架构导航轨 (Atlas Navigator) -->
      <nav
        class="section-rail"
        :aria-label="t('components.lorebookEditor.sectionNavigation')"
      >
        <div class="section-rail-header">
          <span class="rail-title">设定模块</span>
          <span class="rail-hint">SECTIONS</span>
        </div>
        <div class="section-rail-list">
          <button
            v-for="section in visibleSections"
            :key="`${section.index}-${section.title}`"
            type="button"
            class="section-nav-item"
            :class="{ active: section.index === activeSectionIndex }"
            @click="activeSectionIndex = section.index"
          >
            <div class="section-nav-accent-bar" />
            <div class="section-nav-index-box">
              <span class="section-nav-index-num">{{ formatIndex(section.index + 1) }}</span>
            </div>
            <div class="section-nav-copy">
              <strong class="section-nav-title">{{ section.title || t('components.lorebookEditor.legacySection') }}</strong>
              <div class="section-nav-meta">
                <span class="section-nav-tag">{{ sectionSummary(section) }}</span>
              </div>
            </div>
          </button>
        </div>
      </nav>

      <!-- 极简 1px 拖拽分割线 (Slim Resizer Divider) -->
      <div
        class="workbench-resizer"
        :class="{ 'is-active': isResizingRail }"
        title="拖拽调整侧栏宽度，双击恢复默认"
        @mousedown="onResizerMouseDown"
        @dblclick="onResizerDblClick"
      />

      <!-- 右侧工作台画布与属性视窗 (Inspector & Canvas) -->
      <section v-if="activeSection" class="section-editor">
        <!-- 模块头部：无缝大标题与集成操作胶囊 -->
        <div class="section-editor-header">
          <div class="section-heading-copy">
            <div class="section-title-wrap">
              <input
                v-if="!activeSection.legacy"
                :value="activeSection.title"
                class="section-title-hero-input"
                :placeholder="t('components.lorebookEditor.sectionTitlePlaceholder')"
                @input="e => updateSectionTitle((e.target as HTMLInputElement).value)"
              />
              <span v-else class="section-title-hero-text">{{ t('components.lorebookEditor.legacySection') }}</span>
            </div>
            <p class="section-hint-text">
              <span class="hint-meta-dot" />
              <span>{{ activeSectionMetaText }}</span>
            </p>
          </div>

          <div v-if="!activeSection.legacy" class="section-header-actions-capsule">
            <n-tooltip trigger="hover">
              <template #trigger>
                <button
                  type="button"
                  class="action-capsule-btn"
                  :disabled="!canMoveUp"
                  @click="moveSection(-1)"
                >
                  <n-icon :component="ArrowUp" />
                </button>
              </template>
              {{ t('components.lorebookEditor.moveSectionUp') }}
            </n-tooltip>
            <n-tooltip trigger="hover">
              <template #trigger>
                <button
                  type="button"
                  class="action-capsule-btn"
                  :disabled="!canMoveDown"
                  @click="moveSection(1)"
                >
                  <n-icon :component="ArrowDown" />
                </button>
              </template>
              {{ t('components.lorebookEditor.moveSectionDown') }}
            </n-tooltip>
            <div class="action-capsule-divider" />
            <n-popconfirm
              :positive-text="t('common.delete')"
              :negative-text="t('common.cancel')"
              @positive-click="removeSection"
            >
              <template #trigger>
                <button type="button" class="action-capsule-btn is-danger">
                  <n-icon :component="Trash2" />
                </button>
              </template>
              {{ t('components.lorebookEditor.confirmDeleteSection', { title: activeSection.title }) }}
            </n-popconfirm>
          </div>
        </div>

        <!-- 模块内容滚动区 -->
        <div class="section-editor-scroll">
          <!-- 结构化属性卡片流 (Cardified Property Inspector) -->
          <div v-if="activeFields.length" class="field-editor">
            <div class="subsection-heading">
              <div class="subsection-title-wrap">
                <n-icon :component="SlidersHorizontal" class="subsection-icon" />
                <span class="subsection-title">{{ t('components.lorebookEditor.structuredFields') }}</span>
                <span class="subsection-badge">{{ activeFields.length }} 项属性</span>
              </div>
              <small class="subsection-hint">{{ t('components.lorebookEditor.structuredFieldsHint') }}</small>
            </div>

            <div class="property-cards-grid">
              <div
                v-for="field in activeFields"
                :key="field.lineIndex"
                class="field-row property-card"
              >
                <div class="property-card-header">
                  <div class="property-label-pill">
                    <span class="property-label-dot" />
                    <span class="property-label-text">{{ field.label }}</span>
                  </div>
                </div>
                <div class="property-card-body">
                  <n-input
                    :value="field.value"
                    type="textarea"
                    :autosize="{ minRows: 1, maxRows: 6 }"
                    :placeholder="t('components.lorebookEditor.fieldValuePlaceholder')"
                    class="property-input-el"
                    @update:value="value => updateField(field.lineIndex, value)"
                  />
                </div>
              </div>
            </div>
          </div>

          <!-- 深度自由纪事与自由文本区 (Lore Chronicle / Prose Area) -->
          <div class="prose-editor">
            <div class="subsection-heading prose-heading">
              <div class="subsection-title-wrap">
                <n-icon :component="ScrollText" class="subsection-icon" />
                <span class="subsection-title">{{ activeFields.length ? t('components.lorebookEditor.additionalNotes') : t('components.lorebookEditor.sectionContent') }}</span>
              </div>
              <n-button v-if="!activeSection.legacy" size="tiny" secondary type="primary" class="add-field-btn" @click="appendField">
                <template #icon><n-icon :component="ListPlus" /></template>
                {{ t('components.lorebookEditor.addField') }}
              </n-button>
            </div>
            <div class="prose-card-wrap">
              <StudioSeamlessTextarea
                :value="activeProse"
                :autosize="{ minRows: 10, maxRows: 40 }"
                :placeholder="t('components.lorebookEditor.sectionContentPlaceholder')"
                class="section-prose-input"
                @update:value="updateSectionProse"
              />
            </div>
          </div>
        </div>
      </section>
    </div>

    <!-- 底部原始 Markdown 专家视图 -->
    <n-collapse v-model:expanded-names="rawExpanded" class="raw-source-collapse">
      <n-collapse-item name="raw-source">
        <template #header>
          <div class="raw-source-title">
            <n-icon :component="FileText" />
            <span>{{ t('components.lorebookEditor.rawMarkdown') }}</span>
            <small>{{ t('components.lorebookEditor.rawMarkdownHint') }}</small>
          </div>
        </template>
        <n-input
          :value="modelValue"
          type="textarea"
          :autosize="{ minRows: 7, maxRows: 18 }"
          :placeholder="t('components.lorebookEditor.worldviewPlaceholder')"
          class="raw-markdown-input"
          @update:value="emitValue"
        />
      </n-collapse-item>
    </n-collapse>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import {
  NButton,
  NCollapse,
  NCollapseItem,
  NDropdown,
  NIcon,
  NInput,
  NPopconfirm,
  NTooltip,
  type DropdownOption,
} from 'naive-ui';
import {
  ArrowDown,
  ArrowUp,
  FileText,
  ListPlus,
  Plus,
  ScrollText,
  SlidersHorizontal,
  Sparkles,
  Trash2,
} from '@lucide/vue';
import StudioSeamlessTextarea from '../editors/StudioSeamlessTextarea.vue';
import {
  appendWorldviewSection,
  moveWorldviewSection,
  parseWorldviewFields,
  parseWorldviewMarkdown,
  removeWorldviewSection,
  updateWorldviewField,
  updateWorldviewSection,
  type WorldviewSection,
} from '@/utils/worldviewMarkdown';

type SaveStatus = 'idle' | 'dirty' | 'saving' | 'saved' | 'error';
type TemplateKey = 'blank' | 'overview' | 'setting' | 'power' | 'economy' | 'society' | 'factions' | 'rules' | 'terms';

const RAIL_WIDTH_STORAGE_KEY = 'spark_worldview_rail_width_v1';
const MIN_RAIL_WIDTH = 160;
const MAX_RAIL_WIDTH = 340;
const DEFAULT_RAIL_WIDTH = 220;

const props = withDefaults(defineProps<{
  modelValue?: string;
  saveStatus?: SaveStatus;
}>(), {
  modelValue: '',
  saveStatus: 'idle',
});

const emit = defineEmits<{
  'update:modelValue': [value: string];
  input: [value: string];
}>();

const { t } = useI18n();
const activeSectionIndex = ref(0);
const rawExpanded = ref<Array<string | number>>([]);

const railWidth = ref(DEFAULT_RAIL_WIDTH);
const isResizingRail = ref(false);
let startX = 0;
let startWidth = 0;

function loadRailWidth() {
  try {
    const saved = localStorage.getItem(RAIL_WIDTH_STORAGE_KEY);
    if (saved) {
      const parsed = Number(saved);
      if (!isNaN(parsed) && parsed >= MIN_RAIL_WIDTH && parsed <= MAX_RAIL_WIDTH) {
        railWidth.value = parsed;
      }
    }
  } catch {
    // ignore
  }
}

function persistRailWidth() {
  try {
    localStorage.setItem(RAIL_WIDTH_STORAGE_KEY, String(railWidth.value));
  } catch {
    // ignore
  }
}

function onResizerMouseDown(e: MouseEvent) {
  if (e.button !== 0) return;
  e.preventDefault();
  e.stopPropagation();

  isResizingRail.value = true;
  startX = e.clientX;
  startWidth = railWidth.value;

  window.addEventListener('mousemove', onResizerMouseMove);
  window.addEventListener('mouseup', onResizerMouseUp);
  document.body.style.cursor = 'col-resize';
  document.body.style.userSelect = 'none';
}

function onResizerMouseMove(e: MouseEvent) {
  if (!isResizingRail.value) return;
  const delta = e.clientX - startX;
  const nextWidth = Math.max(MIN_RAIL_WIDTH, Math.min(MAX_RAIL_WIDTH, startWidth + delta));
  railWidth.value = nextWidth;
}

function onResizerMouseUp() {
  if (!isResizingRail.value) return;
  isResizingRail.value = false;
  window.removeEventListener('mousemove', onResizerMouseMove);
  window.removeEventListener('mouseup', onResizerMouseUp);
  document.body.style.cursor = '';
  document.body.style.userSelect = '';
  persistRailWidth();
}

function onResizerDblClick() {
  railWidth.value = DEFAULT_RAIL_WIDTH;
  persistRailWidth();
}

onMounted(() => {
  loadRailWidth();
});

onBeforeUnmount(() => {
  window.removeEventListener('mousemove', onResizerMouseMove);
  window.removeEventListener('mouseup', onResizerMouseUp);
});

const worldviewDocument = computed(() => parseWorldviewMarkdown(props.modelValue));
const visibleSections = computed(() => worldviewDocument.value.sections);
const activeSection = computed(() => visibleSections.value[activeSectionIndex.value] || visibleSections.value[0]);
const movableSectionIndexes = computed(() => visibleSections.value.filter(section => !section.legacy).map(section => section.index));
const movableSectionPosition = computed(() => movableSectionIndexes.value.indexOf(activeSectionIndex.value));
const canMoveUp = computed(() => movableSectionPosition.value > 0);
const canMoveDown = computed(() => (
  movableSectionPosition.value >= 0
  && movableSectionPosition.value < movableSectionIndexes.value.length - 1
));
const activeFields = computed(() => activeSection.value?.legacy
  ? []
  : parseWorldviewFields(activeSection.value?.body || ''));
const activeProse = computed(() => {
  const fieldLines = new Set(activeFields.value.map(field => field.lineIndex));
  return String(activeSection.value?.body || '')
    .split('\n')
    .filter((_, index) => !fieldLines.has(index))
    .join('\n')
    .replace(/^\s+|\s+$/g, '');
});

const templateKeys: TemplateKey[] = ['blank', 'overview', 'setting', 'power', 'economy', 'society', 'factions', 'rules', 'terms'];
const templateOptions = computed<DropdownOption[]>(() => templateKeys.map(key => ({
  key,
  label: t(`components.lorebookEditor.moduleTemplates.${key}.title`),
})));

const saveStatusLabel = computed(() => t(`components.lorebookEditor.saveStates.${props.saveStatus}`));

const activeSectionCharCount = computed(() => {
  return (activeSection.value?.body || '').replace(/\s+/g, '').length;
});

const activeSectionMetaText = computed(() => {
  if (activeSection.value?.legacy) {
    return t('components.lorebookEditor.legacySectionHint');
  }
  const fieldCount = activeFields.value.length;
  const chars = activeSectionCharCount.value;
  const fieldPart = fieldCount ? `${fieldCount} 项结构化属性` : '纯文本正文';
  const charPart = chars ? `共 ${chars} 字` : '暂无详细设定';
  return `${fieldPart} · ${charPart}`;
});

function formatIndex(index: number): string {
  return String(index).padStart(2, '0');
}

watch(visibleSections, sections => {
  if (activeSectionIndex.value >= sections.length) {
    activeSectionIndex.value = Math.max(0, sections.length - 1);
  }
});

function emitValue(value: string) {
  emit('update:modelValue', value);
  emit('input', value);
}

function sectionSummary(section: WorldviewSection): string {
  if (section.legacy) return t('components.lorebookEditor.legacySectionSummary');
  const fields = parseWorldviewFields(section.body);
  if (fields.length) return t('components.lorebookEditor.fieldCount', { count: fields.length });
  const characters = section.body.replace(/\s+/g, '').length;
  return characters
    ? t('components.lorebookEditor.characterCount', { count: characters })
    : t('components.lorebookEditor.emptySection');
}

function updateSectionTitle(title: string) {
  emitValue(updateWorldviewSection(props.modelValue, activeSectionIndex.value, { title }));
}

function updateField(lineIndex: number, value: string) {
  if (!activeSection.value) return;
  const body = updateWorldviewField(activeSection.value.body, lineIndex, { value });
  emitValue(updateWorldviewSection(props.modelValue, activeSectionIndex.value, { body }));
}

function updateSectionProse(prose: string) {
  if (!activeSection.value) return;
  if (activeSection.value.legacy) {
    emitValue(updateWorldviewSection(props.modelValue, activeSectionIndex.value, { body: prose }));
    return;
  }
  const fieldLines = activeFields.value.map(field => `- ${field.label}：${field.value ? ` ${field.value}` : ''}`);
  const body = [...fieldLines, prose.trim()].filter(Boolean).join('\n\n');
  emitValue(updateWorldviewSection(props.modelValue, activeSectionIndex.value, { body }));
}

function appendField() {
  if (!activeSection.value || activeSection.value.legacy) return;
  const nextLabel = t('components.lorebookEditor.newFieldLabel', { count: activeFields.value.length + 1 });
  const body = `${activeSection.value.body.trimEnd()}${activeSection.value.body.trim() ? '\n' : ''}- ${nextLabel}：`;
  emitValue(updateWorldviewSection(props.modelValue, activeSectionIndex.value, { body }));
}

function addTemplateSection(rawKey: string | number) {
  const key = String(rawKey) as TemplateKey;
  const title = t(`components.lorebookEditor.moduleTemplates.${key}.title`);
  const fields = t(`components.lorebookEditor.moduleTemplates.${key}.fields`);
  const body = fields === `components.lorebookEditor.moduleTemplates.${key}.fields` ? '' : fields;
  const next = appendWorldviewSection(props.modelValue, title, body);
  emitValue(next);
  activeSectionIndex.value = parseWorldviewMarkdown(next).sections.length - 1;
}

function moveSection(direction: -1 | 1) {
  const next = moveWorldviewSection(props.modelValue, activeSectionIndex.value, direction);
  if (next === props.modelValue) return;
  emitValue(next);
  activeSectionIndex.value = movableSectionIndexes.value[movableSectionPosition.value + direction] ?? activeSectionIndex.value;
}

function removeSection() {
  const next = removeWorldviewSection(props.modelValue, activeSectionIndex.value);
  emitValue(next);
  activeSectionIndex.value = Math.max(0, activeSectionIndex.value - 1);
}
</script>

<style scoped>
.worldview-workbench {
  display: grid;
  grid-template-rows: auto minmax(0, 1fr) auto;
  width: 100%;
  height: 100%;
  min-height: 0;
  overflow: hidden;
  border: 1px solid var(--spark-border);
  border-radius: var(--spark-radius-sm, 8px);
  background: var(--spark-panel-bg);
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
}

/* ==========================================================================
   顶部工具栏 (Header Toolbar)
   ========================================================================== */
.workbench-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  min-height: 48px;
  padding: 8px 16px;
  border-bottom: 1px solid var(--spark-border);
  background: color-mix(in srgb, var(--spark-panel-bg), var(--spark-bg) 20%);
}

.workbench-summary {
  display: flex;
  align-items: center;
  gap: 10px;
}

.workbench-brand-icon {
  display: grid;
  place-items: center;
  width: 28px;
  height: 28px;
  border-radius: 6px;
  background: color-mix(in srgb, var(--spark-primary) 15%, transparent);
  color: var(--spark-primary);
  font-size: 14px;
}

.workbench-title-group {
  display: flex;
  align-items: center;
  gap: 8px;
}

.workbench-title {
  color: var(--spark-text);
  font-size: var(--spark-fs-sm, 13px);
  font-weight: 700;
  letter-spacing: 0.02em;
}

.section-count-badge {
  display: inline-flex;
  align-items: center;
  padding: 2px 7px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--spark-text-muted) 15%, transparent);
  color: var(--spark-text-muted);
  font-size: var(--spark-fs-3xs, 10px);
  font-weight: 600;
}

.workbench-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.save-state-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 3px 9px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--spark-bg), var(--spark-panel-bg) 60%);
  border: 1px solid var(--spark-border);
  font-size: var(--spark-fs-3xs, 11px);
  font-weight: 500;
  color: var(--spark-text-muted);
}

.save-state-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--spark-text-muted);
  transition: background-color 0.2s ease;
}

.save-state-pill.is-dirty .save-state-dot,
.save-state-pill.is-saving .save-state-dot {
  background: var(--spark-warning, #d99a2b);
  box-shadow: 0 0 6px var(--spark-warning, #d99a2b);
}

.save-state-pill.is-saved .save-state-dot {
  background: var(--spark-success, #2e9b62);
  box-shadow: 0 0 6px var(--spark-success, #2e9b62);
}

.save-state-pill.is-error .save-state-dot {
  background: var(--spark-danger, #d84c4c);
  box-shadow: 0 0 6px var(--spark-danger, #d84c4c);
}

.add-module-btn {
  font-weight: 600;
}

/* ==========================================================================
   主体布局 (Main Workbench Grid)
   ========================================================================== */
.workbench-main {
  display: grid;
  grid-template-columns: max-content minmax(0, 1fr);
  min-height: 0;
  overflow: hidden;
}

/* ==========================================================================
   左侧导航轨 (The Atlas Navigator Rail)
   ========================================================================== */
.section-rail {
  display: flex;
  flex-direction: column;
  min-width: 0;
  width: 100%;
  background: color-mix(in srgb, var(--spark-panel-bg), var(--spark-bg) 35%);
  overflow-y: auto;
  overflow-x: hidden;
}

.section-rail-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px 6px;
}

.rail-title {
  color: var(--spark-text);
  font-size: var(--spark-fs-xs, 12px);
  font-weight: 700;
  letter-spacing: 0.05em;
}

.rail-hint {
  color: var(--spark-text-muted);
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0.1em;
  opacity: 0.6;
}

.section-rail-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 4px 8px 12px;
}

.section-nav-item {
  position: relative;
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  min-height: 50px;
  padding: 8px 10px;
  border: 1px solid transparent;
  border-radius: 8px;
  background: transparent;
  color: var(--spark-text);
  text-align: left;
  font-family: inherit;
  cursor: pointer;
  transition: all 0.18s cubic-bezier(0.16, 1, 0.3, 1);
}

.section-nav-accent-bar {
  position: absolute;
  left: 0;
  top: 10px;
  bottom: 10px;
  width: 3px;
  border-radius: 0 4px 4px 0;
  background: var(--spark-primary);
  opacity: 0;
  transform: scaleY(0.4);
  transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
}

.section-nav-item:hover {
  background: color-mix(in srgb, var(--spark-primary) 6%, transparent);
  border-color: color-mix(in srgb, var(--spark-primary) 15%, transparent);
}

.section-nav-item.active {
  background: color-mix(in srgb, var(--spark-primary) 12%, var(--spark-panel-bg));
  border-color: color-mix(in srgb, var(--spark-primary) 30%, transparent);
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.06);
}

.section-nav-item.active .section-nav-accent-bar {
  opacity: 1;
  transform: scaleY(1);
}

.section-nav-index-box {
  display: grid;
  place-items: center;
  flex-shrink: 0;
  width: 26px;
  height: 26px;
  border-radius: 6px;
  background: color-mix(in srgb, var(--spark-text-muted) 12%, transparent);
  transition: all 0.18s ease;
}

.section-nav-index-num {
  font-family: var(--spark-mono, monospace);
  font-variant-numeric: tabular-nums;
  font-size: 11px;
  font-weight: 700;
  color: var(--spark-text-muted);
  letter-spacing: -0.02em;
  transition: color 0.18s ease;
}

.section-nav-item:hover .section-nav-index-box {
  background: color-mix(in srgb, var(--spark-primary) 15%, transparent);
}

.section-nav-item:hover .section-nav-index-num {
  color: var(--spark-text);
}

.section-nav-item.active .section-nav-index-box {
  background: var(--spark-primary);
  box-shadow: 0 2px 8px color-mix(in srgb, var(--spark-primary) 40%, transparent);
}

.section-nav-item.active .section-nav-index-num {
  color: var(--spark-text-inverse, #090b10);
  font-weight: 800;
}

.section-nav-copy {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
  flex: 1;
}

.section-nav-title {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: var(--spark-fs-xs, 12px);
  font-weight: 650;
  color: var(--spark-text);
}

.section-nav-item.active .section-nav-title {
  font-weight: 750;
}

.section-nav-meta {
  display: flex;
  align-items: center;
}

.section-nav-tag {
  display: inline-block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  padding: 1px 5px;
  border-radius: 4px;
  background: color-mix(in srgb, var(--spark-text-muted) 12%, transparent);
  color: var(--spark-text-muted);
  font-size: var(--spark-fs-3xs, 10px);
  font-weight: 500;
}

.section-nav-item.active .section-nav-tag {
  background: color-mix(in srgb, var(--spark-primary) 18%, transparent);
  color: var(--spark-text);
}

/* ==========================================================================
   极简 1px 拖拽分割线 (Slim Resizer Divider)
   ========================================================================== */
.workbench-resizer {
  position: relative;
  width: 1px;
  height: 100%;
  cursor: col-resize;
  background: var(--spark-border);
  z-index: 10;
  user-select: none;
  transition: background-color 0.18s ease, box-shadow 0.18s ease;
}

.workbench-resizer::before {
  content: '';
  position: absolute;
  top: 0;
  bottom: 0;
  left: -4px;
  right: -4px;
  cursor: col-resize;
}

.workbench-resizer:hover,
.workbench-resizer.is-active {
  background: var(--spark-primary);
  box-shadow: 0 0 6px var(--spark-primary);
}

/* ==========================================================================
   右侧工作台画布 (Inspector & Canvas)
   ========================================================================== */
.section-editor {
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
  background: var(--spark-bg);
}

.section-editor-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  min-height: 64px;
  padding: 12px 20px;
  border-bottom: 1px solid var(--spark-border);
  background: var(--spark-panel-bg);
}

.section-heading-copy {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
  flex: 1;
}

.section-title-wrap {
  display: flex;
  align-items: center;
}

.section-title-hero-input {
  width: 100%;
  max-width: 480px;
  padding: 2px 0;
  border: none;
  border-bottom: 1px solid transparent;
  background: transparent;
  color: var(--spark-text);
  font-family: var(--spark-font, inherit);
  font-size: 18px;
  font-weight: 750;
  outline: none;
  transition: border-color 0.2s ease;
}

.section-title-hero-input:focus {
  border-bottom-color: var(--spark-primary);
}

.section-title-hero-input::placeholder {
  color: var(--spark-text-muted);
  font-weight: 500;
  opacity: 0.6;
}

.section-title-hero-text {
  font-size: 18px;
  font-weight: 750;
  color: var(--spark-text);
}

.section-hint-text {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: 0;
  color: var(--spark-text-muted);
  font-size: var(--spark-fs-xs, 12px);
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.hint-meta-dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--spark-primary);
  flex-shrink: 0;
}

.section-header-actions-capsule {
  display: flex;
  align-items: center;
  padding: 3px 4px;
  border-radius: 8px;
  border: 1px solid var(--spark-border);
  background: color-mix(in srgb, var(--spark-panel-bg), var(--spark-bg) 40%);
  gap: 2px;
  flex-shrink: 0;
}

.action-capsule-btn {
  display: grid;
  place-items: center;
  width: 28px;
  height: 28px;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: var(--spark-text-muted);
  font-size: 14px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.action-capsule-btn:not(:disabled):hover {
  color: var(--spark-text);
  background: color-mix(in srgb, var(--spark-text-muted) 16%, transparent);
}

.action-capsule-btn:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}

.action-capsule-btn.is-danger:not(:disabled):hover {
  color: var(--spark-danger, #ff5555);
  background: color-mix(in srgb, var(--spark-danger, #ff5555) 15%, transparent);
}

.action-capsule-divider {
  width: 1px;
  height: 16px;
  background: var(--spark-border);
  margin: 0 2px;
}

/* ==========================================================================
   内容滚动区与属性卡片 (Inspector Body & Cards)
   ========================================================================== */
.section-editor-scroll {
  flex: 1;
  min-height: 0;
  padding: 16px 20px 24px;
  overflow-y: auto;
}

.field-editor,
.prose-editor {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.field-editor + .prose-editor {
  margin-top: 20px;
  padding-top: 20px;
  border-top: 1px solid var(--spark-border);
}

.subsection-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.subsection-title-wrap {
  display: flex;
  align-items: center;
  gap: 6px;
}

.subsection-icon {
  font-size: 14px;
  color: var(--spark-primary);
}

.subsection-title {
  color: var(--spark-text);
  font-size: var(--spark-fs-xs, 12px);
  font-weight: 700;
  letter-spacing: 0.02em;
}

.subsection-badge {
  display: inline-block;
  padding: 1px 6px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--spark-primary) 15%, transparent);
  color: var(--spark-primary);
  font-size: 10px;
  font-weight: 600;
}

.subsection-hint {
  color: var(--spark-text-muted);
  font-size: var(--spark-fs-3xs, 11px);
}

.property-cards-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: 12px;
}

.property-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 10px 12px;
  border-radius: 8px;
  border: 1px solid var(--spark-border);
  background: var(--spark-panel-bg);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
  transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
}

.property-card:hover,
.property-card:focus-within {
  border-color: color-mix(in srgb, var(--spark-primary) 40%, var(--spark-border));
  box-shadow: 0 4px 14px color-mix(in srgb, var(--spark-primary) 8%, transparent);
}

.property-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.property-label-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 2px 8px;
  border-radius: 4px;
  background: color-mix(in srgb, var(--spark-text-muted) 10%, transparent);
}

.property-label-dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--spark-primary);
}

.property-label-text {
  color: var(--spark-text);
  font-size: var(--spark-fs-xs, 12px);
  font-weight: 650;
}

.property-card-body :deep(.n-input) {
  border: 1px solid var(--spark-border) !important;
  border-radius: 6px !important;
  background: var(--spark-bg) !important;
  transition: all 0.18s ease;
}

.property-card-body :deep(.n-input:hover) {
  border-color: var(--spark-border-hover) !important;
}

.property-card-body :deep(.n-input.n-input--focus) {
  border-color: var(--spark-primary) !important;
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--spark-primary) 20%, transparent) !important;
}

.property-card-body :deep(.n-input__textarea-el) {
  font-size: var(--spark-fs-xs, 12px);
  line-height: 1.6;
}

.prose-card-wrap {
  padding: 2px;
}

.section-prose-input :deep(.n-input) {
  border: 1px solid var(--spark-border) !important;
  border-radius: 8px !important;
  background: var(--spark-panel-bg) !important;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
}

.section-prose-input :deep(.n-input:hover) {
  border-color: var(--spark-border-hover) !important;
}

.section-prose-input :deep(.n-input.n-input--focus) {
  border-color: var(--spark-primary) !important;
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--spark-primary) 20%, transparent) !important;
}

/* ==========================================================================
   原始 Markdown 抽屉 (Raw Markdown)
   ========================================================================== */
.raw-source-collapse {
  padding: 0 16px;
  border-top: 1px solid var(--spark-border);
  background: color-mix(in srgb, var(--spark-panel-bg), var(--spark-bg) 20%);
}

.raw-source-collapse :deep(.n-collapse-item__header) {
  min-height: 38px;
  padding: 0 !important;
}

.raw-source-collapse :deep(.n-collapse-item__content-inner) {
  padding: 0 0 12px !important;
}

.raw-source-title {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  font-size: var(--spark-fs-xs, 12px);
  color: var(--spark-text-muted);
  font-weight: 600;
}

.raw-source-title small {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: normal;
  opacity: 0.7;
}

.raw-markdown-input :deep(.n-input__textarea-el) {
  font-family: var(--spark-mono, monospace);
  font-size: var(--spark-fs-xs, 12px);
  line-height: 1.6;
}

@media (max-width: 720px) {
  .workbench-toolbar {
    padding: 6px 10px;
  }

  .section-count-badge,
  .save-state-pill {
    display: none;
  }

  .workbench-main {
    grid-template-columns: max-content minmax(0, 1fr) !important;
  }

  .section-rail {
    min-width: 140px;
    width: 150px !important;
  }

  .workbench-resizer {
    display: none;
  }

  .section-editor-header {
    padding: 10px 12px;
  }

  .section-hint-text {
    display: none;
  }

  .property-cards-grid {
    grid-template-columns: 1fr;
  }
}
</style>
