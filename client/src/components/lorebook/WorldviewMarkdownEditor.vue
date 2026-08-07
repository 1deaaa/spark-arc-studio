<template>
  <div class="worldview-workbench">
    <div class="workbench-toolbar">
      <div class="workbench-summary">
        <n-icon :component="Layers3" />
        <span>{{ t('components.lorebookEditor.worldviewWorkbench') }}</span>
        <span class="section-count">{{ t('components.lorebookEditor.sectionCount', { count: visibleSections.length }) }}</span>
      </div>
      <div class="workbench-actions">
        <span class="save-state" :class="`is-${saveStatus}`">
          <span class="save-state-dot" />
          {{ saveStatusLabel }}
        </span>
        <n-dropdown :options="templateOptions" trigger="click" @select="addTemplateSection">
          <n-button size="small" secondary type="primary">
            <template #icon><n-icon :component="Plus" /></template>
            {{ t('components.lorebookEditor.addModule') }}
          </n-button>
        </n-dropdown>
      </div>
    </div>

    <div class="workbench-main">
      <nav class="section-rail" :aria-label="t('components.lorebookEditor.sectionNavigation')">
        <button
          v-for="section in visibleSections"
          :key="`${section.index}-${section.title}`"
          type="button"
          class="section-nav-item"
          :class="{ active: section.index === activeSectionIndex }"
          @click="activeSectionIndex = section.index"
        >
          <span class="section-nav-index">{{ section.index + 1 }}</span>
          <span class="section-nav-copy">
            <strong>{{ section.title || t('components.lorebookEditor.legacySection') }}</strong>
            <small>{{ sectionSummary(section) }}</small>
          </span>
        </button>
      </nav>

      <section v-if="activeSection" class="section-editor">
        <div class="section-editor-header">
          <div class="section-heading-copy">
            <n-input
              v-if="!activeSection.legacy"
              :value="activeSection.title"
              size="small"
              class="section-title-input"
              :placeholder="t('components.lorebookEditor.sectionTitlePlaceholder')"
              @update:value="updateSectionTitle"
            />
            <strong v-else>{{ t('components.lorebookEditor.legacySection') }}</strong>
            <span>{{ activeModuleHint }}</span>
          </div>
          <div v-if="!activeSection.legacy" class="section-order-actions">
            <n-tooltip trigger="hover">
              <template #trigger>
                <n-button
                  size="tiny"
                  quaternary
                  circle
                  :disabled="!canMoveUp"
                  @click="moveSection(-1)"
                >
                  <template #icon><n-icon :component="ArrowUp" /></template>
                </n-button>
              </template>
              {{ t('components.lorebookEditor.moveSectionUp') }}
            </n-tooltip>
            <n-tooltip trigger="hover">
              <template #trigger>
                <n-button
                  size="tiny"
                  quaternary
                  circle
                  :disabled="!canMoveDown"
                  @click="moveSection(1)"
                >
                  <template #icon><n-icon :component="ArrowDown" /></template>
                </n-button>
              </template>
              {{ t('components.lorebookEditor.moveSectionDown') }}
            </n-tooltip>
            <n-popconfirm
              :positive-text="t('common.delete')"
              :negative-text="t('common.cancel')"
              @positive-click="removeSection"
            >
              <template #trigger>
                <n-button size="tiny" quaternary circle type="error">
                  <template #icon><n-icon :component="Trash2" /></template>
                </n-button>
              </template>
              {{ t('components.lorebookEditor.confirmDeleteSection', { title: activeSection.title }) }}
            </n-popconfirm>
          </div>
        </div>

        <div class="section-editor-scroll">
          <div v-if="activeFields.length" class="field-editor">
            <div class="subsection-heading">
              <span>{{ t('components.lorebookEditor.structuredFields') }}</span>
              <small>{{ t('components.lorebookEditor.structuredFieldsHint') }}</small>
            </div>
            <div class="field-list">
              <label v-for="field in activeFields" :key="field.lineIndex" class="field-row">
                <span>{{ field.label }}</span>
                <n-input
                  :value="field.value"
                  type="textarea"
                  :autosize="{ minRows: 1, maxRows: 4 }"
                  :placeholder="t('components.lorebookEditor.fieldValuePlaceholder')"
                  @update:value="value => updateField(field.lineIndex, value)"
                />
              </label>
            </div>
          </div>

          <div class="prose-editor">
            <div class="subsection-heading">
              <span>{{ activeFields.length ? t('components.lorebookEditor.additionalNotes') : t('components.lorebookEditor.sectionContent') }}</span>
              <n-button v-if="!activeSection.legacy" text size="tiny" @click="appendField">
                <template #icon><n-icon :component="ListPlus" /></template>
                {{ t('components.lorebookEditor.addField') }}
              </n-button>
            </div>
            <StudioSeamlessTextarea
              :value="activeProse"
              :autosize="{ minRows: 10, maxRows: 40 }"
              :placeholder="t('components.lorebookEditor.sectionContentPlaceholder')"
              class="section-prose-input"
              @update:value="updateSectionProse"
            />
          </div>
        </div>
      </section>
    </div>

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
          :autosize="{ minRows: 7, maxRows: 16 }"
          :placeholder="t('components.lorebookEditor.worldviewPlaceholder')"
          class="raw-markdown-input"
          @update:value="emitValue"
        />
      </n-collapse-item>
    </n-collapse>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue';
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
import { ArrowDown, ArrowUp, FileText, Layers3, ListPlus, Plus, Trash2 } from '@lucide/vue';
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

const document = computed(() => parseWorldviewMarkdown(props.modelValue));
const visibleSections = computed(() => document.value.sections);
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

const activeTemplateKey = computed<TemplateKey>(() => {
  const title = activeSection.value?.title.trim().toLowerCase() || '';
  const matched = templateKeys.find(key => {
    if (key === 'blank') return false;
    const localizedTitle = t(`components.lorebookEditor.moduleTemplates.${key}.title`).trim().toLowerCase();
    return localizedTitle === title;
  });
  if (matched) return matched;
  if (/战力|能力|力量|power|ability|combat|전투|능력|戦力|能力/.test(title)) return 'power';
  if (/货币|经济|交易|currency|econom|통화|경제|通貨|経済/.test(title)) return 'economy';
  if (/规则|禁忌|限制|rule|taboo|규칙|금기|ルール|禁忌/.test(title)) return 'rules';
  return 'blank';
});

const activeModuleHint = computed(() => activeSection.value?.legacy
  ? t('components.lorebookEditor.legacySectionHint')
  : t(`components.lorebookEditor.moduleTemplates.${activeTemplateKey.value}.hint`));

const saveStatusLabel = computed(() => t(`components.lorebookEditor.saveStates.${props.saveStatus}`));

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
  background: var(--spark-panel-bg);
}

.workbench-toolbar,
.section-editor-header,
.subsection-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.workbench-toolbar {
  min-height: 42px;
  padding: 6px 8px 6px 10px;
  border-bottom: 1px solid var(--spark-border);
}

.workbench-summary,
.workbench-actions,
.save-state,
.raw-source-title {
  display: flex;
  align-items: center;
  gap: 6px;
}

.workbench-summary {
  min-width: 0;
  color: var(--spark-text);
  font-size: var(--spark-fs-sm);
  font-weight: 650;
}

.workbench-summary > span:first-of-type {
  white-space: nowrap;
}

.section-count,
.save-state,
.raw-source-title small,
.subsection-heading small,
.section-heading-copy > span {
  color: var(--spark-text-muted);
  font-size: var(--spark-fs-3xs);
  font-weight: 500;
}

.workbench-actions {
  flex-shrink: 0;
}

.save-state-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--spark-text-muted);
}

.save-state.is-dirty .save-state-dot,
.save-state.is-saving .save-state-dot {
  background: var(--spark-warning, #d99a2b);
}

.save-state.is-saved .save-state-dot {
  background: var(--spark-success, #2e9b62);
}

.save-state.is-error .save-state-dot {
  background: var(--spark-error, #d84c4c);
}

.workbench-main {
  display: grid;
  grid-template-columns: max-content minmax(0, 1fr);
  min-height: 0;
  overflow: hidden;
}

.section-rail {
  min-width: 0;
  padding: 6px;
  overflow-y: auto;
  border-right: 1px solid var(--spark-border);
  background: color-mix(in srgb, var(--spark-panel-bg), var(--spark-bg) 32%);
}

.section-nav-item {
  display: flex;
  align-items: flex-start;
  gap: 7px;
  width: 100%;
  min-height: 48px;
  padding: 7px;
  border: 0;
  border-left: 2px solid transparent;
  background: transparent;
  color: var(--spark-text);
  text-align: left;
  font-family: inherit;
  cursor: pointer;
}

.section-nav-item:hover {
  background: color-mix(in srgb, var(--spark-primary), transparent 93%);
}

.section-nav-item.active {
  border-left-color: var(--spark-primary);
  background: var(--spark-primary-container);
}

.section-nav-index {
  display: grid;
  place-items: center;
  flex: 0 0 20px;
  height: 20px;
  color: var(--spark-text-muted);
  font-size: var(--spark-fs-3xs);
  font-variant-numeric: tabular-nums;
}

.section-nav-copy {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
}

.section-nav-copy strong,
.section-nav-copy small {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.section-nav-copy strong {
  font-size: var(--spark-fs-xs);
  font-weight: 600;
}

.section-nav-copy small {
  color: var(--spark-text-muted);
  font-size: var(--spark-fs-3xs);
}

.section-editor {
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
}

.section-editor-header {
  min-height: 56px;
  padding: 8px 10px;
  border-bottom: 1px solid var(--spark-border);
}

.section-heading-copy {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.section-title-input {
  max-width: 320px;
}

.section-title-input :deep(.n-input__input-el) {
  font-weight: 650;
}

.section-heading-copy > span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.section-order-actions {
  display: flex;
  align-items: center;
  flex-shrink: 0;
}

.section-editor-scroll {
  flex: 1;
  min-height: 0;
  padding: 10px;
  overflow-y: auto;
}

.field-editor,
.prose-editor {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.field-editor + .prose-editor {
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px solid var(--spark-border);
}

.subsection-heading > span {
  color: var(--spark-text);
  font-size: var(--spark-fs-xs);
  font-weight: 650;
}

.field-list {
  display: grid;
  gap: 7px;
}

.field-row {
  display: grid;
  grid-template-columns: minmax(72px, 0.28fr) minmax(0, 1fr);
  align-items: start;
  gap: 8px;
}

.field-row > span {
  padding-top: 7px;
  overflow: hidden;
  color: var(--spark-text-muted);
  font-size: var(--spark-fs-xs);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.section-prose-input :deep(.n-input) {
  border: 1px solid var(--spark-border) !important;
  border-radius: 4px !important;
}

.raw-source-collapse {
  padding: 0 10px;
  border-top: 1px solid var(--spark-border);
  background: var(--spark-bg);
}

.raw-source-collapse :deep(.n-collapse-item__header) {
  min-height: 36px;
  padding: 0 !important;
}

.raw-source-collapse :deep(.n-collapse-item__content-inner) {
  padding: 0 0 10px !important;
}

.raw-source-title {
  min-width: 0;
  font-size: var(--spark-fs-xs);
}

.raw-source-title small {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.raw-markdown-input :deep(.n-input__textarea-el) {
  font-family: Consolas, 'Courier New', monospace;
  font-size: var(--spark-fs-xs);
  line-height: 1.6;
}

@media (max-width: 720px) {
  .workbench-toolbar {
    align-items: flex-start;
  }

  .section-count,
  .save-state {
    display: none;
  }

  .workbench-main {
    grid-template-columns: max-content minmax(0, 1fr);
  }

  .section-editor-header {
    align-items: flex-start;
  }

  .section-heading-copy > span {
    display: none;
  }

  .field-row {
    grid-template-columns: 1fr;
    gap: 3px;
  }

  .field-row > span {
    padding-top: 0;
  }
}
</style>
