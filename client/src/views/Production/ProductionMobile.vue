<template>
  <div class="production-mobile">
    <GlobalLoading scope="production" />

    <!-- 场景详情视图 -->
    <template v-if="viewMode === 'detail' && currentScene">
      <div class="detail-header">
        <n-button quaternary circle size="small" @click="viewMode = 'list'">
          <template #icon><n-icon :component="ArrowLeft" /></template>
        </n-button>
        <span class="detail-title">{{ currentScene.scene || t('views.production.mobile.sceneDefaultName', { index: 1 }) }}</span>
        <n-button quaternary circle size="small" @click="showSceneMetaDrawer = true">
          <template #icon><n-icon :component="SquarePen" /></template>
        </n-button>
      </div>

      <!-- 顶部操作栏 -->
      <div class="detail-top-actions">
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
        <!-- 文件选择 -->
        <div class="file-selector-bar">
          <n-select
            v-model:value="selectedFilePath"
            :options="groupedStoryOptions"
            :placeholder="t('views.production.mobile.selectStoryFile')"
            size="small"
            clearable
            @update:value="handleFileChange"
          />
          <n-button
            size="small"
            quaternary
            @click="toggleWorkspaceMode"
            :title="workspaceMode === 'script' ? t('views.production.mobile.switchToNovel') : t('views.production.mobile.switchToScript')"
          >
            <template #icon>
              <n-icon :component="workspaceMode === 'script' ? BookOpen : SquarePen" />
            </template>
          </n-button>
        </div>

        <!-- 全自动生成入口 -->
        <div v-if="selectedFilePath" class="auto-write-entry">
          <n-button
            type="primary"
            size="small"
            block
            :disabled="!outlineReady"
            @click="openAutoWrite"
          >
            <template #icon><n-icon :component="SquarePen" /></template>
            {{ t('views.production.mobile.autoGeneration') }}
          </n-button>
          <n-text v-if="!outlineReady" depth="3" class="auto-write-hint">
            {{ t('views.production.mobile.needOutlineHint') }}
          </n-text>
        </div>

        <!-- 场景卡片列表 -->
        <div v-if="scenes.length > 0" class="scene-list">
          <div
            v-for="(s, idx) in scenes"
            :key="String(s.clientId ?? idx)"
            class="scene-card"
            :class="{ 'is-active': currentScene?.clientId === s.clientId }"
            @click="enterSceneDetail(s)"
          >
            <div class="scene-card-header">
              <span class="scene-card-name">{{ s.scene || t('views.production.mobile.sceneDefaultName', { index: idx + 1 }) }}</span>
              <SparkTag v-if="s.dia?.length" type="info" size="small">{{ s.dia.length }} {{ t('views.production.mobile.dialogueCount') }}</SparkTag>
            </div>
            <div class="scene-card-intro" v-if="s.intro">{{ s.intro.substring(0, 80) }}{{ s.intro.length > 80 ? '…' : '' }}</div>
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
          <p class="empty-text">{{ t('views.production.mobile.noScenes') }}</p>
          <n-button size="small" type="primary" @click="createScene" :disabled="!selectedFilePath">
            {{ t('views.production.mobile.createScene') }}
          </n-button>
        </div>

        <!-- 新建场景按钮 -->
        <div v-if="scenes.length > 0" class="fab-spacer">
          <button class="fab-add" @click="createScene" :disabled="!selectedFilePath">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
            </svg>
          </button>
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
            <n-tab-pane name="advanced" :tab="t('views.production.mobile.tabAdvanced')">
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
            <n-tab-pane name="logic" :tab="t('views.production.mobile.tabLogic')">
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
import { ref, computed, onMounted, inject, watch, type Ref } from 'vue';
import { NIcon, NSpin, NButton, NInput, NInputNumber, NSelect, NDrawer, NDrawerContent, NTabs, NTabPane, NSwitch } from 'naive-ui';
import { useI18n } from 'vue-i18n';
import { ArrowLeft, BookOpen, Pencil, Save, Sparkles, SquarePen } from 'lucide-vue-next';
import { useSceneStore, type SceneWithClientId } from '../../components/stores/sceneStore';
import { useFileStore } from '../../components/stores/fileStore';
import { getOutline } from '../../services/api';
import type { OutlineData, StoryFileTreeNode } from '../../services/aiContracts';
import GlobalLoading from '../../components/share/GlobalLoading.vue';
import AiPanel from '../../components/dlg-editor/AiPanel.vue';
import ScriptGenerationModal from '../../components/dlg-editor/ScriptGenerationModal.vue';
import DialogueTree from '../../components/dlg-editor/DialogueTree.vue';
import NovelReader from '../../components/dlg-editor/NovelReader.vue';
import MobileNodeEditor from '../../components/dlg-editor/MobileNodeEditor.vue';
import SparkTag from '../../components/share/SparkTag.vue';
import MobileTextArea from '../../components/share/MobileTextArea.vue';
import ConditionsEditor from '../../components/dlg-editor/ConditionsEditor.vue';
import EffectsEditor from '../../components/dlg-editor/EffectsEditor.vue';

const { t } = useI18n();

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
const showAiDrawer = ref(false);
const showNodeEditor = ref(false);
const selectedFilePath = ref('');
const viewMode = ref<'list' | 'detail'>('list');

const scenes = computed<SceneWithClientId[]>(() => Array.isArray(sceneStore.scriptData) ? sceneStore.scriptData : []);
const currentScene = computed(() => sceneStore.currentScene);
const workspaceMode = computed(() => sceneStore.workspaceMode || 'script');

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

const storyOptions = computed<SelectOption[]>(() => {
  const flat: SelectOption[] = [];
  function walk(list: StoryFileTreeNode[] = []) {
    list.forEach(item => {
      if (item.type === 'story') {
        flat.push({ label: item.name || item.path, value: item.path });
      } else if (Array.isArray(item.children)) {
        walk(item.children);
      }
    });
  }
  walk(fileStore.fileTree || []);
  return flat;
});

const groupedStoryOptions = computed(() => {
  const tree = fileStore.fileTree || [];
  const groups: { type: string; label: string; key: string; children: SelectOption[] }[] = [];
  function walkFolder(list: StoryFileTreeNode[], parentLabel: string) {
    list.forEach(item => {
      if (item.type === 'folder' && Array.isArray(item.children)) {
        const folderLabel = item.name || parentLabel;
        const children: SelectOption[] = [];
        item.children.forEach(child => {
          if (child.type === 'story') {
            children.push({ label: child.name || child.path, value: child.path });
          }
        });
        if (children.length > 0) {
          groups.push({ type: 'group', label: folderLabel, key: `folder:${folderLabel}`, children });
        }
        walkFolder(item.children, folderLabel);
      } else if (item.type === 'story') {
        const rootChildren = groups.find(g => g.key === 'root');
        if (!rootChildren) {
          groups.push({ type: 'group', label: t('views.production.mobile.rootFiles'), key: 'root', children: [{ label: item.name || item.path, value: item.path }] });
        } else {
          rootChildren.children.push({ label: item.name || item.path, value: item.path });
        }
      }
    });
  }
  walkFolder(tree, '');
  return groups.length > 0 ? groups : storyOptions.value;
});

function toggleWorkspaceMode() {
  sceneStore.workspaceMode = workspaceMode.value === 'script' ? 'novel' : 'script';
}

const outlineReady = computed(() => !!outlineData.value?.nodes?.length);

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
}

function enterSceneDetail(s: SceneWithClientId) {
  sceneStore.selectScene(s);
  hydrateSceneForm();
  viewMode.value = 'detail';
}

async function createScene() {
  if (!selectedFilePath.value) return;
  const scene = await sceneStore.createNewScene();
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

function saveSceneMeta() {
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
});

watch(currentScene, () => {
  hydrateSceneForm();
});
</script>

<style scoped>
.production-mobile {
  position: relative;
  display: flex;
  flex-direction: column;
  min-height: 100%;
}

/* 文件选择栏 */
.file-selector-bar {
  margin-bottom: 12px;
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
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.scene-card-name {
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

/* FAB 新建按钮 */
.fab-spacer {
  display: flex;
  justify-content: center;
  padding: 20px 0;
}

.fab-add {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  background: var(--spark-primary);
  color: var(--spark-text-inverse);
  border: none;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 12px rgba(var(--spark-primary-rgb), 0.3);
  transition: transform 0.2s;
}

.fab-add:active {
  transform: scale(0.92);
}

.fab-add:disabled {
  opacity: 0.4;
  cursor: not-allowed;
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
  display: flex;
  gap: 8px;
  padding: 8px 0;
  margin-bottom: 8px;
}

.detail-top-actions .n-button {
  flex: 1;
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
