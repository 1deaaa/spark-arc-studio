<template>
  <div id="node-editor" class="right-panel-section">
    <n-card 
      :title="title" 
      :segmented="{ content: true }" 
      :bordered="false"
      size="small"
    >
      <template #header-extra>
        <n-icon 
          :component="editorType === 'scene' ? Film : editorType === 'dialogue' ? MessageCircle : editorType === 'option' ? CircleDot : CircleHelp"
          size="20" 
        />
      </template>

      <div id="node-editor-content">
        <!-- 场景编辑器 -->
        <n-form v-if="editorType === 'scene'" label-placement="top" size="medium">
          <n-form-item :label="t('nodeEditor.sceneName')">
            <n-input 
              id="scene-name" 
              v-model:value="sceneDraft.scene" 
              @input="applyScene"
              clearable
              :placeholder="t('nodeEditor.sceneNamePlaceholder')"
            />
          </n-form-item>

          <n-form-item :label="t('nodeEditor.sceneGuide')">
            <n-input
              id="scene-guide"
              v-model:value="sceneDraft.guide"
              @input="applyScene"
              clearable
              :placeholder="t('nodeEditor.sceneGuidePlaceholder')"
            />
          </n-form-item>

          <n-form-item :label="t('nodeEditor.sceneIntro')">
            <n-input
              id="scene-intro"
              v-model:value="sceneDraft.intro"
              type="textarea"
              :autosize="{ minRows: 3, maxRows: 8 }"
              @input="applyScene"
              :placeholder="t('nodeEditor.sceneIntroPlaceholder')"
            />
          </n-form-item>

          <n-space vertical style="width: 100%" :size="8">
            <n-button type="primary" @click="addDialogue" block strong>
              <template #icon>
                <n-icon :component="Plus" />
              </template>
              {{ t('nodeEditor.addDialogue') }}
            </n-button>
            <n-popconfirm
              @positive-click="deleteScene"
              :positive-text="t('nodeEditor.delete')"
              :negative-text="t('nodeEditor.cancel')"
            >
              <template #trigger>
                <n-button type="error" block>
                  <template #icon>
                    <n-icon :component="Trash" />
                  </template>
                  {{ t('nodeEditor.deleteScene') }}
                </n-button>
              </template>
              <template #default>
                {{ t('nodeEditor.confirmDeleteScene') }}
              </template>
            </n-popconfirm>
          </n-space>

          <n-form-item :label="t('nodeEditor.sceneThought')">
            <n-input
              v-model:value="sceneDraft.thought"
              type="textarea"
              :autosize="{ minRows: 2, maxRows: 10 }"
              :placeholder="t('nodeEditor.sceneThoughtPlaceholder')"
              @input="applyScene"
            />
            <div v-if="!sceneDraft.thought && scriptwriterThought" class="thought-hint" style="margin-top: 8px; opacity: 0.8;">
              <n-text depth="3" size="small">{{ t('nodeEditor.latestAiThought') }}</n-text>
              <div style="padding: 8px; background: rgba(0,0,0,0.05); border-radius: 4px; margin-top: 4px; font-size: var(--spark-fs-xs);">
                <MarkdownRenderer :content="scriptwriterThought" />
              </div>
            </div>
          </n-form-item>

          <!-- 内容编排：把底层触发字段包装成创作者可理解的内容类型。 -->
          <n-collapse style="margin-top: 8px;">
            <n-collapse-item name="scene-content">
              <template #header>
                <span class="content-runtime-title">
                  <n-icon :component="Layers3" size="16" />
                  <span>{{ t('nodeEditor.sceneRuntime.title') }}</span>
                </span>
              </template>
              <template #header-extra>
                <SparkTag :type="contentKindTagType(sceneRuntimeSummary.kind)" size="small">
                  {{ contentKindLabel(sceneRuntimeSummary.kind) }}
                </SparkTag>
              </template>

              <div class="content-runtime-panel">
                <p class="content-runtime-lede">{{ t('nodeEditor.sceneRuntime.subtitle') }}</p>

                <div class="content-kind-grid">
                  <button
                    v-for="option in contentKindOptions"
                    :key="option.kind"
                    type="button"
                    class="content-kind-card"
                    :class="{ 'is-active': sceneRuntimeSummary.kind === option.kind }"
                    @click="applyContentKindPreset(option.kind)"
                  >
                    <span class="content-kind-card__icon">
                      <n-icon :component="option.icon" size="16" />
                    </span>
                    <span class="content-kind-card__body">
                      <strong>{{ option.label }}</strong>
                      <small>{{ option.description }}</small>
                    </span>
                  </button>
                </div>

                <div class="content-runtime-summary">
                  <SparkTag
                    v-for="chip in sceneRuntimeChips"
                    :key="chip.key"
                    :type="chip.type"
                    size="tiny"
                    ghost
                  >
                    {{ chip.label }}
                  </SparkTag>
                </div>

                <n-form label-placement="top" size="small" class="content-runtime-fields">

                <n-form-item>
                  <template #label>
                    <div class="content-runtime-label">
                      <span>{{ t('nodeEditor.sceneRuntime.buttonText') }}</span>
                      <n-text depth="3" class="content-runtime-label__hint">{{ t('nodeEditor.sceneRuntime.buttonTextHint') }}</n-text>
                    </div>
                  </template>
                  <n-input
                    v-model:value="sceneDraft.button_text"
                    @input="applyScene"
                    clearable
                    :placeholder="t('nodeEditor.sceneRuntime.buttonTextPlaceholder')"
                  />
                </n-form-item>

                <n-form-item>
                  <template #label>
                    <div class="content-runtime-label">
                      <span>{{ t('nodeEditor.sceneRuntime.triggerEvent') }}</span>
                      <n-text depth="3" class="content-runtime-label__hint">{{ t('nodeEditor.sceneRuntime.triggerEventHint') }}</n-text>
                    </div>
                  </template>
                  <n-input
                    v-model:value="sceneDraft.trigger_event"
                    @input="applyScene"
                    clearable
                    :placeholder="t('nodeEditor.sceneRuntime.triggerEventPlaceholder')"
                  />
                </n-form-item>

                <n-form-item>
                  <template #label>
                    <div class="content-runtime-label">
                      <span>{{ t('nodeEditor.sceneRuntime.priority') }}</span>
                      <n-text depth="3" class="content-runtime-label__hint">{{ t('nodeEditor.sceneRuntime.priorityHint') }}</n-text>
                    </div>
                  </template>
                  <n-input-number
                    v-model:value="sceneDraft.priority"
                    @update:value="applyScene"
                    :show-button="true"
                    :placeholder="t('nodeEditor.sceneRuntime.priorityPlaceholder')"
                    style="width: 100%"
                  />
                </n-form-item>

                <n-form-item>
                  <template #label>
                    <div class="content-runtime-label">
                      <span>{{ t('nodeEditor.sceneRuntime.onceKey') }}</span>
                      <n-text depth="3" class="content-runtime-label__hint">{{ t('nodeEditor.sceneRuntime.onceKeyHint') }}</n-text>
                    </div>
                  </template>
                  <n-input
                    v-model:value="sceneDraft.once_key"
                    @input="applyScene"
                    clearable
                    :placeholder="t('nodeEditor.sceneRuntime.onceKeyPlaceholder')"
                  />
                </n-form-item>

                <n-form-item>
                  <template #label>
                    <div class="content-runtime-label">
                      <span>{{ t('nodeEditor.sceneRuntime.hiddenScene') }}</span>
                      <n-text depth="3" class="content-runtime-label__hint">{{ t('nodeEditor.sceneRuntime.hiddenSceneHint') }}</n-text>
                    </div>
                  </template>
                  <n-switch v-model:value="sceneDraft.hiden" @update:value="applyScene" />
                </n-form-item>

                <n-form-item>
                  <template #label>
                    <div class="content-runtime-label">
                      <span>{{ t('nodeEditor.sceneRuntime.conditions') }}</span>
                      <n-text depth="3" class="content-runtime-label__hint">{{ t('nodeEditor.sceneRuntime.conditionsHint') }}</n-text>
                    </div>
                  </template>
                  <conditions-editor
                    v-model:model-value="sceneDraft.conditions"
                    @update:model-value="applyScene"
                    style="width: 100%"
                  />
                </n-form-item>

                <n-form-item>
                  <template #label>
                    <div class="content-runtime-label">
                      <span>{{ t('nodeEditor.sceneRuntime.effects') }}</span>
                      <n-text depth="3" class="content-runtime-label__hint">{{ t('nodeEditor.sceneRuntime.effectsHint') }}</n-text>
                    </div>
                  </template>
                  <effects-editor
                    v-model:model-value="sceneDraft.effects"
                    @update:model-value="applyScene"
                    style="width: 100%"
                  />
                </n-form-item>

                </n-form>
              </div>
            </n-collapse-item>
          </n-collapse>
        </n-form>

        <!-- 对话编辑器 -->
        <n-form v-else-if="editorType === 'dialogue'" label-placement="top" size="medium">
          <n-form-item :label="t('nodeEditor.dialogueId')">
            <n-input id="dialogue-id" :value="String(dialogueDraft.id)" disabled />
          </n-form-item>

          <n-form-item :label="t('nodeEditor.character')">
            <n-select
              id="dialogue-chr"
              v-model:value="dialogueDraft.chr"
              @update:value="applyDialogue"
              :placeholder="t('nodeEditor.selectCharacter')"
              filterable
              :options="characterSelectOptions"
            />
          </n-form-item>

          <n-form-item :label="t('nodeEditor.dialogueText')">
            <n-input 
              id="dialogue-txt" 
              v-model:value="dialogueDraft.txt" 
              type="textarea"
              :autosize="{ minRows: 5, maxRows: 12 }"
              @input="applyDialogue" 
              @keydown.enter.prevent="onEnterAddNextDialogue"
              :placeholder="t('nodeEditor.dialogueTextPlaceholder')"
            />
          </n-form-item>

          <n-form-item :label="t('nodeEditor.jumpToScene')">
            <n-select
              id="dialogue-next"
              v-model:value="dialogueDraft.next"
              @update:value="applyDialogue"
              :placeholder="t('nodeEditor.selectJumpScene')"
              filterable
              clearable
              :options="sceneSelectOptions"
            />
          </n-form-item>

          <n-form-item :label="t('nodeEditor.presentation.conceptionLabel')">
            <n-input
              :value="currentIllustrationPrompt"
              type="textarea"
              :autosize="{ minRows: 2, maxRows: 6 }"
              :placeholder="t('nodeEditor.presentation.conceptionPlaceholder')"
              @update:value="updatePresentationConception"
            />
          </n-form-item>

          <n-form-item v-if="hasPresentationCue">
            <template #label>
              <div class="content-runtime-label">
                <span>{{ t('nodeEditor.presentation.presentationCue') }}</span>
                <n-text depth="3" class="content-runtime-label__hint">{{ t('nodeEditor.presentation.movedToAiPanel') }}</n-text>
              </div>
            </template>
            <div class="presentation-cue-panel">
              <SparkTag v-if="currentBackgroundId" type="primary" size="small">
                {{ t('nodeEditor.presentation.backgroundShort', { value: currentBackgroundId }) }}
              </SparkTag>
              <SparkTag v-if="currentSpriteId" type="info" size="small">
                {{ t('nodeEditor.presentation.spriteShort', { value: currentSpriteId }) }}
              </SparkTag>
              <SparkTag v-if="currentIllustrationId" type="success" size="small">
                {{ t('nodeEditor.presentation.illustrationShort', { value: currentIllustrationId }) }}
              </SparkTag>
              <SparkTag v-else-if="currentIllustrationPrompt" type="warning" size="small">
                {{ t('nodeEditor.presentation.illustrationPlanned') }}
              </SparkTag>
            </div>
          </n-form-item>

          <n-divider />

          <n-space vertical style="width: 100%" :size="8">
            <n-button @click="addOptionToDialogue" block>
              <template #icon>
                <n-icon :component="CirclePlus" />
              </template>
              {{ t('nodeEditor.addOption') }}
            </n-button>
            <n-button @click="addDialogueAfterCurrent" block>
              <template #icon>
                <n-icon :component="ArrowDown" />
              </template>
              {{ t('nodeEditor.addNextDialogue') }}
            </n-button>
            <n-popconfirm 
              @positive-click="deleteDialogue"
              :positive-text="t('nodeEditor.delete')"
              :negative-text="t('nodeEditor.cancel')"
            >
              <template #trigger>
                <n-button type="error" block>
                  <template #icon>
                    <n-icon :component="Trash" />
                  </template>
                  {{ t('nodeEditor.deleteDialogue') }}
                </n-button>
              </template>
              <template #default>
                {{ t('nodeEditor.confirmDeleteDialogue') }}
              </template>
            </n-popconfirm>
          </n-space>

          <!-- Unity 行为配置（可折叠） -->
          <n-collapse style="margin-top: 8px;">
            <n-collapse-item name="unity-act">
              <template #header>
                <span class="unity-collapse-title">
                  <n-icon :component="Gamepad2" size="16" />
                  <span>{{ t('nodeEditor.actBinding') }}</span>
                </span>
              </template>
              <template #header-extra>
                <SparkTag v-if="currentActCount > 0" type="info" size="small">{{ t('nodeEditor.actCount', { count: currentActCount }) }}</SparkTag>
              </template>

              <!-- ActEditor 组件 -->
              <ActEditor
                :model-value="currentDialogueAct"
                @update:model-value="onActChange"
              />
            </n-collapse-item>
          </n-collapse>
        </n-form>

        <!-- 选项编辑器 -->
        <n-form v-else-if="editorType === 'option'" label-placement="top" size="medium">
          <n-form-item :label="t('nodeEditor.optionText')">
            <n-input 
              id="option-text" 
              v-model:value="optionDraft.optn" 
              @input="applyOption"
              clearable
              :placeholder="t('nodeEditor.optionTextPlaceholder')"
            />
          </n-form-item>

          <n-space vertical style="width: 100%" :size="8">
            <n-button type="primary" @click="addDialogueToOption" block strong>
              <template #icon>
                <n-icon :component="Plus" />
              </template>
              {{ t('nodeEditor.addChildDialogue') }}
            </n-button>
            <n-popconfirm 
              @positive-click="deleteOption"
              :positive-text="t('nodeEditor.delete')"
              :negative-text="t('nodeEditor.cancel')"
            >
              <template #trigger>
                <n-button type="error" block>
                  <template #icon>
                    <n-icon :component="Trash" />
                  </template>
                  {{ t('nodeEditor.deleteOption') }}
                </n-button>
              </template>
              <template #default>
                {{ t('nodeEditor.confirmDeleteOption') }}
              </template>
            </n-popconfirm>
          </n-space>
        </n-form>

        <div v-else class="no-selection">
          <n-empty :description="t('nodeEditor.selectNode')" />
        </div>
      </div>
    </n-card>
  </div>
  
</template>

<script setup lang="ts">
import { computed, reactive, watch, onMounted, onBeforeUnmount, type Component } from 'vue';
import { NCard, NForm, NFormItem, NInput, NInputNumber, NSwitch, NSelect, NButton, NIcon, NDivider, NSpace, NPopconfirm, NEmpty, NCollapse, NCollapseItem, NText } from 'naive-ui';
import SparkTag from '../share/SparkTag.vue';
import { ArrowDown, CircleDot, CircleHelp, CirclePlus, Film, Flag, Gamepad2, Layers3, MessageCircle, PanelTopOpen, Plus, RadioTower, Route, Trash } from '@lucide/vue';
import { useI18n } from 'vue-i18n';
import bus from '@/eventBus';
import ConditionsEditor from './ConditionsEditor.vue';
import EffectsEditor from './EffectsEditor.vue';
import ActEditor from './ActEditor.vue';
import { useSceneStore } from '@/components/stores/sceneStore';
import { useProjectStore } from '@/components/stores/projectStore';
import { useFileStore } from '@/components/stores/fileStore';
import { useCharacterStore } from '@/components/stores/characterStore';
import { useActionBindingStore } from '@/components/stores/actionBindingStore';
import MarkdownRenderer from '@/components/share/MarkdownRenderer.vue';
import type { ArcDialogueNode, ArcOptionNode, ArcScene } from '@/services/arcParser';
import { getSceneRuntimeSummary, type SceneContentKind } from '@/utils/sceneContentRuntime';

const { t } = useI18n();
const sceneStore = useSceneStore();
const projectStore = useProjectStore();
const fileStore = useFileStore();
const characterStore = useCharacterStore();
const actionBindingStore = useActionBindingStore();
const characterOptions = computed(() => characterStore.list);

function isDialogueNode(node: unknown): node is ArcDialogueNode {
  return !!node && typeof node === 'object' && 'id' in node && 'txt' in node;
}

function isOptionNode(node: unknown): node is ArcOptionNode {
  return !!node && typeof node === 'object' && 'optn' in node && 'dia' in node;
}


// 角色选项（Naive UI format）
const characterSelectOptions = computed(() => 
  characterOptions.value.map(c => ({
    label: c.name || t('nodeEditor.characterFallback', { id: c.id }),
    value: c.name || String(c.id)
  }))
);

// 场景选项（Naive UI format）
const sceneSelectOptions = computed(() => 
  (Array.isArray(sceneStore.scriptData) ? sceneStore.scriptData : [])
    .map(s => s?.scene)
    .filter(Boolean)
    .map(name => ({ label: name, value: name }))
);
function debouncedAutoSave() {
  if (!fileStore.selectedFile?.path || !projectStore.currentProject) return;
  sceneStore.scheduleStorySave({ boundary: true });
}

const type = computed(() => sceneStore.selectionType);
const editorType = computed<'' | 'scene' | 'dialogue' | 'option'>(() => {
  if (type.value === 'scene' && sceneStore.currentScene) return 'scene';
  if (type.value === 'dialogue' && isDialogueNode(sceneStore.currentNode)) return 'dialogue';
  if (type.value === 'option' && isOptionNode(sceneStore.currentNode)) return 'option';
  return '';
});
const title = computed(() => {
  if (editorType.value === 'scene') return t('nodeEditor.sceneEdit');
  if (editorType.value === 'dialogue') return t('nodeEditor.dialogueEdit');
  if (editorType.value === 'option') return t('nodeEditor.optionEdit');
  return t('nodeEditor.selectNode');
});

const scriptwriterThought = computed(() => (sceneStore.lastScriptwriterThought || '').trim());

// 场景草稿（conditions / effects 直接存对象，由子组件负责序列化）
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
  scene: '',
  guide: '',
  intro: '',
  thought: '',
  button_text: '',
  trigger_event: '',
  priority: 0,
  once_key: '',
  hiden: false,
  conditions: null,
  effects: null,
});

type SparkTagType = 'primary' | 'info' | 'success' | 'warning' | 'danger' | 'error' | 'default';

type SceneContentKindOption = {
  kind: SceneContentKind;
  icon: Component;
  label: string;
  description: string;
};

const contentKindOptions = computed<SceneContentKindOption[]>(() => [
  {
    kind: 'mainline',
    icon: Route,
    label: contentKindLabel('mainline'),
    description: t('nodeEditor.sceneRuntime.kind.mainline.description'),
  },
  {
    kind: 'side',
    icon: Flag,
    label: contentKindLabel('side'),
    description: t('nodeEditor.sceneRuntime.kind.side.description'),
  },
  {
    kind: 'panel',
    icon: PanelTopOpen,
    label: contentKindLabel('panel'),
    description: t('nodeEditor.sceneRuntime.kind.panel.description'),
  },
  {
    kind: 'system',
    icon: RadioTower,
    label: contentKindLabel('system'),
    description: t('nodeEditor.sceneRuntime.kind.system.description'),
  },
]);

const sceneRuntimeSummary = computed(() => getSceneRuntimeSummary(sceneDraft));

const sceneRuntimeChips = computed<Array<{ key: string; label: string; type: SparkTagType }>>(() => {
  const summary = sceneRuntimeSummary.value;
  const chips: Array<{ key: string; label: string; type: SparkTagType }> = [
    {
      key: 'visibility',
      label: summary.hidden ? t('nodeEditor.sceneRuntime.hidden') : t('nodeEditor.sceneRuntime.visible'),
      type: summary.hidden ? 'warning' : 'success',
    },
  ];
  if (summary.triggerEvent) {
    chips.push({
      key: 'trigger',
      label: t('nodeEditor.sceneRuntime.summaryTrigger', { value: summary.triggerEvent }),
      type: 'primary',
    });
  }
  if (summary.buttonText) {
    chips.push({
      key: 'button',
      label: t('nodeEditor.sceneRuntime.summaryButton', { value: summary.buttonText }),
      type: 'primary',
    });
  }
  if (summary.priority > 0) {
    chips.push({
      key: 'priority',
      label: t('nodeEditor.sceneRuntime.summaryPriority', { value: summary.priority }),
      type: 'warning',
    });
  }
  if (summary.onceKey) {
    chips.push({
      key: 'once',
      label: t('nodeEditor.sceneRuntime.summaryOnce', { value: summary.onceKey }),
      type: 'default',
    });
  }
  chips.push({
    key: 'conditions',
    label: t('nodeEditor.sceneRuntime.summaryConditions', { count: summary.conditionCount }),
    type: summary.conditionCount > 0 ? 'warning' : 'default',
  });
  chips.push({
    key: 'effects',
    label: t('nodeEditor.sceneRuntime.summaryEffects', { count: summary.effectCount }),
    type: summary.effectCount > 0 ? 'success' : 'default',
  });
  return chips;
});

function contentKindLabel(kind: SceneContentKind) {
  return t(`nodeEditor.sceneRuntime.kind.${kind}.label`);
}

function contentKindTagType(kind: SceneContentKind): SparkTagType {
  if (kind === 'mainline') return 'success';
  if (kind === 'side') return 'warning';
  if (kind === 'panel') return 'primary';
  return 'danger';
}

function sceneRuntimeSeed() {
  const scenes = Array.isArray(sceneStore.scriptData) ? sceneStore.scriptData : [];
  const index = sceneStore.currentScene ? scenes.indexOf(sceneStore.currentScene as any) + 1 : 0;
  const raw = (sceneDraft.scene || `scene-${index || 1}`).trim().toLowerCase();
  const slug = raw
    .replace(/[^a-z0-9]+/g, '.')
    .replace(/^\.+|\.+$/g, '')
    .replace(/\.+/g, '.');
  return slug || `scene.${index || Date.now().toString(36)}`;
}

function applyContentKindPreset(kind: SceneContentKind) {
  const seed = sceneRuntimeSeed();
  if (kind === 'mainline') {
    sceneDraft.button_text = '';
    sceneDraft.trigger_event = '';
    sceneDraft.priority = 0;
    sceneDraft.once_key = '';
    sceneDraft.hiden = false;
    sceneDraft.conditions = null;
    sceneDraft.effects = null;
  } else if (kind === 'side') {
    sceneDraft.button_text = '';
    sceneDraft.trigger_event = '';
    sceneDraft.priority = 0;
    sceneDraft.hiden = false;
    if (!sceneDraft.once_key.trim()) sceneDraft.once_key = `side.${seed}`;
  } else if (kind === 'panel') {
    sceneDraft.trigger_event = '';
    sceneDraft.priority = 0;
    sceneDraft.hiden = true;
    if (!sceneDraft.button_text.trim()) sceneDraft.button_text = t('nodeEditor.sceneRuntime.panelButtonDefault');
  } else {
    sceneDraft.button_text = '';
    sceneDraft.hiden = true;
    if (!sceneDraft.trigger_event.trim()) sceneDraft.trigger_event = `event.${seed}`;
    if (!Number.isFinite(Number(sceneDraft.priority)) || Number(sceneDraft.priority) < 1) sceneDraft.priority = 1;
  }
  applyScene();
}

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

function addDialogue() {
  if (!sceneStore.currentScene) return;
  const nextId = (() => {
    // 计算场景内最大 id + 1
    let max = 0;
    const dfs = (dias) => {
      dias?.forEach(d => { max = Math.max(max, Number(d.id) || 0); d.opt?.forEach(o => dfs(o.dia)); });
    };
    dfs(sceneStore.currentScene.dia);
    return max + 1;
  })();
  const node = { id: nextId, chr: '旁白', speaker: '旁白', txt: '新对话内容' };
    sceneStore.currentScene.dia = sceneStore.currentScene.dia || [];
    sceneStore.currentScene.dia.push(node);
    sceneStore.selectDialogue(node);
    debouncedAutoSave();
  }
function deleteScene() { sceneStore.deleteCurrentScene(); }

// 对话草稿
const dialogueDraft = reactive<{ id: number; chr: number | string; txt: string; next: string }>({ id: 0, chr: '旁白', txt: '', next: '' });
watch(
  () => [
    sceneStore.currentNode,
    sceneStore.selectionType,
    isDialogueNode(sceneStore.currentNode) ? sceneStore.currentNode.chr : undefined,
    isDialogueNode(sceneStore.currentNode) ? sceneStore.currentNode.speaker : undefined,
  ],
  ([n]) => {
  if (sceneStore.selectionType !== 'dialogue' || !isDialogueNode(n)) return;
  dialogueDraft.id = n.id ?? 0;
  dialogueDraft.chr = n.speaker || n.chr || '旁白';
  dialogueDraft.txt = n.txt ?? '';
  dialogueDraft.next = n.next ?? '';
}, { immediate: true });

function applyDialogue() {
  sceneStore.updateCurrentDialogue({
    chr: dialogueDraft.chr,
    speaker: typeof dialogueDraft.chr === 'string' ? dialogueDraft.chr : undefined,
    txt: dialogueDraft.txt,
    next: dialogueDraft.next
  });
  debouncedAutoSave();
}

// ──────────────────────────────────────────
// 行为(act)编辑 — 委托给 ActEditor 组件
// ──────────────────────────────────────────
const currentDialogueAct = computed(() => {
  if (!isDialogueNode(sceneStore.currentNode) || sceneStore.selectionType !== 'dialogue') return null;
  return sceneStore.currentNode.act ?? null;
});

const currentActCount = computed(() => {
  if (!isDialogueNode(sceneStore.currentNode) || sceneStore.selectionType !== 'dialogue') return 0;
  return Object.keys(sceneStore.currentNode.act || {}).length;
});

const currentDialoguePresentation = computed(() => {
  if (!isDialogueNode(sceneStore.currentNode) || sceneStore.selectionType !== 'dialogue') return null;
  return sceneStore.currentNode.presentation ?? null;
});

const currentBackgroundId = computed(() => {
  const bg = currentDialoguePresentation.value?.bg;
  if (Array.isArray(bg)) return String(bg[0] || '').trim();
  return typeof bg === 'string' ? bg.trim() : '';
});

const currentSpriteId = computed(() => {
  const sprite = currentDialoguePresentation.value?.sprite;
  if (Array.isArray(sprite)) return String(sprite[0] || '').trim();
  return typeof sprite === 'string' ? sprite.trim() : '';
});

const currentIllustrationId = computed(() => {
  const value = currentDialoguePresentation.value?.illustration;
  if (Array.isArray(value)) return String(value[0] || '').trim();
  return typeof value === 'string' ? value.trim() : '';
});

const currentIllustrationPrompt = computed(() => {
  const value = currentDialoguePresentation.value?.illustration_prompt;
  if (Array.isArray(value)) return String(value[0] || '').trim();
  return typeof value === 'string' ? value.trim() : '';
});

const hasPresentationCue = computed(() => !!currentBackgroundId.value
  || !!currentSpriteId.value
  || !!currentIllustrationId.value
  || !!currentIllustrationPrompt.value);

function updatePresentationConception(value: string) {
  if (!isDialogueNode(sceneStore.currentNode) || sceneStore.selectionType !== 'dialogue') return;
  const presentation = { ...(sceneStore.currentNode.presentation || {}) };
  const normalized = String(value || '').replace(/[\r\n]+/g, ' ');
  if (normalized.trim()) presentation.illustration_prompt = normalized;
  else delete presentation.illustration_prompt;
  sceneStore.updateCurrentDialogue({
    presentation: Object.keys(presentation).length > 0 ? presentation : undefined,
  });
  debouncedAutoSave();
}

function onActChange(val: Record<string, string | string[]> | null) {
  if (!isDialogueNode(sceneStore.currentNode) || sceneStore.selectionType !== 'dialogue') return;
  if (!val || Object.keys(val).length === 0) {
    delete (sceneStore.currentNode as any).act;
  } else {
    sceneStore.currentNode.act = val;
  }
  debouncedAutoSave();
}

// 选项草稿
const optionDraft = reactive({ optn: '' });
watch(() => sceneStore.currentNode, (n) => {
  if (sceneStore.selectionType !== 'option' || !isOptionNode(n)) return;
  optionDraft.optn = n.optn ?? '';
}, { immediate: true });

function applyOption() { sceneStore.updateCurrentOption({ optn: optionDraft.optn }); }
watch(() => optionDraft.optn, () => { if (sceneStore.selectionType === 'option') debouncedAutoSave(); });

// 结构操作：与旧前端功能对齐
function nextIdFromScene(scene) {
  let max = 0;
  const dfs = (dias) => dias?.forEach(d => { max = Math.max(max, Number(d.id) || 0); d.opt?.forEach(o => dfs(o.dia)); });
  dfs(scene?.dia);
  return max + 1;
}
function addOptionToDialogue() {
  if (sceneStore.selectionType !== 'dialogue' || !isDialogueNode(sceneStore.currentNode)) return;
  const option: { optn: string; dia: Array<{ id: number; chr: number | string; speaker?: string; txt: string }>; __oid: string } = {
    optn: '新选项',
    dia: [],
    __oid: `oid-${Date.now()}`,
  };
  sceneStore.currentNode.opt = sceneStore.currentNode.opt || [];
  // 默认给选项加一个子对话，便于继续编写
  const nid = nextIdFromScene(sceneStore.currentScene);
  option.dia.push({ id: nid, chr: '旁白', speaker: '旁白', txt: '新选项对话内容' });
  sceneStore.currentNode.opt.push(option);
  sceneStore.selectOption(option, sceneStore.currentNode);
  debouncedAutoSave();
}

function deleteDialogue() {
  if (sceneStore.selectionType !== 'dialogue' || !isDialogueNode(sceneStore.currentNode)) return;
  const node = sceneStore.currentNode;
  const parent = sceneStore.nodeParent; // 若存在则为所属选项
  if (isOptionNode(parent) && Array.isArray(parent.dia)) {
    const idx = parent.dia.indexOf(node);
    if (idx >= 0) parent.dia.splice(idx, 1);
    sceneStore.selectOption(parent, sceneStore.nodeParent || parent); // 回到父选项
  } else if (sceneStore.currentScene?.dia) {
    const idx = sceneStore.currentScene.dia.indexOf(node);
    if (idx >= 0) sceneStore.currentScene.dia.splice(idx, 1);
    sceneStore.selectScene(sceneStore.currentScene);
  }
  debouncedAutoSave();
}

function addDialogueToOption() {
  if (sceneStore.selectionType !== 'option' || !isOptionNode(sceneStore.currentNode)) return;
  const nid = nextIdFromScene(sceneStore.currentScene);
  const dlg = { id: nid, chr: '旁白', speaker: '旁白', txt: '新对话' };
  sceneStore.currentNode.dia = sceneStore.currentNode.dia || [];
  sceneStore.currentNode.dia.push(dlg);
  sceneStore.selectDialogue(dlg, sceneStore.currentNode);
  debouncedAutoSave();
}

function deleteOption() {
  if (sceneStore.selectionType !== 'option' || !isOptionNode(sceneStore.currentNode)) return;
  const option = sceneStore.currentNode;
  const parent = sceneStore.nodeParent; // 父对话
  if (isDialogueNode(parent) && parent.opt) {
    const idx = parent.opt.indexOf(option);
    if (idx >= 0) parent.opt.splice(idx, 1);
    if (parent.opt.length === 0) delete parent.opt;
    sceneStore.selectDialogue(parent, null);
  }
  debouncedAutoSave();
}

// 在当前对话节点后面添加一个新的对话并选中
function addDialogueAfterCurrent() {
  if (sceneStore.selectionType !== 'dialogue' || !isDialogueNode(sceneStore.currentNode)) return;
  const nid = nextIdFromScene(sceneStore.currentScene);
  const dlg = { id: nid, chr: '旁白', speaker: '旁白', txt: '' };
  const parent = sceneStore.nodeParent; // 如果存在则为选项
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

function onEnterAddNextDialogue() {
  // 已通过 .prevent 阻止换行，这里直接添加下一对话
  addDialogueAfterCurrent();
}

// 监听 AI 面板生成文本的追加事件，只更新编辑器草稿与 store
function onAiAppend(e) {
  if (sceneStore.selectionType !== 'dialogue') return;
  const chunk = e?.chunk ?? '';
  dialogueDraft.txt = (dialogueDraft.txt || '') + chunk;
  applyDialogue();
}

onMounted(() => {
  bus.on('ai-append-text', onAiAppend);
  // 确保加载角色列表
  characterStore.load(projectStore.currentProject);
  // 加载 action bindings（供 ActEditor 动态预设使用）
  actionBindingStore.load(projectStore.currentProject);
});
onBeforeUnmount(() => {
  bus.off('ai-append-text', onAiAppend);
});

// 切换项目时重新加载 action bindings
watch(
  () => projectStore.currentProject,
  (proj) => {
    if (proj) actionBindingStore.load(proj);
  }
);

</script>

<style scoped>
.right-panel-section {
  padding: 0;
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* 让 n-card 本体填满右侧面板（flex 子项必须用 flex: 1 而非 height: 100%） */
#node-editor :deep(.n-card) {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* 让 n-card header 固定，content 区域可滚动 */
#node-editor :deep(.n-card-content) {
  flex: 1;
  overflow-y: auto;
  min-height: 0;
}

/* 内容区域底部留白，防止内容被滚动条遮住 */
#node-editor-content {
  padding: 4px 0 20px;
}

#node-editor :deep(.n-card-header__main) {
  font-weight: 700;
}

#node-editor :deep(.n-form) {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

#node-editor :deep(.n-form-item) {
  margin-bottom: 0;
  padding: 12px;
  border: 1px solid color-mix(in srgb, var(--spark-border), transparent 8%);
  border-radius: 14px;
  background: color-mix(in srgb, var(--spark-panel-bg), var(--spark-primary) 2%);
}

#node-editor :deep(.n-form-item-label) {
  padding-bottom: 6px !important;
}

#node-editor :deep(.n-form-item-feedback-wrapper) {
  min-height: 0;
}

#node-editor :deep(.n-collapse-item) {
  overflow: hidden;
  border: 1px solid color-mix(in srgb, var(--spark-border), transparent 6%);
  border-radius: 14px;
  background: color-mix(in srgb, var(--spark-panel-bg), var(--spark-primary) 2%);
}

#node-editor :deep(.n-collapse-item__header) {
  padding: 10px 12px;
}

#node-editor :deep(.n-collapse-item__content-inner) {
  padding: 0 12px 12px;
}

.action-item {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
}
.action-item :deep(.n-input) {
  flex: 1;
}
.no-selection {
  padding: 20px 0;
}

/* Unity 配置区：collapse 标题横向排列，窄宽度下不压缩 */
.unity-collapse-title {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: var(--spark-fs-sm);
  font-weight: 500;
  white-space: nowrap;
}

.content-runtime-title {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: var(--spark-fs-sm);
  font-weight: 650;
  color: var(--spark-text);
  white-space: nowrap;
}

.content-runtime-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-width: 0;
}

.content-runtime-lede {
  margin: 0;
  color: var(--spark-text-muted);
  font-size: var(--spark-fs-xs);
  line-height: 1.5;
}

.content-kind-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.content-kind-card {
  min-width: 0;
  min-height: 84px;
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 9px;
  border: 1px solid color-mix(in srgb, var(--spark-border), transparent 8%);
  border-radius: 8px;
  background: color-mix(in srgb, var(--spark-bg) 46%, transparent);
  color: var(--spark-text);
  cursor: pointer;
  text-align: left;
  transition: border-color 0.16s ease, background 0.16s ease, transform 0.16s ease;
}

.content-kind-card:hover,
.content-kind-card.is-active {
  border-color: color-mix(in srgb, var(--spark-primary), transparent 36%);
  background: color-mix(in srgb, var(--spark-primary), transparent 90%);
}

.content-kind-card:active {
  transform: translateY(1px);
}

.content-kind-card__icon {
  flex: 0 0 auto;
  width: 24px;
  height: 24px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 7px;
  background: color-mix(in srgb, var(--spark-primary), transparent 88%);
  color: var(--spark-primary);
}

.content-kind-card__body {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.content-kind-card__body strong {
  font-size: var(--spark-fs-xs);
  font-weight: 650;
  line-height: 1.2;
}

.content-kind-card__body small {
  color: var(--spark-text-muted);
  font-size: var(--spark-fs-3xs);
  line-height: 1.35;
}

.content-runtime-summary {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  min-width: 0;
}

.content-runtime-summary :deep(.spark-tag) {
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
}

.content-runtime-fields {
  gap: 8px !important;
}

.content-runtime-label {
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 2px 8px;
}
.content-runtime-label > span {
  font-weight: 500;
  white-space: nowrap;
}
.content-runtime-label__hint {
  font-size: var(--spark-fs-2xs);
  font-weight: normal;
  line-height: 1.4;
}

.presentation-cue-panel {
  width: 100%;
  min-width: 0;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
</style>
