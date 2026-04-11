<template>
  <div class="production-mobile">
    <GlobalLoading scope="production" />

    <!-- 场景详情视图 -->
    <template v-if="viewMode === 'detail' && currentScene">
      <div class="detail-header">
        <n-button quaternary circle size="small" @click="viewMode = 'list'">
          <template #icon><n-icon :component="ArrowBackOutline" /></template>
        </n-button>
        <span class="detail-title">{{ currentScene.scene || t('views.production.mobile.sceneDefaultName', { index: 1 }) }}</span>
        <n-button quaternary circle size="small" @click="showSceneMetaDrawer = true">
          <template #icon><n-icon :component="CreateOutline" /></template>
        </n-button>
      </div>

      <!-- 剧情阅读区 -->
      <div class="detail-content">
        <DialogueTree v-if="workspaceMode === 'script'" />
        <NovelReader v-else :content="typeof sceneStore.scriptData === 'string' ? sceneStore.scriptData : ''" />
      </div>

      <!-- 底部 AI 操作栏 -->
      <div class="detail-actions">
        <n-button
          type="primary"
          secondary
          size="small"
          @click="showAiDrawer = true"
          :disabled="!currentScene"
        >
          <template #icon><n-icon :component="SparklesOutline" /></template>
          {{ t('views.production.mobile.sceneGeneration') }}
        </n-button>
        <n-button
          type="primary"
          size="small"
          :disabled="!outlineReady"
          @click="openAutoWrite"
        >
          <template #icon><n-icon :component="CreateOutline" /></template>
          {{ t('views.production.mobile.autoGeneration') }}
        </n-button>
      </div>
    </template>

    <!-- 场景列表视图 -->
    <template v-else>
      <n-spin :show="loading">
        <!-- 文件选择 -->
        <div class="file-selector-bar">
          <n-select
            v-model:value="selectedFilePath"
            :options="storyOptions"
            :placeholder="t('views.production.mobile.selectStoryFile')"
            size="small"
            clearable
            @update:value="handleFileChange"
          />
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
              <n-icon :component="ReaderOutline" size="14" />
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
    <n-drawer v-model:show="showSceneMetaDrawer" placement="bottom" height="70%">
      <n-drawer-content closable>
        <template #header>{{ t('views.production.mobile.sceneInfo') }}</template>
        <div class="scene-meta-form" v-if="currentScene">
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
          <n-button type="primary" block @click="saveSceneMeta">
            <template #icon><n-icon :component="SaveOutline" /></template>
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
            :allowed-modes="['multi-node', 'rewrite-scene']"
            default-mode="multi-node"
            :hide-mode-selector="true"
          />
        </div>
      </n-drawer-content>
    </n-drawer>

    <ScriptGenerationModal
      v-model:show="showAutoWrite"
      :outline="outlineData || undefined"
      @refresh-files="handleRefreshFiles"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, inject, watch, type Ref } from 'vue';
import { NIcon, NSpin, NButton, NInput, NSelect, NDrawer, NDrawerContent } from 'naive-ui';
import { useI18n } from 'vue-i18n';
import { 
  CreateOutline, 
  SparklesOutline,
  ReaderOutline,
  ArrowBackOutline,
  SaveOutline
} from '@vicons/ionicons5';
import { useSceneStore, type SceneWithClientId } from '../../components/stores/sceneStore';
import { useFileStore } from '../../components/stores/fileStore';
import { getOutline } from '../../services/api';
import type { OutlineData, StoryFileTreeNode } from '../../services/aiContracts';
import GlobalLoading from '../../components/share/GlobalLoading.vue';
import AiPanel from '../../components/dlg-editor/AiPanel.vue';
import ScriptGenerationModal from '../../components/dlg-editor/ScriptGenerationModal.vue';
import DialogueTree from '../../components/dlg-editor/DialogueTree.vue';
import NovelReader from '../../components/dlg-editor/NovelReader.vue';
import SparkTag from '../../components/share/SparkTag.vue';
import MobileTextArea from '../../components/share/MobileTextArea.vue';

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
const selectedFilePath = ref('');
const viewMode = ref<'list' | 'detail'>('list');

const scenes = computed<SceneWithClientId[]>(() => Array.isArray(sceneStore.scriptData) ? sceneStore.scriptData : []);
const currentScene = computed(() => sceneStore.currentScene);
const workspaceMode = computed(() => sceneStore.workspaceMode || 'script');

const sceneTitle = ref('');
const sceneIntro = ref('');
const sceneGuide = ref('');

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
    return;
  }
  sceneTitle.value = currentScene.value.scene || '';
  sceneIntro.value = currentScene.value.intro || '';
  sceneGuide.value = currentScene.value.guide || '';
}

function saveSceneMeta() {
  if (!currentScene.value) return;
  sceneStore.updateCurrentScene({
    scene: sceneTitle.value.trim() || currentScene.value.scene,
    intro: sceneIntro.value,
    guide: sceneGuide.value
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
  font-size: 15px;
  font-weight: 600;
  color: var(--spark-text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.scene-card-intro {
  font-size: 13px;
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
  font-size: 12px;
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
  font-size: 14px;
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
  font-size: 16px;
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

.detail-actions {
  display: flex;
  gap: 8px;
  padding: 12px 0 0;
  border-top: 1px solid var(--spark-border);
  margin-top: 8px;
}

.detail-actions .n-button {
  flex: 1;
}

/* 场景信息表单 */
.scene-meta-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.form-item label {
  display: block;
  font-size: 14px;
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
  font-size: 13px;
  color: var(--spark-text-muted);
  margin: 0;
}
</style>
