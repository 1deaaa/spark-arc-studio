<template>
  <n-drawer v-model:show="visible" placement="bottom" :height="drawerHeight" :auto-size="true" :max-height="85">
    <n-drawer-content closable>
      <template #header>
        <div class="drawer-header-inner">
          <n-icon :component="headerIcon" size="20" />
          <span>{{ headerTitle }}</span>
        </div>
      </template>

      <!-- 场景编辑 -->
      <div v-if="type === 'scene' && currentScene" class="editor-form">
        <div class="form-item">
          <label>{{ t('mobileNodeEditor.sceneName') }}</label>
          <n-input v-model:value="sceneDraft.scene" :placeholder="t('mobileNodeEditor.sceneName')" @input="applyScene" />
        </div>
        <div class="form-item">
          <label>{{ t('mobileNodeEditor.sceneIntro') }}</label>
          <MobileTextArea
            v-model:value="sceneDraft.intro"
            :title="t('mobileNodeEditor.sceneIntro')"
            :placeholder="t('mobileNodeEditor.sceneIntroPlaceholder')"
            :autosize="{ minRows: 2, maxRows: 6 }"
            @input="applyScene"
          />
        </div>
        <div class="form-item">
          <label>{{ t('mobileNodeEditor.sceneGuide') }}</label>
          <MobileTextArea
            v-model:value="sceneDraft.guide"
            :title="t('mobileNodeEditor.sceneGuide')"
            :placeholder="t('mobileNodeEditor.sceneGuidePlaceholder')"
            :autosize="{ minRows: 2, maxRows: 6 }"
            @input="applyScene"
          />
        </div>
        <div class="form-item">
          <label>{{ t('mobileNodeEditor.sceneThought') }}</label>
          <MobileTextArea
            v-model:value="sceneDraft.thought"
            :title="t('mobileNodeEditor.sceneThought')"
            :placeholder="t('mobileNodeEditor.sceneThoughtPlaceholder')"
            :autosize="{ minRows: 1, maxRows: 4 }"
            @input="applyScene"
          />
          <div v-if="!sceneDraft.thought && scriptwriterThought" class="thought-hint">
            <n-text depth="3" size="small">{{ t('mobileNodeEditor.lastAiThought') }}</n-text>
            <div class="thought-preview">
              <MarkdownRenderer :content="scriptwriterThought" />
            </div>
          </div>
        </div>

        <!-- 高级配置（折叠） -->
        <n-collapse>
          <n-collapse-item name="scene-advanced">
            <template #header>
              <n-space align="center" :size="6">
                <n-icon :component="SettingsOutline" size="16" />
                <span class="collapse-label">{{ t('mobileNodeEditor.advancedConfig') }}</span>
              </n-space>
            </template>
            <div class="form-item">
              <label>{{ t('mobileNodeEditor.buttonText') }}</label>
              <n-input v-model:value="sceneDraft.button_text" :placeholder="t('mobileNodeEditor.buttonTextPlaceholder')" @input="applyScene" clearable />
            </div>
            <div class="form-item">
              <label>{{ t('mobileNodeEditor.triggerEvent') }}</label>
              <n-input v-model:value="sceneDraft.trigger_event" :placeholder="t('mobileNodeEditor.triggerEventPlaceholder')" @input="applyScene" clearable />
            </div>
            <div class="form-item">
              <label>{{ t('mobileNodeEditor.priority') }}</label>
              <n-input-number v-model:value="sceneDraft.priority" :show-button="true" :placeholder="'0'" style="width: 100%" @update:value="applyScene" />
            </div>
            <div class="form-item">
              <label>{{ t('mobileNodeEditor.onceKey') }}</label>
              <n-input v-model:value="sceneDraft.once_key" :placeholder="t('mobileNodeEditor.onceKeyPlaceholder')" @input="applyScene" clearable />
            </div>
            <div class="form-item inline">
              <label>{{ t('mobileNodeEditor.hiddenScene') }}</label>
              <n-switch v-model:value="sceneDraft.hiden" @update:value="applyScene" />
            </div>
            <div class="form-item">
              <label>{{ t('mobileNodeEditor.conditions') }}</label>
              <ConditionsEditor v-model:model-value="sceneDraft.conditions" @update:model-value="applyScene" style="width: 100%" />
            </div>
            <div class="form-item">
              <label>{{ t('mobileNodeEditor.effects') }}</label>
              <EffectsEditor v-model:model-value="sceneDraft.effects" @update:model-value="applyScene" style="width: 100%" />
            </div>
          </n-collapse-item>
        </n-collapse>

        <div class="form-actions">
          <n-button type="primary" block @click="addDialogue">
            <template #icon><n-icon :component="AddOutline" /></template>
            {{ t('mobileNodeEditor.addDialogue') }}
          </n-button>
          <n-popconfirm @positive-click="deleteScene" :positive-text="t('mobileNodeEditor.delete')" :negative-text="t('mobileNodeEditor.cancel')">
            <template #trigger>
              <n-button type="error" block>
                <template #icon><n-icon :component="TrashOutline" /></template>
                {{ t('mobileNodeEditor.deleteScene') }}
              </n-button>
            </template>
            <template #default>{{ t('mobileNodeEditor.confirmDeleteScene') }}</template>
          </n-popconfirm>
        </div>
      </div>

      <!-- 对话编辑 -->
      <div v-else-if="type === 'dialogue' && isDialogueNode(currentNode)" class="editor-form">
        <div class="form-item">
          <label>{{ t('mobileNodeEditor.dialogueId') }}</label>
          <n-input :value="String(dialogueDraft.id)" disabled />
        </div>
        <div class="form-item">
          <label>{{ t('mobileNodeEditor.character') }}</label>
          <n-select
            v-model:value="dialogueDraft.chr"
            :options="characterSelectOptions"
            :placeholder="t('mobileNodeEditor.selectCharacter')"
            filterable
            @update:value="applyDialogue"
          />
        </div>
        <div class="form-item">
          <label>{{ t('mobileNodeEditor.dialogueText') }}</label>
          <MobileTextArea
            v-model:value="dialogueDraft.txt"
            :title="t('mobileNodeEditor.dialogueText')"
            :placeholder="t('mobileNodeEditor.dialogueTextPlaceholder')"
            :autosize="{ minRows: 3, maxRows: 10 }"
            @input="applyDialogue"
          />
        </div>
        <div class="form-item">
          <label>{{ t('mobileNodeEditor.jumpToScene') }}</label>
          <n-select
            v-model:value="dialogueDraft.next"
            :options="sceneSelectOptions"
            :placeholder="t('mobileNodeEditor.selectJumpScene')"
            clearable
            @update:value="applyDialogue"
          />
        </div>

        <!-- 行为绑定（折叠） -->
        <n-collapse>
          <n-collapse-item name="dialogue-act">
            <template #header>
              <n-space align="center" :size="6">
                <n-icon :component="GameControllerOutline" size="16" />
                <span class="collapse-label">{{ t('mobileNodeEditor.actBinding') }}</span>
              </n-space>
            </template>
            <template #header-extra>
              <SparkTag v-if="currentActCount > 0" type="info" size="small">{{ currentActCount }}</SparkTag>
            </template>
            <ActEditor :model-value="currentDialogueAct" @update:model-value="onActChange" />
          </n-collapse-item>
        </n-collapse>

        <div class="form-actions">
          <n-button type="primary" block @click="addOptionToDialogue">
            <template #icon><n-icon :component="AddCircleOutline" /></template>
            {{ t('mobileNodeEditor.addOption') }}
          </n-button>
          <n-button block @click="addDialogueAfterCurrent">
            <template #icon><n-icon :component="ArrowDownOutline" /></template>
            {{ t('mobileNodeEditor.addNextDialogue') }}
          </n-button>
          <n-popconfirm @positive-click="deleteDialogue" :positive-text="t('mobileNodeEditor.delete')" :negative-text="t('mobileNodeEditor.cancel')">
            <template #trigger>
              <n-button type="error" block>
                <template #icon><n-icon :component="TrashOutline" /></template>
                {{ t('mobileNodeEditor.deleteDialogue') }}
              </n-button>
            </template>
            <template #default>{{ t('mobileNodeEditor.confirmDeleteDialogue') }}</template>
          </n-popconfirm>
        </div>
      </div>

      <!-- 选项编辑 -->
      <div v-else-if="type === 'option' && isOptionNode(currentNode)" class="editor-form">
        <div class="form-item">
          <label>{{ t('mobileNodeEditor.optionText') }}</label>
          <n-input v-model:value="optionDraft.optn" :placeholder="t('mobileNodeEditor.optionTextPlaceholder')" @input="applyOption" />
        </div>
        <div class="form-actions">
          <n-button type="primary" block @click="addDialogueToOption">
            <template #icon><n-icon :component="AddOutline" /></template>
            {{ t('mobileNodeEditor.addChildDialogue') }}
          </n-button>
          <n-popconfirm @positive-click="deleteOption" :positive-text="t('mobileNodeEditor.delete')" :negative-text="t('mobileNodeEditor.cancel')">
            <template #trigger>
              <n-button type="error" block>
                <template #icon><n-icon :component="TrashOutline" /></template>
                {{ t('mobileNodeEditor.deleteOption') }}
              </n-button>
            </template>
            <template #default>{{ t('mobileNodeEditor.confirmDeleteOption') }}</template>
          </n-popconfirm>
        </div>
      </div>

      <!-- 无选中 -->
      <div v-else class="no-selection">
        <n-empty :description="t('mobileNodeEditor.selectNode')" />
      </div>
    </n-drawer-content>
  </n-drawer>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue';
import { NDrawer, NDrawerContent, NInput, NInputNumber, NSelect, NButton, NIcon, NSwitch, NCollapse, NCollapseItem, NPopconfirm, NEmpty, NSpace, NText } from 'naive-ui';
import {
  FilmOutline, ChatbubbleEllipsesOutline, RadioButtonOnOutline,
  AddOutline, TrashOutline, AddCircleOutline, ArrowDownOutline,
  SettingsOutline, GameControllerOutline
} from '@vicons/ionicons5';
import { useI18n } from 'vue-i18n';
import { useSceneStore, type SceneWithClientId } from '../stores/sceneStore';
import { useProjectStore } from '../stores/projectStore';
import { useFileStore } from '../stores/fileStore';
import { useCharacterStore } from '../stores/characterStore';
import { useActionBindingStore } from '../stores/actionBindingStore';
import type { ArcDialogueNode, ArcOptionNode, ArcScene } from '../../services/arcParser';
import MobileTextArea from '../share/MobileTextArea.vue';
import SparkTag from '../share/SparkTag.vue';
import MarkdownRenderer from '../share/MarkdownRenderer.vue';
import ConditionsEditor from './ConditionsEditor.vue';
import EffectsEditor from './EffectsEditor.vue';
import ActEditor from './ActEditor.vue';
import bus from '../../eventBus';

const { t } = useI18n();
const sceneStore = useSceneStore();
const projectStore = useProjectStore();
const fileStore = useFileStore();
const characterStore = useCharacterStore();
const actionBindingStore = useActionBindingStore();

const visible = defineModel<boolean>('show', { default: false });

const drawerHeight = computed(() => {
  if (type.value === 'scene') return '75%';
  return '65%';
});

const type = computed(() => sceneStore.selectionType);
const currentScene = computed(() => sceneStore.currentScene);
const currentNode = computed(() => sceneStore.currentNode);

const headerIcon = computed(() => {
  if (type.value === 'scene') return FilmOutline;
  if (type.value === 'dialogue') return ChatbubbleEllipsesOutline;
  if (type.value === 'option') return RadioButtonOnOutline;
  return ChatbubbleEllipsesOutline;
});

const headerTitle = computed(() => {
  if (type.value === 'scene') return t('mobileNodeEditor.sceneEdit');
  if (type.value === 'dialogue') return t('mobileNodeEditor.dialogueEdit');
  if (type.value === 'option') return t('mobileNodeEditor.optionEdit');
  return t('mobileNodeEditor.selectNode');
});

// ── 类型守卫 ──
function isDialogueNode(node: unknown): node is ArcDialogueNode {
  return !!node && typeof node === 'object' && 'id' in node && 'txt' in node;
}

function isOptionNode(node: unknown): node is ArcOptionNode {
  return !!node && typeof node === 'object' && 'optn' in node && 'dia' in node;
}

// ── 角色选项 ──
const characterSelectOptions = computed(() =>
  characterStore.list.map(c => ({
    label: c.name || `角色 ${c.id}`,
    value: Number(c.id)
  }))
);

// ── 场景选项（用于 next 跳转） ──
const sceneSelectOptions = computed(() =>
  (Array.isArray(sceneStore.scriptData) ? sceneStore.scriptData : [])
    .map(s => s?.scene)
    .filter(Boolean)
    .map(name => ({ label: name, value: name }))
);

// ── 自动保存 ──
const autoSaveEnabled = computed(() => localStorage.getItem('autoSaveEnabled') !== 'false');

function useDebounce(fn: Function, delay = 600) {
  let timer: ReturnType<typeof setTimeout> | null = null;
  return (...args: unknown[]) => {
    if (timer) clearTimeout(timer);
    timer = setTimeout(() => fn(...args), delay);
  };
}

import { AUTO_SAVE_DEBOUNCE_TIME } from '../../config';

async function maybeAutoSave() {
  if (!autoSaveEnabled.value) return;
  const path = fileStore.selectedFile?.path;
  if (!path || !projectStore.currentProject) return;
  try {
    const { saveStory } = await import('../../services/api');
    const { serializeToArc } = await import('../../services/arcParser');
    const dataToSave = serializeToArc(Array.isArray(sceneStore.scriptData) ? sceneStore.scriptData : []);
    await saveStory(projectStore.currentProject, path, dataToSave);
    bus.emit('saved');
  } catch (e) {
    console.error('Auto save failed:', e);
  }
}

const debouncedAutoSave = useDebounce(maybeAutoSave, AUTO_SAVE_DEBOUNCE_TIME);

// ── 场景草稿 ──
const sceneDraft = reactive<{
  scene: string;
  guide: string;
  intro: string;
  thought: string;
  button_text: string;
  trigger_event: string;
  priority: number;
  once_key: string;
  hiden: boolean;
  conditions: ArcScene['conditions'];
  effects: ArcScene['effects'];
}>({
  scene: '', guide: '', intro: '', thought: '',
  button_text: '', trigger_event: '', priority: 0,
  once_key: '', hiden: false, conditions: null, effects: null,
});

const scriptwriterThought = computed(() => (sceneStore.lastScriptwriterThought || '').trim());

watch([
  () => sceneStore.currentScene,
  () => sceneStore.selectionType
], ([s, t]) => {
  if (!s || t !== 'scene') return;
  sceneDraft.scene = s.scene || '';
  sceneDraft.guide = s.guide || '';
  sceneDraft.intro = s.intro || '';
  sceneDraft.thought = s.thought || '';
  sceneDraft.button_text = typeof s.button_text === 'string' ? s.button_text : '';
  sceneDraft.trigger_event = typeof s.trigger_event === 'string' ? s.trigger_event : '';
  sceneDraft.priority = Number.isFinite(Number(s.priority)) ? Number(s.priority) : 0;
  sceneDraft.once_key = typeof s.once_key === 'string' ? s.once_key : '';
  sceneDraft.hiden = !!s.hiden;
  sceneDraft.conditions = (s.conditions != null && typeof s.conditions === 'object') ? s.conditions as ArcScene['conditions'] : null;
  sceneDraft.effects = (s.effects != null) ? s.effects as ArcScene['effects'] : null;
}, { immediate: true });

function applyScene() {
  sceneStore.updateCurrentScene({
    scene: sceneDraft.scene,
    guide: sceneDraft.guide,
    intro: sceneDraft.intro,
    thought: sceneDraft.thought,
    button_text: sceneDraft.button_text.trim() || undefined,
    trigger_event: sceneDraft.trigger_event.trim() || undefined,
    priority: Number.isFinite(Number(sceneDraft.priority)) ? Number(sceneDraft.priority) : 0,
    once_key: sceneDraft.once_key.trim() || undefined,
    hiden: !!sceneDraft.hiden,
    conditions: sceneDraft.conditions,
    effects: sceneDraft.effects,
  });
  debouncedAutoSave();
}

// ── 对话草稿 ──
const dialogueDraft = reactive({ id: 0, chr: 0, txt: '', next: '' });

watch(() => sceneStore.currentNode, (n) => {
  if (sceneStore.selectionType !== 'dialogue' || !isDialogueNode(n)) return;
  dialogueDraft.id = n.id ?? 0;
  dialogueDraft.chr = n.chr ?? 0;
  dialogueDraft.txt = n.txt ?? '';
  dialogueDraft.next = n.next ?? '';
}, { immediate: true });

function applyDialogue() {
  sceneStore.updateCurrentDialogue({
    chr: dialogueDraft.chr,
    txt: dialogueDraft.txt,
    next: dialogueDraft.next
  });
  debouncedAutoSave();
}

// ── 行为绑定 ──
const currentDialogueAct = computed(() => {
  if (!isDialogueNode(sceneStore.currentNode) || sceneStore.selectionType !== 'dialogue') return null;
  return sceneStore.currentNode.act ?? null;
});

const currentActCount = computed(() => {
  if (!isDialogueNode(sceneStore.currentNode) || sceneStore.selectionType !== 'dialogue') return 0;
  return Object.keys(sceneStore.currentNode.act || {}).length;
});

function onActChange(val: Record<string, string | string[]> | null) {
  if (!isDialogueNode(sceneStore.currentNode) || sceneStore.selectionType !== 'dialogue') return;
  if (!val || Object.keys(val).length === 0) {
    delete (sceneStore.currentNode as any).act;
  } else {
    sceneStore.currentNode.act = val;
  }
  debouncedAutoSave();
}

// ── 选项草稿 ──
const optionDraft = reactive({ optn: '' });

watch(() => sceneStore.currentNode, (n) => {
  if (sceneStore.selectionType !== 'option' || !isOptionNode(n)) return;
  optionDraft.optn = n.optn ?? '';
}, { immediate: true });

function applyOption() {
  sceneStore.updateCurrentOption({ optn: optionDraft.optn });
  debouncedAutoSave();
}

// ── 结构操作 ──
function nextIdFromScene(scene: ArcScene | null) {
  let max = 0;
  const dfs = (dias: ArcDialogueNode[] | undefined) => {
    dias?.forEach(d => { max = Math.max(max, Number(d.id) || 0); d.opt?.forEach(o => dfs(o.dia)); });
  };
  dfs(scene?.dia);
  return max + 1;
}

function addDialogue() {
  if (!sceneStore.currentScene) return;
  const nid = nextIdFromScene(sceneStore.currentScene);
  const node = { id: nid, chr: 0, txt: t('mobileNodeEditor.newDialogueContent') };
  sceneStore.currentScene.dia = sceneStore.currentScene.dia || [];
  sceneStore.currentScene.dia.push(node);
  sceneStore.selectDialogue(node);
  debouncedAutoSave();
}

function deleteScene() {
  sceneStore.deleteCurrentScene();
  visible.value = false;
}

function addOptionToDialogue() {
  if (sceneStore.selectionType !== 'dialogue' || !isDialogueNode(sceneStore.currentNode)) return;
  const nid = nextIdFromScene(sceneStore.currentScene);
  const option: { optn: string; dia: ArcDialogueNode[]; __oid: string } = {
    optn: t('mobileNodeEditor.newOption'),
    dia: [{ id: nid, chr: 0, txt: t('mobileNodeEditor.newOptionDialogue') }],
    __oid: `oid-${Date.now()}`,
  };
  sceneStore.currentNode.opt = sceneStore.currentNode.opt || [];
  sceneStore.currentNode.opt.push(option);
  sceneStore.selectOption(option, sceneStore.currentNode);
  debouncedAutoSave();
}

function addDialogueAfterCurrent() {
  if (sceneStore.selectionType !== 'dialogue' || !isDialogueNode(sceneStore.currentNode)) return;
  const nid = nextIdFromScene(sceneStore.currentScene);
  const dlg = { id: nid, chr: 0, txt: '' };
  const parent = sceneStore.nodeParent;
  if (isOptionNode(parent) && Array.isArray(parent.dia)) {
    const arr = parent.dia;
    const idx = arr.indexOf(sceneStore.currentNode);
    if (idx >= 0) arr.splice(idx + 1, 0, dlg); else arr.push(dlg);
    sceneStore.selectDialogue(dlg, parent);
  } else if (sceneStore.currentScene?.dia) {
    const arr = sceneStore.currentScene.dia;
    const idx = arr.indexOf(sceneStore.currentNode);
    if (idx >= 0) arr.splice(idx + 1, 0, dlg); else arr.push(dlg);
    sceneStore.selectDialogue(dlg, null);
  }
  debouncedAutoSave();
}

function deleteDialogue() {
  if (sceneStore.selectionType !== 'dialogue' || !isDialogueNode(sceneStore.currentNode)) return;
  const node = sceneStore.currentNode;
  const parent = sceneStore.nodeParent;
  if (isOptionNode(parent) && Array.isArray(parent.dia)) {
    const idx = parent.dia.indexOf(node);
    if (idx >= 0) parent.dia.splice(idx, 1);
    sceneStore.selectOption(parent, sceneStore.nodeParent || parent);
  } else if (sceneStore.currentScene?.dia) {
    const idx = sceneStore.currentScene.dia.indexOf(node);
    if (idx >= 0) sceneStore.currentScene.dia.splice(idx, 1);
    sceneStore.selectScene(sceneStore.currentScene);
  }
  visible.value = false;
  debouncedAutoSave();
}

function addDialogueToOption() {
  if (sceneStore.selectionType !== 'option' || !isOptionNode(sceneStore.currentNode)) return;
  const nid = nextIdFromScene(sceneStore.currentScene);
  const dlg = { id: nid, chr: 0, txt: t('mobileNodeEditor.newDialogue') };
  sceneStore.currentNode.dia = sceneStore.currentNode.dia || [];
  sceneStore.currentNode.dia.push(dlg);
  sceneStore.selectDialogue(dlg, sceneStore.currentNode);
  debouncedAutoSave();
}

function deleteOption() {
  if (sceneStore.selectionType !== 'option' || !isOptionNode(sceneStore.currentNode)) return;
  const option = sceneStore.currentNode;
  const parent = sceneStore.nodeParent;
  if (isDialogueNode(parent) && parent.opt) {
    const idx = parent.opt.indexOf(option);
    if (idx >= 0) parent.opt.splice(idx, 1);
    if (parent.opt.length === 0) delete parent.opt;
    sceneStore.selectDialogue(parent, null);
  }
  visible.value = false;
  debouncedAutoSave();
}

// ── 加载角色和 action bindings ──
watch(() => projectStore.currentProject, (proj) => {
  if (proj) {
    characterStore.load(proj);
    actionBindingStore.load(proj);
  }
}, { immediate: true });
</script>

<style scoped>
.drawer-header-inner {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  font-size: var(--spark-fs-md);
}

.editor-form {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding-bottom: 40px;
}

.form-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.form-item label {
  font-size: var(--spark-fs-sm);
  font-weight: 600;
  color: var(--spark-text-muted);
}

.form-item.inline {
  flex-direction: row;
  align-items: center;
  justify-content: space-between;
}

.form-item.inline label {
  margin: 0;
}

.collapse-label {
  font-size: var(--spark-fs-sm);
  font-weight: 500;
}

.thought-hint {
  margin-top: 6px;
  opacity: 0.8;
}

.thought-preview {
  padding: 8px;
  background: rgba(0,0,0,0.04);
  border-radius: 6px;
  margin-top: 4px;
  font-size: var(--spark-fs-xs);
  max-height: 120px;
  overflow-y: auto;
}

.form-actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 8px;
}

.no-selection {
  padding: 40px 0;
}
</style>
