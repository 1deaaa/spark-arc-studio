<template>
  <div class="production-mobile">
    <GlobalLoading scope="production" />

    <n-spin :show="loading">
      <!-- 文件与场景选择 -->
      <div class="flow-section">
        <div class="section-header">
          <n-icon :component="DocumentTextOutline" size="18" />
          <span>{{ t('views.production.mobile.fileAndScene') }}</span>
        </div>
        <n-select
          v-model:value="selectedFilePath"
          :options="storyOptions"
          :placeholder="t('views.production.mobile.selectStoryFile')"
          size="small"
          clearable
          @update:value="handleFileChange"
        />
        <div class="scene-row">
          <n-select
            v-model:value="selectedSceneName"
            :options="sceneOptions"
            :placeholder="t('views.production.mobile.selectScene')"
            size="small"
            clearable
            :disabled="sceneOptions.length === 0"
            @update:value="handleSceneChange"
          />
          <n-button size="small" secondary @click="createScene" :disabled="!selectedFilePath">{{ t('views.production.mobile.createScene') }}</n-button>
        </div>
        <div class="small-hint">{{ t('views.production.mobile.fileSceneHint') }}</div>
      </div>

      <!-- 场景信息 -->
      <div class="flow-section" v-if="currentScene">
        <div class="section-header">
          <n-icon :component="ReaderOutline" size="18" />
          <span>{{ t('views.production.mobile.sceneInfo') }}</span>
        </div>
        <n-input v-model:value="sceneTitle" :placeholder="t('views.production.mobile.sceneName')" />
        <n-input
          v-model:value="sceneIntro"
          type="textarea"
          :placeholder="t('views.production.mobile.sceneIntro')"
          :autosize="{ minRows: 4, maxRows: 15 }"
        />
        <n-input
          v-model:value="sceneGuide"
          type="textarea"
          :placeholder="t('views.production.mobile.sceneGuide')"
          :autosize="{ minRows: 4, maxRows: 15 }"
        />
        <n-button type="primary" secondary block size="small" @click="saveSceneMeta">{{ t('views.production.mobile.saveSceneInfo') }}</n-button>
      </div>

      <!-- 场景生成 -->
      <div class="flow-section">
        <div class="section-header">
          <n-icon :component="SparklesOutline" size="18" />
          <span>{{ t('views.production.mobile.sceneGeneration') }}</span>
        </div>
        <div class="small-hint">{{ t('views.production.mobile.sceneGenerationHint') }}</div>
        <div class="small-hint" v-if="!currentScene">{{ t('views.production.mobile.selectOrCreateSceneHint') }}</div>
        <AiPanel
          :allowed-modes="['multi-node', 'rewrite-scene']"
          default-mode="multi-node"
          :hide-mode-selector="true"
        />
      </div>

      <!-- 全自动生成 -->
      <div class="flow-section">
        <div class="section-header">
          <n-icon :component="CreateOutline" size="18" />
          <span>{{ t('views.production.mobile.autoGeneration') }}</span>
        </div>
        <n-button type="primary" block size="medium" :disabled="!outlineReady" @click="openAutoWrite">
          {{ t('views.production.mobile.startAutoWrite') }}
        </n-button>
        <div class="small-hint" v-if="!outlineReady">{{ t('views.production.mobile.needOutlineHint') }}</div>
      </div>
    </n-spin>

    <ScriptGenerationModal
      v-model:show="showAutoWrite"
      :outline="outlineData || undefined"
      @refresh-files="handleRefreshFiles"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, inject, watch, type Ref } from 'vue';
import { NIcon, NSpin, NButton, NInput, NSelect } from 'naive-ui';
import { useI18n } from 'vue-i18n';
import { 
  CreateOutline, 
  DocumentTextOutline, 
  SparklesOutline,
  ReaderOutline
} from '@vicons/ionicons5';
import { useSceneStore, type SceneWithClientId } from '../../components/stores/sceneStore';
import { useFileStore } from '../../components/stores/fileStore';
import { getOutline } from '../../services/api';
import type { OutlineData, StoryFileTreeNode } from '../../services/aiContracts';
import GlobalLoading from '../../components/share/GlobalLoading.vue';
import AiPanel from '../../components/dlg-editor/AiPanel.vue';
import ScriptGenerationModal from '../../components/dlg-editor/ScriptGenerationModal.vue';

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
const selectedFilePath = ref('');
const selectedSceneName = ref('');

const scenes = computed<SceneWithClientId[]>(() => Array.isArray(sceneStore.scriptData) ? sceneStore.scriptData : []);
const currentScene = computed(() => sceneStore.currentScene);

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

const sceneOptions = computed<SelectOption[]>(() => {
  return scenes.value.map((s, idx: number) => ({
    label: s.scene || t('views.production.mobile.sceneDefaultName', { index: idx + 1 }),
    value: s.scene
  }));
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
  selectedSceneName.value = sceneStore.currentScene?.scene || '';
}

function handleSceneChange(val: string | null) {
  const found = scenes.value.find(s => s.scene === val);
  if (found) sceneStore.selectScene(found);
}

async function createScene() {
  if (!selectedFilePath.value) return;
  const scene = await sceneStore.createNewScene();
  if (scene?.scene) {
    selectedSceneName.value = String(scene.scene);
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
  selectedSceneName.value = currentScene.value?.scene || '';
  hydrateSceneForm();
});
</script>

<style scoped>
.production-mobile {
  padding: 0 4px;
  position: relative;
}

.mobile-section {
  margin-bottom: 16px;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 600;
  color: var(--spark-primary);
  margin: 0 0 8px 0;
}

.section-desc {
  font-size: 13px;
  color: var(--spark-text-muted);
  margin: 0;
}

.flow-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 14px;
  background: var(--spark-panel-bg);
  border: 1px solid var(--spark-border);
  border-radius: 12px;
  margin-bottom: 16px;
}

.section-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 600;
  color: var(--spark-primary);
}

.scene-row {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 8px;
}

.small-hint {
  font-size: 12px;
  color: var(--spark-text-muted);
}

.right-panel-section {
  border: 1px solid var(--spark-border);
  border-radius: 10px;
  overflow: hidden;
}
</style>
