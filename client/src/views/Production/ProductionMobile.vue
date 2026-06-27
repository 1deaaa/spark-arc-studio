<template>
  <div class="production-mobile">
    <GlobalLoading scope="production" />

    <!-- 场景详情视图 -->
    <template v-if="viewMode === 'detail' && (currentScene || isNovelMode)">
      <div class="detail-header">
        <n-button quaternary circle size="small" @click="viewMode = 'list'">
          <template #icon><n-icon :component="ArrowLeft" /></template>
        </n-button>
        <span class="detail-title">{{ isNovelMode ? (fileStore.selectedFile?.name || t('views.production.mobile.selectStoryFile')) : (currentScene?.scene || t('views.production.mobile.sceneDefaultName', { index: 1 })) }}</span>
        <n-button v-if="!isNovelMode" quaternary circle size="small" @click="showSceneMetaDrawer = true">
          <template #icon><n-icon :component="SquarePen" /></template>
        </n-button>
      </div>

      <!-- 顶部操作栏（仅剧本模式） -->
      <div v-if="!isNovelMode" class="detail-top-actions">
        <n-button
          secondary
          size="small"
          @click="showNodeEditor = true"
          :disabled="!sceneStore.selectionType"
        >
          <template #icon><n-icon :component="Pencil" /></template>
          {{ t('views.production.mobile.editNode') }}
        </n-button>
        <n-button
          secondary
          size="small"
          @click="showRuntimeTestDrawer = true"
          :disabled="!currentScene"
        >
          <template #icon><n-icon :component="RadioTower" /></template>
          {{ t('views.production.mobile.triggerTest') }}
        </n-button>
        <n-button
          type="primary"
          secondary
          size="small"
          @click="showAiDrawer = true"
          :disabled="!currentScene"
        >
          <template #icon><n-icon :component="Sparkles" /></template>
          {{ t('views.production.mobile.sceneGeneration') }}
        </n-button>
      </div>

      <!-- 剧情阅读区 -->
      <div class="detail-content">
        <DialogueTree v-if="workspaceMode === 'script'" />
        <NovelReader v-else :content="typeof sceneStore.scriptData === 'string' ? sceneStore.scriptData : ''" />
      </div>

    </template>

    <!-- 场景列表视图 -->
    <template v-else>
      <n-spin :show="loading">
        <section class="mobile-workbench-panel">
          <div class="workbench-heading">
            <div class="workbench-copy">
              <span class="workbench-kicker">{{ t('views.production.mobile.workbenchKicker') }}</span>
              <h3>{{ isNovelMode ? t('views.production.mobile.workbenchTitleNovel') : t('views.production.mobile.workbenchTitleScript') }}</h3>
              <p>{{ isNovelMode ? t('views.production.mobile.workbenchSubtitleNovel') : t('views.production.mobile.workbenchSubtitleScript') }}</p>
            </div>
            <SparkTag :type="isNovelMode ? 'warning' : 'info'" size="small">
              {{ isNovelMode ? t('views.scriptWriter.desktop.modeNovel') : t('views.scriptWriter.desktop.modeScript') }}
            </SparkTag>
          </div>

          <div class="file-selector-bar">
            <n-select
              v-model:value="selectedFilePath"
              :options="groupedStoryOptions"
              :placeholder="t('views.production.mobile.selectStoryFile')"
              size="small"
              clearable
              @update:value="handleFileChange"
            />
          </div>

          <div class="workbench-stats">
            <div class="workbench-stat">
              <span>{{ isNovelMode ? t('views.scriptWriter.desktop.chapterNav') : t('views.scriptWriter.desktop.sceneCount') }}</span>
              <strong>{{ isNovelMode ? (selectedFilePath ? 1 : 0) : scenes.length }}</strong>
            </div>
            <div class="workbench-stat">
              <span>{{ t('views.production.mobile.outlineStatus') }}</span>
              <strong>{{ outlineReady ? t('views.production.mobile.outlineReady') : t('views.production.mobile.outlineMissing') }}</strong>
            </div>
          </div>

          <div v-if="selectedFilePath" class="workbench-action-row">
            <n-button
              secondary
              size="small"
              @click="createScene"
            >
              <template #icon><n-icon :component="Plus" /></template>
              {{ isNovelMode ? t('views.production.mobile.openNovelEditor') : t('views.production.mobile.createSceneScript') }}
            </n-button>
            <n-button
              type="primary"
              secondary
              size="small"
              :disabled="!outlineReady"
              @click="openAutoWrite"
            >
              <template #icon><n-icon :component="SquarePen" /></template>
              {{ t('views.production.mobile.autoGeneration') }}
            </n-button>
          </div>

          <n-text v-if="selectedFilePath && !outlineReady" depth="3" class="auto-write-hint">
            {{ t('views.production.mobile.needOutlineHint') }}
          </n-text>
        </section>

        <!-- 场景卡片列表 -->
        <div v-if="scenes.length > 0" class="scene-list">
          <div
            v-for="{ scene: s, summary, index: idx } in sceneCards"
            :key="String(s.clientId ?? idx)"
            class="scene-card"
            :class="{ 'is-active': currentScene?.clientId === s.clientId }"
            @click="enterSceneDetail(s)"
          >
            <div class="scene-card-header">
              <span class="scene-card-name">{{ s.scene || t('views.production.mobile.sceneDefaultName', { index: idx + 1 }) }}</span>
              <span class="scene-card-badges">
                <SparkTag :type="contentKindTagType(summary.kind)" size="small">{{ contentKindLabel(summary.kind) }}</SparkTag>
                <SparkTag v-if="s.dia?.length" type="info" size="small">{{ s.dia.length }} {{ t('views.production.mobile.dialogueCount') }}</SparkTag>
              </span>
            </div>
            <div class="scene-card-intro" v-if="s.intro">{{ s.intro.substring(0, 80) }}{{ s.intro.length > 80 ? '…' : '' }}</div>
            <div class="scene-card-runtime" v-if="runtimeMetaLine(summary)">
              <n-icon :component="RadioTower" size="14" />
              <span>{{ runtimeMetaLine(summary) }}</span>
            </div>
            <div class="scene-card-meta" v-if="s.guide">
              <n-icon :component="BookOpen" size="14" />
              <span>{{ s.guide.substring(0, 40) }}{{ s.guide.length > 40 ? '…' : '' }}</span>
            </div>
          </div>
        </div>

        <!-- 空状态 -->
        <div v-else-if="!loading" class="empty-state">
          <div class="empty-icon">
            <svg width="48" height="48" viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
              <rect x="6" y="8" width="36" height="32" rx="4" stroke="currentColor" stroke-width="2" opacity="0.3"/>
              <path d="M16 20h16M16 26h10" stroke="currentColor" stroke-width="2" stroke-linecap="round" opacity="0.2"/>
            </svg>
          </div>
          <p class="empty-text">{{ isNovelMode ? t('views.production.mobile.fileSceneHintNovel') : t('views.production.mobile.fileSceneHintScript') }}</p>
          <n-button size="small" type="primary" @click="createScene" :disabled="!selectedFilePath">
            {{ isNovelMode ? t('views.production.mobile.createSceneNovel') : t('views.production.mobile.createSceneScript') }}
          </n-button>
        </div>

      </n-spin>
    </template>

    <!-- 场景信息编辑抽屉 -->
    <n-drawer v-model:show="showSceneMetaDrawer" placement="bottom" height="80%">
      <n-drawer-content closable>
        <template #header>{{ t('views.production.mobile.sceneInfo') }}</template>
        <div class="scene-meta-form" v-if="currentScene">
          <n-tabs type="line" animated>
            <n-tab-pane name="basic" :tab="t('views.production.mobile.tabBasic')">
              <div class="form-item">
                <label>{{ t('views.production.mobile.sceneName') }}</label>
                <n-input v-model:value="sceneTitle" :placeholder="t('views.production.mobile.sceneName')" size="large" />
              </div>
              <div class="form-item">
                <label>{{ t('views.production.mobile.sceneIntro') }}</label>
                <MobileTextArea
                  v-model:value="sceneIntro"
                  :title="t('views.production.mobile.sceneIntro')"
                  :placeholder="t('views.production.mobile.sceneIntro')"
                  customClass="intro-input"
                  :autosize="{ minRows: 3, maxRows: 10 }"
                />
              </div>
              <div class="form-item">
                <label>{{ t('views.production.mobile.sceneGuide') }}</label>
                <MobileTextArea
                  v-model:value="sceneGuide"
                  :title="t('views.production.mobile.sceneGuide')"
                  :placeholder="t('views.production.mobile.sceneGuide')"
                  customClass="guide-input"
                  :autosize="{ minRows: 2, maxRows: 8 }"
                />
              </div>
              <div class="form-item">
                <label>{{ t('views.production.mobile.sceneThought') }}</label>
                <MobileTextArea
                  v-model:value="sceneThought"
                  :title="t('views.production.mobile.sceneThought')"
                  :placeholder="t('views.production.mobile.sceneThoughtPlaceholder')"
                  :autosize="{ minRows: 1, maxRows: 6 }"
                />
              </div>
            </n-tab-pane>
            <n-tab-pane v-if="showRuntimeFields" name="advanced" :tab="t('views.production.mobile.tabAdvanced')">
              <div class="form-item">
                <label>{{ t('views.production.mobile.buttonText') }}</label>
                <n-input v-model:value="sceneButtonText" :placeholder="t('views.production.mobile.buttonTextPlaceholder')" clearable />
              </div>
              <div class="form-item">
                <label>{{ t('views.production.mobile.triggerEvent') }}</label>
                <n-input v-model:value="sceneTriggerEvent" :placeholder="t('views.production.mobile.triggerEventPlaceholder')" clearable />
              </div>
              <div class="form-item">
                <label>{{ t('views.production.mobile.priority') }}</label>
                <n-input-number v-model:value="scenePriority" :show-button="true" style="width: 100%" />
              </div>
              <div class="form-item">
                <label>{{ t('views.production.mobile.onceKey') }}</label>
                <n-input v-model:value="sceneOnceKey" :placeholder="t('views.production.mobile.onceKeyPlaceholder')" clearable />
              </div>
              <div class="form-item inline">
                <label>{{ t('views.production.mobile.hiddenScene') }}</label>
                <n-switch v-model:value="sceneHidden" />
              </div>
            </n-tab-pane>
            <n-tab-pane v-if="showRuntimeFields" name="logic" :tab="t('views.production.mobile.tabLogic')">
              <div class="form-item">
                <label>{{ t('views.production.mobile.conditions') }}</label>
                <ConditionsEditor v-model:model-value="sceneConditions" style="width: 100%" />
              </div>
              <div class="form-item">
                <label>{{ t('views.production.mobile.effects') }}</label>
                <EffectsEditor v-model:model-value="sceneEffects" style="width: 100%" />
              </div>
            </n-tab-pane>
          </n-tabs>
          <n-button type="primary" block @click="saveSceneMeta" style="margin-top: 16px;">
            <template #icon><n-icon :component="Save" /></template>
            {{ t('views.production.mobile.saveSceneInfo') }}
          </n-button>
        </div>
      </n-drawer-content>
    </n-drawer>

    <!-- 触发测试抽屉：移动端只读，不编辑运行时参数 -->
    <n-drawer v-model:show="showRuntimeTestDrawer" placement="bottom" height="58%">
      <n-drawer-content closable>
        <template #header>{{ t('views.production.mobile.triggerTest') }}</template>
        <div class="runtime-test-body" v-if="currentScene">
          <div class="runtime-test-hero">
            <SparkTag :type="contentKindTagType(currentRuntimeSummary.kind)" size="small">
              {{ contentKindLabel(currentRuntimeSummary.kind) }}
            </SparkTag>
            <h3>{{ currentScene.scene || t('views.production.mobile.sceneDefaultName', { index: 1 }) }}</h3>
            <p>{{ runtimeTestHint }}</p>
          </div>

          <div class="runtime-test-grid">
            <div v-for="row in runtimeRows" :key="row.key" class="runtime-test-row">
              <span>{{ row.label }}</span>
              <strong>{{ row.value }}</strong>
            </div>
          </div>

          <n-button
            block
            type="primary"
            secondary
            :disabled="!currentRuntimeSummary.triggerEvent"
            @click="copyRuntimeTriggerEvent"
          >
            <template #icon><n-icon :component="Clipboard" /></template>
            {{ t('views.production.mobile.copyTriggerEvent') }}
          </n-button>
        </div>
      </n-drawer-content>
    </n-drawer>

    <!-- AI 生成抽屉 -->
    <n-drawer v-model:show="showAiDrawer" placement="bottom" height="80%">
      <n-drawer-content closable>
        <template #header>{{ t('views.production.mobile.sceneGeneration') }}</template>
        <div class="ai-drawer-body">
          <p class="ai-hint">{{ t('views.production.mobile.sceneGenerationHint') }}</p>
          <AiPanel
            default-mode="multi-node"
          />
        </div>
      </n-drawer-content>
    </n-drawer>

    <ScriptGenerationModal
      v-model:show="showAutoWrite"
      :outline="outlineData || undefined"
      @refresh-files="handleRefreshFiles"
    />

    <!-- 移动端节点编辑器 -->
    <MobileNodeEditor v-model:show="showNodeEditor" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, inject, watch, type Ref } from 'vue';
import { NIcon, NSpin, NButton, NInput, NInputNumber, NSelect, NDrawer, NDrawerContent, NTabs, NTabPane, NSwitch, NText, useMessage } from 'naive-ui';
import { useI18n } from 'vue-i18n';
import { ArrowLeft, BookOpen, Clipboard, Pencil, Plus, RadioTower, Save, Sparkles, SquarePen } from '@lucide/vue';
import { useSceneStore, type SceneWithClientId } from '../../components/stores/sceneStore';
import { useFileStore } from '../../components/stores/fileStore';
import { getOutline } from '../../services/api';
import type { OutlineData } from '../../services/aiContracts';
import GlobalLoading from '../../components/share/GlobalLoading.vue';
import AiPanel from '../../components/dlg-editor/AiPanel.vue';
import ScriptGenerationModal from '../../components/dlg-editor/ScriptGenerationModal.vue';
import DialogueTree from '../../components/dlg-editor/DialogueTree.vue';
import NovelReader from '../../components/dlg-editor/NovelReader.vue';
import MobileNodeEditor from '../../components/dlg-editor/MobileNodeEditor.vue';
import SparkTag from '../../components/share/SparkTag.vue';
import MobileTextArea from '../../components/editors/mobile/MobileTextArea.vue';
import ConditionsEditor from '../../components/dlg-editor/ConditionsEditor.vue';
import EffectsEditor from '../../components/dlg-editor/EffectsEditor.vue';
import { useStoryFileOptions } from '../../composables/useStoryFileOptions';
import { getSceneRuntimeSummary, type SceneContentKind, type SceneRuntimeSummary } from '../../utils/sceneContentRuntime';
import bus from '../../eventBus';

const { t } = useI18n();
const message = useMessage();

type SparkTagType = 'primary' | 'info' | 'success' | 'warning' | 'danger' | 'error' | 'default';

type SelectOption = {
  label: string;
  value: string;
};

const sceneStore = useSceneStore();
const fileStore = useFileStore();
const projectId = inject<Ref<string | null>>('projectId', ref<string | null>(null));

const loading = ref(false);
const outlineData = ref<OutlineData | null>(null);
const showAutoWrite = ref(false);
const showSceneMetaDrawer = ref(false);
const showRuntimeTestDrawer = ref(false);
const showAiDrawer = ref(false);
const showNodeEditor = ref(false);
const selectedFilePath = ref('');
const viewMode = ref<'list' | 'detail'>('list');
const showRuntimeFields = false;

const scenes = computed<SceneWithClientId[]>(() => Array.isArray(sceneStore.scriptData) ? sceneStore.scriptData : []);
const sceneCards = computed(() => scenes.value.map((scene, index) => ({
  scene,
  index,
  summary: getSceneRuntimeSummary(scene),
})));
const currentScene = computed(() => sceneStore.currentScene);
const workspaceMode = computed(() => sceneStore.workspaceMode || 'script');
const isNovelMode = computed(() => workspaceMode.value === 'novel');

const sceneTitle = ref('');
const sceneIntro = ref('');
const sceneGuide = ref('');
const sceneThought = ref('');
const sceneButtonText = ref('');
const sceneTriggerEvent = ref('');
const scenePriority = ref(0);
const sceneOnceKey = ref('');
const sceneHidden = ref(false);
const sceneConditions = ref<any>(null);
const sceneEffects = ref<any>(null);

const { flatOptions: flatStoryOptions, groupedOptions } = useStoryFileOptions(
  () => t('views.production.mobile.rootFiles')
);

const storyOptions = computed<SelectOption[]>(() => flatStoryOptions.value);

const groupedStoryOptions = computed(() => groupedOptions.value);

const outlineReady = computed(() => !!outlineData.value?.nodes?.length);
const currentRuntimeSummary = computed(() => getSceneRuntimeSummary(currentScene.value));

const runtimeTestHint = computed(() => {
  const kind = currentRuntimeSummary.value.kind;
  if (kind === 'system') return t('views.production.mobile.runtimeHintSystem');
  if (kind === 'panel') return t('views.production.mobile.runtimeHintPanel');
  if (kind === 'side') return t('views.production.mobile.runtimeHintSide');
  return t('views.production.mobile.runtimeHintMainline');
});

const runtimeRows = computed(() => {
  const summary = currentRuntimeSummary.value;
  return [
    { key: 'kind', label: t('views.production.mobile.runtimeKind'), value: contentKindLabel(summary.kind) },
    { key: 'visibility', label: t('views.production.mobile.runtimeVisibility'), value: summary.hidden ? t('views.production.mobile.runtimeHidden') : t('views.production.mobile.runtimeVisible') },
    { key: 'trigger', label: t('views.production.mobile.triggerEvent'), value: summary.triggerEvent || t('views.production.mobile.runtimeEmpty') },
    { key: 'priority', label: t('views.production.mobile.priority'), value: String(summary.priority) },
    { key: 'button', label: t('views.production.mobile.buttonText'), value: summary.buttonText || t('views.production.mobile.runtimeEmpty') },
    { key: 'once', label: t('views.production.mobile.onceKey'), value: summary.onceKey || t('views.production.mobile.runtimeEmpty') },
    { key: 'conditions', label: t('views.production.mobile.conditions'), value: t('views.production.mobile.runtimeCount', { count: summary.conditionCount }) },
    { key: 'effects', label: t('views.production.mobile.effects'), value: t('views.production.mobile.runtimeCount', { count: summary.effectCount }) },
  ];
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

function runtimeMetaLine(summary: SceneRuntimeSummary) {
  const parts: string[] = [];
  if (summary.triggerEvent) parts.push(t('views.production.mobile.runtimeCardEvent', { value: summary.triggerEvent }));
  else if (summary.buttonText) parts.push(t('views.production.mobile.runtimeCardButton', { value: summary.buttonText }));
  if (summary.priority > 0) parts.push(t('views.production.mobile.runtimeCardPriority', { value: summary.priority }));
  if (summary.conditionCount > 0) parts.push(t('views.production.mobile.runtimeCardConditions', { count: summary.conditionCount }));
  return parts.join(' · ');
}

async function copyRuntimeTriggerEvent() {
  const value = currentRuntimeSummary.value.triggerEvent;
  if (!value) return;
  try {
    await navigator.clipboard.writeText(value);
    message.success(t('views.production.mobile.copyTriggerEventSuccess'));
  } catch {
    message.error(t('views.production.mobile.copyTriggerEventFailed'));
  }
}

async function loadOutline() {
  if (!projectId.value) return;
  try {
    outlineData.value = await getOutline(projectId.value);
  } catch {
    outlineData.value = null;
  }
}

async function loadFiles() {
  if (!projectId.value) return;
  loading.value = true;
  try {
    await fileStore.loadFileTree(projectId.value);
  } finally {
    loading.value = false;
  }
}

async function handleFileChange(val: string | null) {
  if (!val || !projectId.value) return;
  await fileStore.setCurrentFile(projectId.value, val);
  selectedFilePath.value = val;
  // 小说模式选中文件后直接进入编辑器
  if (isNovelMode.value) {
    viewMode.value = 'detail';
  }
}

function enterSceneDetail(s: SceneWithClientId) {
  sceneStore.selectScene(s);
  hydrateSceneForm();
  viewMode.value = 'detail';
}

async function createScene() {
  if (!selectedFilePath.value) return;
  // 小说模式是连续正文，不支持新建场景节点；直接进入编辑器
  if (isNovelMode.value) {
    viewMode.value = 'detail';
    return;
  }
  const opts = { title: t('views.production.mobile.createSceneScript'), message: t('components.fileExplorer.promptMessageStoryNovel') };
  const scene = await sceneStore.createNewScene(opts);
  if (scene) {
    hydrateSceneForm();
    viewMode.value = 'detail';
  }
}

function hydrateSceneForm() {
  if (!currentScene.value) {
    sceneTitle.value = '';
    sceneIntro.value = '';
    sceneGuide.value = '';
    sceneThought.value = '';
    sceneButtonText.value = '';
    sceneTriggerEvent.value = '';
    scenePriority.value = 0;
    sceneOnceKey.value = '';
    sceneHidden.value = false;
    sceneConditions.value = null;
    sceneEffects.value = null;
    return;
  }
  sceneTitle.value = currentScene.value.scene || '';
  sceneIntro.value = currentScene.value.intro || '';
  sceneGuide.value = currentScene.value.guide || '';
  sceneThought.value = currentScene.value.thought || '';
  sceneButtonText.value = typeof currentScene.value.button_text === 'string' ? currentScene.value.button_text : '';
  sceneTriggerEvent.value = typeof currentScene.value.trigger_event === 'string' ? currentScene.value.trigger_event : '';
  scenePriority.value = Number.isFinite(Number(currentScene.value.priority)) ? Number(currentScene.value.priority) : 0;
  sceneOnceKey.value = typeof currentScene.value.once_key === 'string' ? currentScene.value.once_key : '';
  sceneHidden.value = !!currentScene.value.hiden;
  sceneConditions.value = (currentScene.value.conditions != null && typeof currentScene.value.conditions === 'object') ? currentScene.value.conditions : null;
  sceneEffects.value = (currentScene.value.effects != null) ? currentScene.value.effects : null;
}

async function saveSceneMeta() {
  if (!currentScene.value) return;
  sceneStore.updateCurrentScene({
    scene: sceneTitle.value.trim() || currentScene.value.scene,
    intro: sceneIntro.value,
    guide: sceneGuide.value,
    thought: sceneThought.value,
    button_text: sceneButtonText.value.trim() || undefined,
    trigger_event: sceneTriggerEvent.value.trim() || undefined,
    priority: Number.isFinite(Number(scenePriority.value)) ? Number(scenePriority.value) : 0,
    once_key: sceneOnceKey.value.trim() || undefined,
    hiden: !!sceneHidden.value,
    conditions: sceneConditions.value,
    effects: sceneEffects.value,
  });
  await sceneStore._saveStory();
  showSceneMetaDrawer.value = false;
}

function openAutoWrite() {
  showAutoWrite.value = true;
}

async function handleRefreshFiles() {
  await loadFiles();
}

onMounted(async () => {
  await loadFiles();
  await loadOutline();
  if (fileStore.selectedFile?.path) {
    selectedFilePath.value = fileStore.selectedFile.path;
    // 小说模式下自动进入编辑器
    if (isNovelMode.value) {
      viewMode.value = 'detail';
    }
  } else if (storyOptions.value[0]?.value) {
    selectedFilePath.value = storyOptions.value[0].value;
    await handleFileChange(selectedFilePath.value);
  }
});

watch(projectId, async () => {
  await loadFiles();
  await loadOutline();
});

watch(() => fileStore.selectedFile?.path, (val) => {
  if (val) selectedFilePath.value = val;
  // 小说模式下切换文件后自动进入编辑器
  if (val && isNovelMode.value) {
    viewMode.value = 'detail';
  }
});

watch(currentScene, () => {
  hydrateSceneForm();
});

// 进入场景详情（沉浸阅读）时通知外层隐藏右侧步骤导航，避免下滑误触跳走工作流
watch(viewMode, (mode) => {
  bus.emit('mobile-flow-immersive', mode === 'detail');
});

onUnmounted(() => {
  // 组件卸载时务必复位，防止离开创作页后导航仍处于隐藏态
  bus.emit('mobile-flow-immersive', false);
});
</script>

<style scoped>
.production-mobile {
  position: relative;
  display: flex;
  flex-direction: column;
  min-height: 100%;
}

.mobile-workbench-panel {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 12px;
  margin-bottom: 12px;
  border: 1px solid var(--spark-border);
  border-radius: 8px;
  background: color-mix(in srgb, var(--spark-panel-bg) 94%, var(--spark-primary) 6%);
}

.workbench-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.workbench-copy {
  min-width: 0;
}

.workbench-kicker {
  display: block;
  margin-bottom: 2px;
  font-size: var(--spark-fs-3xs);
  font-weight: 700;
  color: var(--spark-primary);
}

.workbench-copy h3 {
  margin: 0;
  font-size: var(--spark-fs-md);
  font-weight: 650;
  color: var(--spark-text);
}

.workbench-copy p {
  margin: 3px 0 0;
  font-size: var(--spark-fs-xs);
  line-height: 1.45;
  color: var(--spark-text-muted);
}

.file-selector-bar {
  min-width: 0;
}

.workbench-stats {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.workbench-stat {
  min-width: 0;
  padding: 8px 10px;
  border: 1px solid color-mix(in srgb, var(--spark-border) 80%, transparent);
  border-radius: 8px;
  background: color-mix(in srgb, var(--spark-bg) 38%, transparent);
}

.workbench-stat span,
.workbench-stat strong {
  display: block;
  min-width: 0;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.workbench-stat span {
  font-size: var(--spark-fs-3xs);
  color: var(--spark-text-muted);
}

.workbench-stat strong {
  margin-top: 2px;
  font-size: var(--spark-fs-xs);
  color: var(--spark-text);
}

.workbench-action-row {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.workbench-action-row :deep(.n-button) {
  min-width: 0;
}

.workbench-action-row :deep(.n-button__content) {
  min-width: 0;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}

/* 场景卡片列表 */
.scene-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.scene-card {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 12px 14px;
  background: var(--spark-panel-bg);
  border: 1px solid var(--spark-border);
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.2s;
}

.scene-card:active {
  transform: scale(0.98);
  background: rgba(var(--spark-primary-rgb), 0.04);
}

.scene-card.is-active {
  border-color: rgba(var(--spark-primary-rgb), 0.4);
  background: rgba(var(--spark-primary-rgb), 0.06);
}

.scene-card-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
}

.scene-card-badges {
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: 4px;
  max-width: 42%;
}

.scene-card-name {
  min-width: 0;
  font-size: var(--spark-fs-md);
  font-weight: 600;
  color: var(--spark-text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.scene-card-intro {
  font-size: var(--spark-fs-sm);
  color: var(--spark-text-secondary);
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.scene-card-runtime {
  display: flex;
  align-items: center;
  gap: 5px;
  min-width: 0;
  font-size: var(--spark-fs-xs);
  color: var(--spark-primary);
}

.scene-card-runtime span {
  min-width: 0;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.scene-card-meta {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: var(--spark-fs-xs);
  color: var(--spark-text-muted);
}

/* 空状态 */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 40px 20px;
}

.empty-icon {
  color: var(--spark-text-muted);
  opacity: 0.5;
}

.empty-text {
  font-size: var(--spark-fs-base);
  color: var(--spark-text-muted);
  margin: 0;
}

/* 场景详情视图 */
.detail-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 0;
  margin-bottom: 8px;
  border-bottom: 1px solid var(--spark-border);
}

.detail-title {
  flex: 1;
  font-size: var(--spark-fs-lg);
  font-weight: 600;
  color: var(--spark-text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.detail-content {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
  border: 1px solid var(--spark-border);
  border-radius: 12px;
  background: var(--spark-panel-bg);
  padding: 8px;
}

.detail-top-actions {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
  padding: 8px 0;
  margin-bottom: 8px;
}

.detail-top-actions :deep(.n-button) {
  min-width: 0;
}

.detail-top-actions :deep(.n-button__content) {
  min-width: 0;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}

/* 全自动生成入口 */
.auto-write-entry {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 12px;
}

.auto-write-hint {
  font-size: var(--spark-fs-xs);
  line-height: 1.4;
}

/* 场景信息表单 */
.scene-meta-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.form-item label {
  display: block;
  font-size: var(--spark-fs-base);
  font-weight: 600;
  color: var(--spark-text-muted);
  margin-bottom: 8px;
}

.runtime-test-body {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.runtime-test-hero {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 12px;
  border: 1px solid var(--spark-border);
  border-radius: 8px;
  background: color-mix(in srgb, var(--spark-panel-bg) 92%, var(--spark-primary) 8%);
}

.runtime-test-hero h3 {
  margin: 0;
  font-size: var(--spark-fs-lg);
  font-weight: 650;
  color: var(--spark-text);
}

.runtime-test-hero p {
  margin: 0;
  font-size: var(--spark-fs-xs);
  line-height: 1.45;
  color: var(--spark-text-muted);
}

.runtime-test-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.runtime-test-row {
  min-width: 0;
  padding: 9px 10px;
  border: 1px solid color-mix(in srgb, var(--spark-border) 82%, transparent);
  border-radius: 8px;
  background: color-mix(in srgb, var(--spark-bg) 36%, transparent);
}

.runtime-test-row span,
.runtime-test-row strong {
  display: block;
  min-width: 0;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.runtime-test-row span {
  font-size: var(--spark-fs-3xs);
  color: var(--spark-text-muted);
}

.runtime-test-row strong {
  margin-top: 3px;
  font-size: var(--spark-fs-xs);
  font-weight: 650;
  color: var(--spark-text);
}

/* AI 抽屉 */
.ai-drawer-body {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.ai-hint {
  font-size: var(--spark-fs-sm);
  color: var(--spark-text-muted);
  margin: 0;
}
</style>
